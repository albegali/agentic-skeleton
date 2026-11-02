#!/usr/bin/env python3
"""Run a command with a short output on success: its WARN lines and last summary lines; on failure, everything.

Usage: python3 tools/quiet.py [--verbose] [--tail N] -- <command…>
Used by `make test-tools` and the [stack] `make setup|test|lint`; `V=1` (make) passes --verbose: the full output, streamed.
Agents pay for every line of tool output on each later call of the session, so a passing run prints a few lines only.
The exit code is the command's.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402,F401  (UTF-8 console)

RULE = re.compile(r"^[\s=_*-]*$")  # blank and separator lines (`-----`, `=====`)


def summary(out: str, tail: int = 2) -> list[str]:
    lines = [ln.rstrip() for ln in out.splitlines() if not RULE.match(ln)]
    last = lines[len(lines) - tail:] if tail > 0 else []
    return [ln for ln in lines[:len(lines) - len(last)] if ln.lstrip().upper().startswith("WARN")] + last


def main(argv: list[str]) -> int:
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        print(__doc__)
        return 2
    opts, cmd = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    tail = int(opts[opts.index("--tail") + 1]) if "--tail" in opts else 2
    if "--verbose" in opts:
        return subprocess.run(cmd).returncode
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.stdout.write(r.stdout)
    elif lines := summary(r.stdout, tail):
        print("\n".join(lines))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
