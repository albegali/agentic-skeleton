#!/usr/bin/env python3
"""Compute the next workflow step from the files in the repository (deterministic, no LLM, no network).

Usage:
  python3 tools/next_step.py            # full view + recommended step
  python3 tools/next_step.py PR0101     # state of one story
  python3 tools/next_step.py --json     # machine output (+ stage of every story in delivery)

Phases: inception (project.toml → vision → requirements → mockup → architecture → backlog → PLAN.md; for an existing
codebase adopted with tools/adopt.py: project.toml → onboard → backlog → PLAN.md), then analysis/delivery per story following the sprints of PLAN.md. Steps are defined in workflow/workflow.toml.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

APPROVED = {"approved", "accepted"}


# ---------------------------------------------------------------- inception

def inception() -> dict | None:
    """First inception gate not yet passed, or None when the plan is approved."""
    proj = wf.project().get("project", {})
    if not proj.get("initialized"):
        return {"step": "kickoff", "owner": "agent", "ids": [], "why": "project not initialized (project.toml)"}
    if proj.get("origin") == "brownfield":
        gates = [("onboard", ["reference/product/vision.md", "reference/product/functional-requirements.md",
                              "reference/architecture/architecture.md"])]
    else:
        gates = [
            ("kickoff", ["reference/product/vision.md"]),
            ("requirements", ["reference/product/functional-requirements.md", "reference/product/non-functional-requirements.md"]),
        ]
        if wf.project().get("inception", {}).get("mockup", True):
            gates.append(("mockup", ["reference/product/mockup-reference.md"]))
        gates.append(("architecture", ["reference/architecture/architecture.md"]))
    gates += [
        ("backlog", ["backlog/stories.toml"]),
        ("plan", ["PLAN.md"]),
    ]
    for step, files in gates:
        missing = [f for f in files if not wf.exists(f)]
        if missing:
            return {"step": step, "owner": "agent", "ids": [], "why": f"missing: {', '.join(missing)}"}
        if step == "backlog" and not wf.stories():
            return {"step": step, "owner": "agent", "ids": [], "why": "backlog/stories.toml has no stories"}
        pending = [f for f in files if (wf.artifact_status(f) or "draft") not in APPROVED]
        if step in ("architecture", "onboard"):
            pending += [wf.rel(p) for p in wf.matches("reference/architecture/ADR-*.md")
                        if (wf.front(wf.read(p), "status") or "proposed") not in APPROVED and "superseded" not in (wf.front(wf.read(p), "status") or "")]
            if not wf.project().get("stack", {}).get("decided"):
                pending.append("project.toml [stack] decided = true")
        if pending:
            return {"step": "approve", "owner": "human", "ids": [], "files": pending, "after": step,
                    "why": f"waiting for your approval ({step}): {', '.join(pending)}"}
    return None


# ---------------------------------------------------------------- per-story stage

def stage(i: str) -> tuple[str, str, str]:
    """(stage, detail, owner) — owner: agent | human | done."""
    analysis = wf.one(f"analysis/20-analysis/ANALYSIS_{i}_*.md")
    refined = wf.one(f"analysis/30-refined/REFINED_{i}_*.md")
    int_ = wf.one(f"delivery/10-briefs/BRIEF-{i}-*.md")
    spec = wf.one(f"delivery/20-specs/SPEC-{i}-*.md")
    run = wf.one(f"delivery/30-runs/RUN-{i}.md") or wf.one(f"delivery/30-runs/RUN-{i}*.md")
    if run:
        t = wf.read(run)
        st = wf.md_status(t) or "Draft"
        approved = bool(re.search(r"-\s*\[x\]\s*Approved", t))
        if st == "Closed":
            return ("done", "RUN closed", "done")
        if st == "Persisted":
            return ("review", "RUN persisted: review and closure", "agent")
        if st == "Tuning":
            return ("tuning", "human verification / in-scope tuning, then persistence", "human")
        if st in ("Strategy Approved", "Executing"):
            return ("execute", f"RUN {st}", "agent")
        if not approved:
            if "### Plan" in t and re.search(r"- Step 1: (?!…)", t):
                return ("run-approval", "strategy written, human approval missing (RUN §2)", "human")
            return ("run-strategy", "RUN draft without strategy", "agent")
        return ("execute", "strategy approved", "agent")
    if spec:
        st = wf.md_status(wf.read(spec)) or "Draft"
        if st == "Draft":
            return ("spec-approval", "Spec draft: human review, status → Ready", "human")
        if st == "Blocked":
            return ("blocked", "Spec blocked", "human")
        return ("run-strategy", f"Spec {st}, RUN missing", "agent")
    if int_:
        return ("brief-spec", "Brief present, Spec missing", "agent")
    if refined:
        t = wf.read(refined)
        st = wf.front(t, "status") or "draft"
        outcome = t.split("## 8.")[-1].lower() if "## 8." in t else ""
        if "not ready" in outcome and "ready for brief" not in outcome:
            return ("workshop", "Refined Story 'not ready': another refinement is needed", "human")
        if st in ("refined", "approved"):
            return ("brief-spec", f"Refined Story {st}: ready for the Brief", "agent")
        return ("refine", f"Refined Story {st}: to be completed", "agent")
    if analysis:
        st = wf.front(wf.read(analysis), "status") or "draft"
        return ("workshop", f"Analysis {st}: workshop needed, then the Refined Story with its evidence", "human")
    return ("analysis", "no artifact yet", "agent")


def deps_done(i: str) -> bool:
    st = wf.stories()
    return all(stage(d)[0] == "done" for d in st[i].get("deps", []) if d in st)


def recommend(plan: list[dict]) -> dict:
    st = wf.stories()
    states = {i: stage(i) for sp in plan for i in sp["ids"] if i in st}
    current = next((sp for sp in plan if sp["ids"] and any(states.get(i, ("done",))[0] != "done" for i in sp["ids"])), None)
    idx = plan.index(current) if current else len(plan)
    nxt = next((sp for sp in plan[idx + 1:] if sp["ids"]), None)
    human = [(i, s) for i, s in states.items() if s[2] == "human"]
    base = {"current": current, "next_sprint": nxt, "human_gates": human, "states": states}

    # 1. development: continue the most advanced story of the current sprint (one at a time)
    if current:
        for stg in ("review", "execute", "run-strategy", "brief-spec"):
            for i in current["ids"]:
                if i in states and states[i][0] == stg and deps_done(i):
                    return {**base, "step": stg, "ids": [i], "owner": "agent",
                            "why": f"{current['sprint']}: {i} is in '{stg}' ({states[i][1]}); dependencies closed"}
    # 2. analysis: missing Analysis of the current + next sprint (look-ahead)
    pool = (current["ids"] if current else []) + (nxt["ids"] if nxt else [])
    missing = [i for i in pool if i in states and states[i][0] == "analysis"]
    if missing:
        return {**base, "step": "analysis", "ids": missing[:4], "owner": "agent",
                "why": f"Analysis missing for {current['sprint'] if current else ''}{' and ' + nxt['sprint'] if nxt else ''}"
                       + (f" ({len(missing)} total, max 4 per session)" if len(missing) > 4 else "")}
    # 3. Refined Story to complete
    r = [i for i in pool if i in states and states[i][0] == "refine"]
    if r:
        return {**base, "step": "refine", "ids": r[:1], "owner": "agent", "why": f"Refined Story to complete: {', '.join(r)}"}
    # 4. only human gates: the analyst can work ahead on later sprints
    if human:
        ahead: list[str] = []
        for sp in plan[idx + 2:]:
            ahead = [i for i in sp["ids"] if i in st and stage(i)[0] == "analysis"][:4]
            if ahead:
                break
        return {**base, "step": "human-gate", "ids": [i for i, _ in human], "owner": "human",
                "why": "no step runnable by agents: human actions needed",
                "optional": {"step": "analysis", "ids": ahead} if ahead else None}
    return {**base, "step": "none", "ids": [], "owner": "done", "why": "plan completed or dependencies open"}


def weekly_due() -> bool:
    files = wf.matches("project-journal/weekly/*.md")
    if not files:
        return wf.project().get("project", {}).get("initialized", False)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(files[-1]))
    return not m or (dt.date.today() - dt.date.fromisoformat(m.group(1))).days >= 7


def step_info(step: str) -> dict:
    return wf.workflow().get("steps", {}).get(step, {})


def command_for(step: str, ids: list[str]) -> str:
    s = step_info(step)
    if s.get("owner") == "human" or not s.get("command"):
        return "human action (see workflow/steps/%s.md)" % step
    return f"/{s['command']}" + (" " + " ".join(ids) if ids else "")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if args:
        i = args[0].replace("-", "")
        st = wf.stories()
        if i not in st:
            sys.exit(f"Unknown ID: {i}")
        stg, det, own = stage(i)
        res = {"step": stg, "ids": [i], "why": det, "owner": own, "deps": st[i].get("deps", []), "deps_done": deps_done(i)}
        if as_json:
            wf.dump_json(res)
        else:
            print(f"{i} — {st[i].get('title', '')}\n  stage: {stg} ({own}) · {det}\n"
                  f"  dependencies: {', '.join(res['deps']) or '—'} (closed: {res['deps_done']})\n  next: {command_for(stg, [i])}")
        return

    rec = inception()
    phase = "inception" if rec else "delivery"
    if not rec:
        rec = recommend(wf.sprints())
    rec["phase"] = phase
    rec["weekly_due"] = weekly_due()
    info = step_info(rec["step"])
    rec["tier"] = info.get("tier")
    rec["models"] = {k: wf.model_for(k, info["tier"]) for k in wf.enabled_tools()} if info.get("tier") else {}
    rec["command"] = command_for(rec["step"], rec["ids"])

    if as_json:
        out = {k: v for k, v in rec.items() if k not in ("states", "current", "next_sprint", "human_gates")}
        out["current_sprint"] = rec["current"]["sprint"] if rec.get("current") else None
        out["next_sprint"] = rec["next_sprint"]["sprint"] if rec.get("next_sprint") else None
        out["human_gates"] = [{"id": i, "stage": s[0], "detail": s[1]} for i, s in rec.get("human_gates", [])]
        if phase == "delivery":  # every story of the backlog, for boards and dashboards
            out["stories"] = [{"id": i, "stage": g[0], "detail": g[1], "owner": g[2]} for i in wf.stories() for g in [stage(i)]]
        wf.dump_json(out)
        return

    if phase == "inception":
        print(f"Phase: inception — {wf.project().get('project', {}).get('name', '')}")
    else:
        cur = rec["current"]
        print(f"Current sprint: {cur['sprint']} ({cur['dates']}) — {cur['goal']}" if cur else "No open sprint")
        for sp in [x for x in (cur, rec["next_sprint"]) if x]:
            print(f"\n{sp['sprint']}:")
            for i in sp["ids"]:
                if i in rec["states"]:
                    s = rec["states"][i]
                    print(f"  {i:8} {s[0]:13} [{s[2]}] {s[1]}")
        if rec["human_gates"]:
            print("\nWaiting on human actions:")
            for i, s in rec["human_gates"]:
                print(f"  {i}: {s[1]}")
    print(f"\n→ Recommended step: {rec['step']} {' '.join(rec['ids'])}\n  {rec['why']}")
    print(f"  Run: {rec['command']}" + (" (fresh session)" if info.get("owner") == "agent" else ""))
    if rec.get("tier"):
        print(f"  Tier: {rec['tier']} → {wf.tier_line(rec['tier'])}")
        if info.get("deep_when"):
            print(f"  Deep tier when: {info['deep_when']}")
    if rec.get("optional"):
        print(f"  In parallel (analysis ahead): /analysis {' '.join(rec['optional']['ids'])}")
    print(f"  Step file: workflow/steps/{rec['step']}.md")
    if rec["weekly_due"]:
        print("\n(reminder) The weekly journal is older than 7 days: /weekly")


if __name__ == "__main__":
    main()
