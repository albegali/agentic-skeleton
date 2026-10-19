#!/usr/bin/env python3
"""Deterministic consistency check of the workflow (review mode helper). Exit 1 on errors.

Inception: unique FR/NFR IDs; ADR numbering; mockup map cites existing FRs.
Backlog:   story IDs match project.toml prefix; epics exist; deps exist and are acyclic; FR/NFR links exist; Must FRs covered.
Chain:     naming of Story/Analysis/Refined Story/Brief/Spec/RUN; Spec ↔ Brief; RUN ↔ Spec; status values; approval before execution; Persisted before Closed.
Adapters:  generated tool files are up to date (tools/render_agents.py --check).
--json:    {"ok", "errors", "warnings", "counts", "issues": [{"level", "area", "message"}]} (same exit code).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render_agents  # noqa: E402
import wf  # noqa: E402

E: list[str] = []
W: list[str] = []
FR_FILE = "reference/product/functional-requirements.md"
NFR_FILE = "reference/product/non-functional-requirements.md"
SPEC_ST = {"Draft", "Ready", "In Progress", "Done", "Blocked"}
RUN_ST = {"Draft", "Strategy Approved", "Executing", "Tuning", "Persisted", "Closed"}


def heading_ids(p: str, kind: str) -> list[str]:
    if not wf.exists(p):
        return []
    return re.findall(rf"^#+\s+({kind}-\d+)\b", wf.read(p), re.M)


def check_inception() -> tuple[set[str], set[str], dict[str, str]]:
    fr, nfr = heading_ids(FR_FILE, "FR"), heading_ids(NFR_FILE, "NFR")
    for kind, ids in (("FR", fr), ("NFR", nfr)):
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            E.append(f"{kind} duplicated IDs: {', '.join(sorted(dup))}")
    prio: dict[str, str] = {}
    if wf.exists(FR_FILE):
        for sec in re.split(r"^(?=#+\s+FR-\d+)", wf.read(FR_FILE), flags=re.M):
            m = re.match(r"#+\s+(FR-\d+)", sec)
            p = re.search(r"\*\*Priority\*\*:\s*(\w+)", sec)
            if m and p:
                prio[m.group(1)] = p.group(1)
    adrs = [os.path.basename(p) for p in wf.matches("reference/architecture/ADR-*.md")]
    nums = [m.group(1) for a in adrs if (m := re.match(r"ADR-(\d{3})-[a-z0-9-]+\.md$", a))]
    for a in adrs:
        if not re.match(r"ADR-\d{3}-[a-z0-9-]+\.md$", a):
            E.append(f"ADR naming (ADR-NNN-slug.md): {a}")
    if len(nums) != len(set(nums)):
        E.append("ADR numbers duplicated")
    for src in wf.sources() + ([wf.design()] if wf.design() else []):
        if not wf.exists(src):
            W.append(f"project.toml [inception] source not found: {src}")
    mref = "reference/product/mockup-reference.md"
    if wf.exists(mref) and fr:
        for x in sorted(set(re.findall(r"\bFR-\d+\b", wf.read(mref))) - set(fr)):
            E.append(f"mockup-reference cites unknown {x}")
    return set(fr), set(nfr), prio


def check_backlog(fr: set[str], nfr: set[str], prio: dict[str, str]) -> None:
    b = wf.backlog()
    st = b.get("story", [])
    if not st:
        return
    rx = re.compile(rf"^{wf.id_rx()}$")
    epics = {e["id"] for e in b.get("epic", [])}
    ids = [s["id"] for s in st]
    for i in {i for i in ids if ids.count(i) > 1}:
        E.append(f"story ID duplicated: {i}")
    known = set(ids)
    for s in st:
        i = s["id"]
        if not rx.match(i):
            E.append(f"story ID {i} does not match prefix {wf.prefix()} + 4 digits")
        if s.get("epic") not in epics:
            E.append(f"{i}: unknown epic {s.get('epic')}")
        if not re.match(r"^[a-z0-9-]+$", s.get("slug", "")):
            E.append(f"{i}: slug must be kebab-case")
        for d in s.get("deps", []):
            if d not in known:
                E.append(f"{i}: unknown dependency {d}")
        if fr:
            for x in s.get("fr", []):
                if x not in fr:
                    E.append(f"{i}: unknown {x}")
        if nfr:
            for x in s.get("nfr", []):
                if x not in nfr:
                    E.append(f"{i}: unknown {x}")
        if not s.get("ac"):
            W.append(f"{i}: no acceptance criteria")
        if s.get("size") == "XL":
            W.append(f"{i}: size XL, consider splitting")
    graph = {s["id"]: [d for d in s.get("deps", []) if d in known] for s in st}
    seen: dict[str, int] = {}

    def visit(n: str, stack: list[str]) -> None:
        if seen.get(n) == 1:
            E.append("dependency cycle: " + " → ".join(stack[stack.index(n):] + [n]))
            return
        if seen.get(n) == 2:
            return
        seen[n] = 1
        for d in graph[n]:
            visit(d, stack + [n])
        seen[n] = 2

    for n in graph:
        visit(n, [])
    covered = {x for s in st for x in s.get("fr", [])}
    for x in sorted(f for f, p in prio.items() if p == "Must" and f not in covered):
        W.append(f"Must requirement {x} not covered by any story")


def check_chain() -> None:
    idrx = rf"{wf.id_rx()}"
    for kind, pat, rx in [
        ("Story", "analysis/10-stories/*.md", rf"^STORY_{idrx}_[a-z0-9_]+\.md$"),
        ("Analysis", "analysis/20-analysis/*.md", rf"^ANALYSIS_{idrx}_[a-z0-9_]+\.md$"),
        ("Refined Story", "analysis/30-refined/*.md", rf"^REFINED_{idrx}_[a-z0-9_]+\.md$"),
        ("Brief", "delivery/10-briefs/*.md", rf"^BRIEF-{idrx}-[a-z0-9-]+\.md$"),
        ("Spec", "delivery/20-specs/SPEC-*.md", rf"^SPEC-{idrx}-[a-z0-9-]+\.md$"),
        ("RUN", "delivery/30-runs/*.md", rf"^RUN-{idrx}[a-z0-9-]*\.md$"),
    ]:
        for p in wf.matches(pat):
            if not re.match(rx, os.path.basename(p)):
                E.append(f"{kind} naming: {wf.rel(p)}")
    for p in wf.matches("analysis/30-refined/REFINED_*.md"):
        i = os.path.basename(p).split("_")[1]
        if not wf.matches(f"analysis/20-analysis/ANALYSIS_{i}_*.md"):
            W.append(f"Refined Story {i} without Analysis")
    for p in wf.matches("delivery/20-specs/SPEC-*.md"):
        t = wf.read(p)
        i = os.path.basename(p).split("-")[1]
        s = wf.md_status(t)
        if s and s not in SPEC_ST:
            E.append(f"SPEC-{i}: invalid status '{s}'")
        if f"BRIEF-{i}" not in t:
            E.append(f"SPEC-{i}: does not reference BRIEF-{i}")
        if not wf.matches(f"delivery/10-briefs/BRIEF-{i}-*.md"):
            E.append(f"SPEC-{i}: BRIEF-{i} missing")
        if s in ("In Progress", "Done") and not wf.matches(f"delivery/30-runs/RUN-{i}*.md"):
            E.append(f"SPEC-{i} {s} without RUN")
    for p in wf.matches("delivery/30-runs/RUN-*.md"):
        t = wf.read(p)
        m = re.match(rf"RUN-({idrx})", os.path.basename(p))
        if not m:
            continue
        i = m.group(1)
        s = wf.md_status(t)
        if s and s not in RUN_ST:
            E.append(f"RUN-{i}: invalid status '{s}'")
        if not wf.matches(f"delivery/20-specs/SPEC-{i}-*.md"):
            E.append(f"RUN-{i}: SPEC-{i} missing")
        if "# 1. Execution Strategy" not in t:
            E.append(f"RUN-{i}: Execution Strategy missing")
        if s and s != "Draft" and not re.search(r"- \[x\] Approved", t):
            E.append(f"RUN-{i}: status {s} without recorded approval (§2)")
        if s == "Closed" and not re.search(r"# 7\. Persistence.*?- \[x\]", t, re.S):
            E.append(f"RUN-{i}: Closed without Persistence")


def check_adapters() -> None:
    for p in render_agents.check(render_agents.render()):
        E.append(f"stale adapter (run `make agents`): {p}")


def main() -> None:
    issues: list[dict] = []

    def tag(area: str, ne: int, nw: int) -> None:
        issues.extend([{"level": "error", "area": area, "message": m} for m in E[ne:]]
                      + [{"level": "warning", "area": area, "message": m} for m in W[nw:]])

    fr, nfr, prio = check_inception()
    tag("inception", 0, 0)
    for area, fn in (("backlog", lambda: check_backlog(fr, nfr, prio)), ("chain", check_chain), ("adapters", check_adapters)):
        ne, nw = len(E), len(W)
        fn()
        tag(area, ne, nw)
    counts = {"FR": len(fr), "NFR": len(nfr), "ADR": len(wf.matches("reference/architecture/ADR-*.md")), "stories": len(wf.stories()),
              "Analysis": len(wf.matches("analysis/20-analysis/ANALYSIS_*.md")), "Refined Story": len(wf.matches("analysis/30-refined/REFINED_*.md")),
              "Brief": len(wf.matches("delivery/10-briefs/BRIEF-*.md")), "Spec": len(wf.matches("delivery/20-specs/SPEC-*.md")),
              "RUN": len(wf.matches("delivery/30-runs/RUN-*.md"))}
    if "--json" in sys.argv:
        wf.dump_json({"ok": not E, "errors": len(E), "warnings": len(W), "counts": counts, "issues": issues})
        sys.exit(1 if E else 0)
    print(" · ".join(f"{k} {v}" for k, v in counts.items()))
    for w in W:
        print("WARN ", w)
    for e in E:
        print("ERROR", e)
    print("OK" if not E else f"{len(E)} errors")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
