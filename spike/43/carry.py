"""Spike #43: how much of the main agent's context cost comes from reading large files?

For every main-chain API call of a Claude Code session, the prompt re-sends every earlier tool result still in context
(cache read at 0.1x, first send as cache write at 1.25x). Each tool result is classified, its tokens estimated from its
characters, and charged for every later call until the context is reset (/clear, compaction, a >60% drop).
Usage: python3 -I carry.py <project log dir> [threshold_lines]
"""
import collections
import glob
import json
import os
import re
import shlex
import sys

CHARS_PER_TOKEN = 3.5
PRICE = {"input": 1.0, "cache_write": 1.25, "cache_read": 0.1, "output": 5.0}  # relative to input, Sonnet/Opus/Haiku alike
READERS = {"cat", "head", "tail", "less", "more", "sed", "awk", "nl", "bat"}
COMMAND_RX = re.compile(r"<command-name>/?([\w:-]+)</command-name>")


def kind(name, inp, text, threshold):
    lines = text.count("\n") + 1
    if name == "Read":
        targeted = inp.get("offset") is not None or inp.get("limit") is not None
        if targeted:
            return "read_targeted"
        return "read_large" if lines > threshold else "read_small"
    if name == "Bash":
        cmd = inp.get("command", "")
        try:
            first = shlex.split(cmd.split("|")[0].split("&&")[-1])[0] if cmd.strip() else ""
        except ValueError:
            first = ""
        if os.path.basename(first) in READERS:
            return "bash_read_large" if lines > threshold else "bash_read_small"
        if "context.py" in cmd:
            return "context_py"
        return "bash_other"
    if name in ("Agent", "Task"):
        return "subagent_result"
    return "other"


def session(path, threshold):
    uses, live, out = {}, [], collections.Counter()
    calls, seen, last_ctx, step = 0, set(), 0, None
    steps = collections.Counter()
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("isSidechain"):
            continue
        msg = d.get("message") or {}
        content = msg.get("content")
        if d.get("type") == "user":
            texts = [content] if isinstance(content, str) else [b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
            m = next((COMMAND_RX.search(t) for t in texts if COMMAND_RX.search(t)), None)
            if m:
                cmd = m.group(1).split(":")[-1]
                if cmd in ("clear", "compact"):
                    live = []
                else:
                    step = cmd
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                    c = b.get("content")
                    text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                    name, inp = uses[b["tool_use_id"]]
                    live.append([kind(name, inp, text, threshold), len(text) / CHARS_PER_TOKEN, step])
            continue
        if d.get("type") != "assistant":
            continue
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                uses[b["id"]] = (b["name"], b.get("input") or {})
        u, key = msg.get("usage"), f'{msg.get("id")}:{d.get("requestId")}'
        if not u or key in seen or (msg.get("model") or "<").startswith("<"):
            continue
        seen.add(key)
        ctx = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
        if last_ctx and ctx < 0.4 * last_ctx:
            live = [x for x in live if x[1] < 0]  # compaction or new conversation: earlier results left the context
        last_ctx = ctx
        calls += 1
        cost = sum(PRICE[k] * (u.get(f) or 0) for k, f in
                   (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                    ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")))
        out["_total"] += cost
        steps[step or "-"] += cost
        for x in live:
            # first call after the result: written to cache; later calls: read from cache
            first = len(x) == 3
            out[x[0]] += (PRICE["cache_write"] if first else PRICE["cache_read"]) * x[1]
            out[("tokens", x[0])] += x[1] if first else 0
            if first:
                x.append(True)
    return out, calls, steps


def main():
    root, threshold = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 400
    tot, steps_all, n_calls, n = collections.Counter(), collections.Counter(), 0, 0
    for f in glob.glob(os.path.join(root, "*.jsonl")):
        out, calls, steps = session(f, threshold)
        if calls:
            n += 1
            n_calls += calls
            tot.update(out)
            steps_all.update(steps)
    T = tot["_total"]
    print(f"{root}\nsessions {n}, main-chain calls {n_calls}, threshold {threshold} lines")
    print(f"{'category':18} {'tokens read':>12} {'cost share':>10}")
    for k in ("read_large", "bash_read_large", "read_small", "bash_read_small", "read_targeted", "context_py", "bash_other", "subagent_result", "other"):
        print(f"{k:18} {tot[('tokens', k)]:12,.0f} {tot[k] / T:10.1%}")
    print(f"{'large reads total':18} {tot[('tokens', 'read_large')] + tot[('tokens', 'bash_read_large')]:12,.0f} {(tot['read_large'] + tot['bash_read_large']) / T:10.1%}")
    print("cost share by step:", ", ".join(f"{k} {v / T:.0%}" for k, v in steps_all.most_common(8)))


if __name__ == "__main__":
    main()
