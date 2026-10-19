#!/usr/bin/env python3
"""Replace a story ID everywhere (file names and contents), e.g. when an external tracker assigns its own IDs.

  python3 tools/rename_id.py PR0701 21890

Scope: backlog/, analysis/, delivery/, reference/backlog/, PLAN.md. Uses `git mv` for renamed files when possible.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

SCOPE = ["backlog", "analysis", "delivery", "reference/backlog"]


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    old, new = sys.argv[1], sys.argv[2]
    files = [wf.path("PLAN.md")] if wf.exists("PLAN.md") else []
    for base in SCOPE:
        for r, _, fs in os.walk(wf.path(base)):
            files += [os.path.join(r, f) for f in fs if f.endswith((".md", ".toml", ".csv"))]
    changed = 0
    for p in files:
        t = wf.read(p)
        if old in t:
            wf.write(p, t.replace(old, new))
            changed += 1
        f = os.path.basename(p)
        if old in f:
            dst = os.path.join(os.path.dirname(p), f.replace(old, new))
            if subprocess.run(["git", "mv", p, dst], cwd=wf.ROOT, capture_output=True).returncode != 0:
                os.rename(p, dst)
    print(f"{old} -> {new} ({changed} files updated)")


if __name__ == "__main__":
    main()
