#!/usr/bin/env python3
"""Agent usage signals of this repository from the agent tools' local session logs (for /weekly).

Usage:
  python3 tools/usage.py [--days 7 | --since YYYY-MM-DD] [--until YYYY-MM-DD] [--json]

Sources (read-only, this repository only):
  claude-code  $CLAUDE_CONFIG_DIR or ~/.claude → projects/<repo path slug>/**/*.jsonl
               tokens per model, cost and lines from the session's last `cost-state` record when present
  codex        $CODEX_HOME or ~/.codex → sessions/**/rollout-*.jsonl whose session cwd is this repository
               tokens from the last `token_count` event; no cost recorded
Copilot and Cursor keep no readable local logs: not counted.

A session is split into one row per workflow command it ran (`/analysis`, `/run`, …); tool built-ins such as
`/clear` or `/compact` neither label nor split it. Rows are assigned to the day they started. Peak context is the
largest prompt of one call (flagged over 80k tokens). Supervision signals are counts of human prompts, interrupts and
rejected tool calls. Cost is recorded per session (Claude Code): a row shows it only when the session ran one command;
per-model cost and its share come from the sessions' per-model cost. Prompt text is never printed.

Context cost share (Claude Code only; Codex logs carry no tool results): on every main-context call (subagents excluded)
each tool result still in context is charged, its first send as a cache write (×1.25), then a cache read (×0.1) per call,
until /clear, /compact or a context drop below 40% of the previous call (tokens ≈ chars / 3.5). Kinds: full reads longer
than `project.toml [context] max_read_lines` (Read without offset/limit, or cat/head/tail/less/more/sed/awk/nl), small
reads, targeted reads (offset/limit), `context.py` output, other Bash output, subagent results, other. The fixed prefix is
the session's first-call context re-read (×0.1) on every call; output is ×5. Shares are of the weighted cost of all
main-context calls (input ×1, cache write ×1.25, cache read ×0.1, output ×5).

Fixed prefix: per tool, the median first-call context of the period's sessions (Claude Code: the first main-context
call's input + cache read + cache write; Codex: the first `token_count` call's input), against the repository's own
always-loaded share (`wf.prefix_tokens()`: AGENTS.md, CLAUDE.md, command and agent descriptions). The rest is the tool's
setup: system prompt, tool schemas, MCP servers, skills and plugins (docs/GUIDE.md § 9.1 Trim your tool prefix).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

COMMAND_RX = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
CODEX_COMMAND_RX = re.compile(r"^(?:/(?:prompts:)?|\$)([\w-]+)")  # /prompts:name (custom prompt) or $name (skill)
REJECTED = "tool use was rejected"
LARGE_READ = "Blocked by the workflow guard (tools/gate_guard.py): large read"
INTERRUPTED = "[Request interrupted by user"
# tool built-ins: never a workflow step, so they neither label nor split a session
BUILTINS = {"clear", "compact", "model", "context", "cost", "help", "status", "config", "login", "logout", "resume", "init",
            "memory", "mcp", "permissions", "exit", "quit", "new", "diff", "review", "approvals", "fast", "usage", "agents", "hooks"}
PEAK_LIMIT = 80_000  # tokens of context in one call: past this, /clear and resume (docs/GUIDE.md)
CHARS_PER_TOKEN = 3.5
WEIGHT = {"input": 1.0, "cache_write": 1.25, "cache_read": 0.1, "output": 5.0}  # relative to the input price
READERS = {"cat", "head", "tail", "less", "more", "sed", "awk", "nl"}
KINDS = {"large_reads": "full reads", "small_reads": "small reads", "targeted_reads": "targeted reads", "context_py": "context.py",
         "bash_other": "other Bash", "subagents": "subagent results", "other": "other", "prefix": "fixed prefix", "output": "output"}


def _ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone()  # naive timestamps are taken as local time


def _segment(step: str | None = None) -> dict:
    return {"step": step, "start": None, "end": None, "prompts": 0, "interrupts": 0, "rejected": 0, "large_reads": 0, "models": {}, "peak": 0,
            "context_cost": dict.fromkeys([*KINDS, "total"], 0.0)}


def _session(tool: str, sid: str) -> dict:
    return {"tool": tool, "id": sid, "segments": [_segment()], "cost": None, "lines": None, "cost_models": {}, "first": None}


def _seen(s: dict, t: dt.datetime | None) -> None:
    if t:
        s["start"] = min(s["start"] or t, t)
        s["end"] = max(s["end"] or t, t)


def _busy(seg: dict) -> bool:
    return bool(seg["step"] or seg["models"] or seg["prompts"])


def _command(s: dict, cmd: str) -> dict:
    """A workflow command starts a new segment of the session (built-ins are ignored)."""
    cur = s["segments"][-1]
    if _busy(cur):
        cur = _segment(cmd)
        s["segments"].append(cur)
    cur["step"] = cmd
    return cur


def _add(seg: dict, model: str, calls: int = 1, **tok: int) -> None:
    m = seg["models"].setdefault(model, {"calls": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0})
    m["calls"] += calls
    for k, v in tok.items():
        m[k] += v or 0
    seg["peak"] = max(seg["peak"], (tok.get("input") or 0) + (tok.get("cache_read") or 0) + (tok.get("cache_write") or 0))


# ---------------------------------------------------------------- claude code

def claude_dir() -> str:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(base, "projects", re.sub(r"[^A-Za-z0-9]", "-", wf.ROOT))


def _texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]


def _results(content) -> list[tuple[str | None, str]]:
    out = []
    for b in content if isinstance(content, list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            c = b.get("content")
            out.append((b.get("tool_use_id"), c if isinstance(c, str) else " ".join(_texts(c))))
    return out


def read_limit() -> int:
    return int(wf.project().get("context", {}).get("max_read_lines") or 400)


def result_kind(name: str, inp: dict, text: str, limit: int) -> str:
    big = text.count("\n") + 1 > limit
    if name == "Read":
        if inp.get("offset") is not None or inp.get("limit") is not None:
            return "targeted_reads"
        return "large_reads" if big else "small_reads"
    if name == "Bash":
        cmd = inp.get("command") or ""
        words = cmd.split("|")[0].split("&&")[-1].split()
        if words and os.path.basename(words[0]) in READERS:
            return "large_reads" if big else "small_reads"
        return "context_py" if "context.py" in cmd else "bash_other"
    return "subagents" if name in ("Agent", "Task") else "other"


def _carry(cc: dict, st: dict, u: dict) -> None:
    """Charge one main-context call: its weighted cost, the fixed prefix and every tool result still in context."""
    tok = {"input": u.get("input_tokens") or 0, "cache_write": u.get("cache_creation_input_tokens") or 0,
           "cache_read": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0}
    ctx = tok["input"] + tok["cache_write"] + tok["cache_read"]
    if ctx < 0.4 * st["last"]:  # compaction or a new conversation: earlier results left the context
        st["live"] = []
    st["last"], st["prefix"] = ctx, st["prefix"] or ctx
    cc["total"] += sum(WEIGHT[k] * v for k, v in tok.items())
    cc["output"] += WEIGHT["output"] * tok["output"]
    cc["prefix"] += WEIGHT["cache_read"] * st["prefix"]
    for r in st["live"]:  # [kind, tokens, sent]: first send written to cache, later calls read it
        cc[r[0]] += WEIGHT["cache_read" if r[2] else "cache_write"] * r[1]
        r[2] = True


def claude_sessions() -> list[dict]:
    sessions: dict[str, dict] = {}
    seen_msgs: set[str] = set()
    states: dict[str, dict] = {}  # per session: tool uses, results in context, last context, fixed prefix
    limit = read_limit()
    for f in sorted(glob.glob(os.path.join(claude_dir(), "**", "*.jsonl"), recursive=True)):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = d.get("sessionId")
                if not sid:
                    continue
                s = sessions.setdefault(sid, _session("claude-code", sid))
                st = states.setdefault(sid, {"uses": {}, "live": [], "last": 0, "prefix": 0})
                seg = s["segments"][-1]
                kind = d.get("type")
                if kind == "cost-state":
                    s["cost"] = d.get("totalCostUSD")
                    s["lines"] = (d.get("totalLinesAdded", 0), d.get("totalLinesRemoved", 0))
                    s["cost_models"] = {k: v.get("costUSD") for k, v in (d.get("modelUsage") or {}).items()}
                    continue
                if kind not in ("user", "assistant"):
                    continue
                msg = d.get("message") or {}
                content, main = msg.get("content"), not d.get("isSidechain")
                if kind == "assistant":
                    for b in content if main and isinstance(content, list) else []:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            st["uses"][b.get("id")] = (b.get("name"), b.get("input") or {})
                    key = f'{msg.get("id")}:{d.get("requestId")}'
                    model, u = msg.get("model"), msg.get("usage")
                    if key in seen_msgs or not u or not model or model.startswith("<"):
                        continue
                    seen_msgs.add(key)
                    _seen(seg, _ts(d.get("timestamp")))
                    _add(seg, model, input=u.get("input_tokens"), output=u.get("output_tokens"),
                         cache_write=u.get("cache_creation_input_tokens"), cache_read=u.get("cache_read_input_tokens"))
                    if main:
                        _carry(seg["context_cost"], st, u)
                    continue
                results = _results(content)
                seg["rejected"] += sum(REJECTED in r for _, r in results)
                seg["large_reads"] += sum(LARGE_READ in r for _, r in results)
                for tid, r in results if main else []:
                    if tid in st["uses"]:
                        name, inp = st["uses"].pop(tid)
                        st["live"].append([result_kind(name, inp, r, limit), len(r) / CHARS_PER_TOKEN, False])
                if d.get("isMeta") or d.get("isSidechain") or d.get("userType", "external") != "external":
                    continue
                texts = [t.strip() for t in _texts(content)]
                if any(t.startswith(INTERRUPTED) for t in texts):
                    seg["interrupts"] += 1
                    continue
                cmd = next((m.group(1) for t in texts if (m := COMMAND_RX.search(t))), None)
                if cmd and cmd.split(":")[-1] in BUILTINS:
                    if cmd.split(":")[-1] in ("clear", "compact"):
                        st["live"] = []
                    continue
                if cmd:
                    seg = _command(s, cmd.split(":")[-1])
                if cmd or any(t and not t.startswith("<") for t in texts):
                    seg["prompts"] += 1
                    _seen(seg, _ts(d.get("timestamp")))
    for sid, s in sessions.items():
        s["first"] = states[sid]["prefix"] or None
    return list(sessions.values())


# ---------------------------------------------------------------- codex

def codex_sessions() -> list[dict]:
    base = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    out = []
    for f in sorted(glob.glob(os.path.join(base, "sessions", "**", "rollout-*.jsonl"), recursive=True)):
        s, model, ours = _session("codex", os.path.basename(f)), "codex", False
        total = {"input": 0, "cached": 0, "output": 0}  # cumulative totals: each segment gets the difference
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                p, kind = d.get("payload") or {}, d.get("type")
                seg = s["segments"][-1]
                _seen(seg, _ts(d.get("timestamp")))
                if kind == "session_meta":
                    s["id"] = p.get("id") or s["id"]
                    cwd = os.path.abspath(p.get("cwd") or "")
                    ours = cwd == wf.ROOT or cwd.startswith(wf.ROOT + os.sep)
                elif kind == "turn_context":
                    model = p.get("model") or model
                elif kind == "event_msg" and p.get("type") == "token_count":
                    info = p.get("info") or {}
                    tot, last = info.get("total_token_usage") or {}, info.get("last_token_usage") or {}
                    if not tot:
                        continue
                    now = {"input": tot.get("input_tokens", 0), "cached": tot.get("cached_input_tokens", 0), "output": tot.get("output_tokens", 0)}
                    cached = now["cached"] - total["cached"]
                    _add(seg, model, input=now["input"] - total["input"] - cached, output=now["output"] - total["output"], cache_read=cached)
                    seg["peak"] = last.get("input_tokens", 0) if last else seg["peak"]
                    s["first"] = s["first"] or last.get("input_tokens") or None
                    total = now
                elif kind == "event_msg" and p.get("type") == "user_message":
                    m = CODEX_COMMAND_RX.match((p.get("message") or "").strip())
                    if m and m.group(1) in BUILTINS:
                        continue
                    seg = _command(s, m.group(1)) if m else seg
                    seg["prompts"] += 1
                elif kind == "event_msg" and p.get("type") == "turn_aborted":
                    seg["interrupts"] += 1
        if ours:
            out.append(s)
    return out


# ---------------------------------------------------------------- tiers

def tier_of(model: str) -> str | None:
    """Tier whose configured model is `model` (exact name first, then alias inside the name: haiku → claude-haiku-5-5)."""
    pairs = [(tier, wf.model_for(tool, tier).lower()) for tool in wf.enabled_tools() for tier in wf.TIERS]
    m = model.lower()
    return (next((t for t, a in pairs if a == m), None)
            or next((t for t, a in pairs if re.search(rf"(^|[-_ ]){re.escape(a)}($|[-_ ])", m)), None))


def expected_tier(step: str | None) -> str | None:
    if not step:
        return None
    return wf.workflow().get("commands", {}).get(step, {}).get("tier")


def main_model(seg: dict) -> str:
    return max(seg["models"], key=lambda m: seg["models"][m]["output"])


# ---------------------------------------------------------------- output

def collect(since: dt.date, until: dt.date) -> tuple[list[dict], list[dict]]:
    """Rows (one per workflow command of a session) and the sessions they come from."""
    sessions, rows = [], []
    for s in claude_sessions() + codex_sessions():
        segs = [g for g in s["segments"] if g["models"] and g["start"] and since <= g["start"].date() <= until]
        if not segs:
            continue
        sessions.append(s)
        whole = len([g for g in s["segments"] if g["models"]]) == 1
        for g in segs:
            main = main_model(g)
            tier, main_tier = expected_tier(g["step"]), tier_of(main)
            rows.append({**g, "tool": s["tool"], "session": s["id"], "main": main, "tier": tier, "main_tier": main_tier,
                         "mismatch": bool(tier and main_tier and tier != main_tier), "over": g["peak"] > PEAK_LIMIT,
                         "cost": s["cost"] if whole else None, "lines": s["lines"] if whole else None})
    return sorted(rows, key=lambda r: r["start"]), sessions


def per_model(rows: list[dict], sessions: list[dict]) -> dict[str, dict]:
    models: dict[str, dict] = {}
    for r in rows:
        for name, m in r["models"].items():
            t = models.setdefault(name, {"tier": tier_of(name), "calls": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost": None})
            for k in ("calls", "input", "output", "cache_write", "cache_read"):
                t[k] += m[k]
    for s in sessions:  # cost per model is recorded per session (Claude Code); sessions straddling the period count whole
        for name, c in s["cost_models"].items():
            if name in models and c is not None:
                models[name]["cost"] = (models[name]["cost"] or 0) + c
    calls = sum(m["calls"] for m in models.values()) or 1
    cost = sum(m["cost"] or 0 for m in models.values())
    for m in models.values():
        m["call_share"] = m["calls"] / calls
        m["cost_share"] = (m["cost"] or 0) / cost if cost else None
    return models


def per_tier(models: dict[str, dict]) -> dict[str, dict]:
    tiers: dict[str, dict] = {}
    for m in models.values():
        t = tiers.setdefault(m["tier"] or "?", {"call_share": 0.0, "cost_share": None})
        t["call_share"] += m["call_share"]
        if m["cost_share"] is not None:
            t["cost_share"] = (t["cost_share"] or 0) + m["cost_share"]
    return tiers


def cost_share(rows: list[dict]) -> dict[str, float] | None:
    """Share of the main-context weighted cost per tool-result kind, fixed prefix and output (Claude Code rows only)."""
    total = sum(r["context_cost"]["total"] for r in rows)
    return {k: sum(r["context_cost"][k] for r in rows) / total for k in KINDS} if total else None


def prefix(sessions: list[dict]) -> dict:
    """Median first-call context per tool and the repository's always-loaded share of it."""
    repo, tools = sum(wf.prefix_tokens().values()), {}
    for t in sorted({s["tool"] for s in sessions}):
        firsts = [s["first"] for s in sessions if s["tool"] == t and s["first"]]
        if firsts:
            med = statistics.median(firsts)
            tools[t] = {"sessions": len(firsts), "first_call_median": med, "repo_share": repo / med}
    return {"repo_tokens": repo, "tools": tools}


