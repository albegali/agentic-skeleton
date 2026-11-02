"""Human gates as data: which change of a file passes a gate, which command may pass it, and how to apply an approval.

Used by tools/gate_guard.py (agent hook: blocks agent edits that pass a gate), tools/approve.py (`make approve`, run by
the human) and tools/check_workflow.py --git (the strategy approval is committed before any code).

Also a contract CLI for portals (contract 1.1), run by the human or through a portal acting for the owner:
  python3 tools/gates.py list --json
  python3 tools/gates.py approve <gate-id> [--expect <current>] [--by <owner>] [--no-commit]
  python3 tools/gates.py request-changes <gate-id> --comment <text> [--expect <current>] [--by <owner>]
A gate id is `<gate>:<artifact path>` as listed. Agents never run `approve` / `request-changes` (gate_guard blocks them).
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import os
import re
import subprocess
import sys
import tomllib

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

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


_EOL: dict[str, str] = {}


def _read(p: str) -> str:
    """Text with `\n` line ends; the original line ending of the file is remembered for _write."""
    with open(wf.path(p), encoding="utf-8", newline="") as f:
        raw = f.read()
    _EOL[p] = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n")


def _write(p: str, text: str) -> None:
    """Atomic (temp file + replace), keeping the file's line ending and mode."""
    full = wf.path(p)
    data = text.replace("\n", _EOL.get(p, "\n")) if _EOL.get(p) == "\r\n" else text
    tmp = f"{full}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        if os.path.exists(full):
            os.chmod(tmp, os.stat(full).st_mode & 0o7777)
        os.replace(tmp, full)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def approve(gate: str, ident: str | None, file: str | None, who: str, when: str, before: dict | None = None) -> list[str]:
    """Apply the approval; return the paths changed. Raises ValueError when the gate cannot be applied.
    `before` (optional) receives the original text of every changed file (for diffs)."""
    def one(pat: str) -> str:
        hit = wf.matches(pat)
        if not hit:
            raise ValueError(f"not found: {pat}")
        return wf.rel(hit[0])

    changed: dict[str, str] = {}
    if gate == "strategy":
        run, spec = one(f"delivery/30-runs/RUN-{ident}*.md"), one(f"delivery/20-specs/SPEC-{ident}-*.md")
        t = _read(run)
        if not wf.strategy_written(t):
            raise ValueError(f"{run}: no execution strategy to approve yet (§1 Plan)")
        sec = wf.heading_section(t, r"^#\s+2\.") or ""
        if not re.search(r"^\s*-\s*\[[ xX]\]\s*Approved\b", sec, re.M):
            raise ValueError(f"{run}: §2 has no `- [ ] Approved` line")
        new = re.sub(r"^(\s*-\s*)\[ \](\s*Approved\b)", r"\1[x]\2", sec, count=1, flags=re.M)
        new = re.sub(r"^(Reviewer:)[ \t]*$", lambda m: f"{m.group(1)} {who}", new, count=1, flags=re.M)
        new = re.sub(r"^(Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", new, count=1, flags=re.M)
        changed[run] = set_md_status(t.replace(sec, new, 1), "Strategy Approved")
        st = _read(spec)
        changed[spec] = set_md_status(st, "In Progress")
    elif gate == "spec":
        spec = one(f"delivery/20-specs/SPEC-{ident}-*.md")
        changed[spec] = set_md_status(_read(spec), "Ready")
    elif gate == "tuning":
        run = one(f"delivery/30-runs/RUN-{ident}*.md")
        t = _read(run)
        if "Tuning accepted by:" not in t:
            t = t.replace("# 5. Tuning Log", "# 5. Tuning Log\n\nTuning accepted by:\nDate:", 1)
        sec = wf.heading_section(t, r"^#\s+5\.") or ""
        new = re.sub(r"^(Tuning accepted by:)[ \t]*$", lambda m: f"{m.group(1)} {who}", sec, count=1, flags=re.M)
        new = re.sub(r"^(Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", new, count=1, flags=re.M)
        changed[run] = t.replace(sec, new, 1)
    elif gate.startswith("deviation:"):
        n = gate.split(":", 1)[1]
        run = one(f"delivery/30-runs/RUN-{ident}*.md")
        t = _read(run)
        m = re.search(rf"^###\s+Deviation\s+#{re.escape(n)}\b.*?(?=^#{{1,3}}\s|\Z)", t, re.M | re.S)
        if not m:
            raise ValueError(f"{run}: no `### Deviation #{n}`")
        body = re.sub(r"^(\s*-\s*Approved by:)[ \t]*$", lambda m: f"{m.group(1)} {who}", m.group(0), count=1, flags=re.M)
        body = re.sub(r"^(\s*-\s*Date:)[ \t]*$", lambda m: f"{m.group(1)} {when}", body, count=1, flags=re.M)
        changed[run] = t.replace(m.group(0), body, 1)
    elif gate == "spike":
        note = one(f"delivery/40-spikes/SPIKE-{ident}-*.md")
        changed[note] = set_md_status(_read(note), "Accepted")
    elif gate == "refined":
        ref = one(f"analysis/30-refined/REFINED_{ident}_*.md")
        changed[ref] = set_front_status(_read(ref), "approved")
    elif gate == "inception":
        if not file or not (file in INCEPTION or ADR_RX.match(file)) or not wf.exists(file):
            raise ValueError(f"FILE must be an existing inception artifact or ADR: {', '.join(INCEPTION)}, reference/architecture/ADR-*.md")
        t = _read(file)
        if file.endswith(".toml"):
            changed[file] = re.sub(r'^status\s*=\s*"[^"]*"', 'status = "approved"', t, count=1, flags=re.M)
        else:
            changed[file] = set_front_status(t, "accepted" if ADR_RX.match(file) else "approved")
    elif gate == "stack":
        t = _read("project.toml")
        changed["project.toml"] = re.sub(r"^(decided\s*=\s*)false\b", r"\1true", t, count=1, flags=re.M)
    else:
        raise ValueError(f"unknown gate {gate!r}: spec | strategy | tuning | deviation:<n> | spike | refined | inception | stack")
    out = []
    for p, text in changed.items():
        old = _read(p)
        if text != old:
            if before is not None:
                before[p] = old
            _write(p, text)
            out.append(p)
    if not out:
        raise ValueError("nothing to approve: the gate is already passed")
    return out


