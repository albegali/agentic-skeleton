#!/usr/bin/env python3
"""Claim a story for yourself: its branch, the claim in stories.toml on that branch, optionally a worktree.

Usage:
  make claim ID=<ID> [WORKTREE=1] [ME="<name>"]
  python3 tools/claim.py <ID> [--worktree] [--me <name>] [--no-push] [--force]

Creates `<id-lowercase>-<slug>` from main (`delivery/guide/git.md`), records `claimed_by` / `claimed_at` on the story in
backlog/stories.toml, commits that on the branch and pushes it: the pushed branch is how the team sees the claim
(`make next --me <name>` skips stories claimed by others). `--worktree` checks the branch out in ../<repo>-<id> so
several stories can run side by side, one agent session per worktree.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402


def git(*args: str, cwd: str | None = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd or wf.ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def set_claim(text: str, i: str, who: str, when: str) -> str:
    """stories.toml with claimed_by / claimed_at set on story i (other lines untouched)."""
    blocks = re.split(r"(?m)^(?=\[\[)", text)
    for n, b in enumerate(blocks):
        if b.startswith("[[story]]") and re.search(rf'(?m)^id\s*=\s*"{re.escape(i)}"', b):
            b = re.sub(r'(?m)^claimed_(by|at)\s*=.*\n?', "", b)
            b = re.sub(rf'(?m)^(id\s*=\s*"{re.escape(i)}"[^\n]*\n)', lambda m: f'{m.group(1)}claimed_by = "{who}"\nclaimed_at = "{when}"\n', b, count=1)
            blocks[n] = b
            return "".join(blocks)
    sys.exit(f"{i} not found in backlog/stories.toml")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("id")
    ap.add_argument("--me", default="")
    ap.add_argument("--worktree", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--force", action="store_true", help="claim even if someone else did")
    a = ap.parse_args()
    i = wf.norm_id(a.id)
    st = wf.stories()
    if i not in st:
        sys.exit(f"Unknown ID: {i}")
    me = a.me or git("config", "user.name", check=False) or wf.project().get("project", {}).get("owner", "")
    if not me:
        sys.exit("who are you? set `git config user.name` or pass --me")
    other = wf.claims().get(i)
    if other and not wf.same_person(other["by"], me) and not a.force:
        sys.exit(f"{i} is claimed by {other['by']} ({other['source']}): agree with them, or --force")
    open_deps = [d for d in st[i].get("deps", []) if d in st and not wf.matches(f"delivery/30-runs/RUN-{d}*.md")]
    if open_deps:
        print(f"note: dependencies without a RUN yet: {', '.join(open_deps)} (make next {i})")
    branch = f"{i.lower()}-{st[i].get('slug', 'story')}"
    remote = "origin" in git("remote", check=False).split()
    base = "main"
    if remote:
        git("fetch", "-q", "origin", "main", check=False)
        base = "origin/main" if git("rev-parse", "--verify", "--quiet", "origin/main", check=False) else "main"
    exists = bool(git("rev-parse", "--verify", "--quiet", branch, check=False))
    where = wf.ROOT
    if a.worktree:
        where = os.path.join(os.path.dirname(wf.ROOT), f"{os.path.basename(wf.ROOT)}-{i.lower()}")
        git("worktree", "add", where, branch) if exists else git("worktree", "add", "-b", branch, where, base)
    else:
        if git("status", "--porcelain", "--untracked-files=no"):
            sys.exit("uncommitted changes: commit or stash them first, or use --worktree")
        git("switch", branch) if exists else git("switch", "-c", branch, base)
    path = os.path.join(where, "backlog", "stories.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new = set_claim(text, i, me, dt.date.today().isoformat())
    if new != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        git("commit", "-q", "-m", f"claim({i}): {me}", "--", "backlog/stories.toml", cwd=where)
    if remote and not a.no_push:
        git("push", "-q", "-u", "origin", branch, cwd=where, check=False)
    print(f"{i} claimed by {me} on branch {branch}" + (f" in worktree {where}" if a.worktree else "")
          + (" (pushed)" if remote and not a.no_push else "") + f"\nnext: {'cd ' + where + ' && ' if a.worktree else ''}make next {i}")


if __name__ == "__main__":
    main()
