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
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

COMMAND_RX = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
CODEX_COMMAND_RX = re.compile(r"^(?:/(?:prompts:)?|\$)([\w-]+)")  # /prompts:name (custom prompt) or $name (skill)
REJECTED = "tool use was rejected"
INTERRUPTED = "[Request interrupted by user"
# tool built-ins: never a workflow step, so they neither label nor split a session
BUILTINS = {"clear", "compact", "model", "context", "cost", "help", "status", "config", "login", "logout", "resume", "init",
            "memory", "mcp", "permissions", "exit", "quit", "new", "diff", "review", "approvals", "fast", "usage", "agents", "hooks"}
PEAK_LIMIT = 80_000  # tokens of context in one call: past this, /clear and resume (docs/GUIDE.md)


def _ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone()  # naive timestamps are taken as local time


def _segment(step: str | None = None) -> dict:
    return {"step": step, "start": None, "end": None, "prompts": 0, "interrupts": 0, "rejected": 0, "models": {}, "peak": 0}


def _session(tool: str, sid: str) -> dict:
    return {"tool": tool, "id": sid, "segments": [_segment()], "cost": None, "lines": None, "cost_models": {}}


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


def _results(content) -> list[str]:
    out = []
    for b in content if isinstance(content, list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            c = b.get("content")
            out.append(c if isinstance(c, str) else " ".join(_texts(c)))
    return out


def claude_sessions() -> list[dict]:
    sessions: dict[str, dict] = {}
    seen_msgs: set[str] = set()
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
                if kind == "assistant":
                    key = f'{msg.get("id")}:{d.get("requestId")}'
                    model, u = msg.get("model"), msg.get("usage")
                    if key in seen_msgs or not u or not model or model.startswith("<"):
                        continue
                    seen_msgs.add(key)
                    _seen(seg, _ts(d.get("timestamp")))
                    _add(seg, model, input=u.get("input_tokens"), output=u.get("output_tokens"),
                         cache_write=u.get("cache_creation_input_tokens"), cache_read=u.get("cache_read_input_tokens"))
                    continue
                content = msg.get("content")
                seg["rejected"] += sum(REJECTED in r for r in _results(content))
                if d.get("isMeta") or d.get("isSidechain") or d.get("userType", "external") != "external":
                    continue
                texts = [t.strip() for t in _texts(content)]
                if any(t.startswith(INTERRUPTED) for t in texts):
                    seg["interrupts"] += 1
                    continue
                cmd = next((m.group(1) for t in texts if (m := COMMAND_RX.search(t))), None)
                if cmd and cmd.split(":")[-1] in BUILTINS:
                    continue
                if cmd:
                    seg = _command(s, cmd.split(":")[-1])
                if cmd or any(t and not t.startswith("<") for t in texts):
                    seg["prompts"] += 1
                    _seen(seg, _ts(d.get("timestamp")))
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
    out += ["| Start | Tool | Step | Step tier | Main model (tier) | Peak context | Prompts | Interrupts | Rejected | Output tok | Lines +/− | Cost USD |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['start']:%m-%d %H:%M} | {r['tool']} | {r['step'] or '—'} | {r['tier'] or '—'} "
                   f"| {r['main']} ({r['main_tier'] or '?'}){' ✗' if r['mismatch'] else ''} | {_n(r['peak'])}{' ⚠' if r['over'] else ''} "
                   f"| {r['prompts']} | {r['interrupts']} | {r['rejected']} | {_n(sum(m['output'] for m in r['models'].values()))} "
                   f"| {'+%d/−%d' % r['lines'] if r['lines'] else '—'} | {_usd(r['cost'])} |")
    models = per_model(rows, sessions)
    out += ["", "| Model | Tier | Calls (share) | Input tok | Output tok | Cache write tok | Cache read tok | Cost USD (share) |",
            "|---|---|---|---|---|---|---|---|"]
    for name, t in sorted(models.items(), key=lambda kv: -kv[1]["calls"]):
        out.append(f"| {name} | {t['tier'] or '?'} | {t['calls']} ({_pct(t['call_share'])}) | {_n(t['input'])} | {_n(t['output'])} "
                   f"| {_n(t['cache_write'])} | {_n(t['cache_read'])} | {_usd(t['cost'])} ({_pct(t['cost_share'])}) |")
    tiers = per_tier(models)
    out += ["", "Per tier: " + " · ".join(f"{k} {_pct(v['call_share'])} of calls, {_pct(v['cost_share'])} of cost" for k, v in sorted(tiers.items()))]
    costs = [s["cost"] for s in sessions if s["cost"] is not None]
    out += [f"Totals: {len(sessions)} sessions, {len(rows)} commands · {sum(r['prompts'] for r in rows)} prompts · "
            f"{sum(r['interrupts'] for r in rows)} interrupts · {sum(r['rejected'] for r in rows)} rejected tool calls · "
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
                          "models": models, "tiers": per_tier(models)}, indent=2))
    else:
        print(render(rows, sessions, since, a.until))


if __name__ == "__main__":
    main()