# ---------------------------------------------------------------- committing an approval

def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8")


def in_git() -> bool:
    try:
        return git("rev-parse", "--is-inside-work-tree").returncode == 0
    except OSError:
        return False


def commit_paths(subject: str, trailers: list[str], paths: list[str]) -> str:
    """Commit only `paths` with the trailers; return the short hash. Raises RuntimeError with git's output on failure."""
    git("add", "--", *paths)  # an artifact not yet tracked (a fresh Spec) is committed with its approval
    r = git("commit", "-m", subject, "-m", "\n".join(trailers), "--", *paths)
    if r.returncode != 0:
        raise RuntimeError(f"{r.stdout}{r.stderr}")
    return git("log", "-1", "--format=%h").stdout.strip()


# ---------------------------------------------------------------- pending gates as data (contract 1.1)

REQUEST_GATES = ("spec", "strategy", "inception", "stack", "spike", "refined")  # request-changes is defined for these
GATE_NAMES = ("spec", "strategy", "tuning", "spike", "refined", "inception", "stack", "workshop")


class GateError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _item(gate: str, artifact: str, field: str, current: str, proposed: str, story: str | None = None) -> dict:
    d = {"gate": gate, "artifact": artifact, "field": field, "current": current, "proposed": proposed}
    if story:
        d["story_id"] = story
    return d


def _since(path: str) -> dt.datetime:
    """Last commit that touched the artifact; the file's mtime when there is no git or no commit yet."""
    try:
        out = git("log", "-1", "--format=%cI", "--", path).stdout.strip()
        if out:
            return dt.datetime.fromisoformat(out)
    except (OSError, ValueError):
        pass
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(wf.path(path))).astimezone()
    except OSError:
        return dt.datetime.now().astimezone()


