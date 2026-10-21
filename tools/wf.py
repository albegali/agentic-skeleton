"""Shared helpers for the workflow tools (stdlib only, Python >= 3.11).

The repository root is the parent of tools/, or $WF_ROOT when set (used by the tests).
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys
import tomllib
from functools import lru_cache

ROOT = os.path.abspath(os.environ.get("WF_ROOT") or os.path.join(os.path.dirname(__file__), ".."))
TIERS = ("fast", "balanced", "deep")
SCHEMA = 1  # legacy flat --json of context.py (outside the contract)
CONTRACT_VERSION = "1.0"  # semver of the --json envelope (tools/README.md "JSON contract"): minor adds fields, major breaks

for _s in (sys.stdout, sys.stderr):  # the text views print → ≈ ⚠ ✓: a cp1252 console or pipe (Windows) must not crash
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


def path(*p: str) -> str:
    return os.path.join(ROOT, *p)


def rel(p: str) -> str:
    """Path relative to the root, always with `/` (JSON contract and comparisons are OS-independent)."""
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def read(p: str) -> str:
    with open(p if os.path.isabs(p) else path(p), encoding="utf-8") as f:
        return f.read()


def write(p: str, text: str) -> None:
    full = p if os.path.isabs(p) else path(p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def exists(p: str) -> bool:
    return os.path.exists(path(p))


def matches(pattern: str) -> list[str]:
    return sorted(glob.glob(path(pattern), recursive=True))


def one(pattern: str) -> str | None:
    m = matches(pattern)
    return m[0] if m else None


def dump_json(obj: dict) -> None:
    """Print a --json result: {"schema": SCHEMA, **obj}, compact (machines read it, agents read fewer tokens)."""
    print(json.dumps({"schema": SCHEMA, **obj}, ensure_ascii=False, separators=(",", ":")))


def skeleton_version() -> str:
    return read("tools/VERSION").strip() if exists("tools/VERSION") else "unknown"  # not the root VERSION: apps own that one


def dump_envelope(tool: str, data: dict) -> None:
    """Print a contract --json result: {"contract", "tool", "data"}, compact."""
    print(json.dumps({"contract": CONTRACT_VERSION, "tool": tool, "data": data}, ensure_ascii=False, separators=(",", ":")))


def fail_envelope(tool: str, code: str, message: str, exit_code: int = 1) -> None:
    """Print the error envelope {"contract", "tool", "error": {"code", "message"}} (no data) and exit non-zero."""
    print(json.dumps({"contract": CONTRACT_VERSION, "tool": tool, "error": {"code": code, "message": message}},
                     ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(exit_code)


def approx_tokens(chars: int) -> int:
    """Rough token estimate (≈ 4 characters per token) for context budgets."""
    return (chars + 3) // 4


def load_toml(p: str) -> dict:
    """Parsed TOML file ({} when absent); a malformed file raises ValueError naming the file."""
    if not exists(p):
        return {}
    with open(path(p), "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"{p}: {e}") from None


@lru_cache(maxsize=None)
def project() -> dict:
    return load_toml("project.toml")


@lru_cache(maxsize=None)
def models() -> dict:
    return load_toml("models.toml")


@lru_cache(maxsize=None)
def workflow() -> dict:
    return load_toml("workflow/workflow.toml")


@lru_cache(maxsize=None)
def backlog() -> dict:
    return load_toml("backlog/stories.toml")


def prefix() -> str:
    return project().get("project", {}).get("id_prefix", "PR")


def sources() -> list[str]:
    """Kickoff sources recorded in project.toml [inception] sources (paths relative to the root)."""
    return list(project().get("inception", {}).get("sources", []))


def design() -> str:
    """Existing design (prototype, HTML mockup, exported frames) recorded in project.toml [inception] design."""
    return project().get("inception", {}).get("design", "")


def id_rx() -> str:
    """Regex (no anchors) matching a story ID, e.g. PR0101."""
    return rf"{re.escape(prefix())}\d{{4}}"


def norm_id(x: str) -> str:
    """A story ID as typed by a human or an agent (`pr-0101`, `PR0101`) in its canonical form `PR0101`."""
    return x.replace("-", "").upper()


STORY_KEYS = {"id": str, "epic": str, "slug": str, "title": str}
STORY_LISTS = ("fr", "nfr", "deps")
STORY_LINKS = ("supersedes", "split_from")  # another story's ID
SIZES = ("XS", "S", "M", "L", "XL")
PRIORITIES = ("Must", "Should", "Could", "Won't")
STORY_STATES = ("open", "cancelled", "superseded")  # per-story `status`; cancelled / superseded count as done
TYPES = ("feature", "technical", "bug", "hotfix", "chore", "refactor", "spike")
QUICK_TYPES = ("bug", "hotfix", "chore")           # quick track: Brief + Spec + RUN strategy, one approval
NO_ANALYSIS_TYPES = (*QUICK_TYPES, "refactor", "spike")


def track(s: dict) -> str:
    """Delivery track of a story: spike (findings note, no code merged) | quick (one approval) | standard."""
    if s.get("type") == "spike":
        return "spike"
    return "quick" if s.get("type") in QUICK_TYPES or s.get("size") == "XS" else "standard"


def skips_analysis(s: dict) -> bool:
    """`skip_analysis` when set; otherwise true for non-feature work types and quick-track stories."""
    if "skip_analysis" in s:
        return s["skip_analysis"] is True
    return s.get("type") in NO_ANALYSIS_TYPES or track(s) == "quick"
SECURITY_RX = re.compile(r"\b(auth\w*|login|password\w*|passwd|credential\w*|secret\w*|token\w*|api[ -]?keys?|oauth|sso|"
                         r"session cookies?|encrypt\w*|permission\w*|role-based|rbac|personal data|pii|gdpr|privacy)\b", re.I)
SECURITY_SECTIONS = ("security", "privacy")


BRANCH_ID = re.compile(r"(?:^|/)([A-Za-z]+\d{4})-[\w.-]+$")


def story_branches() -> dict[str, list[dict]]:
    """Story branches, local and remote (`<id-lowercase>-<slug>`): {ID: [{"ref", "author"}]}. A pushed story branch is
    a claim the whole team sees, without writing to main."""
    import subprocess
    try:
        r = subprocess.run(["git", "for-each-ref", "--format=%(refname:short)\t%(authorname)\t%(authoremail)", "refs/heads", "refs/remotes"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out: dict[str, list[dict]] = {}
    ids = set(stories())
    for line in r.stdout.splitlines() if r.returncode == 0 else []:
        ref, name, email = (line.split("\t") + ["", ""])[:3]
        if (m := BRANCH_ID.search(ref)) and (i := norm_id(m.group(1))) in ids and not ref.endswith("/HEAD"):
            short = ref.split("/", 1)[1] if ref.startswith(("origin/", "upstream/")) else ref
            if not any(b["branch"] == short for b in out.get(i, [])):
                out.setdefault(i, []).append({"ref": ref, "branch": short, "author": name, "email": email.strip("<>")})
    return out


def stale_branches(max_days: int | None = None) -> list[dict]:
    """Trunk-based development: branches (local and remote, not main, not spikes) whose oldest commit not yet in main is
    older than `[git] max_branch_age_days` (default 3): [{"branch", "days", "commits"}], oldest first."""
    import subprocess
    if max_days is None:
        max_days = int(project().get("git", {}).get("max_branch_age_days", 3))
    def git(*a: str) -> str | None:
        try:
            r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout if r.returncode == 0 else None
    trunk = next((t for t in ("origin/main", "main") if git("rev-parse", "--verify", "-q", t) is not None), None)
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
    if not trunk or refs is None:
        return []
    seen, out, now = set(), [], dt.datetime.now().timestamp()
    for ref in refs.split():
        short = ref.split("/", 1)[1] if ref.startswith("origin/") else ref
        if short in ("main", "HEAD", "origin") or short.startswith(("spike/", "backup/")) or short in seen:
            continue
        seen.add(short)
        times = git("log", f"{trunk}..{ref}", "--format=%ct")
        times = times.split() if times else []
        if times and (days := int((now - int(times[-1])) // 86400)) > max_days:
            out.append({"branch": short, "days": days, "commits": len(times)})
    return sorted(out, key=lambda b: -b["days"])


def claims() -> dict[str, dict]:
    """Who works on which story: `claimed_by` / `claimed_at` in stories.toml, else the author of its story branch."""
    out = {}
    branches = story_branches()
    for i, s in stories().items():
        if s.get("claimed_by"):
            out[i] = {"by": s["claimed_by"], "at": s.get("claimed_at"), "source": "stories.toml", "branches": branches.get(i, [])}
        elif branches.get(i):
            b = branches[i][0]
            out[i] = {"by": b["author"], "at": None, "source": f"branch {b['ref']}", "branches": branches[i]}
    return out


def same_person(a: str | None, b: str | None) -> bool:
    return bool(a and b) and a.strip().lower() == b.strip().lower()


def pending_actions(text: str) -> list[str]:
    """Open owner actions of a RUN: unticked lines of `## Pending owner actions` (`- [ ] <action> — owner: … — since: …`)."""
    sec = heading_section(text, r"^##\s+Pending owner actions\b") or ""
    return [m.strip() for m in re.findall(r"^\s*-\s*\[ \]\s*(\S.*)$", sec, re.M) if not m.strip().startswith("<")]


def security_nfrs() -> set[str]:
    """NFR IDs filed under the Security or Privacy heading of the NFR file (FR-1 = FR-01 normalised to NFR-01)."""
    p = "reference/product/non-functional-requirements.md"
    if not exists(p):
        return set()
    out, cur = set(), ""
    for _, level, line in headings(read(p)):
        if level == 2:
            cur = line.lstrip("#").strip().lower()
        elif m := re.search(r"\bNFR-0*(\d+)\b", line):
            if any(cur.startswith(s) for s in SECURITY_SECTIONS):
                out.add(f"NFR-{int(m.group(1)):02d}")
    return out


def security_sensitive(i: str) -> str | None:
    """Why story i needs the security review step, or None. `security = true|false` in stories.toml decides when set;
    otherwise a cited Security/Privacy NFR or a security keyword in the Spec."""
    s = stories().get(i, {})
    if "security" in s:
        return "stories.toml security = true" if s["security"] is True else None
    spec = one(f"delivery/20-specs/SPEC-{i}-*.md")
    text = read(spec) if spec else ""
    cited = {f"NFR-{int(n):02d}" for n in re.findall(r"\bNFR-0*(\d+)\b", text + " ".join(s.get("nfr", [])))}
    if hit := sorted(cited & security_nfrs()):
        return f"cites {', '.join(hit)} (Security/Privacy)"
    if m := SECURITY_RX.search(text):
        return f"the Spec mentions '{m.group(0)}'"
    return None


def security_review(text: str) -> str | None:
    """Outcome of the RUN §8 `### Security review` subsection: ok | changes-requested | None."""
    sec = heading_section(text, r"^###\s+Security review\b") or ""
    m = re.search(r"^\s*-\s*Outcome:([^\n]*)$", sec, re.M)
    codes = [c for c in ("ok", "changes-requested") if m and re.search(rf"`?\b{c}\b`?", m.group(1).lower())]
    return codes[0] if len(codes) == 1 else None


POINTS = {"XS": 1, "S": 1, "M": 2, "L": 3, "XL": 5}  # default story points per size (PLAN.md `points:` overrides)


def backlog_errors() -> list[str]:
    """Schema problems of backlog/stories.toml that would crash or mislead the other tools (empty = valid)."""
    out = []
    for n, s in enumerate(backlog().get("story", []), 1):
        if not isinstance(s, dict):
            out.append(f"[[story]] #{n} is not a table")
            continue
        who = s.get("id") if isinstance(s.get("id"), str) else f"[[story]] #{n}"
        for k, t in STORY_KEYS.items():
            if not isinstance(s.get(k), t) or not s.get(k):
                out.append(f"{who}: missing or invalid `{k}`")
        for k in STORY_LISTS:
            if k in s and not (isinstance(s[k], list) and all(isinstance(x, str) for x in s[k])):
                out.append(f"{who}: `{k}` must be a list of strings")
        ac = s.get("ac", [])
        if not isinstance(ac, list) or any(not (isinstance(a, list) and len(a) == 3 and all(isinstance(x, str) for x in a)) for a in ac):
            out.append(f"{who}: `ac` must be a list of [given, when, then] string triples")
        if s.get("size") not in (None, *SIZES):
            out.append(f"{who}: size '{s.get('size')}' not in {' | '.join(SIZES)}")
        if s.get("priority") not in (None, *PRIORITIES):
            out.append(f"{who}: priority '{s.get('priority')}' not in {' | '.join(PRIORITIES)}")
        if s.get("type") not in (None, *TYPES):
            out.append(f"{who}: type '{s.get('type')}' not in {' | '.join(TYPES)}")
        if s.get("status") not in (None, *STORY_STATES):
            out.append(f"{who}: status '{s.get('status')}' not in {' | '.join(STORY_STATES)}")
        for k in STORY_LINKS:
            if k in s and not (isinstance(s[k], str) and s[k]):
                out.append(f"{who}: `{k}` must be a story ID")
        for k in ("claimed_by", "claimed_at", "repo"):
            if k in s and not (isinstance(s[k], str) and s[k].strip()):
                out.append(f"{who}: `{k}` must be a non-empty string")
        for flag in ("skip_analysis", "security"):
            if flag in s and not isinstance(s[flag], bool):
                out.append(f"{who}: `{flag}` must be true or false")
    for n, e in enumerate(backlog().get("epic", []), 1):
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            out.append(f"[[epic]] #{n} has no id")
    return [f"backlog/stories.toml: {m}" for m in out]


def stories() -> dict[str, dict]:
    out = {}
    for n, s in enumerate(backlog().get("story", []), 1):
        if not isinstance(s, dict) or not isinstance(s.get("id"), str):
            raise ValueError(f"backlog/stories.toml: [[story]] #{n} has no id")
        out[s["id"]] = s
    return out


# ---------------------------------------------------------------- markdown status

FENCE = re.compile(r"^\s*(```|~~~)")


def frontmatter(text: str) -> str:
    """The YAML frontmatter block (between the leading `---` lines), or "" when the file has none."""
    m = re.match(r"\A\ufeff?---[ \t]*\n(.*?)^---[ \t]*$", text, re.M | re.S)
    return m.group(1) if m else ""


def front(text: str, key: str) -> str | None:
    """Value of `key:` in the YAML frontmatter, without quotes and trailing comment; None when absent or empty."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*([^#\n]*)", frontmatter(text), re.M)
    v = m.group(1).strip().strip("'\"").strip() if m else ""
    return v or None