def _n(v: int) -> str:
    return f"{v / 1e6:.2f}M" if v >= 1e6 else f"{v / 1e3:.1f}k" if v >= 1e3 else str(v)


def _usd(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def render(rows: list[dict], sessions: list[dict], since: dt.date, until: dt.date) -> str:
    by_tool = {t: sum(s["tool"] == t for s in sessions) for t in ("claude-code", "codex")}
    out = [f"# Agent usage — {since} → {until}", "",
           f"Sources: claude-code {by_tool['claude-code']} sessions, codex {by_tool['codex']} sessions "
           "(local logs of this repository). Copilot, Cursor: no local logs. One row per workflow command; built-ins (/clear, /compact, …) ignored.", ""]
    if not rows:
        return "\n".join(out + ["No sessions in the period."])
    out += ["| Start | Tool | Step | Step tier | Main model (tier) | Peak context | Prompts | Interrupts | Rejected | Large reads blocked | Output tok | Lines +/− | Cost USD |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['start']:%m-%d %H:%M} | {r['tool']} | {r['step'] or '—'} | {r['tier'] or '—'} "
                   f"| {r['main']} ({r['main_tier'] or '?'}){' ✗' if r['mismatch'] else ''} | {_n(r['peak'])}{' ⚠' if r['over'] else ''} "
                   f"| {r['prompts']} | {r['interrupts']} | {r['rejected']} | {r['large_reads']} | {_n(sum(m['output'] for m in r['models'].values()))} "
                   f"| {'+%d/−%d' % r['lines'] if r['lines'] else '—'} | {_usd(r['cost'])} |")
    models = per_model(rows, sessions)
    out += ["", "| Model | Tier | Calls (share) | Input tok | Output tok | Cache write tok | Cache read tok | Cost USD (share) |",
            "|---|---|---|---|---|---|---|---|"]
    for name, t in sorted(models.items(), key=lambda kv: -kv[1]["calls"]):
        out.append(f"| {name} | {t['tier'] or '?'} | {t['calls']} ({_pct(t['call_share'])}) | {_n(t['input'])} | {_n(t['output'])} "
                   f"| {_n(t['cache_write'])} | {_n(t['cache_read'])} | {_usd(t['cost'])} ({_pct(t['cost_share'])}) |")
    tiers = per_tier(models)
    out += ["", "Per tier: " + " · ".join(f"{k} {_pct(v['call_share'])} of calls, {_pct(v['cost_share'])} of cost" for k, v in sorted(tiers.items()))]
    share = cost_share(rows)
    if share:
        out += [f"Context cost share (main context, Claude Code; full reads > {read_limit()} lines): "
                + " · ".join(f"{label} {share[k]:.1%}" for k, label in KINDS.items())]
    pre = prefix(sessions)
    out += [f"Fixed prefix: first-call context median {_n(p['first_call_median'])} tokens ({t}, {p['sessions']} session{'s' * (p['sessions'] != 1)}), "
            f"of which this repository ~{_n(pre['repo_tokens'])} ({_pct(p['repo_share'])}): see docs/GUIDE.md § 9.1 Trim your tool prefix"
            for t, p in pre["tools"].items()]
    costs = [s["cost"] for s in sessions if s["cost"] is not None]
    out += [f"Totals: {len(sessions)} sessions, {len(rows)} commands · {sum(r['prompts'] for r in rows)} prompts · "
            f"{sum(r['interrupts'] for r in rows)} interrupts · {sum(r['rejected'] for r in rows)} rejected tool calls · {sum(r['large_reads'] for r in rows)} large reads blocked · "
            f"cost {_usd(sum(costs)) if costs else '—'} USD ({len(costs)}/{len(sessions)} sessions with recorded cost) · "
            f"tier mismatches (✗): {sum(r['mismatch'] for r in rows)} · over {_n(PEAK_LIMIT)} context (⚠): {sum(r['over'] for r in rows)}"]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--since", type=dt.date.fromisoformat)
    ap.add_argument("--until", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    since = a.since or a.until - dt.timedelta(days=a.days)
    rows, sessions = collect(since, a.until)
    if a.json:
        models = per_model(rows, sessions)
        print(json.dumps({"rows": [{**r, "start": r["start"].isoformat(), "end": r["end"].isoformat() if r["end"] else None} for r in rows],
                          "models": models, "tiers": per_tier(models), "cost_share": cost_share(rows), "prefix": prefix(sessions)}, indent=2))
    else:
        print(render(rows, sessions, since, a.until))


if __name__ == "__main__":
    main()
