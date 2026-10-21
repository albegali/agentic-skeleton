#!/usr/bin/env python3
"""Bring this project's workflow files up to the skeleton's latest version (the one sync mechanism; no merges of
skeleton branches, no copied patches).

Usage: make sync-skeleton [SKELETON=<path or git URL>] [ARGS="--dry-run | --keep <file> | --take <file>"]
       python3 tools/sync_skeleton.py [--from <path or URL>] [--dry-run] [--keep <file>]… [--take <file>]…

Source: --from, else project.toml [skeleton] source, else the public skeleton. A URL is cloned (full history: the
upgrade needs the commit of the version this project records) into a temporary directory. Then the skeleton's
tools/adopt.py --upgrade runs a 3-way merge per file (tools/upgrade.py there): nothing is written on conflict.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

DEFAULT = "https://github.com/albegali/agentic-skeleton"


def main() -> None:
    argv = sys.argv[1:]
    src = argv[argv.index("--from") + 1] if "--from" in argv[:-1] else (wf.project().get("skeleton", {}).get("source") or DEFAULT)
    rest = [a for a in argv if a == "--dry-run"]
    for opt in ("--keep", "--take"):  # conflicts resolved by hand / by the skeleton's file (repeatable)
        rest += [x for k, a in enumerate(argv[:-1]) if a == opt for x in (opt, argv[k + 1])]
    with tempfile.TemporaryDirectory(prefix="skeleton-") as tmp:
        if not os.path.isdir(src):
            print(f"cloning {src} …")
            r = subprocess.run(["git", "clone", "-q", src, tmp], capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"cannot clone {src}:\n{r.stderr}")
            src = tmp
        tool = os.path.join(src, "tools", "adopt.py")
        if not os.path.exists(tool):
            sys.exit(f"{src} is not an agentic-skeleton checkout (tools/adopt.py missing)")
        env = {k: v for k, v in os.environ.items() if k != "WF_ROOT"}
        sys.exit(subprocess.run([sys.executable, tool, wf.ROOT, "--upgrade", *rest], env=env).returncode)


if __name__ == "__main__":
    main()