def headings(text: str) -> list[tuple[int, int, str]]:
    """(line number, level, line) of the Markdown headings, ignoring `#` lines inside fenced code blocks."""
    out, fence = [], None
    for n, line in enumerate(text.splitlines()):
        if f := FENCE.match(line):
            fence = None if fence == f.group(1) else fence or f.group(1)
        elif not fence and (h := re.match(r"^(#{1,6})\s", line)):
            out.append((n, len(h.group(1)), line))
    return out


def heading_section(text: str, start_rx: str) -> str | None:
    """From the first heading matching start_rx to the next heading of the same or higher level (code fences aware)."""
    lines = text.splitlines()
    hs = headings(text)
    for k, (n, level, line) in enumerate(hs):
        if re.search(start_rx, line):
            end = next((m for m, lv, _ in hs[k + 1:] if lv <= level), len(lines))
            return "\n".join(lines[n:end]).strip()
    return None


def md_status(text: str) -> str | None:
    """Value under a `## Status` heading; None while the template placeholder (with arrows) is still there."""
    m = re.search(r"^## Status\s*\n+([^\n]+)", text, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    return None if "→" in v else v


# Status vocabulary per artifact (single source for next_step, check_workflow and the templates' lifecycles).
STATUSES = {
    "inception": ("draft", "approved"),                        # vision, requirements, mockup, architecture, stories.toml, PLAN.md
    "adr": ("proposed", "accepted", "superseded", "rejected"),  # `superseded by ADR-xxx` → superseded
    "analysis": ("draft", "analyzed", "workshop-ready", "updated"),
    "refined": ("draft", "refined", "approved"),
    "brief": ("Captured", "Refined into Spec", "Superseded", "Closed"),
    "spec": ("Draft", "Ready", "In Progress", "Done", "Blocked", "Cancelled"),
    "spike": ("Draft", "Accepted"),
    "run": ("Draft", "Strategy Approved", "Executing", "Tuning", "Persisted", "Reviewed", "Closed", "Stopped", "Blocked", "Cancelled"),
}


def _norm_status(v: str) -> str:
    v = re.sub(r"[*_`~]", "", v)                    # **Ready**, `Closed`
    v = re.sub(r"\s*[(\[].*$", "", v)               # Closed (2026-10-19), Done [see §9]
    v = re.sub(r"[^\w\s-]", " ", v, flags=re.U)     # Closed ✅, Ready.
    return re.sub(r"\s+", " ", v).strip().lower()


def status(kind: str, raw: str | None) -> str | None:
    """Canonical status of an artifact kind (case, emphasis, emoji, trailing parenthetical ignored); None if unknown."""
    if raw is None:
        return None
    n = _norm_status(raw)
    for v in STATUSES[kind]:
        if _norm_status(v) == n or (kind == "adr" and v == "superseded" and n.startswith("superseded by")):
            return v
    return None


def expected(kind: str) -> str:
    return " | ".join(STATUSES[kind])


def run_approved(text: str) -> bool:
    """RUN §2 Human Approval has `- [x] Approved` ticked (case-insensitive box; prose elsewhere does not count)."""
    sec = heading_section(text, r"^#\s+2\.") or ""
    return bool(re.search(r"^\s*-\s*\[[xX]\]\s*Approved\b", sec, re.M))


def run_stopped(text: str) -> bool:
    """RUN §2 Human Approval has `- [x] Stopped` ticked."""
    sec = heading_section(text, r"^#\s+2\.") or ""
    return bool(re.search(r"^\s*-\s*\[[xX]\]\s*Stopped\b", sec, re.M))


def open_deviations(text: str) -> list[str]:
    """Numbers of the RUN §6 entries `### Deviation #n` with scope impact `Requires approval` and no `Approved by:` value."""
    out = []
    for m in re.finditer(r"^###\s+Deviation\s+#(\d+)\b(.*?)(?=^#{1,3}\s|\Z)", heading_section(text, r"^#\s+6\.") or "", re.M | re.S):
        body = m.group(2)
        needs = re.search(r"^\s*-\s*Scope impact:[ \t]*\**Requires approval\**[ \t]*$", body, re.M | re.I)
        if needs and not re.search(r"^\s*-\s*Approved by:[ \t]*\S", body, re.M):
            out.append(m.group(1))
    return out


REVIEW_OUTCOMES = ("ok-to-close", "changes-requested")


def run_review(text: str) -> dict | None:
    """Latest RUN §11 `### Review #n` entry: {n, date, outcome}; outcome None unless exactly one code is written
    (the template line lists both). None when §11 has no entry."""
    last = None
    for m in re.finditer(r"^###\s+Review\s+#(\d+)\b(.*?)(?=^#{1,3}\s|\Z)", heading_section(text, r"^#\s+11\.") or "", re.M | re.S):
        body = m.group(2)
        date = re.search(r"^\s*-\s*Date:[ \t]*(\S[^\n]*)$", body, re.M)
        line = re.search(r"^\s*-\s*Outcome:([^\n]*)$", body, re.M)
        codes = [c for c in REVIEW_OUTCOMES if line and c in line.group(1).lower()]
        last = {"n": m.group(1), "date": date.group(1).strip() if date else "", "outcome": codes[0] if len(codes) == 1 else None}
    return last


def strategy_written(text: str) -> bool:
    """RUN §1 has a plan: a first step under `### Plan` (`- TSK-<ID>-01: …`, or `- Step 1` before 1.11) that is not the
    template placeholder, or `Strategy ready: yes`."""
    if re.search(r"^\s*Strategy ready:\s*yes\b", text, re.M | re.I):
        return True
    plan = heading_section(text, r"^###\s+Plan\b") or ""
    m = re.search(r"^\s*-\s*(?:Step 1\b|TSK-[A-Za-z]+\d{4}-\d+\b)(.*)$", plan, re.M)
    return bool(m) and bool(re.sub(r"\([^)]*\)", "", m.group(1)).strip(" :.…"))  # `- Step 1 (TSK-01): …` is still empty


def artifact_status(p: str) -> str | None:
    """Status of an inception artifact: frontmatter `status:` (md) or top-level `status` (toml)."""
    if not exists(p):
        return None
    if p.endswith(".toml"):
        return load_toml(p).get("status")
    v = front(read(p), "status")
    return v.split("|")[0].strip() if v else None


# ---------------------------------------------------------------- models

def enabled_tools() -> dict[str, dict]:
    return {k: v for k, v in models().get("tools", {}).items() if v.get("enabled", True)}


def model_for(tool: str, tier: str) -> str:
    t = models().get("tools", {}).get(tool, {})
    if tier in t.get("models", {}):
        return t["models"][tier]
    return models().get("vendors", {}).get(t.get("vendor", ""), {}).get(tier, f"<{tier}>")


def tier_line(tier: str) -> str:
    tools = enabled_tools()
    return " · ".join(f"{k}: {model_for(k, tier)}" for k in tools) or f"<{tier}>"


# ---------------------------------------------------------------- plan

def sprints() -> list[dict]:
    """Rows `| S<n> | dates | goal | IDs |` of PLAN.md; EP-xx expands to the epic's stories."""
    if not exists("PLAN.md"):
        return []
    st = stories()
    out = []
    for line in read("PLAN.md").splitlines():
        m = re.match(r"^\|\s*(S\d+(?:\s*[–-]\s*S\d+)?)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|", line)
        if not m:
            continue
        ids: list[str] = []
        for tok in re.findall(rf"{id_rx()}|EP-\d{{2}}", m.group(4)):
            ids += [k for k, s in st.items() if s.get("epic") == tok] if tok.startswith("EP-") else [tok]
        out.append({"sprint": m.group(1), "dates": m.group(2).strip(), "goal": m.group(3).strip(),
                    "ids": list(dict.fromkeys(ids))})
    return out


def plan_date(text: str, year: int) -> dt.date | None:
    """`2026-10-26`, `26/10/2026` or `26/10` (year given) as a date; None if unparsable."""
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text.strip()):
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", text.strip()):
            return dt.date(int(m[3] or year), int(m[2]), int(m[1]))
    except ValueError:
        pass
    return None


