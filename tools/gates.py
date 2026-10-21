"""Human gates as data: which change of a file passes a gate, which command may pass it, and how to apply an approval.

Used by tools/gate_guard.py (agent hook: blocks agent edits that pass a gate), tools/approve.py (`make approve`, run by
the human) and tools/check_workflow.py --git (the strategy approval is committed before any code).
"""
from __future__ import annotations

import os
import re
import tomllib

import wf

RUN_RX = re.compile(r"^delivery/30-runs/RUN-([A-Za-z]+[0-9]{4})[a-z0-9-]*\.md$")
SPEC_RX = re.compile(r"^delivery/20-specs/SPEC-([A-Za-z]+[0-9]{4})-[a-z0-9-]+\.md$")
SPIKE_RX = re.compile(r"^delivery/40-spikes/SPIKE-([A-Za-z]+[0-9]{4})-[a-z0-9-]+\.md$")
REFINED_RX = re.compile(r"^analysis/30-refined/REFINED_([A-Za-z]+[0-9]{4})_[a-z0-9_]+\.md$")
ADR_RX = re.compile(r"^reference/architecture/ADR-\d{3}-[a-z0-9-]+\.md$")
INCEPTION = ("reference/product/functional-requirements.md", "reference/product/non-functional-requirements.md",
             "reference/product/vision.md", "reference/product/mockup-reference.md", "reference/architecture/architecture.md",
             "backlog/stories.toml", "PLAN.md")
# the artifacts of the workflow; anything else in the repository is code (for the approval-before-code rule)
WORKFLOW_PATHS = ("analysis/", "delivery/", "reference/", "backlog/", "project-journal/", "PLAN.md", "project.toml", "models.toml")


def tuning_accepted(text: str) -> bool:
    m = re.search(r"^Tuning accepted by:[ \t]*(\S.*)$", text, re.M)
    return bool(m)


def approved_deviations(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"^###\s+Deviation\s+#(\d+)\b(.*?)(?=^#{1,3}\s|\Z)", wf.heading_section(text, r"^#\s+6\.") or "", re.M | re.S):
        if re.search(r"^\s*-\s*Approved by:[ \t]*\S", m.group(2), re.M):
            out.add(m.group(1))
    return out


def _inception_status(p: str, text: str) -> str | None:
    if p.endswith(".toml"):
        try:
            return tomllib.loads(text).get("status")
        except tomllib.TOMLDecodeError:
            return None
    v = wf.front(text, "status")
    return v.split("|")[0].strip().lower() if v else None


def _decided(text: str) -> bool:
    try:
        return bool(tomllib.loads(text).get("stack", {}).get("decided"))
    except tomllib.TOMLDecodeError:
        return False


def passed(p: str, before: str, after: str) -> list[dict]:
    """Gates that the change before → after of repository path p passes: [{gate, id, file}]."""
    p = p.replace(os.sep, "/")
    out: list[dict] = []

    def add(gate: str, ident: str | None = None) -> None:
        out.append({"gate": gate, "id": ident, "file": p})

    if m := RUN_RX.match(p):
        i = m.group(1)
        if wf.run_approved(after) and not wf.run_approved(before):
            add("strategy", i)
        for n in sorted(approved_deviations(after) - approved_deviations(before)):
            add(f"deviation:{n}", i)
        if tuning_accepted(after) and not tuning_accepted(before):
            add("tuning", i)
    elif m := SPEC_RX.match(p):
        old, new = wf.status("spec", wf.md_status(before)), wf.status("spec", wf.md_status(after))
        if new in ("Ready", "In Progress", "Done") and old in (None, "Draft", "Blocked", "Cancelled"):
            add("spec", m.group(1))
    elif m := SPIKE_RX.match(p):
        if wf.status("spike", wf.md_status(after)) == "Accepted" and wf.status("spike", wf.md_status(before)) != "Accepted":
            add("spike", m.group(1))
    elif m := REFINED_RX.match(p):
        if wf.status("refined", wf.front(after, "status")) == "approved" and wf.status("refined", wf.front(before, "status")) != "approved":
            add("refined", m.group(1))
    elif p in INCEPTION or ADR_RX.match(p):
        ok = ("approved", "accepted")
        if _inception_status(p, after) in ok and _inception_status(p, before) not in ok:
            add("inception")
    elif p == "project.toml":
        if _decided(after) and not _decided(before):
            add("stack")
    return out


