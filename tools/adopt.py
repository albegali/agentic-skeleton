#!/usr/bin/env python3
"""Install the agentic workflow into an EXISTING repository (brownfield). Run it from the skeleton, not from the target.

  python3 tools/adopt.py ../my-app [--name "My App"] [--prefix MA] [--language en] [--owner "Jane Doe"]
                                   [--tools claude-code,codex,copilot,cursor] [--dry-run] [--allow-dirty]
  make adopt TARGET=../my-app ARGS="--prefix MA"

Deterministic, no LLM. It never overwrites a file of the target:
  - workflow files (tools, steps, templates, guides, project.toml, models.toml) are copied only where absent; an
    existing different file is a conflict and nothing is written (non-essential READMEs are skipped instead);
  - an existing AGENTS.md gets a marked workflow block; CLAUDE.md, copilot-instructions and .claude/settings.json
    are merged by render_agents.py;
  - an existing Makefile gets `include workflow.mk`, holding only the workflow targets it does not define already;
  - project.toml gets origin = "brownfield" and the [stack] commands guessed from the manifests (best effort, may stay
    empty: /onboard confirms them; decided = false);
  - nothing CI- or vendor-specific is installed or assumed.
Then it runs the target's tools/init_project.py, and `make next` there recommends /onboard.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import repo_map  # noqa: E402
from init_project import TOOLS, set_key  # noqa: E402
from render_agents import BEGIN, END  # noqa: E402

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# skeleton files installed in the target (path segments matched one by one)
INSTALL = ["tools/*.py", "tools/README.md", "workflow/README.md", "workflow/workflow.toml", "workflow/steps/*.md",
           "inception/templates/*", "analysis/AGENTS.md", "analysis/AGENT_GUIDE.md", "analysis/templates/*", "analysis/*/.gitkeep",
           "delivery/AGENTS.md", "delivery/AGENT_GUIDE.md", "delivery/guide/*", "delivery/templates/*", "delivery/*/.gitkeep",
           "delivery/20-specs/README.md", "reference/README.md", "reference/*/.gitkeep", "reference/*/*/.gitkeep",
           "project-journal/*.md", "project-journal/*/README.md", "project-journal/templates/*", "project-journal/*/.gitkeep",
           "project-journal/notes/current-week.md", "models.toml", "project.toml"]
NOT_INSTALLED = {"tools/adopt.py"}  # the installer stays in the skeleton
OPTIONAL = re.compile(r"(^|/)(README\.md|\.gitkeep)$")  # on conflict: keep the target's file, skip ours
MERGED_BY_RENDER = {"CLAUDE.md", ".github/copilot-instructions.md", ".claude/settings.json"}
DROP_TARGETS = {"adopt", "test-tools"}  # the tools tests copy the whole repository: not for an application repo
STACK_TARGETS = {"help", "setup", "test", "lint"}  # if the target defines them, its own version wins
GITIGNORE = ["__pycache__/", "*.pyc"]


def seg_match(p: str, pat: str) -> bool:
    a, b = p.split("/"), pat.split("/")
    return len(a) == len(b) and all(fnmatch.fnmatch(x, y) for x, y in zip(a, b))


def skeleton_files() -> list[str]:
    try:
        files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=SRC, capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        files = [os.path.relpath(os.path.join(d, n), SRC) for d, _, ns in os.walk(SRC) for n in ns if "/.git/" not in d + "/"]
    return sorted(f for f in files if f not in NOT_INSTALLED and any(seg_match(f, p) for p in INSTALL))


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def make_targets(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"^([A-Za-z0-9_.%/-]+(?:[ \t]+[A-Za-z0-9_.%/-]+)*)[ \t]*::?(?!=)", text, re.M):
        out |= {t for t in m.group(1).split() if not t.startswith(".")}
    return out


def renamed(taken: set[str]) -> set[str]:
    """Workflow targets the target repository already defines (other than the stack ones): installed as wf-<name>."""
    return {t for t in taken if t not in STACK_TARGETS}


def workflow_mk(src: str, taken: set[str], header: str) -> str:
    """The skeleton Makefile without the skeleton-only targets and the stack targets in `taken`; other clashes get wf-."""
    drop = (taken & STACK_TARGETS) | DROP_TARGETS
    ren = renamed(taken)
    out, kept = [header], []
    lines = src.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)*)\s*:(?!=)(.*)$", line)
        if line.startswith(".PHONY") or line.startswith("# Workflow targets"):
            i += 1
            continue
        if m:
            recipe = []
            i += 1
            while i < len(lines) and lines[i].startswith("\t"):
                recipe.append(lines[i])
                i += 1
            names = [f"wf-{n}" if n in ren else n for n in m.group(1).split() if n not in drop]
            if names:
                kept += names
                out += [" ".join(names) + ":" + m.group(2)] + recipe
            continue
        out.append(line)
        i += 1
    text = "\n".join(out).replace("STACK =", "WF_STACK =").replace("$(STACK)", "$(WF_STACK)")
    for t in drop:  # the help line lists the targets
        text = re.sub(rf" \| {re.escape(t)}(?![\w-])[^|\"]*?(?= \||\")", "", text)
    for t in ren:
        text = re.sub(rf"(\| ){re.escape(t)}(?= \||\")", rf"\1wf-{t}", text)
    text = text.replace("/architecture", "/onboard")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.replace(header, header + f"\n.PHONY: {' '.join(kept)}", 1).rstrip() + "\n"


def agents_block(existing: str, skeleton: str) -> str:
    body = re.sub(r"^# AGENTS\.md\s*\n", "", skeleton, count=1)
    body = re.sub(r"^(#{2,5}) ", r"#\1 ", body, flags=re.M)  # demote one level under our section
    block = f"{BEGIN}\n## Agentic workflow\n{body.rstrip()}\n{END}"
    return existing.rstrip() + "\n\n" + block + "\n"



def default_prefix(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z]+", name) if w]
    if len(words) > 1:
        return "".join(w[0] for w in words[:3]).upper()
    return words[0][:2].upper() if words and len(words[0]) > 1 else "PR"


def git_out(cwd: str, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="path of the existing repository")
    ap.add_argument("--name")
    ap.add_argument("--prefix", help="2-3 uppercase letters (default: from the name)")
    ap.add_argument("--language", default="en")
    ap.add_argument("--owner", help="product owner / approver (default: git user.name of the target)")
    ap.add_argument("--description", default="")
    ap.add_argument("--tools", default=",".join(TOOLS))
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--allow-dirty", action="store_true", help="run even with uncommitted changes in the target")
    a = ap.parse_args()

    dst = os.path.abspath(a.target)
    if not os.path.isdir(dst):
        sys.exit(f"not a directory: {dst}")
    if dst == SRC or dst.startswith(SRC + os.sep):
        sys.exit("the target must be another repository, outside the skeleton")
    if os.path.exists(os.path.join(dst, "project.toml")) and "[project]" in read(os.path.join(dst, "project.toml")) \
            and os.path.exists(os.path.join(dst, "workflow/workflow.toml")):
        sys.exit("the target already uses the workflow; to update it see docs/GUIDE.md §12")
    if os.path.isdir(os.path.join(dst, ".git")) and git_out(dst, "status", "--porcelain") and not a.allow_dirty:
        sys.exit("the target has uncommitted changes: commit or stash them first, so the adoption is one reviewable diff "
                 "(or pass --allow-dirty)")

    name = a.name or os.path.basename(dst)
    prefix = a.prefix or default_prefix(name)
    owner = a.owner if a.owner is not None else git_out(dst, "config", "user.name")

    # ---- plan
    copy, skipped, conflicts = [], [], []
    for f in skeleton_files():
        t = os.path.join(dst, f)
        if not os.path.exists(t):
            copy.append(f)
        elif read(t) != read(os.path.join(SRC, f)):
            (skipped if OPTIONAL.search(f) else conflicts).append(f)
    generated = read(os.path.join(SRC, "workflow/.generated")).split() if os.path.exists(os.path.join(SRC, "workflow/.generated")) else []
    conflicts += [g for g in generated if g not in MERGED_BY_RENDER and os.path.exists(os.path.join(dst, g))]
    mk_src = read(os.path.join(SRC, "Makefile"))
    has_mk = os.path.exists(os.path.join(dst, "Makefile"))
    taken = make_targets(read(os.path.join(dst, "Makefile"))) if has_mk else set()
    if has_mk and os.path.exists(os.path.join(dst, "workflow.mk")):
        conflicts.append("workflow.mk")
    has_agents = os.path.exists(os.path.join(dst, "AGENTS.md"))
    if has_agents and BEGIN in read(os.path.join(dst, "AGENTS.md")):
        conflicts.append("AGENTS.md (already has a workflow block)")
    stack = repo_map.detect_stack(dst)

    print(f"Adopt the agentic workflow into {dst}")
    print(f"  project: {name} · prefix {prefix} · language {a.language} · owner {owner or '—'} · tools {a.tools}")
    print(f"  copy: {len(copy)} files" + (f" · keep the target's: {', '.join(skipped)}" if skipped else ""))
    print(f"  AGENTS.md: {'append a marked workflow block' if has_agents else 'create'}")
    clash = taken & make_targets(mk_src)
    print("  Makefile: " + ("append `include workflow.mk`" + (f"; already defined there, kept as yours: {', '.join(sorted(clash & STACK_TARGETS))}"
                                                                if clash & STACK_TARGETS else "")
                            + (f"; workflow targets renamed: {', '.join('wf-' + t for t in sorted(renamed(clash)))}" if renamed(clash) else "")
                            if has_mk else "create"))
    merged = [m for m in sorted(MERGED_BY_RENDER) if os.path.exists(os.path.join(dst, m))]
    if merged:
        print(f"  merge (marked block / permissions union): {', '.join(merged)}")
    print("  [stack] detected: " + " · ".join(f"{k}={v or '—'}" for k, v in stack.items()))
    if conflicts:
        print("\nConflicts — nothing written. Move or rename these files in the target, then rerun:")
        print("\n".join(f"  - {c}" for c in conflicts))
        sys.exit(2)
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return

    # ---- write
    created: list[str] = []
    for f in copy:
        os.makedirs(os.path.dirname(os.path.join(dst, f)) or dst, exist_ok=True)
        shutil.copy2(os.path.join(SRC, f), os.path.join(dst, f))
        created.append(f)

    def write(p: str, text: str, new: bool = True) -> None:
        full = os.path.join(dst, p)
        os.makedirs(os.path.dirname(full) or dst, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
        if new:
            created.append(p)

    skel_agents = read(os.path.join(SRC, "AGENTS.md"))
    if has_agents:
        write("AGENTS.md", agents_block(read(os.path.join(dst, "AGENTS.md")), skel_agents), new=False)
    else:
        write("AGENTS.md", skel_agents)
    if has_mk:
        write("workflow.mk", workflow_mk(mk_src, taken, "# Agentic workflow targets (installed by agentic-skeleton tools/adopt.py)."))
        write("Makefile", read(os.path.join(dst, "Makefile")).rstrip() + "\n\n# Agentic workflow: make next, check, backlog, agents, …\ninclude workflow.mk\n", new=False)
    else:
        write("Makefile", workflow_mk(mk_src, set(), "# Workflow targets (stdlib Python >= 3.11, no dependencies). Stack targets read project.toml [stack]."))
    gi = os.path.join(dst, ".gitignore")
    cur = read(gi) if os.path.exists(gi) else ""
    missing = [x for x in GITIGNORE if x not in cur.splitlines()]
    if missing:
        write(".gitignore", (cur.rstrip() + "\n\n" if cur.strip() else "") + "# agentic workflow tools\n" + "\n".join(missing) + "\n",
              new=not cur)

    p = read(os.path.join(dst, "project.toml"))
    p = set_key(p, "project", "origin", "brownfield")
    for k, v in stack.items():
        p = set_key(p, "stack", k, v)
    p = set_key(p, "stack", "decided", False)
    write("project.toml", p, new=False)
    write("workflow/.installed", "\n".join(sorted(set(created) | {"workflow/.installed"})) + "\n", new=False)

    env = {k: v for k, v in os.environ.items() if k != "WF_ROOT"}
    cmd = [sys.executable, "tools/init_project.py", "--name", name, "--prefix", prefix, "--language", a.language,
           "--owner", owner, "--description", a.description, "--no-mockup", "--tools", a.tools]
    r = subprocess.run(cmd, cwd=dst, env=env, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode:
        sys.exit("init_project failed: fix the arguments and rerun tools/init_project.py in the target")
    print(f"\nDone: {len(created)} files created. Next, in {dst}:\n"
          "  1. review and commit:  git add -A && git diff --cached --stat\n"
          "  2. make next          → /onboard (fresh session, deep tier)\n"
          "  CI is untouched: to enforce the workflow, add `python3 tools/check_workflow.py` to your pipeline, if any.")


if __name__ == "__main__":
    main()
