#!/usr/bin/env python3
"""Pass a human gate: set the approval field and commit it alone, with who and when as commit trailers.

Run by the human, never by an agent (the agent hook blocks it). Usage:
  make approve ID=<ID> GATE=spec|strategy|tuning|deviation:<n>|spike|refined
  make approve GATE=inception FILE=<reference/… | backlog/stories.toml | PLAN.md | ADR file>
  make approve GATE=stack
  python3 tools/approve.py --gate strategy --id PR0101 [--no-commit]

The commit holds only the approved files and carries `Approved-by: <git user>` and `Approved-at: <ISO datetime>`, so
history shows that the approval preceded the code (`make check` with `--git` verifies it for the strategy).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gates  # noqa: E402
import wf  # noqa: E402


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", required=True)
    ap.add_argument("--id", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--no-commit", action="store_true", help="set the field only (no git, or you commit yourself)")
    a = ap.parse_args()
    ident = wf.norm_id(a.id) if a.id else None
    if a.gate not in ("inception", "stack") and not ident:
        sys.exit(f"GATE={a.gate} needs ID=<story ID>")
    name = git("config", "user.name").stdout.strip()
    email = git("config", "user.email").stdout.strip()
    who = name or wf.project().get("project", {}).get("owner", "") or "owner"
    now = dt.datetime.now().astimezone()
    try:
        changed = gates.approve(a.gate, ident, a.file.replace(os.sep, "/") or None, who, now.date().isoformat())
    except ValueError as e:
        sys.exit(f"not approved: {e}")
    print(f"approved {a.gate} {ident or a.file or ''}: {', '.join(changed)}")
    if a.no_commit or git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return
    subject = f"approve({a.gate}): {ident or a.file or 'stack'}"
    trailers = [f"Approved-by: {name} <{email}>" if email else f"Approved-by: {who}", f"Approved-at: {now.isoformat(timespec='seconds')}"]
    r = git("commit", "-m", subject, "-m", "\n".join(trailers), "--", *changed)
    if r.returncode != 0:
        sys.exit(f"field set, commit failed (commit it yourself with the trailers):\n{r.stdout}{r.stderr}")
    print(git("log", "-1", "--format=%h %s").stdout.strip())


if __name__ == "__main__":
    main()
