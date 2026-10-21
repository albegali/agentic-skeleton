#!/usr/bin/env python3
"""Agent hook (Claude Code PreToolUse): keep human gates and mode boundaries out of the agent's reach.

Rendered into .claude/settings.json by tools/render_agents.py. Reads the hook event on stdin; exit 2 blocks the tool
call and its stderr goes back to the agent. Blocks:
  - an edit that passes a human gate (RUN §2 Approved, Spec → Ready, status approved/accepted, `decided = true`,
    tuning acceptance, deviation approval), unless the human's latest prompt is the explicit gate command for it
    (`/run <ID> approve`, `/run <ID> approve-deviation <n>`, `/persist <ID>`);
  - a write outside the paths of the current mode (taken from the latest workflow command in the transcript);
  - shell commands that run the human approval, rewrite or delete history and branches, bypass protection, or read
    secrets (.env).
Anything it cannot parse is allowed: the hook is a guard rail, `make check --git` in CI is the backstop.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gates  # noqa: E402
import wf  # noqa: E402

COMMAND = re.compile(r"<command-name>/?([\w:-]+)</command-name>(?:\s*<command-args>(.*?)</command-args>)?", re.S)
# where each mode may write with the edit tools (AGENTS.md §1; analyst exceptions in analysis/AGENTS.md)
MODE_PATHS = {
    "analyst": ["analysis/*", "backlog/stories.toml", "reference/architecture/ADR-*.md", "reference/architecture/architecture.md"],
    "review": ["delivery/30-runs/RUN-*.md"],
    "journal": ["project-journal/*"],
}
AT = r"(?:^|[;&|(\n]|\$\()\s*(?:\w+=\S*\s+)*"  # command position: a mention inside a string or heredoc is not a run
ARGS = r"[^|;&\n]*"
SHELL_DENY = [
    (AT + r"(?:make\s+approve\b|python3?\s+\S*tools/approve\.py\b)", "approvals are run by the human (`make approve …`), never by an agent"),
    (AT + r"git\s+push\b" + ARGS + r"\s(-f|--force|--force-with-lease|--force-if-includes|--delete|-d)\b", "no force push or remote branch deletion"),
    (AT + r"git\s+push\b" + ARGS + r"\s\+\S", "no forced refspec (+branch)"),
    (AT + r"git\s+push\b" + ARGS + r"\s:\S", "no remote branch deletion (:branch)"),
    (AT + r"git\s+branch\b" + ARGS + r"\s(-D|--delete\s+--force)\b", "no forced branch deletion"),
    (AT + r"git\s+(?:switch\s+(?:-c|--create)|checkout\s+-[bB]|branch(?!\s+(?:-[dD]|--delete)\b))\b" + ARGS + r"\s(?:origin/)?(?:release|releases|develop|development|dev|staging|integration|next)(?:[/_.-]\S*)?(?=\s|$)",
     "trunk-based development: no long-lived branches (release/develop/staging/integration); a release is a tag on main"),
    (AT + r"git\s+reset\b" + ARGS + r"\s--hard\b", "no hard reset"),
    (AT + r"git\s+(?:filter-branch|filter-repo)\b|" + AT + r"git\s+rebase\b" + ARGS + r"\s(-i|--root)\b", "no history rewrite"),
    (AT + r"gh\s+pr\s+merge\b" + ARGS + r"\s--admin\b", "never bypass branch protection"),
    (AT + r"gh\s+api\b" + ARGS + r"\bprotection\b", "never change branch protection"),
    (AT + r"(?:cat|less|more|head|tail|source|\.|bat|strings|xxd|od|base64|cp|scp|grep|rg|awk|sed)(?=\s)" + ARGS
     + r"(?:^|[\s<'\"/=])\.env(?:\.(?!example\b|sample\b|template\b)[\w.-]+)?(?=$|[\s'\";|&>)])", "secrets: never read or print .env files"),
]


def last_command(transcript: str | None) -> tuple[str | None, str]:
    """(command, args) of the human's latest prompt when it is a workflow command; (None, "") otherwise."""
    if not transcript or not os.path.exists(transcript):
        return None, ""
    last: tuple[str | None, str] = (None, "")
    with open(transcript, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain") or d.get("userType", "external") != "external":
                continue
            c = (d.get("message") or {}).get("content")
            texts = [c] if isinstance(c, str) else [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
            if not any(t.strip() for t in texts):
                continue  # tool results
            m = next((COMMAND.search(t) for t in texts if COMMAND.search(t)), None)
            last = (m.group(1).split(":")[-1], (m.group(2) or "").strip()) if m else (None, "")
    return last


def mode_of(command: str | None) -> str | None:
    return wf.workflow().get("commands", {}).get(command or "", {}).get("mode") if command else None


def after_edit(tool: str, inp: dict, before: str) -> str | None:
    if tool == "Write":
        return inp.get("content", "")
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old and old not in text:
            return None  # the edit will fail anyway
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


FORCE_DELETE = re.compile(r"^\s*git\s+branch\s+-D\s+([\w][\w./-]*)\s*$")


def merged_by_content(branch: str) -> bool:
    """True when merging `branch` into trunk changes nothing: its content is already in main (squash/rebase merge)."""
    import subprocess

    def git(*a: str) -> str | None:
        try:
            r = subprocess.run(["git", *a], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    if branch in ("main", "master") or git("rev-parse", "--verify", "-q", f"refs/heads/{branch}") is None:
        return False
    trunk = next((t for t in ("origin/main", "main") if git("rev-parse", "--verify", "-q", t) is not None), None)
    merged = git("merge-tree", "--write-tree", trunk, branch) if trunk else None
    return bool(merged) and merged.split()[0] == git("rev-parse", f"{trunk}^{{tree}}")


def deny(reason: str) -> None:
    print(f"Blocked by the workflow guard (tools/gate_guard.py): {reason}", file=sys.stderr)
    sys.exit(2)


def check(event: dict) -> None:
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool == "Bash":
        cmd = inp.get("command", "")
        force = FORCE_DELETE.match(cmd)
        for rx, why in SHELL_DENY:
            if re.search(rx, cmd):
                if why == "no forced branch deletion" and force and merged_by_content(force.group(1)):
                    continue  # squash-merged story branch: `git branch -d` refuses it, but nothing is lost
                deny(f"{why}: `{cmd[:120]}`")
        return
    if tool not in ("Edit", "Write", "MultiEdit"):
        return
    full = inp.get("file_path") or ""
    rel = os.path.relpath(os.path.abspath(full), wf.ROOT).replace(os.sep, "/")
    if rel.startswith(".."):
        return  # outside the repository
    command, args = last_command(event.get("transcript_path"))
    mode = mode_of(command)
    if mode in MODE_PATHS and not any(fnmatch.fnmatch(rel, pat) for pat in MODE_PATHS[mode]):
        deny(f"/{command} runs in {mode} mode, which writes only {', '.join(MODE_PATHS[mode])}; not {rel}")
    before = wf.read(rel) if wf.exists(rel) else ""
    after = after_edit(tool, inp, before)
    if after is None:
        return
    for g in gates.passed(rel, before, after):
        if not gates.allowed_by(g, command, args):
            what = f"{g['gate']} of {g['id']}" if g["id"] else f"{g['gate']} ({rel})"
            deny(f"this edit passes the human gate {what}. Agents never pass a gate: ask the human to run "
                 f"`{gates.hint(g)}`. Leave the field as it is and stop.")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    try:
        check(event)
    except (OSError, ValueError, KeyError):  # never break the agent on a parse problem
        return


if __name__ == "__main__":
    main()