def pending() -> list[dict]:
    """Every pending human gate: {id, gate, artifact, field, current, proposed, story_id?, since, age_days}.
    One detection with `next_step.py` (its `inception()` and `recommend()` human stages), plus the Refined Story approval."""
    import next_step as ns
    items: list[dict] = []
    rec = ns.inception()
    if rec:
        for f in rec.get("files", []) if rec["step"] == "approve" else []:
            if f.startswith("project.toml"):
                items.append(_item("stack", "project.toml", "[stack] decided", "false", "true"))
            else:
                adr = bool(ADR_RX.match(f))
                items.append(_item("inception", f, "status", wf.artifact_status(f) or ("proposed" if adr else "draft"),
                                   "accepted" if adr else "approved"))
    else:
        for i, (stg, detail, _owner) in ns.recommend(wf.sprints())["human_gates"]:
            run, spec = wf.find("run", i), wf.find("spec", i)
            if stg == "run-approval" and run:
                items.append(_item("strategy", wf.rel(run), "status", wf.md_status(wf.read(run)) or "Draft", "Strategy Approved", i))
            elif stg == "spec-approval" and spec:
                items.append(_item("spec", wf.rel(spec), "status", wf.md_status(wf.read(spec)) or "Draft", "Ready", i))
            elif stg == "blocked" and run:
                for n in wf.open_deviations(wf.read(run)):
                    items.append(_item(f"deviation:{n}", wf.rel(run), f"§6 Deviation #{n} Approved by", "open", "approved", i))
            elif stg == "tuning" and run and detail.startswith("human verification"):
                items.append(_item("tuning", wf.rel(run), "Tuning accepted by", "pending", "accepted", i))
            elif stg == "spike-review" and (note := wf.one(wf.SPIKE.format(i=i))):
                items.append(_item("spike", wf.rel(note), "status", wf.md_status(wf.read(note)) or "Draft", "Accepted", i))
            elif stg == "workshop" and (art := wf.find("refined", i) or wf.find("analysis", i)):
                items.append(_item("workshop", wf.rel(art), "status", wf.front(wf.read(art), "status") or "draft", "refined", i))
        for i in wf.stories():  # a Refined Story waiting for its approval (the Brief may already start from `refined`)
            ref = wf.find("refined", i)
            if ref and not wf.find("brief", i) and not wf.find("spec", i) and not wf.find("run", i):
                cur = wf.status("refined", wf.front(wf.read(ref), "status") or "draft")
                if cur == "refined" and not ns.refined_not_ready(wf.read(ref)):
                    items.append(_item("refined", wf.rel(ref), "status", cur, "approved", i))
    now = dt.datetime.now().astimezone()
    for it in items:
        it["id"] = f"{it['gate']}:{it['artifact']}"
        since = _since(it["artifact"])
        it["since"] = since.isoformat(timespec="seconds")
        it["age_days"] = max(0, (now - since).days)
    return items


def _artifact_ok(gate: str, path: str) -> bool:
    if gate in ("strategy", "tuning") or gate.startswith("deviation:"):
        return bool(RUN_RX.match(path))
    return bool({"spec": lambda: SPEC_RX.match(path), "spike": lambda: SPIKE_RX.match(path), "refined": lambda: REFINED_RX.match(path),
                 "inception": lambda: path in INCEPTION or ADR_RX.match(path), "stack": lambda: path == "project.toml",
                 "workshop": lambda: re.match(r"^analysis/(20-analysis|30-refined)/[^/]+\.md$", path)}.get(gate, lambda: None)())


def resolve(gate_id: str) -> dict:
    """The pending gate with this id; GateError unknown_gate / stale_gate otherwise (nothing outside `list` is ever acted on)."""
    m = re.match(r"^(deviation:\d+|[a-z]+):(.+)$", gate_id or "")
    if not m or not (m.group(1) in GATE_NAMES or m.group(1).startswith("deviation:")) or ".." in m.group(2).split("/") \
            or os.path.isabs(m.group(2)) or "\\" in m.group(2) or not _artifact_ok(*m.groups()):
        raise GateError("unknown_gate", f"unknown gate id {gate_id!r}: take one from `gates.py list --json`")
    for it in pending():
        if it["id"] == gate_id:
            return it
    if not wf.exists(m.group(2)):
        raise GateError("unknown_gate", f"{gate_id}: no such artifact")
    raise GateError("stale_gate", f"{gate_id} is not pending any more (already resolved or changed): list the gates again")


# ---------------------------------------------------------------- request changes

GATES_LINE = "{when} — changes requested by {who}: {comment}"