def sprint_ends() -> dict[str, dt.date]:
    """End date of each sprint row of PLAN.md (`DD/MM – DD/MM` takes its year from frontmatter `start:`, else this year)."""
    if not exists("PLAN.md"):
        return {}
    start = plan_date(front(read("PLAN.md"), "start") or "", 0)
    year = start.year if start else dt.date.today().year
    out, prev = {}, None
    for s in sprints():
        parts = re.split(r"\s+[–-]\s+|\s*–\s*", s["dates"])
        end = plan_date(parts[-1], year)
        if end and prev and end < prev and re.fullmatch(r"\d{1,2}/\d{1,2}", parts[-1].strip()):
            year += 1  # DD/MM rows crossing the new year
            end = plan_date(parts[-1], year)
        if end:
            out[s["sprint"]] = prev = end
    return out


def releases() -> list[dict]:
    """Rows `| R<n> | content | target | exit criterion |` of PLAN.md; `sprints` = sprints whose stories belong to it."""
    if not exists("PLAN.md"):
        return []
    sp = sprints_with_release()
    out = []
    for line in read("PLAN.md").splitlines():
        m = re.match(r"^\|\s*(R\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
        if m:
            rid = m.group(1)
            out.append({"id": rid, "title": m.group(2).strip(), "goal": m.group(4).strip(), "target": m.group(3).strip(),
                        "sprints": [s["sprint"] for s in sp if s.get("release") == rid]})
    return out


def sprints_with_release() -> list[dict]:
    """sprints() plus `release`: the release (stories.toml) of the first story of the row that has one."""
    st = stories()
    out = []
    for s in sprints():
        rel_ = next((st[i]["release"] for i in s["ids"] if st.get(i, {}).get("release")), None)
        out.append({**s, "release": rel_} if rel_ else s)
    return out


# ---------------------------------------------------------------- journal

def journal_entries(folder: str) -> list[dict]:
    """`project-journal/<folder>/*.md` except README.md: file, title (first `# ` heading), date (frontmatter or file name)."""
    out = []
    for p in matches(f"project-journal/{folder}/*.md"):
        if os.path.basename(p) == "README.md":
            continue
        text = read(p)
        e: dict = {"file": rel(p)}
        if m := re.search(r"^# (.+)$", text, re.M):
            e["title"] = m.group(1).strip()
        named = re.search(r"\d{4}-\d{2}-\d{2}", os.path.basename(p))
        if d := front(text, "date") or (named.group(0) if named else None):
            e["date"] = d.strip("'\"")
        out.append(e)
    return out


def journal() -> dict:
    ctx = [read(p).strip() for p in matches("project-journal/context/*.md") if os.path.basename(p) != "README.md"]
    return {"context": "\n\n".join(ctx) if ctx else None,
            **{k: journal_entries(k) for k in ("decisions", "learnings", "weekly", "monthly")}}


# ---------------------------------------------------------------- story chain

CHAIN = {"story": "analysis/10-stories/STORY_{i}_*.md", "analysis": "analysis/20-analysis/ANALYSIS_{i}_*.md",
         "refined": "analysis/30-refined/REFINED_{i}_*.md", "brief": "delivery/10-briefs/BRIEF-{i}-*.md",
         "spec": "delivery/20-specs/SPEC-{i}-*.md", "run": "delivery/30-runs/RUN-{i}*.md"}
SPIKE = "delivery/40-spikes/SPIKE-{i}-*.md"  # spike findings note (outside the chain: spikes have no Brief/Spec/RUN)


def find(kind: str, i: str) -> str | None:
    """Absolute path of one chain artifact of a story; for the RUN, `RUN-<ID>.md` wins over `RUN-<ID>-<suffix>.md`."""
    if kind == "run" and exists(f"delivery/30-runs/RUN-{i}.md"):
        return path(f"delivery/30-runs/RUN-{i}.md")
    return one(CHAIN[kind].format(i=i))


def artifacts(i: str) -> dict:
    """Paths of the chain artifacts of a story (None when absent)."""
    return {k: (rel(h) if (h := find(k, i)) else None) for k in CHAIN}


def section(text: str, start: str, end: str) -> str:
    """Text after the first line starting with `start` up to the next line starting with `end` (or the end)."""
    m = re.search(rf"^{re.escape(start)}.*?$(.*?)(?=^{re.escape(end)}|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def task_ids(text: str, i: str) -> set[str]:
    """Task IDs named in a RUN §9 list, ranges included (`TSK-X-01 to TSK-X-08`, `–`, `—`, `..`, ` - `, `TSK-X-01 - 03`)."""
    tid = rf"TSK-{re.escape(i)}-(\d+)"
    ids = {f"TSK-{i}-{n}" for n in re.findall(tid, text)}
    for a, full, short in re.findall(rf"{tid}\s*(?:to|–|—|\.\.|-)\s*(?:{tid}|(\d+)\b)", text):
        b = full or short
        if short and len(short) != len(a):  # `TSK-X-03 — 2 files`: prose, not a range
            continue
        ids |= {f"TSK-{i}-{n:0{len(a)}d}" for n in range(int(a), int(b) + 1)}
    return ids


def tasks(i: str, spec: str | None, run: str | None) -> list[dict]:
    """`TSK-<ID>-NN` of Spec §5 with title; status done/deferred from RUN §9, else open."""
    if not spec:
        return []
    outcome = section(read(run), "# 9.", "# 10.") if run else ""
    done = task_ids(section(outcome, "Tasks completed", "Tasks deferred"), i)
    deferred = task_ids(section(outcome, "Tasks deferred", "Goal achieved"), i)
    out = []
    for m in re.finditer(rf"^- `?(TSK-{re.escape(i)}-\d+)`?\s*(.*)$", section(read(spec), "# 5.", "# 6."), re.M):
        tid = m.group(1)
        out.append({"id": tid, "title": m.group(2).strip(),
                    "status": "done" if tid in done else "deferred" if tid in deferred else "open"})
    return out


def story_chain(i: str) -> dict:
    import next_step  # lazy: next_step imports wf
    paths = artifacts(i)
    arts = []
    for kind, p in paths.items():
        if p:
            text = read(p)
            arts.append({"kind": kind, "path": p, "status": md_status(text) or front(text, "status")})
    return {"id": i, "title": stories()[i].get("title", ""), "stage": next_step.stage(i)[0], "artifacts": arts,
            "tasks": tasks(i, paths["spec"], paths["run"])}


USAGE = "usage: python3 tools/wf.py version|plan|journal [--json] · python3 tools/wf.py story <ID> [--json]"


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    cmd = args[0] if args else ""
    if cmd not in ("version", "plan", "journal", "story") or len(args) != (2 if cmd == "story" else 1):
        if as_json and cmd in ("plan", "journal", "story"):
            fail_envelope(cmd, "usage", USAGE, 2)
        print(USAGE)
        return 2
    if cmd == "version":
        data = {"skeleton": skeleton_version(), "contract": CONTRACT_VERSION}
        if not as_json:
            print(f"agentic-skeleton {data['skeleton']} (contract {data['contract']})")
            return 0
    else:
        try:
            if cmd == "story":
                i = norm_id(args[1])
                if i not in stories():
                    if as_json:
                        fail_envelope("story", "unknown_id", f"Unknown ID: {i}")
                    print(f"Unknown ID: {i}")
                    return 1
                data = story_chain(i)
            else:
                data = {"releases": releases(), "sprints": sprints_with_release()} if cmd == "plan" else journal()
        except (OSError, ValueError) as e:  # unreadable or malformed files (tomllib.TOMLDecodeError is a ValueError)
            if not as_json:
                raise
            fail_envelope(cmd, "bad_input", str(e))
        if not as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
    dump_envelope(cmd, data)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
