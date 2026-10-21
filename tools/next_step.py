#!/usr/bin/env python3
"""Compute the next workflow step from the files in the repository (deterministic, no LLM, no network).

Usage:
  python3 tools/next_step.py            # full view + recommended step
  python3 tools/next_step.py PR0101     # state of one story
  python3 tools/next_step.py --json     # machine output (+ stage of every story in delivery)
  python3 tools/next_step.py --me <git user name>   # team use: skip stories others claimed, list the claimable ones

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
        pending, unknown = [], []
        for f in files:
            raw = wf.artifact_status(f)
            if wf.status("inception", raw or "draft") != "approved":
                pending.append(f)
                if raw and not wf.status("inception", raw):
                    unknown.append(f"{f}: unknown status '{raw}' (expected {wf.expected('inception')})")
        if step in ("architecture", "onboard"):
            for p in wf.matches("reference/architecture/ADR-*.md"):
                raw = wf.front(wf.read(p), "status")
                if wf.status("adr", raw or "proposed") not in ("accepted", "superseded", "rejected"):
                    pending.append(wf.rel(p))
                    if raw and not wf.status("adr", raw):
                        unknown.append(f"{wf.rel(p)}: unknown status '{raw}' (expected {wf.expected('adr')})")
            if not wf.project().get("stack", {}).get("decided"):
                pending.append("project.toml [stack] decided = true")
        if pending:
            return {"step": "approve", "owner": "human", "ids": [], "files": pending, "after": step,
                    "why": f"waiting for your approval ({step}): {', '.join(pending)}" + "".join(f"; {u}" for u in unknown)}
    return None


# ---------------------------------------------------------------- per-story stage

def bad_status(path: str, kind: str, raw: str) -> tuple[str, str, str]:
    """An unrecognised status never passes a gate: a human fixes the file."""
    return ("blocked", f"{wf.rel(path)}: unknown status '{raw}' (expected {wf.expected(kind)})", "human")


def stage(i: str) -> tuple[str, str, str]:
    """(stage, detail, owner) — owner: agent | human | done."""
    story = wf.stories().get(i, {})
    if story.get("status") == "cancelled":
        return ("done", "story cancelled", "done")
    if story.get("status") == "superseded":
        by = [k for k, s in wf.stories().items() if i in (s.get("supersedes"), s.get("split_from"))]
        return ("done", f"story superseded{' by ' + ', '.join(by) if by else ''}", "done")
    track = wf.track(story)
    if track == "spike":
        return spike_stage(i)
    analysis, refined, brief, spec, run = (wf.find(k, i) for k in ("analysis", "refined", "brief", "spec", "run"))
    if run:
        t = wf.read(run)
        raw = wf.md_status(t) or "Draft"
        st = wf.status("run", raw)
        if not st:
            return bad_status(run, "run", raw)
        approved = wf.run_approved(t)
        if st == "Closed":
            return ("done", "RUN closed", "done")
        if st == "Cancelled":
            return ("done", "RUN cancelled", "done")
        if spec:  # a Spec changed or blocked after the RUN started stops the RUN until a human acts
            sraw = wf.md_status(wf.read(spec)) or "Draft"
            sst = wf.status("spec", sraw)
            if not sst:
                return bad_status(spec, "spec", sraw)
            if sst == "Draft" and approved:
                return ("spec-approval", "Spec changed after the RUN approval: review it, status → Ready", "human")
            if sst == "Blocked":
                return ("blocked", "Spec blocked: unblock it (decision, dependency), status → Ready", "human")
        if st == "Blocked":
            dev = wf.open_deviations(t)
            return ("blocked", f"RUN blocked: approve deviation #{dev[0]} (RUN §6) with /run {i} approve-deviation {dev[0]}"
                    if dev else "RUN blocked: record the stop condition as a RUN §6 deviation, or resolve it", "human")
        if st == "Stopped" or (st == "Draft" and not approved and wf.run_stopped(t)):
            return ("stopped", f"RUN stopped by you: /run {i} revise: … to resume, or /run {i} cancel: … to drop the story", "human")
        if st == "Persisted":
            if (why := wf.security_sensitive(i)) and wf.security_review(t) != "ok":
                return ("security", f"security-sensitive ({why}): security review before the independent review (RUN §8)", "agent")
            return ("review", "RUN persisted: independent review (RUN §11)", "agent")
        if st == "Reviewed":
            rv = wf.run_review(t)
            if not rv or rv["outcome"] != "ok-to-close":
                return ("review", "RUN Reviewed without an `ok-to-close` review in RUN §11: review again", "agent")
            return ("close", f"review #{rv['n']} ok-to-close: close the story and merge its PR", "agent")
        if st == "Tuning":
            rv = wf.run_review(t)
            if wf.security_review(t) == "changes-requested" and not (rv and rv["outcome"] == "changes-requested"):
                return ("tuning", f"the security review requested changes (RUN §8): /run {i} tuning: …, then /persist {i}", "human")
            if rv and rv["outcome"] == "changes-requested":
                return ("tuning", f"review #{rv['n']} requested changes (RUN §11): /run {i} tuning: …, then /persist {i}", "human")
            return ("tuning", "human verification / in-scope tuning, then persistence", "human")
        if st in ("Strategy Approved", "Executing"):
            return ("execute", f"RUN {st}", "agent")
        if not approved:
            if wf.strategy_written(t):
                return ("run-approval", "strategy written, human approval missing (RUN §2)", "human")
            return ("run-strategy", "RUN draft without strategy", "agent")
        return ("execute", "strategy approved", "agent")
    if spec:
        raw = wf.md_status(wf.read(spec)) or "Draft"
        st = wf.status("spec", raw)
        if not st:
            return bad_status(spec, "spec", raw)
        if st == "Draft" and track == "quick":
            return ("quick", "quick track: Spec draft, RUN strategy missing", "agent")
        if st == "Draft":
            return ("spec-approval", "Spec draft: human review, status → Ready", "human")
        if st == "Blocked":
            return ("blocked", "Spec blocked", "human")
        if st == "Cancelled":
            return ("done", "Spec cancelled", "done")
        return ("run-strategy", f"Spec {st}, RUN missing", "agent")
    if brief:
        if track == "quick":
            return ("quick", "quick track: Brief present, Spec and RUN strategy missing", "agent")
        return ("brief-spec", "Brief present, Spec missing", "agent")
    if refined:
        t = wf.read(refined)
        raw = wf.front(t, "status") or "draft"
        st = wf.status("refined", raw)
        if not st:
            return bad_status(refined, "refined", raw)
        if refined_not_ready(t):
            return ("workshop", "Refined Story 'not ready': another refinement is needed", "human")
        if st in ("refined", "approved"):
            if track == "quick":
                return ("quick", f"Refined Story {st}: ready for the quick track", "agent")
            return ("brief-spec", f"Refined Story {st}: ready for the Brief", "agent")
        return ("refine", f"Refined Story {st}: to be completed", "agent")
    if analysis:
        raw = wf.front(wf.read(analysis), "status") or "draft"
        st = wf.status("analysis", raw)
        if not st:
            return bad_status(analysis, "analysis", raw)
        return ("workshop", f"Analysis {st}: workshop needed, then the Refined Story with its evidence", "human")
    if wf.skips_analysis(story):
        why = "skip_analysis = true" if story.get("skip_analysis") else f"type {story.get('type') or 'XS'}"
        if track == "quick":
            return ("quick", f"no artifact yet; quick track ({why}): Brief, Spec and RUN strategy, one approval", "agent")
        return ("brief-spec", f"no artifact yet; analysis skipped ({why})", "agent")
    return ("analysis", "no artifact yet", "agent")


def spike_stage(i: str) -> tuple[str, str, str]:
    note = wf.one(wf.SPIKE.format(i=i))
    if not note:
        return ("spike", "spike: time-boxed investigation, findings note and follow-up stories", "agent")
    raw = wf.md_status(wf.read(note)) or "Draft"
    st = wf.status("spike", raw)
    if not st:
        return bad_status(note, "spike", raw)
    if st == "Accepted":
        return ("done", "spike findings accepted", "done")
    return ("spike-review", "spike findings: review, add the follow-up stories, status → Accepted", "human")


def refined_not_ready(text: str) -> bool:
    """Refined §8 outcome is `not-ready` (code kept in English, any language around it); legacy English line accepted."""
    outcome = (wf.heading_section(text, r"^##\s+8\.") or "").lower()
    if re.search(r"`(ready|ready-with-open-points|not-ready)`", outcome):
        return "`not-ready`" in outcome
    return "not ready" in outcome and "ready for brief" not in outcome


def deps_done(i: str) -> bool:
    """Every dependency is closed; an unknown dependency is never done (make check reports it)."""
    st = wf.stories()
    return all(d in st and stage(d)[0] == "done" for d in st[i].get("deps", []))


def claimable(plan: list[dict], me: str | None) -> list[str]:
    """Stories nobody else claimed, not done, dependencies closed, in plan order (hotfixes first)."""
    st, cl = wf.stories(), wf.claims()
    order = [i for i, s in st.items() if s.get("type") == "hotfix"] + [i for sp in plan for i in sp["ids"]]
    return [i for i in dict.fromkeys(order) if i in st and stage(i)[0] != "done" and deps_done(i)
            and (i not in cl or wf.same_person(cl[i]["by"], me))]


def recommend(plan: list[dict], me: str | None = None) -> dict:
    st = wf.stories()
    cl = wf.claims() if me else {}
    mine = lambda i: i not in cl or wf.same_person(cl[i]["by"], me)  # noqa: E731 (with --me, others' claims are skipped)
    states = {i: stage(i) for sp in plan for i in sp["ids"] if i in st}
    current = next((sp for sp in plan if sp["ids"] and any(states.get(i, ("done",))[0] != "done" for i in sp["ids"])), None)
    idx = plan.index(current) if current else len(plan)
    nxt = next((sp for sp in plan[idx + 1:] if sp["ids"]), None)
    hotfixes = {i: stage(i) for i, s in st.items() if s.get("type") == "hotfix" and i not in states}
    hotfixes = {i: g for i, g in hotfixes.items() if g[2] != "done"}  # open hotfixes run ahead of the plan, planned or not
    human = [(i, s) for i, s in {**hotfixes, **states}.items() if s[2] == "human"]
    base = {"current": current, "next_sprint": nxt, "human_gates": human, "states": states}

    # 0. hotfixes first
    for i, s in sorted({**hotfixes, **{k: g for k, g in states.items() if st[k].get("type") == "hotfix"}}.items()):
        if s[2] == "agent":
            return {**base, "step": s[0], "ids": [i], "owner": "agent", "why": f"hotfix {i} ahead of the sprint order ({s[1]})"}

    # 1. development: continue the most advanced story of the current sprint (one at a time)
    if current:
        for stg in ("close", "review", "execute", "run-strategy", "quick", "brief-spec", "spike"):
            for i in current["ids"]:
                if i in states and states[i][0] == stg and deps_done(i) and mine(i):
                    return {**base, "step": stg, "ids": [i], "owner": "agent",
                            "why": f"{current['sprint']}: {i} is in '{stg}' ({states[i][1]}); dependencies closed"}
    # 2. analysis: missing Analysis of the current + next sprint (look-ahead)
    pool = (current["ids"] if current else []) + (nxt["ids"] if nxt else [])
    missing = [i for i in pool if i in states and states[i][0] == "analysis" and mine(i)]
    if missing:
        return {**base, "step": "analysis", "ids": missing[:4], "owner": "agent",
                "why": f"Analysis missing for {current['sprint'] if current else ''}{' and ' + nxt['sprint'] if nxt else ''}"
                       + (f" ({len(missing)} total, max 4 per session)" if len(missing) > 4 else "")}
    # 3. Refined Story to complete
    r = [i for i in pool if i in states and states[i][0] == "refine" and mine(i)]
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
    """The latest weekly (date in the file name, README excluded) is 7 or more days old, or there is none yet."""
    dates = [m.group(1) for p in wf.matches("project-journal/weekly/*.md")
             if (m := re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(p)))]
    if not dates:
        return wf.project().get("project", {}).get("initialized", False)
    try:
        return (dt.date.today() - dt.date.fromisoformat(max(dates))).days >= 7
    except ValueError:  # 2026-13-45
        return True


def step_info(step: str) -> dict:
    return wf.workflow().get("steps", {}).get(step, {})


DEEP_SIZES = ("L", "XL")


def deep(step: str, ids: list[str]) -> bool:
    """L/XL stories run the step's deep_command (deep tier) when it declares one."""
    st = wf.stories()
    return bool(step_info(step).get("deep_command")) and any(st.get(i, {}).get("size") in DEEP_SIZES for i in ids)


