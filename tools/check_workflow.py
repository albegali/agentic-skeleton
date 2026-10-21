#!/usr/bin/env python3
"""Deterministic consistency check of the workflow (review mode helper). Exit 1 on errors.

Inception: unique FR/NFR IDs; ADR numbering; mockup map cites existing FRs.
Backlog:   stories.toml schema; story IDs match project.toml prefix; epics exist; deps, supersedes, split_from exist and deps
           are acyclic; FR/NFR links exist; Must FRs covered; superseded story without successor; dependency on a cancelled
           story. PLAN.md ↔ backlog: unknown IDs/epics, unplanned (hotfixes exempt) or twice-planned stories, a dependency
           planned after its dependant, sprint capacity (frontmatter `capacity:`), Must stories planned after their release
           target, sprints past their end date with open stories.
Chain:     naming of Story/Analysis/Refined Story/Brief/Spec/RUN/spike note; Spec ↔ Brief; RUN ↔ Spec; status values; approval
           before execution; Persistence (§7) before Closed; Blocked RUN without an open §6 deviation; RUN still open on a
           cancelled story; Spec Done / RUN Closed with an unchecked acceptance criterion or gate; template placeholders left
           in Briefs, Specs and RUNs past Draft. --git: closed artifacts changed later without a Revisions line.
Adapters:  generated tool files are up to date (tools/render_agents.py --check).
--json:    contract envelope `check`, data {"ok", "errors", "warnings", "counts", "issues": [{"level", "area", "message"}]}
           (same exit code: a workflow with errors is still a successful check, reported in data).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render_agents  # noqa: E402
import wf  # noqa: E402

E: list[str] = []
W: list[str] = []
FR_FILE = "reference/product/functional-requirements.md"
NFR_FILE = "reference/product/non-functional-requirements.md"
INCEPTION = [FR_FILE, NFR_FILE, "reference/product/vision.md", "reference/product/mockup-reference.md",
             "reference/architecture/architecture.md", "backlog/stories.toml", "PLAN.md"]


def bad_status(label: str, kind: str, raw: str | None) -> None:
    """Error when a status value is not in the shared vocabulary (wf.STATUSES): next_step would block on it."""
    if raw and not wf.status(kind, raw):
        E.append(f"{label}: invalid status '{raw}' (expected {wf.expected(kind)})")


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
    for f in INCEPTION:
        bad_status(f, "inception", wf.artifact_status(f))
    for p in wf.matches("reference/architecture/ADR-*.md"):
        bad_status(wf.rel(p), "adr", wf.front(wf.read(p), "status"))
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
    schema = wf.backlog_errors()
    if schema:  # the other checks (and tools) assume a valid schema
        E.extend(schema)
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
        for k in wf.STORY_LINKS:
            if k in s and s[k] not in known:
                E.append(f"{i}: `{k}` names unknown story {s[k]}")
        if s.get("status") == "superseded" and not any(i in (x.get("supersedes"), x.get("split_from")) for x in st):
            W.append(f"{i}: superseded, but no story has `supersedes` or `split_from` = \"{i}\"")
        if s.get("status") in (None, "open"):
            for d in s.get("deps", []):
                if next((x for x in st if x["id"] == d), {}).get("status") == "cancelled":
                    W.append(f"{i}: depends on cancelled story {d}: drop the dependency or cancel {i}")
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


def check_plan() -> None:
    """PLAN.md sprints and releases against backlog/stories.toml (reported under the backlog area)."""
    if not wf.exists("PLAN.md") or wf.backlog_errors():
        return
    import next_step  # lazy: next_step imports wf
    st = wf.stories()
    epics = {e.get("id") for e in wf.backlog().get("epic", [])}
    text = wf.read("PLAN.md")
    rows = wf.sprints()
    where: dict[str, list[str]] = {}
    for sp in rows:
        for i in sp["ids"]:
            where.setdefault(i, []).append(sp["sprint"])
    for line in text.splitlines():
        if re.match(r"^\|\s*S\d+", line):
            for ep in re.findall(r"EP-\d{2}", line.split("|")[4] if line.count("|") > 4 else ""):
                if ep not in epics:
                    E.append(f"PLAN.md: unknown epic {ep}")
    for i, sps in where.items():
        if i not in st:
            E.append(f"PLAN.md: unknown story {i} ({sps[0]})")
        elif len(sps) > 1:
            W.append(f"PLAN.md: {i} planned in more than one sprint ({', '.join(sps)})")
    if rows:
        unplanned = [i for i in st if i not in where and st[i].get("type") != "hotfix"]  # hotfixes run outside the plan
        if unplanned:
            W.append(f"PLAN.md: stories in no sprint: {', '.join(unplanned)}")
    order = {sp["sprint"]: n for n, sp in enumerate(rows)}
    for i, sps in where.items():
        for d in st.get(i, {}).get("deps", []):
            if d in where and order[where[d][0]] > order[sps[0]]:
                W.append(f"PLAN.md: {i} ({sps[0]}) depends on {d}, planned later ({where[d][0]})")
    fm = wf.front(text, "capacity")
    cap = int(fm) if fm and fm.isdigit() else None
    points = dict(wf.POINTS)
    for k, v in re.findall(r"\b(XS|S|M|L|XL)\s*=\s*(\d+)", wf.front(text, "points") or ""):
        points[k] = int(v)
    if cap:
        for sp in rows:
            used = sum(points.get(st[i].get("size", ""), 0) for i in sp["ids"] if i in st)
            if used > cap:
                W.append(f"PLAN.md: {sp['sprint']} has {used} points, capacity {cap}")
    ends = wf.sprint_ends()
    targets = {r["id"]: wf.plan_date(r["target"], 0) for r in wf.releases()}
    for i, sps in where.items():
        s = st.get(i, {})
        end, target = ends.get(sps[0]), targets.get(s.get("release", ""))
        if s.get("priority") == "Must" and end and target and end > target:
            W.append(f"PLAN.md: Must story {i} planned in {sps[0]} (ends {end}), after {s['release']} target {target}")
    today = dt.date.today()
    for sp in rows:
        end = ends.get(sp["sprint"])
        if end and end < today:
            late = [i for i in sp["ids"] if i in st and next_step.stage(i)[0] != "done"]
            if late:
                W.append(f"PLAN.md: {sp['sprint']} ended {end} with open stories {', '.join(late)}: update the plan")


UNCHECKED = re.compile(r"^\s*-\s*\[ \]\s*(.*)$", re.M)


def unchecked(text: str, heading_rx: str) -> list[str]:
    """Unticked boxes of a section, except those marked deferred / n/a (a decision, not a forgotten box)."""
    sec = wf.heading_section(text, heading_rx) or ""
    return [m.strip() for m in UNCHECKED.findall(sec) if not re.search(r"\b(deferred|n/a|not applicable)\b", m, re.I)]


PLACEHOLDER = re.compile(r"^\s*(?:-\s*)?(?:…|\.\.\.)\s*$|^\s*-\s*Step \d+:\s*…\s*$|(?:^|[\s(])<[A-Z][^<>\n]{0,60}>|\bYYYY-MM-DD\b")


def placeholders(text: str) -> list[int]:
    """Line numbers still holding template placeholders (`…` items, `<Title>`, `YYYY-MM-DD`), code excluded."""
    out, fence = [], None
    for n, line in enumerate(text.splitlines(), 1):
        if f := wf.FENCE.match(line):
            fence = None if fence == f.group(1) else fence or f.group(1)
            continue
        if not fence and PLACEHOLDER.search(re.sub(r"`[^`]*`", "", line)):
            out.append(n)
    return out


def check_placeholders(label: str, text: str) -> None:
    lines = placeholders(text)
    if lines:
        W.append(f"{label}: {len(lines)} template placeholder(s) left (line {', '.join(map(str, lines[:5]))}"
                 + (", …" if len(lines) > 5 else "") + ")")


def check_chain() -> None:
    idrx = rf"{wf.id_rx()}"
    for kind, pat, rx in [
        ("Story", "analysis/10-stories/*.md", rf"^STORY_{idrx}_[a-z0-9_]+\.md$"),
        ("Analysis", "analysis/20-analysis/*.md", rf"^ANALYSIS_{idrx}_[a-z0-9_]+\.md$"),
        ("Refined Story", "analysis/30-refined/*.md", rf"^REFINED_{idrx}_[a-z0-9_]+\.md$"),
        ("Brief", "delivery/10-briefs/*.md", rf"^BRIEF-{idrx}-[a-z0-9-]+\.md$"),
        ("Spec", "delivery/20-specs/SPEC-*.md", rf"^SPEC-{idrx}-[a-z0-9-]+\.md$"),
        ("RUN", "delivery/30-runs/*.md", rf"^RUN-{idrx}[a-z0-9-]*\.md$"),
        ("Spike note", "delivery/40-spikes/*.md", rf"^SPIKE-{idrx}-[a-z0-9-]+\.md$"),
    ]:
        for p in wf.matches(pat):
            if not re.match(rx, os.path.basename(p)):
                E.append(f"{kind} naming: {wf.rel(p)}")
    for kind, pat in (("analysis", "analysis/20-analysis/ANALYSIS_*.md"), ("refined", "analysis/30-refined/REFINED_*.md")):
        for p in wf.matches(pat):
            bad_status(wf.rel(p), kind, wf.front(wf.read(p), "status"))
    for p in wf.matches("delivery/10-briefs/BRIEF-*.md"):
        t = wf.read(p)
        bad_status(wf.rel(p), "brief", wf.md_status(t))
        if wf.status("brief", wf.md_status(t)):
            check_placeholders(wf.rel(p), t)
    for p in wf.matches("delivery/40-spikes/SPIKE-*.md"):
        bad_status(wf.rel(p), "spike", wf.md_status(wf.read(p)))
    for p in wf.matches("analysis/30-refined/REFINED_*.md"):
        i = os.path.basename(p).split("_")[1]
        if not wf.matches(f"analysis/20-analysis/ANALYSIS_{i}_*.md"):
            W.append(f"Refined Story {i} without Analysis")
    for p in wf.matches("delivery/20-specs/SPEC-*.md"):
        t = wf.read(p)
        i = os.path.basename(p).split("-")[1]
        raw = wf.md_status(t)
        bad_status(f"SPEC-{i}", "spec", raw)
        s = wf.status("spec", raw)
        if f"BRIEF-{i}" not in t:
            E.append(f"SPEC-{i}: does not reference BRIEF-{i}")
        if not wf.matches(f"delivery/10-briefs/BRIEF-{i}-*.md"):
            E.append(f"SPEC-{i}: BRIEF-{i} missing")
        if s in ("In Progress", "Done") and not wf.matches(f"delivery/30-runs/RUN-{i}*.md"):
            E.append(f"SPEC-{i} {s} without RUN")
        if s == "Done":
            for sec, rx in (("acceptance criteria", r"^#\s+4\."), ("quality gates", r"^#\s+7\.")):
                if left := unchecked(t, rx):
                    E.append(f"SPEC-{i} Done with unchecked {sec}: {'; '.join(left)}")
        if s and s != "Draft":
            check_placeholders(f"SPEC-{i}", t)
    stories = {} if wf.backlog_errors() else wf.stories()
    for p in wf.matches("delivery/30-runs/RUN-*.md"):
        t = wf.read(p)
        m = re.match(rf"RUN-({idrx})", os.path.basename(p))
        if not m:
            continue
        i = m.group(1)
        raw = wf.md_status(t)
        bad_status(f"RUN-{i}", "run", raw)
        s = wf.status("run", raw)
        if not wf.matches(f"delivery/20-specs/SPEC-{i}-*.md"):
            E.append(f"RUN-{i}: SPEC-{i} missing")
        if "# 1. Execution Strategy" not in t:
            E.append(f"RUN-{i}: Execution Strategy missing")
        if s and s not in ("Draft", "Stopped", "Cancelled") and not wf.run_approved(t):
            E.append(f"RUN-{i}: status {s} without recorded approval (§2)")
        if s == "Blocked" and not wf.open_deviations(t):
            W.append(f"RUN-{i}: Blocked without a §6 deviation awaiting approval (`Scope impact: Requires approval`)")
        if s not in ("Closed", "Cancelled") and (gone := stories.get(i, {}).get("status")) in ("cancelled", "superseded"):
            W.append(f"RUN-{i}: story {gone} but RUN {s or 'Draft'}: set the RUN to Cancelled")
        if s == "Closed" and not re.search(r"^\s*-\s*\[[xX]\]", wf.heading_section(t, r"^#\s+7\.") or "", re.M):
            E.append(f"RUN-{i}: Closed without Persistence")
        if s == "Closed" and (left := unchecked(t, r"^#\s+8\.")):
            E.append(f"RUN-{i}: Closed with unchecked quality gates: {'; '.join(left)}")
        if s and s != "Draft":
            check_placeholders(f"RUN-{i}", t)


CLOSED = (("delivery/10-briefs/BRIEF-*.md", "brief", "Closed"), ("delivery/20-specs/SPEC-*.md", "spec", "Done"),
          ("delivery/30-runs/RUN-*.md", "run", "Closed"))


def git(*args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def revisions(text: str) -> int:
    return len(re.findall(r"^\s*-\s+\S", wf.heading_section(text, r"^#+\s+Revisions\b") or "", re.M))


def check_revisions() -> None:
    """--git: an artifact changed after the commit that closed it must add a line under a `Revisions` heading."""
    if git("rev-parse", "--is-inside-work-tree") is None:
        W.append("--git: not a git repository, revision check skipped")
        return
    for pat, kind, final in CLOSED:
        for p in wf.matches(pat):
            r = wf.rel(p)
            closed_at = None
            for c in (git("log", "--format=%H", "--reverse", "--", r) or "").split():
                old = git("show", f"{c}:{r}")
                if old is not None and wf.status(kind, wf.md_status(old)) == final:
                    closed_at = (c, old)
                    break
            if closed_at and wf.read(p) != closed_at[1] and revisions(wf.read(p)) <= revisions(closed_at[1]):
                W.append(f"{r}: changed after closure ({closed_at[0][:7]}) without a new line under `## Revisions`")


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
    steps = [("backlog", lambda: check_backlog(fr, nfr, prio)), ("backlog", check_plan), ("chain", check_chain)]
    steps += [("chain", check_revisions)] if "--git" in sys.argv else []
    for area, fn in steps + [("adapters", check_adapters)]:
        ne, nw = len(E), len(W)
        fn()
        tag(area, ne, nw)
    counts = {"FR": len(fr), "NFR": len(nfr), "ADR": len(wf.matches("reference/architecture/ADR-*.md")), "stories": len(wf.backlog().get("story", [])),
              "Analysis": len(wf.matches("analysis/20-analysis/ANALYSIS_*.md")), "Refined Story": len(wf.matches("analysis/30-refined/REFINED_*.md")),
              "Brief": len(wf.matches("delivery/10-briefs/BRIEF-*.md")), "Spec": len(wf.matches("delivery/20-specs/SPEC-*.md")),
              "RUN": len(wf.matches("delivery/30-runs/RUN-*.md"))}
    if "--json" in sys.argv:
        wf.dump_envelope("check", {"ok": not E, "errors": len(E), "warnings": len(W), "counts": counts, "issues": issues})
        sys.exit(1 if E else 0)
    print(" · ".join(f"{k} {v}" for k, v in counts.items()))
    for w in W:
        print("WARN ", w)
    for e in E:
        print("ERROR", e)
    print("OK" if not E else f"{len(E)} errors")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as e:  # unreadable or malformed TOML/Markdown (tomllib.TOMLDecodeError is a ValueError)
        if "--json" not in sys.argv:
            raise
        wf.fail_envelope("check", "bad_input", str(e))