# The explicit gate commands a human types: the agent may then record that gate (and only that one).
def allowed_by(g: dict, command: str | None, args: str) -> bool:
    if not command:
        return False
    words = args.split()
    ident = words[0].upper() if words else ""
    if g["id"] and wf.norm_id(ident) != g["id"]:
        return False
    rest = words[1:]
    if g["gate"] in ("strategy", "spec") and command in ("run", "run-deep"):
        return rest[:1] == ["approve"]  # quick track: one approval covers Spec and strategy
    if g["gate"].startswith("deviation:") and command in ("run", "run-deep"):
        return rest[:2] == ["approve-deviation", g["gate"].split(":")[1]]
    if g["gate"] == "tuning":
        return command == "persist"
    return False


def hint(g: dict) -> str:
    """What the human runs to pass the gate."""
    if g["gate"] == "inception":
        return f"make approve GATE=inception FILE={g['file']}"
    if g["gate"] == "stack":
        return "make approve GATE=stack"
    cmd = {"strategy": f" (or type `/run {g['id']} approve`)", "tuning": f" (or type `/persist {g['id']}`)",
           "spec": f" (quick track: type `/run {g['id']} approve`)"}.get(g["gate"], "")
    if g["gate"].startswith("deviation:"):
        cmd = f" (or type `/run {g['id']} approve-deviation {g['gate'].split(':')[1]}`)"
    return f"make approve ID={g['id']} GATE={g['gate']}{cmd}"


# ---------------------------------------------------------------- applying an approval (make approve)

def set_md_status(text: str, value: str) -> str:
    return re.sub(r"(^## Status\s*\n+)[^\n]+", lambda m: m.group(1) + value, text, count=1, flags=re.M)


def set_front_status(text: str, value: str) -> str:
    fm = wf.frontmatter(text)
    if not fm:
        return f"---\nstatus: {value}\n---\n" + text
    new = re.sub(r"^status:[^\n]*", f"status: {value}", fm, count=1, flags=re.M) if re.search(r"^status:", fm, re.M) else fm.rstrip("\n") + f"\nstatus: {value}\n"
    return text.replace(fm, new, 1)


def set_field(text: str, label: str, value: str, section_rx: str | None = None) -> str:
    """Fill `label:` (optionally `- label:`) in the given section, or the first one in the file."""
    sec = wf.heading_section(text, section_rx) if section_rx else None
    scope = sec if sec is not None else text
    new = re.sub(rf"^(\s*-?\s*{re.escape(label)}:)[ \t]*$", lambda m: f"{m.group(1)} {value}", scope, count=1, flags=re.M)
    return text.replace(scope, new, 1) if sec is not None else new