def commands_for(step: str, ids: list[str]) -> dict[str, str]:
    """The command per enabled tool: Codex invokes the generated skills as `$name`, the others as `/name`."""
    cmd = command_for(step, ids)
    return {t: ("$" + cmd[1:] if t == "codex" and cmd.startswith("/") else cmd) for t in wf.enabled_tools()}


def command_for(step: str, ids: list[str]) -> str:
    s = step_info(step)
    if step == "done":
        return "nothing: the story is finished"
    if not s:  # per-story human stages (blocked, stopped) are explained in the human-gate table
        return "human action (see workflow/steps/human-gate.md)"
    if s.get("owner") == "human" or not s.get("command"):
        return "human action (see workflow/steps/%s.md)" % step
    return f"/{s['deep_command'] if deep(step, ids) else s['command']}" + (" " + " ".join(ids) if ids else "")


def main() -> None:
    argv = sys.argv[1:]
    if "--me" in argv[:-1]:
        k = argv.index("--me")
        argv = argv[:k] + argv[k + 2:]
    args = [a for a in argv if not a.startswith("--")]
    try:
        run(args, "--json" in sys.argv)
    except (OSError, ValueError) as e:  # unreadable or malformed files (tomllib errors are ValueErrors naming the file)
        if "--json" not in sys.argv:
            raise
        wf.fail_envelope("next-story" if args else "next", "bad_input", str(e))


