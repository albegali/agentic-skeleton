#!/usr/bin/env python3
"""Secret scan (stdlib, no dependencies): code and workflow artifacts alike (Briefs, RUNs, journal are data too).

Usage:
  python3 tools/secret_scan.py                 # every tracked and untracked, not ignored file
  python3 tools/secret_scan.py --staged        # the staged content (pre-commit hook: `make hooks`)
  python3 tools/secret_scan.py --branch        # files changed on the story branch against main ($WF_BASE)
  python3 tools/secret_scan.py <path>…         # given files
  add --json for machine output

Exit 1 when something is found. Values are never printed in full. A line that must stay (a documented fake key in a
test) carries `secret-scan: ignore`. In CI, gitleaks runs as well (.github/workflows/workflow-check.yml).
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

RULES = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{30,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")),
    ("JSON web token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("connection string with password", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@'\"]+:([^@\s'\"/]{6,})@[^\s'\"]+", re.I)),
]
ASSIGN = re.compile(r"""(?i)\b([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret)[\w.-]*)\b"""
                    r"""\s*[:=]\s*["']([^"'\s]{12,})["']""")
PLACEHOLDER = re.compile(r"(?i)^(?:<.*>|\$\{.*\}|\{\{.*\}\}|%\(.*\)s|x{4,}|\*{4,}|changeme\w*|example\w*|dummy\w*|fake\w*|test\w*|"
                         r"placeholder\w*|your[_-]\w+|redacted|null|none|true|false)$")
IGNORE = "secret-scan: ignore"
SKIP_DIRS = ("node_modules/", ".venv/", "venv/", "dist/", "build/", ".git/")
MAX_BYTES = 1_000_000


def entropy(s: str) -> float:
    return -sum(c / len(s) * math.log2(c / len(s)) for c in (s.count(ch) for ch in set(s))) if s else 0.0


def mask(v: str) -> str:
    return v[:4] + "…" + f"({len(v)} chars)"


def scan_text(path: str, text: str) -> list[dict]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if IGNORE in line:
            continue
        for name, rx in RULES:
            if m := rx.search(line):
                v = m.group(1) if rx.groups else m.group(0)
                if not PLACEHOLDER.match(v):
                    out.append({"file": path, "line": n, "rule": name, "value": mask(v)})
        for m in ASSIGN.finditer(line):
            v = m.group(2)
            if not PLACEHOLDER.match(v) and entropy(v) >= 3.5 and not any(f["line"] == n and f["file"] == path for f in out):
                out.append({"file": path, "line": n, "rule": f"hard-coded {m.group(1)}", "value": mask(v)})
    return out


def git(*args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=wf.ROOT, capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def targets(argv: list[str]) -> list[tuple[str, str]]:
    """(path, text) pairs to scan."""
    if "--staged" in argv:
        names = (git("diff", "--cached", "--name-only", "--diff-filter=ACMR") or "").split("\n")
        return [(p, git("show", f":{p}") or "") for p in names if p]
    if "--branch" in argv:
        base = os.environ.get("WF_BASE") or "main"
        names = (git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD") or "").split("\n")
        names += (git("ls-files", "-mo", "--exclude-standard") or "").split("\n")  # not committed yet
    elif paths := [a for a in argv if not a.startswith("--")]:
        names = paths
    else:
        names = (git("ls-files", "-co", "--exclude-standard") or "").split("\n")
    out = []
    for p in dict.fromkeys(n for n in names if n):
        full = wf.path(p)
        if p.startswith(SKIP_DIRS) or "/node_modules/" in p or not os.path.isfile(full) or os.path.getsize(full) > MAX_BYTES:
            continue
        with open(full, "rb") as f:
            data = f.read()
        if b"\0" in data[:8192]:
            continue  # binary
        out.append((p, data.decode("utf-8", "replace")))
    return out


def main() -> None:
    argv = sys.argv[1:]
    found = [f for p, t in targets(argv) for f in scan_text(p, t)]
    if "--json" in argv:
        wf.dump_json({"ok": not found, "findings": found})
    else:
        for f in found:
            print(f"{f['file']}:{f['line']}: {f['rule']} {f['value']}")
        print("secret scan: OK" if not found else f"secret scan: {len(found)} finding(s). Remove the secret (and rotate it if it was "
              f"ever committed), or mark a documented fake with `{IGNORE}`.")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
