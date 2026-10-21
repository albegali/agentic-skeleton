#!/usr/bin/env python3
"""Replace a story ID everywhere (file names and contents), e.g. to renumber a story or move it to another epic.

  python3 tools/rename_id.py PR0701 PR0305 [--dry-run]

Both IDs must have the project format (project.toml id_prefix + 4 digits); the old ID must exist in
backlog/stories.toml and the new one must not. Only whole IDs are replaced (PR030 never touches PR0301).
To link an external tracker, keep the workflow ID and record the tracker's own ID as `tracker_id` in stories.toml.
Scope: backlog/, analysis/, delivery/, reference/backlog/, PLAN.md. Uses `git mv` for renamed files when possible.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

SCOPE = ["backlog", "analysis", "delivery", "reference/backlog"]


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    old, new = (wf.norm_id(a) for a in args)
    fmt = re.compile(rf"^{wf.id_rx()}$")
    bad = [x for x in (old, new) if not fmt.match(x)]
    if bad:
        sys.exit(f"not a story ID of this project ({wf.prefix()} + 4 digits): {', '.join(bad)}")
    known = wf.stories()
    if old not in known:
        sys.exit(f"unknown ID: {old} (not in backlog/stories.toml)")
    if new in known:
        sys.exit(f"{new} already exists in backlog/stories.toml: choose a free ID")
    whole = re.compile(rf"(?<![A-Za-z0-9]){re.escape(old)}(?![0-9])")
    files = [wf.path("PLAN.md")] if wf.exists("PLAN.md") else []
    for base in SCOPE:
        for r, _, fs in os.walk(wf.path(base)):
            files += [os.path.join(r, f) for f in fs if f.endswith((".md", ".toml", ".csv"))]
    moves = [(p, os.path.join(os.path.dirname(p), whole.sub(new, os.path.basename(p))))
             for p in files if whole.search(os.path.basename(p))]
    taken = [wf.rel(d) for _, d in moves if os.path.exists(d)]
    if taken:
        sys.exit(f"would overwrite existing files: {', '.join(taken)}")
    changed = [p for p in files if whole.search(wf.read(p))]
    if dry:
        print(f"{old} -> {new} (dry run): {len(changed)} files to update, {len(moves)} to rename")
        for p in changed:
            print(f"  update {wf.rel(p)}")
        for p, d in moves:
            print(f"  rename {wf.rel(p)} -> {wf.rel(d)}")
        return
    for p in changed:
        wf.write(p, whole.sub(new, wf.read(p)))
    for p, d in moves:
        if subprocess.run(["git", "mv", p, d], cwd=wf.ROOT, capture_output=True).returncode != 0:
            os.rename(p, d)
    print(f"{old} -> {new} ({len(changed)} files updated, {len(moves)} renamed)")


if __name__ == "__main__":
    main()