def run(args: list[str], as_json: bool) -> None:
    if args:
        i = wf.norm_id(args[0])
        st = wf.stories()
        if i not in st:
            if as_json:
                wf.fail_envelope("next-story", "unknown_id", f"Unknown ID: {i}")
            sys.exit(f"Unknown ID: {i}")
        stg, det, own = stage(i)
        res = {"step": stg, "ids": [i], "why": det, "owner": own, "deps": st[i].get("deps", []), "deps_done": deps_done(i)}
        if as_json:
            wf.dump_envelope("next-story", res)
        else:
            print(f"{i} — {st[i].get('title', '')}\n  stage: {stg} ({own}) · {det}\n"
                  f"  dependencies: {', '.join(res['deps']) or '—'} (closed: {res['deps_done']})\n  next: {command_for(stg, [i])}")
        return

    rec = inception()
    phase = "inception" if rec else "delivery"
    me = sys.argv[sys.argv.index("--me") + 1] if "--me" in sys.argv[:-1] else None
    if not rec:
        rec = recommend(wf.sprints(), me)
        if me:
            rec["me"] = me
            rec["claimable"] = claimable(wf.sprints(), me)
    rec["phase"] = phase
    rec["weekly_due"] = weekly_due()
    rec["stale_branches"] = wf.stale_branches()
    rec["pending"] = [{"id": os.path.basename(p)[4:].split(".")[0], "action": a} for p in wf.matches("delivery/30-runs/RUN-*.md")
                      for a in wf.pending_actions(wf.read(p))]
    info = step_info(rec["step"])
    rec["tier"] = "deep" if deep(rec["step"], rec["ids"]) else info.get("tier")
    rec["models"] = {k: wf.model_for(k, rec["tier"]) for k in wf.enabled_tools()} if rec["tier"] else {}
    rec["command"] = command_for(rec["step"], rec["ids"])
    rec["commands"] = commands_for(rec["step"], rec["ids"])

    if as_json:
        out = {k: v for k, v in rec.items() if k not in ("states", "current", "next_sprint", "human_gates")}
        out["current_sprint"] = rec["current"]["sprint"] if rec.get("current") else None
        out["next_sprint"] = rec["next_sprint"]["sprint"] if rec.get("next_sprint") else None
        out["human_gates"] = [{"id": i, "stage": s[0], "detail": s[1]} for i, s in rec.get("human_gates", [])]
        if phase == "delivery":  # every story of the backlog, for boards and dashboards
            cl = wf.claims()
            out["stories"] = [{"id": i, "stage": g[0], "detail": g[1], "owner": g[2], "claimed_by": cl.get(i, {}).get("by")}
                              for i in wf.stories() for g in [stage(i)]]
        wf.dump_envelope("next", out)
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
    codex = rec["commands"].get("codex")
    print(f"  Run: {rec['command']}" + (" (fresh session)" if info.get("owner") == "agent" else "")
          + (f" · Codex: {codex}" if codex and codex != rec["command"] else ""))
    if rec.get("tier"):
        print(f"  Tier: {rec['tier']} → {wf.tier_line(rec['tier'])}")
        if info.get("deep_when") and rec["tier"] != "deep":
            print(f"  Deep tier when: {info['deep_when']}")
    if rec.get("me"):
        cl = wf.claims()
        print(f"  Claimable for {rec['me']}: " + (", ".join(f"{i}{' (yours)' if i in cl else ''}" for i in rec["claimable"]) or "none")
              + (f" — claim one: make claim ID={rec['claimable'][0]}" if rec["claimable"] else ""))
    if rec.get("optional"):
        print(f"  In parallel (analysis ahead): /analysis {' '.join(rec['optional']['ids'])}")
    print(f"  Step file: workflow/steps/{rec['step']}.md")
    if rec["pending"]:
        print("\nPending owner actions (RUN `## Pending owner actions`):")
        for x in rec["pending"]:
            print(f"  {x['id']}: {x['action']}")
    if stale := wf.stale_branches():
        print("\nStale branches (trunk-based development: merge within days, or split / drop):")
        for b in stale:
            print(f"  {b['branch']}: {b['commits']} commit(s) not in main, {b['days']} days old")
    if rec["weekly_due"]:
        print("\n(reminder) The weekly journal is older than 7 days: /weekly")


if __name__ == "__main__":
    main()
