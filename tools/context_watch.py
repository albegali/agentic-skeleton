#!/usr/bin/env python3
"""Agent hook (Claude Code PostToolUse): tell the agent when its context passes the checkpoint threshold.

Rendered into .claude/settings.json by tools/render_agents.py. Hooks get no token usage, so the context size is taken
from the session transcript (JSONL): only its last ~256 KB are read, and the last main-chain assistant record with
`message.usage` gives input + cache read + cache write tokens (it may lag one call behind; that is fine).

Above `project.toml [context] checkpoint_tokens` (default 80000, 0 = off) it prints `additionalContext` for the agent:
once per crossing, then again every +20k tokens (state in the system temp dir, keyed by session; never in the
repository). The message follows the session's latest workflow command (free-text follow-ups keep it): an executing `/run`
checkpoints into RUN §3 and asks for `/clear` + `/run <ID>`; another command finishes its output first. Never a gate.
Anything it cannot read or parse produces no output and exit 0: the hook must never break the agent.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402
from gate_guard import last_command  # noqa: E402

DEFAULT_THRESHOLD = 80000
STEP = 20000          # repeat the message every +20k tokens past the last one
TAIL = 256 * 1024     # bytes read from the end of the transcript
STATE_DIR = os.path.join(tempfile.gettempdir(), "agentic-context-watch")
RUN_ID = re.compile(r"^[A-Za-z]+\d{4}$")


def context_tokens(transcript: str | None) -> int | None:
    """Context size of the last main-chain assistant call in the transcript tail; None when none is found."""
    if not transcript or not os.path.isfile(transcript):
        return None
    with open(transcript, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL))
        chunk = f.read()
    lines = chunk.decode("utf-8", "replace").splitlines()
    if size > TAIL and lines:
        lines = lines[1:]  # the first line is cut
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        u = (d.get("message") or {}).get("usage")
        if not isinstance(u, dict):
            continue
        n = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        if n:
            return n
    return None


def threshold() -> int:
    try:
        return int(wf.project().get("context", {}).get("checkpoint_tokens", DEFAULT_THRESHOLD))
    except (ValueError, TypeError):
        return DEFAULT_THRESHOLD


def state_file(event: dict) -> str:
    key = event.get("session_id") or event.get("transcript_path") or "default"
    return os.path.join(STATE_DIR, re.sub(r"[^\w.-]", "_", str(key))[-120:])


def due(event: dict, tokens: int, limit: int) -> bool:
    """True when the message is due (first crossing, or +STEP since the last one); records it. Below the threshold
    (e.g. after /compact) the state is reset, so the next crossing warns again."""
    p = state_file(event)
    if tokens < limit:
        if os.path.exists(p):
            os.remove(p)
        return False
    try:
        with open(p, encoding="utf-8") as f:
            last = int(f.read().strip() or 0)
    except (OSError, ValueError):
        last = 0
    if last and tokens < last + STEP:
        return False
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(str(tokens))
    return True


def executing_run(command: str | None, args: str) -> str | None:
    """Story ID when the latest command is `/run <ID>` (or `/run-deep`) and its RUN strategy is approved and executing."""
    if command not in ("run", "run-deep"):
        return None
    i = (args.split() or [""])[0]
    if not RUN_ID.match(i) or not (p := wf.find("run", i)):
        return None
    with open(p, encoding="utf-8") as f:
        t = f.read()
    if not wf.run_approved(t) or wf.status("run", wf.md_status(t)) not in ("Strategy Approved", "Executing"):
        return None
    return i


def message(tokens: int, limit: int, command: str | None, args: str) -> str:
    head = f"Context ~{tokens // 1000}k tokens (threshold {limit // 1000}k)."
    if i := executing_run(command, args):
        return (f"{head} Finish the current plan step, record it in RUN §3 (`- TSK-…: done · files · tests · next: …`), "
                f"then stop and tell the human: `/clear`, then `/{command} {i}` — the RUN is the memory.")
    if command:
        return f"{head} Finish this step's output, then tell the human to `/clear` before the next command."
    return f"{head} Suggest `/clear` to the human and resuming from `make next`."


def check(event: dict) -> str | None:
    limit = threshold()
    if limit <= 0:
        return None
    transcript = event.get("transcript_path")
    tokens = context_tokens(transcript)
    if tokens is None or not due(event, tokens, limit):
        return None
    command, args = last_command(transcript, sticky=True)  # a follow-up ("ok, continue") stays in the /run
    return message(tokens, limit, command, args)


def main() -> None:
    try:
        event = json.load(sys.stdin)
        msg = check(event) if isinstance(event, dict) else None
    except Exception:  # noqa: BLE001 — never break the agent
        return
    if msg:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    main()
