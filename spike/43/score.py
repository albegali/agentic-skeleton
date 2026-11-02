"""Spike #43: ground truth from the code (AST / regex) and a strict score of each worker answer.
Usage: python3 -I score.py <repo root> <result.json>…
An item counts as found when its name appears in the answer; as exact when the right line number appears on the same line.
"""
import ast
import json
import os
import re
import sys

FILES = ["tools/wf.py", "tools/check_workflow.py", "tools/next_step.py", "tools/gates.py", "tools/gate_guard.py", "tools/context.py"]


def q1(root):
    out = []
    for f in FILES:
        tree = ast.parse(open(os.path.join(root, f)).read())
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            own = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
            if any(c.args and isinstance(c.args[0], ast.List) and c.args[0].elts and isinstance(c.args[0].elts[0], ast.Constant)
                   and c.args[0].elts[0].value == "git" for c in own):
                out.append((fn.name, f, fn.lineno))
    return out


def q2(root):
    rx = re.compile(r"project\(\)\.get\(\"(\w+)\".*?\)\.get\(\"(\w+)\"(?:,\s*([^)]*))?\)")
    out = []
    for f in FILES:
        for i, line in enumerate(open(os.path.join(root, f)), 1):
            for m in rx.finditer(line):
                out.append((f"{m.group(1)}.{m.group(2)}", f, i))
    return out


def q3(root):
    out = []
    for i, line in enumerate(open(os.path.join(root, "tools/gate_guard.py")), 1):
        for m in re.finditer(r'"((?:no |never |approvals |trunk-based|secrets:)[^"]+)"\)', line):
            out.append((m.group(1), "tools/gate_guard.py", i))
    return out


def score(items, answer):
    lines = answer.splitlines()
    found = exact = 0
    for name, _f, ln in items:
        key = name[:40]
        hits = [l for l in lines if key in l]
        found += bool(hits)
        exact += any(re.search(rf"(?<!\d){ln}(?!\d)", l) for l in hits)
    return found, exact, len(items)


def main():
    root = sys.argv[1]
    truth = {"q1_git": q1(root), "q2_config": q2(root), "q3_deny": q3(root)}
    for q, items in truth.items():
        print(q, len(items), "items:", "; ".join(f"{n} {f.split('/')[-1]}:{l}" for n, f, l in items))
    for path in sys.argv[2:]:
        res = json.load(open(path))
        for q, items in truth.items():
            r = res.get(q, {})
            if "answer" not in r:
                print(res["worker"], q, "ERROR", r.get("error"))
                continue
            found, exact, n = score(items, r["answer"])
            extra = len([l for l in r["answer"].splitlines() if l.strip().startswith(("-", "*", "•"))]) - found
            print(f"{res['worker']:28} {q:10} found {found}/{n}  exact line {exact}/{n}  extra bullets ~{max(extra, 0)}  "
                  f"{r['seconds']}s  out {r['output']} tok  ${r['cost_usd']:.3f}")


if __name__ == "__main__":
    main()
