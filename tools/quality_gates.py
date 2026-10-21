#!/usr/bin/env python3
"""Run the quality gates of project.toml [gates] and write the results into RUN §8 `### Gates` (facts, not ticks).

Usage: make gates ID=<ID>   ·   python3 tools/quality_gates.py <ID> [--no-write] [--json]

Gates: test and lint from [stack]; typecheck, coverage (+ coverage_min), mutation from [gates]; secrets (tools/secret_scan.py
--branch) unless `secrets = false`. Empty commands are skipped. Exit 1 when a gate fails. `make check` refuses to close a
RUN whose `### Gates` has a failing line, or none while gates are configured.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

TIMEOUT = 1800  # seconds per gate
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def configured() -> list[tuple[str, str]]:
    """(gate, command) pairs in run order."""
    p = wf.project()
    stack, g = p.get("stack", {}), p.get("gates", {})
    out = [("test", stack.get("test", "")), ("lint", stack.get("lint", "")), ("typecheck", g.get("typecheck", "")),
           ("coverage", g.get("coverage", "")), ("mutation", g.get("mutation", ""))]
    if g.get("secrets", True):
        out.append(("secrets", f"{sys.executable} tools/secret_scan.py --branch"))
    return [(k, c) for k, c in out if c]


def run(gate: str, cmd: str) -> dict:
    try:
        r = subprocess.run(cmd, shell=True, cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
        out, ok = (r.stdout + r.stderr).strip(), r.returncode == 0
    except subprocess.TimeoutExpired:
        out, ok = f"timed out after {TIMEOUT}s", False
    detail = (out.splitlines() or [""])[-1][:120]
    if gate == "coverage" and ok:
        pcts = PCT.findall(out)
        minimum = float(wf.project().get("gates", {}).get("coverage_min", 0) or 0)
        if not pcts:
            ok, detail = False, "no percentage in the output"
        else:
            value = float(pcts[-1])
            ok, detail = value >= minimum, f"{value:g}% (min {minimum:g}%)"
    return {"gate": gate, "cmd": cmd, "ok": ok, "detail": detail}


def section(results: list[dict]) -> str:
    lines = [f"### Gates", f"> Written by `make gates` on {dt.datetime.now().astimezone().isoformat(timespec='minutes')}; do not edit by hand."]
    lines += [f"- {r['gate']}: `{r['cmd']}` → {'pass' if r['ok'] else 'fail'}" + (f" ({r['detail']})" if r["detail"] else "") for r in results]
    return "\n".join(lines) + "\n"


def write(i: str, results: list[dict]) -> str:
    run_file = wf.one(f"delivery/30-runs/RUN-{i}*.md")
    if not run_file:
        sys.exit(f"RUN-{i} not found")
    t = wf.read(run_file)
    new = section(results)
    if old := wf.heading_section(t, r"^###\s+Gates\b"):
        t = t.replace(old, new.rstrip("\n") + ("\n\n" if old.endswith("\n\n") else "\n"), 1)
    elif gates8 := wf.heading_section(t, r"^#\s+8\."):
        t = t.replace(gates8, gates8.rstrip("\n") + "\n\n" + new + "\n", 1)
    else:
        t = t.rstrip("\n") + "\n\n# 8. Quality Gates Check\n\n" + new
    tests = next((r for r in results if r["gate"] == "test"), None)
    if tests:  # keep the §8 `Tests:` fact in step with the gate
        fact = f" {tests['cmd']} → {'pass' if tests['ok'] else 'fail'}"  # a function replacement: Windows paths hold backslashes
        t = re.sub(r"^(\s*-\s*Tests:)[^\n]*$", lambda m: m.group(1) + fact, t, count=1, flags=re.M)
    wf.write(run_file, t)
    return wf.rel(run_file)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    i = wf.norm_id(args[0])
    gates = configured()
    if not gates:
        sys.exit("no gates configured: set [stack] test/lint (by /architecture) or [gates] in project.toml")
    results = [run(k, c) for k, c in gates]
    if "--json" in sys.argv:
        wf.dump_json({"id": i, "ok": all(r["ok"] for r in results), "gates": results})
    else:
        for r in results:
            print(f"{'pass' if r['ok'] else 'FAIL'}  {r['gate']}: {r['detail']}")
    if "--no-write" not in sys.argv:
        print(f"written to {write(i, results)} §8 Gates") if "--json" not in sys.argv else write(i, results)
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