def approve(gate: str, ident: str | None, file: str | None, who: str, when: str) -> list[str]:
    """Apply the approval; return the paths changed. Raises ValueError when the gate cannot be applied."""
    def one(pat: str) -> str:
        hit = wf.matches(pat)
        if not hit:
            raise ValueError(f"not found: {pat}")
        return wf.rel(hit[0])

    changed: dict[str, str] = {}
    if gate == "strategy":
        run, spec = one(f"delivery/30-runs/RUN-{ident}*.md"), one(f"delivery/20-specs/SPEC-{ident}-*.md")
        t = wf.read(run)
        if not wf.strategy_written(t):
            raise ValueError(f"{run}: no execution strategy to approve yet (§1 Plan)")
        sec = wf.heading_section(t, r"^#\s+2\.") or ""
        if not re.search(r"^\s*-\s*\[[ xX]\]\s*Approved\b", sec, re.M):
            raise ValueError(f"{run}: §2 has no `- [ ] Approved` line")
        new = re.sub(r"^(\s*-\s*)\[ \](\s*Approved\b)", r"\1[x]\2", sec, count=1, flags=re.M)
        new = re.sub(r"^(Reviewer:)[ \t]*$", lambda m: f"{m.group(1)} {who}", new, count=1, flags=re.M)
        new = re.sub(r"^(Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", new, count=1, flags=re.M)
        changed[run] = set_md_status(t.replace(sec, new, 1), "Strategy Approved")
        st = wf.read(spec)
        changed[spec] = set_md_status(st, "In Progress")
    elif gate == "spec":
        spec = one(f"delivery/20-specs/SPEC-{ident}-*.md")
        changed[spec] = set_md_status(wf.read(spec), "Ready")
    elif gate == "tuning":
        run = one(f"delivery/30-runs/RUN-{ident}*.md")
        t = wf.read(run)
        if "Tuning accepted by:" not in t:
            t = t.replace("# 5. Tuning Log", "# 5. Tuning Log\n\nTuning accepted by:\nDate:", 1)
        sec = wf.heading_section(t, r"^#\s+5\.") or ""
        new = re.sub(r"^(Tuning accepted by:)[ \t]*$", lambda m: f"{m.group(1)} {who}", sec, count=1, flags=re.M)
        new = re.sub(r"^(Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", new, count=1, flags=re.M)
        changed[run] = t.replace(sec, new, 1)
    elif gate.startswith("deviation:"):
        n = gate.split(":", 1)[1]
        run = one(f"delivery/30-runs/RUN-{ident}*.md")
        t = wf.read(run)
        m = re.search(rf"^###\s+Deviation\s+#{re.escape(n)}\b.*?(?=^#{{1,3}}\s|\Z)", t, re.M | re.S)
        if not m:
            raise ValueError(f"{run}: no `### Deviation #{n}`")
        body = re.sub(r"^(\s*-\s*Approved by:)[ \t]*$", lambda m: f"{m.group(1)} {who}", m.group(0), count=1, flags=re.M)
        body = re.sub(r"^(\s*-\s*Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", body, count=1, flags=re.M)
        changed[run] = t.replace(m.group(0), body, 1)
    elif gate == "spike":
        note = one(f"delivery/40-spikes/SPIKE-{ident}-*.md")
        changed[note] = set_md_status(wf.read(note), "Accepted")
    elif gate == "refined":
        ref = one(f"analysis/30-refined/REFINED_{ident}_*.md")
        changed[ref] = set_front_status(wf.read(ref), "approved")
    elif gate == "inception":
        if not file or not (file in INCEPTION or ADR_RX.match(file)) or not wf.exists(file):
            raise ValueError(f"FILE must be an existing inception artifact or ADR: {', '.join(INCEPTION)}, reference/architecture/ADR-*.md")
        t = wf.read(file)
        if file.endswith(".toml"):
            changed[file] = re.sub(r'^status\s*=\s*"[^"]*"', 'status = "approved"', t, count=1, flags=re.M)
        else:
            changed[file] = set_front_status(t, "accepted" if ADR_RX.match(file) else "approved")
    elif gate == "stack":
        t = wf.read("project.toml")
        changed["project.toml"] = re.sub(r"^(decided\s*=\s*)false\b", r"\1true", t, count=1, flags=re.M)
    else:
        raise ValueError(f"unknown gate {gate!r}: spec | strategy | tuning | deviation:<n> | spike | refined | inception | stack")
    out = []
    for p, text in changed.items():
        if text != wf.read(p):
            wf.write(p, text)
            out.append(p)
    if not out:
        raise ValueError("nothing to approve: the gate is already passed")
    return out
