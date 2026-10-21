"""Upgrade a project that uses the workflow to this skeleton's version: a 3-way merge per file, nothing on conflict.

Called by `tools/adopt.py --upgrade <target>` (run from the skeleton) and by `make sync-skeleton` in the target
(tools/sync_skeleton.py fetches the skeleton, then calls adopt.py --upgrade). Per installed file:
  base   = the file in the skeleton at the version the project records (project.toml [skeleton] version, else tools/VERSION)
  ours   = the project's file          theirs = the skeleton's file now
  ours == base → take theirs · base == theirs → keep ours · ours == theirs → nothing · otherwise a conflict.
Any conflict stops the upgrade before anything is written (like adopt.py); the report says how to resolve it.
Then: missing project.toml / models.toml keys are added with the skeleton's defaults, migrations between the two
versions run (tools/migrations/<from>-<to>.py, ordered), [skeleton] version/source are recorded, adapters re-rendered.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib

from init_project import set_key
from render_agents import BEGIN, END

PROJECT_OWNED = {"project.toml", "models.toml"}  # never replaced: new keys are added instead


def vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def git(cwd: str, *args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def base_commit(src: str, version: str) -> str | None:
    """The newest skeleton commit whose tools/VERSION is `version` (the state a project of that version was taken from)."""
    for c in (git(src, "rev-list", "HEAD", "--", "tools/VERSION") or "").split():
        if (git(src, "show", f"{c}:tools/VERSION") or "").strip() == version:
            nxt = (git(src, "rev-list", "--reverse", "--ancestry-path", f"{c}..HEAD", "--", "tools/VERSION") or "").split()
            return f"{nxt[0]}^" if nxt else "HEAD"  # just before the next bump
    return None


def add_missing_keys(ours: str, theirs: str) -> tuple[str, list[str]]:
    """New sections and keys of the skeleton's TOML, with their default values; the project's values are kept."""
    try:
        o, t = tomllib.loads(ours), tomllib.loads(theirs)
    except tomllib.TOMLDecodeError:
        return ours, []
    added = []
    for sec, keys in t.items():
        if not isinstance(keys, dict) or sec in ("vendors", "tools"):  # per-vendor/tool tables: the project's choice
            continue
        if sec not in o:  # a new section: copied whole, with its comments
            block = re.search(rf"(?ms)^\[{re.escape(sec)}\]\s*\n.*?(?=^\[|\Z)", theirs)
            if block:
                ours = ours.rstrip() + "\n\n" + block.group(0).rstrip() + "\n"
                added.append(f"[{sec}]")
            continue
        for k, v in keys.items():
            if not isinstance(v, dict) and k not in o[sec]:
                ours = set_key(ours, sec, k, v)
                added.append(f"[{sec}] {k}")
    return ours, added


def upgrade(src: str, dst: str, files: list[str], read, installed, dry_run: bool) -> None:
    """files: the skeleton files installed in projects now; installed(path): whether a path is one of them by pattern."""
    pt = os.path.join(dst, "project.toml")
    proj = tomllib.loads(read(pt)) if os.path.exists(pt) else {}
    have = proj.get("skeleton", {}).get("version") or (read(os.path.join(dst, "tools/VERSION")).strip()
                                                        if os.path.exists(os.path.join(dst, "tools/VERSION")) else "")
    new = read(os.path.join(src, "tools/VERSION")).strip()
    if not have:
        sys.exit("the target records no skeleton version (project.toml [skeleton] version, tools/VERSION): set the version it was taken from")
    if vkey(have) > vkey(new):
        sys.exit(f"the target is at {have}, newer than this skeleton ({new}): update the skeleton checkout first")
    base = base_commit(src, have)
    if base is None:
        sys.exit(f"version {have} not found in the skeleton history (tools/VERSION): is this the right skeleton?")
    print(f"Upgrade {dst}: skeleton {have} → {new} (base {git(src, 'rev-parse', '--short', base).strip()})")

    def at_base(f: str) -> str | None:
        return git(src, "show", f"{base}:{f}")

    take, keep, conflicts, delete = [], [], [], []
    agents = os.path.join(dst, "AGENTS.md")
    block = os.path.exists(agents) and BEGIN in read(agents)  # adopted repository: AGENTS.md holds a marked block
    candidates = list(files) + ([] if block else ["AGENTS.md"])
    candidates += ["Makefile"] if not os.path.exists(os.path.join(dst, "workflow.mk")) else []
    base_files = set((git(src, "ls-tree", "-r", "--name-only", base) or "").split())
    for f in candidates:
        if f in PROJECT_OWNED:
            continue
        o_path = os.path.join(dst, f)
        ours = read(o_path) if os.path.exists(o_path) else None
        theirs = read(os.path.join(src, f))
        b = at_base(f)
        if ours == theirs:
            continue
        if ours is None:
            (take if b is None else keep).append(f)  # new upstream file / deleted by the project: kept deleted
        elif ours == b:
            take.append(f)
        elif b == theirs:
            keep.append(f)
        else:
            conflicts.append(f)
    for f in sorted(base_files - set(files)):  # removed upstream: deleted only where the project never changed it
        o_path = os.path.join(dst, f)
        if installed(f) and f not in PROJECT_OWNED and os.path.exists(o_path) and read(o_path) == at_base(f):
            delete.append(f)

    print(f"  update: {len(take)} · keep the project's change: {len(keep)} · remove (gone upstream): {len(delete)}")
    for f in take:
        print(f"    + {f}")
    for f in delete:
        print(f"    - {f}")
    if conflicts:
        print("\nConflicts — nothing written. Both the project and the skeleton changed these files since "
              f"{have}; merge each by hand, then rerun:")
        for f in conflicts:
            print(f"  - {f}   (upstream change: git -C {src} diff {base} HEAD -- {f})")
        sys.exit(2)
    if dry_run:
        print("\n(dry run: nothing written)")
        return

    for f in take:
        full = os.path.join(dst, f)
        os.makedirs(os.path.dirname(full) or dst, exist_ok=True)
        with open(os.path.join(src, f), "rb") as a, open(full, "wb") as b:
            b.write(a.read())
    for f in delete:
        os.remove(os.path.join(dst, f))
    if block:  # refresh the marked AGENTS.md block
        body = re.sub(r"^# AGENTS\.md\s*\n", "", read(os.path.join(src, "AGENTS.md")), count=1)
        body = re.sub(r"^(#{2,5}) ", r"#\1 ", body, flags=re.M)
        cur = read(agents)
        new_block = f"{BEGIN}\n## Agentic workflow\n{body.rstrip()}\n{END}"
        with open(agents, "w", encoding="utf-8") as fh:
            fh.write(cur[:cur.index(BEGIN)] + new_block + cur[cur.index(END) + len(END):])
    added = []
    for f in PROJECT_OWNED:
        if os.path.exists(os.path.join(dst, f)):
            text, a = add_missing_keys(read(os.path.join(dst, f)), read(os.path.join(src, f)))
            added += [f"{f} {x}" for x in a]
            if f == "project.toml":
                origin = (git(src, "remote", "get-url", "origin") or "").strip() or src
                text = set_key(set_key(text, "skeleton", "version", new), "skeleton", "source", origin)
            with open(os.path.join(dst, f), "w", encoding="utf-8") as fh:
                fh.write(text)
    if added:
        print("  new settings (defaults): " + ", ".join(added))
    env = {k: v for k, v in os.environ.items() if k != "WF_ROOT"}
    for m in sorted((f for f in os.listdir(os.path.join(dst, "tools", "migrations")) if f.endswith(".py") and "-" in f)
                    if os.path.isdir(os.path.join(dst, "tools", "migrations")) else [],
                    key=lambda n: vkey(n.split("-")[0])):
        frm, to = m[:-3].split("-", 1)
        if vkey(have) <= vkey(frm) and vkey(to) <= vkey(new):
            r = subprocess.run([sys.executable, os.path.join("tools", "migrations", m)], cwd=dst, env=env, capture_output=True, text=True)
            print(f"  migration {m}: " + (r.stdout.strip() or "ok") if r.returncode == 0 else f"  migration {m} FAILED:\n{r.stderr}")
            if r.returncode:
                sys.exit(1)
    r = subprocess.run([sys.executable, "tools/render_agents.py"], cwd=dst, env=env, capture_output=True, text=True)
    print("  " + (r.stdout.strip() or r.stderr.strip()))
    print(f"\nDone: {dst} is at skeleton {new}. Review and commit (git diff --stat), then `make check`.")