def _add_gates_line(text: str, path: str, line: str) -> str:
    """One line under `## Gates` (markdown, section created at the end when missing) or in the trailing `# Gates` comment block (TOML)."""
    if path.endswith(".toml"):
        lines = text.split("\n")
        if "# Gates" in lines:
            k = lines.index("# Gates") + 1
            while k < len(lines) and lines[k].startswith("# "):
                k += 1
            lines.insert(k, f"# {line}")
            return "\n".join(lines)
        return text.rstrip("\n") + f"\n\n# Gates\n# {line}\n"
    m = re.search(r"^## Gates[ \t]*$", text, re.M)
    if not m:
        return text.rstrip("\n") + f"\n\n---\n\n## Gates\n\n- {line}\n"
    nxt = re.search(r"^#{1,2}\s", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    body = text[m.end():end].rstrip("\n")
    tail = text[end:]
    return text[:m.end()] + body + f"\n- {line}\n" + ("\n" + tail if tail else "")


def request_changes(gate: str, file: str, who: str, when: str, comment: str, before: dict | None = None) -> list[str]:
    """Put the gate's field at its draft value (never an approval value) and record the comment; return the paths changed."""
    text = _read(file)
    if gate in ("spec", "spike"):
        new = set_md_status(text, "Draft")
    elif gate == "refined":
        new = set_front_status(text, "draft")
    elif gate == "inception":
        if file.endswith(".toml"):
            new = re.sub(r'^status\s*=\s*"[^"]*"', 'status = "draft"', text, count=1, flags=re.M)
        else:
            new = set_front_status(text, "proposed" if ADR_RX.match(file) else "draft")
    elif gate == "stack":
        new = re.sub(r"^(decided\s*=\s*)true\b", r"\1false", text, count=1, flags=re.M)
    elif gate == "strategy":
        sec = wf.heading_section(text, r"^#\s+2\.") or ""
        s2 = re.sub(r"^(\s*-\s*)\[[xX]\](\s*Approved\b)", r"\1[ ]\2", sec, count=1, flags=re.M)
        s2 = re.sub(r"^(\s*-\s*)\[ \](\s*Revisions requested\b)", r"\1[x]\2", s2, count=1, flags=re.M)
        new = set_md_status(text.replace(sec, s2, 1) if sec else text, "Draft")
    else:
        raise GateError("invalid_transition", f"request-changes is not available for {gate} gates")
    new = _add_gates_line(new, file, GATES_LINE.format(when=when, who=who, comment=comment))
    _write(file, new)
    if before is not None:
        before[file] = text
    return [file]


def diff_of(before: dict[str, str]) -> str:
    out: list[str] = []
    for p, old in before.items():
        out += difflib.unified_diff(old.splitlines(), _read(p).splitlines(), f"a/{p}", f"b/{p}", lineterm="")
    return "\n".join(out)


# ---------------------------------------------------------------- CLI

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # usage errors are envelopes too
        wf.fail_envelope("gates", "usage", message, 2)


def _owner(by: str | None) -> str:
    owner = str(wf.project().get("project", {}).get("owner", "") or "").strip()
    if not owner:
        raise GateError("no_owner", "project.toml [project] owner is empty: the approver is the project owner")
    if by is not None and by.strip() != owner:
        raise GateError("bad_input", f"--by {by!r} is not the project owner ({owner!r})")
    return owner


def _act(a: argparse.Namespace) -> dict:
    owner = _owner(a.by)
    comment = " ".join((getattr(a, "comment", None) or "").split())
    if a.cmd == "request-changes" and not comment:
        raise GateError("comment_required", "request-changes needs --comment <text>")
    it = resolve(a.gate_id)
    if a.expect is not None and a.expect != it["current"]:
        raise GateError("stale_gate", f"{it['id']}: current value is {it['current']!r}, not {a.expect!r}")
    gate, ident, path = it["gate"], it.get("story_id"), it["artifact"]
    if gate == "workshop" or (a.cmd == "request-changes" and gate not in REQUEST_GATES):
        raise GateError("invalid_transition", f"{a.cmd} is not available for {gate} gates")
    now = dt.datetime.now().astimezone()
    before: dict[str, str] = {}
    try:
        if a.cmd == "approve":
            changed = approve(gate, ident, path if gate == "inception" else None, owner, now.date().isoformat(), before)
        else:
            changed = request_changes(gate, path, owner, now.date().isoformat(), comment, before)
    except ValueError as e:
        raise GateError("stale_gate", str(e)) from None
    out = {"id": it["id"], "gate": gate, "changed": changed, "diff": diff_of(before), "commit": None,
           "by": owner, "at": now.isoformat(timespec="seconds")}
    if a.cmd == "approve" and not a.no_commit and in_git():
        label = path if gate == "inception" else ident or "stack"
        try:
            out["commit"] = commit_paths(f"approve({gate}): {label}", [f"Approved-by: {owner}", f"Approved-at: {out['at']}"], changed)
        except RuntimeError as e:
            raise GateError("bad_input", f"field set, commit failed (commit it yourself with the trailers):\n{e}") from None
    if a.cmd == "request-changes":
        out["comment"] = comment
    return out


def main(argv: list[str] | None = None) -> None:
    ap = _Parser(prog="gates.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    ls = sub.add_parser("list", help="pending human gates")
    ls.add_argument("--json", action="store_true")
    for name in ("approve", "request-changes"):
        p = sub.add_parser(name)
        p.add_argument("gate_id")
        p.add_argument("--expect", default=None, help="the `current` value from list; refused when it changed")
        p.add_argument("--by", default=None, help="accepted only if equal to the project.toml owner")
        if name == "approve":
            p.add_argument("--no-commit", action="store_true")
        else:
            p.add_argument("--comment", default=None)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "list":
            items = pending()
            if a.json:
                wf.dump_envelope("gates", {"gates": items})
            else:
                for it in items:
                    print(f"{it['id']}  {it['field']}: {it['current']} → {it['proposed']}  ({it['age_days']}d)")
                if not items:
                    print("No pending human gates.")
            return
        wf.dump_envelope("gates", _act(a))
    except GateError as e:
        wf.fail_envelope("gates", e.code, e.message)


if __name__ == "__main__":
    main()
