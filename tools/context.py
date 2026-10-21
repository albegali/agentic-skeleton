#!/usr/bin/env python3
"""Print the exact context budget of a step, so agents read nothing else.

Usage:
  python3 tools/context.py <step> [ID…] [--with <file>…]   # files to read, cited FR/NFR/ADR sections, command outputs;
                                               # --with adds files passed to the step (workshop minutes, sources)
  python3 tools/context.py --index <file.md>   # headings only (cheap table of contents)
  python3 tools/context.py --package-rules     # package-level AGENTS.md files
  python3 tools/context.py --repo-map          # map of an existing codebase (tools/repo_map.py)
  add --json to any form for machine output (schema in tools/README.md)

Budgets are declared in workflow/workflow.toml ([steps.<step>]: read, first, refs_from, deps, run, run_max, sources, design,
package_rules, diff).
`sources = true` adds the kickoff sources of project.toml [inception]; `design = true` points to the existing design.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

REQ_FILES = {"FR": "reference/product/functional-requirements.md", "NFR": "reference/product/non-functional-requirements.md"}
REF_RX = re.compile(r"\b(FR|NFR|ADR)-(\d+)\b")
PATH_RX = re.compile(r"\b(reference/[\w./-]+\.md)(#[^\s)\]>,;]*)?")  # `file.md#FR-27` cites a section, extracted by ID
ARCH_RX = re.compile(r"\barchitecture(?:\.md)?\s*§\s*(\d+)")
ARCH = "reference/architecture/architecture.md"
BIG = 400  # lines: warn the agent to read only what it needs
ROOT_RULES = {"AGENTS.md", "analysis/AGENTS.md", "delivery/AGENTS.md"}
RUN_TIMEOUT = 60  # seconds per `run` command of a budget
DIFF_BIG = 8000  # tokens: above this, review the story diff file by file
BASE = "main"
section = wf.heading_section


def tail_from(text: str, num: str) -> str | None:
    """From heading `## <num>.` to the end of the file (e.g. Analysis §6-7)."""
    m = re.search(rf"^##\s+{re.escape(num)}\.", text, re.M)
    return text[m.start():].strip() if m else None


def index(p: str) -> str:
    if not wf.exists(p):
        return f"(missing: {p})"
    t = wf.read(p)
    if p.lower().endswith((".html", ".htm")):  # mockups, prototypes: <title> and h1–h3 as an outline
        out = []
        for lvl, body in re.findall(r"<(title|h[1-3])\b[^>]*>(.*?)</\1>", t, re.S | re.I):
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", body)).strip()
            if txt:
                out.append(("#" * int(lvl[1]) if lvl.lower() != "title" else "title:") + " " + txt)
        return "\n".join(out)
    return "\n".join(line for _, level, line in wf.headings(t) if level <= 4)


def package_rules() -> list[str]:
    out = []
    for p in wf.matches("**/AGENTS.md"):
        r = wf.rel(p)
        if r not in ROOT_RULES and not r.startswith(("node_modules", ".venv")) and "/node_modules/" not in r:
            out.append(r)
    return out


def refs_in(text: str) -> list[tuple[str, str]]:
    """Cited (kind, number) pairs in order; `FR-1` and `FR-01` are the same reference (first spelling kept)."""
    seen: dict[tuple[str, int], str] = {}
    for kind, num in REF_RX.findall(text):
        seen.setdefault((kind, int(num)), num)
    return [(kind, num) for (kind, _), num in seen.items()]


def expand(pattern: str, ids: list[str], dep: str | None = None) -> str:
    return pattern.replace("{ID}", ids[0] if ids else "*").replace("{DEP}", dep or "*")


def size(p: str) -> dict:
    t = wf.read(p)
    n = t.count("\n") + 1
    return {"path": wf.rel(p), "lines": n, "tokens": wf.approx_tokens(len(t)), "long": n > BIG}


def git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=RUN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def story_diff() -> dict | None:
    """Size of the story branch diff against main, so the review can budget it (file by file when large)."""
    stat = git("diff", "--stat", f"{BASE}...HEAD")
    if stat is None:
        return None
    body = git("diff", f"{BASE}...HEAD") or ""
    files = [line.split("|")[0].strip() for line in stat.splitlines() if "|" in line]
    tokens = wf.approx_tokens(len(body))
    return {"base": BASE, "files": files, "stat": stat.rstrip(), "tokens": tokens, "by_file": tokens > DIFF_BIG}


def budget_data(step: str, ids: list[str], extra: list[str] | None = None) -> dict:
    """The context budget as data: files to read in full, cited sections, dependency excerpts, command outputs."""
    cfg = wf.workflow().get("steps", {}).get(step)
    if cfg is None:
        sys.exit(f"Unknown step: {step}. Steps: {', '.join(wf.workflow().get('steps', {}))}")
    ids = ids or []
    full: list[str] = []
    missing: list[str] = []
    needs_id = any("{ID}" in p for k in ("read", "first", "refs_from") for p in cfg.get(k, []))
    for i in ids or [None]:
        cur = [i] if i else []
        for pat in cfg.get("read", []):
            if "{ID}" in pat and not i:
                continue
            found = wf.matches(expand(pat, cur))
            (full.extend(found) if found else missing.append(expand(pat, cur)))
        alts = cfg.get("first", [])
        if alts and i:
            hit = next((wf.matches(expand(a, cur)) for a in alts if wf.matches(expand(a, cur))), None)
            full.extend(hit[:1]) if hit else missing.append(" | ".join(expand(a, cur) for a in alts))
    # kickoff sources and existing design recorded in project.toml [inception]
    if cfg.get("sources"):
        for p in wf.sources():
            (full.append(wf.path(p)) if wf.exists(p) else missing.append(p))
    design = wf.design() if cfg.get("design") else ""
    if design and not wf.exists(design):
        missing.append(design)
    for p in extra or []:  # files passed to the step: workshop minutes, further sources
        (full.append(wf.path(p)) if wf.exists(p) else missing.append(p))
    full = list(dict.fromkeys(full))
    missing = list(dict.fromkeys(missing))
    read = [size(p) for p in full]

    # cited references: only the sections
    refs: list[tuple[str, str]] = []
    paths: list[str] = []
    arch: list[str] = []
    for i in ids:
        for pat in cfg.get("refs_from", []):
            for p in wf.matches(expand(pat, [i])):
                text = wf.read(p)
                refs += refs_in(text)
                paths += [m.group(1) for m in PATH_RX.finditer(text) if not m.group(2)]
                arch += ARCH_RX.findall(text)
    sections = []
    unique: dict[tuple[str, int], tuple[str, str]] = {}
    for kind, num in refs:  # across files too: FR-1 in the Story, FR-01 in the Analysis
        unique.setdefault((kind, int(num)), (kind, num))
    for kind, num in unique.values():
        if kind == "ADR":
            hit = wf.matches(f"reference/architecture/ADR-{int(num):03d}*.md") or wf.matches(f"reference/architecture/ADR-{num}*.md")
            sections.append({"ref": f"ADR-{num}", "file": wf.rel(hit[0]) if hit else None, "text": None,
                             "tokens": size(hit[0])["tokens"] if hit else 0})
            continue
        f = REQ_FILES[kind]
        sec = section(wf.read(f), rf"\b{kind}-0*{int(num)}\b") if wf.exists(f) else None
        sections.append({"ref": f"{kind}-{num}", "file": f, "text": sec, "tokens": wf.approx_tokens(len(sec or ""))})
    # files and architecture sections cited by path in the Story (e.g. notes)
    arch = list(dict.fromkeys(arch))
    arch_text = wf.read(ARCH) if arch and wf.exists(ARCH) else ""
    for num in arch:
        sec = section(arch_text, rf"^#+\s+{num}\.") if arch_text else None
        sections.append({"ref": f"architecture §{num}", "file": ARCH, "text": sec, "tokens": wf.approx_tokens(len(sec or ""))})
    # a file whose sections were extracted, or an ADR already listed by ID, is not read again in full
    in_read = {r["path"] for r in read} | {s["file"] for s in sections if s["file"]}
    cited = []
    for p in dict.fromkeys(paths):
        if p in in_read:
            continue
        if not wf.exists(p):
            cited.append({"path": p, "exists": False, "lines": 0, "tokens": 0, "long": False})
            continue
        cited.append({**size(wf.path(p)), "exists": True})

    # dependency excerpts
    excerpts = []
    deps_cfg = cfg.get("deps", [])
    if deps_cfg and ids:
        st = wf.stories()
        for d in dict.fromkeys(d for i in ids for d in st.get(i, {}).get("deps", [])):
            for pat in deps_cfg:
                file_pat, _, num = pat.partition("#")
                hit = wf.matches(expand(file_pat, ids, d))
                if hit:
                    exc = tail_from(wf.read(hit[0]), num) if num else wf.read(hit[0])
                    excerpts.append({"id": d, "file": wf.rel(hit[0]), "from": num or None, "text": exc})

    cap = cfg.get("run_max", 80)
    runs = []
    for cmd in cfg.get("run", []):
        try:  # commands come from workflow/workflow.toml (repository config), hence a shell
            res = subprocess.run(cmd, shell=True, cwd=wf.ROOT, capture_output=True, text=True, timeout=RUN_TIMEOUT)
            lines = (res.stdout + res.stderr).strip().splitlines()
        except subprocess.TimeoutExpired:
            lines = [f"(timed out after {RUN_TIMEOUT}s)"]
        runs.append({"cmd": cmd, "output": "\n".join(lines[:cap]), "truncated": max(0, len(lines) - cap)})

    # package AGENTS.md: counted in full (an upper bound: read only those of the packages you touch)
    rules = [size(wf.path(r)) for r in package_rules()] if cfg.get("package_rules") else []
    diff = story_diff() if cfg.get("diff") else None

    inline = sum(len(x["text"] or "") for x in excerpts) + sum(len(x["output"]) for x in runs)
    return {"step": step, "tier": cfg.get("tier"), "ids": ids, "needs_ids": needs_id and not ids, "read": read, "missing": missing,
            "design": design or None, "cited": cited, "sections": sections, "dependencies": excerpts, "runs": runs,
            "package_rules": rules, "diff": diff,
            "tokens": sum(x["tokens"] for x in read + cited + sections + rules) + wf.approx_tokens(inline) + (diff["tokens"] if diff else 0)}


def budget(step: str, ids: list[str], extra: list[str] | None = None) -> str:
    b = budget_data(step, ids, extra)
    out = [f"# Context budget — step '{step}' · tier {b['tier'] or '—'}" + (f" · IDs {' '.join(ids)}" if ids else "")
           + f" · ≈{b['tokens']:,} tokens",
           f"Step file: workflow/steps/{step}.md. Read ONLY what follows; for anything else, ask or grep a specific symbol.",
           "(The tool adds a fixed per-session baseline on top: system prompt, MCP servers, skills; see docs/GUIDE.md.)", ""]
    if b["needs_ids"]:
        out += [f"⚠ step '{step}' needs story IDs: python3 tools/context.py {step} <ID…>", ""]
    out.append("## Read in full")
    for r in b["read"]:
        out.append(f"- {r['path']} ({r['lines']} lines){'  ⚠ long: read only the sections you need' if r['long'] else ''}")
    if b["design"]:
        out += ["", "## Existing design (map it, do not rebuild it)",
                f"- {b['design']} — read its screen list first: python3 tools/context.py --index {b['design']} (Markdown/HTML headings), "
                "then only the parts each screen needs"]
    if b["cited"]:
        out += ["", "## Cited files"]
        for c in b["cited"]:
            out.append(f"- {c['path']}: missing" if not c["exists"] else
                       f"- read {c['path']} ({c['lines']} lines)" + (f"  ⚠ long: `python3 tools/context.py --index {c['path']}` first" if c["long"] else ""))
    if b["missing"]:
        out += ["", "## Missing (declare as missing source if relevant)"] + [f"- {m}" for m in b["missing"]]
    if b["sections"]:
        out += ["", "## Cited references (extracted sections only)"]
        for s in b["sections"]:
            if s["ref"].startswith("ADR-"):
                out.append(f"- {s['ref']}: " + (f"read {s['file']}" if s["file"] else "missing"))
            else:
                out += ["", f"### {s['ref']} ({s['file']})", s["text"] or "(not found)"]
    if b["package_rules"]:
        out += ["", "## Package rules (read those of the packages you touch)"] + [f"- {r['path']} ({r['lines']} lines)" for r in b["package_rules"]]
    if b["diff"]:
        d = b["diff"]
        how = (f"≈{d['tokens']:,} tokens: too large to read at once. Review file by file: `git diff {d['base']}...HEAD -- <path>`"
               if d["by_file"] else f"≈{d['tokens']:,} tokens: `git diff {d['base']}...HEAD`")
        out += ["", f"## Story diff vs {d['base']} ({len(d['files'])} files) — {how}", d["stat"] or "(empty diff)"]
    for d in b["dependencies"]:
        out += ["", f"### Dependency {d['id']} — {d['file']}" + (f" §{d['from']}+" if d["from"] else ""), d["text"] or "(section not found)"]
    for r in b["runs"]:
        body = r["output"] + (f"\n… ({r['truncated']} more lines)" if r["truncated"] else "")
        out += ["", f"## $ {r['cmd']}", body or "(no output)"]
    return "\n".join(out)


def main() -> None:
    try:
        run()
    except (OSError, ValueError) as e:  # unreadable or malformed files (tomllib errors are ValueErrors naming the file)
        if "--json" not in sys.argv:
            raise
        print(json.dumps({"schema": wf.SCHEMA, "error": {"code": "bad_input", "message": str(e)}}, ensure_ascii=False))
        sys.exit(1)


def run() -> None:
    a = [x for x in sys.argv[1:] if x != "--json"]
    as_json = "--json" in sys.argv
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    if a[0] == "--index":
        if as_json:
            wf.dump_json({"file": a[1], "headings": index(a[1]).splitlines()})
        else:
            print(index(a[1]))
    elif a[0] == "--package-rules":
        rules = package_rules()
        if as_json:
            wf.dump_json({"rules": rules})
        else:
            print("Package rules (read those of the packages you touch):\n" + "\n".join(f"- {r}" for r in rules) if rules else "No package AGENTS.md yet.")
    elif a[0] == "--repo-map":
        import repo_map
        if as_json:
            wf.dump_json(repo_map.repo_data())
        else:
            print(repo_map.repo_map())
    else:
        rest, extra = a[1:], []
        while "--with" in rest:
            k = rest.index("--with")
            extra += rest[k + 1:k + 2]
            rest = rest[:k] + rest[k + 2:]
        ids = [wf.norm_id(x) if re.fullmatch(r"[A-Za-z]+-?\d{4}", x) else x for x in rest]
        if as_json:
            wf.dump_json(budget_data(a[0], ids, extra))
        else:
            print(budget(a[0], ids, extra))


if __name__ == "__main__":
    main()
