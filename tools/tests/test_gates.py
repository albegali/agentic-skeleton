"""gates.py contract CLI (contract 1.1): list, approve, request-changes.

Fixtures only: nothing here runs against a real repository. `jsonschema` validates the envelopes when installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_workflow import BRIEF_MD, RUN, SPEC_MD, Repo  # noqa: E402

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    jsonschema = None

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
I = "DM0101"
SPEC = f"delivery/20-specs/SPEC-{I}-walking-skeleton.md"
RUNF = f"delivery/30-runs/RUN-{I}.md"


def schema_validate(env: dict) -> None:
    if jsonschema is None:
        return
    reg = Registry()
    for n in ("envelope", "gates"):
        with open(os.path.join(SRC, "schemas", f"{n}.schema.json"), encoding="utf-8") as f:
            s = json.load(f)
        reg = reg.with_resource(s["$id"], Resource.from_contents(s))
    with open(os.path.join(SRC, "schemas", "gates.schema.json"), encoding="utf-8") as f:
        jsonschema.validate(env, json.load(f), registry=reg, cls=jsonschema.Draft202012Validator)


class GatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.r = Repo()
        self.addCleanup(shutil.rmtree, self.r.dir, True)
        self.r.through_inception()
        self.r.write(f"delivery/10-briefs/BRIEF-{I}-walking-skeleton.md", BRIEF_MD.format(i=I))
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Draft"))

    def git(self, *a: str) -> str:
        return subprocess.run(["git", *a], cwd=self.r.dir, capture_output=True, text=True, check=True).stdout

    def init_git(self) -> None:
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Someone Else")
        self.git("config", "user.email", "else@example.org")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")

    def gates(self, *args: str, ok: bool = True) -> dict:
        p = self.r.run("tools/gates.py", *args, ok=ok)
        self.assertEqual(len(p.stdout.strip().splitlines()), 1, p.stdout)
        env = json.loads(p.stdout)
        self.assertEqual((env["contract"], env["tool"]), ("1.1", "gates"))
        if "data" in env:
            schema_validate(env)
            self.assertNotIn("error", env)
        else:
            self.assertNotEqual(p.returncode, 0)
        return env

    def snapshot(self) -> dict:
        out = {}
        for base, dirs, names in os.walk(self.r.dir):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for n in names:
                with open(os.path.join(base, n), "rb") as f:
                    out[os.path.join(base, n)] = f.read()
        return out

    def error(self, *args: str) -> str:
        before = self.snapshot()
        env = self.gates(*args, ok=False)
        self.assertIn("error", env)
        self.assertNotIn("data", env)
        self.assertEqual(before, self.snapshot(), "an error must not write anything")
        return env["error"]["code"]

    # ------------------------------------------------------------ list

    def test_list_is_one_detection_with_next_step(self) -> None:
        env = self.gates("list", "--json")
        (g,) = env["data"]["gates"]
        self.assertEqual((g["id"], g["gate"], g["artifact"], g["field"], g["current"], g["proposed"], g["story_id"]),
                         (f"spec:{SPEC}", "spec", SPEC, "status", "Draft", "Ready", I))
        self.assertIsInstance(g["age_days"], int)
        self.assertTrue(g["since"])
        human = self.r.next()["human_gates"]
        self.assertEqual(human, [{"id": I, "stage": "spec-approval", "detail": "Spec draft: human review, status → Ready"}])

    def test_list_empty_is_valid(self) -> None:
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Ready"))
        self.assertEqual(self.gates("list", "--json")["data"], {"gates": []})
        self.assertIn("No pending", self.r.run("tools/gates.py", "list").stdout)

    def test_list_inception_and_stack(self) -> None:
        r = Repo()
        self.addCleanup(shutil.rmtree, r.dir, True)
        r.init()
        r.write("reference/product/vision.md", "---\nstatus: draft\n---\n# Vision\n")
        (g,) = json.loads(r.run("tools/gates.py", "list", "--json").stdout)["data"]["gates"]
        self.assertEqual((g["id"], g["current"], g["proposed"]), ("inception:reference/product/vision.md", "draft", "approved"))
        self.assertNotIn("story_id", g)

    # ------------------------------------------------------------ approve

    def test_approve_commits_the_field_alone_as_the_owner(self) -> None:
        self.init_git()
        self.r.write("src/app.py", "print('hi')\n")  # untracked, not part of the approval
        before = self.snapshot()
        env = self.gates("approve", f"spec:{SPEC}", "--expect", "Draft", "--by", "PO")
        d = env["data"]
        self.assertEqual((d["gate"], d["changed"], d["by"]), ("spec", [SPEC], "PO"))
        self.assertIn("-Draft", d["diff"])
        self.assertIn("+Ready", d["diff"])
        self.assertEqual(self.r.read(SPEC), SPEC_MD.format(i=I, st="Ready"))
        self.assertEqual(d["commit"], self.git("log", "-1", "--format=%h").strip())
        body = self.git("log", "-1", "--format=%B")
        self.assertIn("Approved-by: PO", body)
        self.assertIn("Approved-at: ", body)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD").split(), [SPEC])
        changed = [p for p in before if before[p] != self.snapshot().get(p)]
        self.assertEqual([os.path.relpath(p, self.r.dir) for p in changed], [SPEC])

    def test_approve_strategy_same_edit_as_make_approve(self) -> None:
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Ready"))
        self.r.write(RUNF, RUN.format(i=I, st="Draft", plan="build", ok=" "))
        (g,) = [x for x in self.gates("list", "--json")["data"]["gates"] if x["gate"] == "strategy"]
        self.assertEqual((g["current"], g["proposed"]), ("Draft", "Strategy Approved"))
        twin = Repo()
        self.addCleanup(shutil.rmtree, twin.dir, True)
        twin.through_inception()
        twin.write(f"delivery/10-briefs/BRIEF-{I}-walking-skeleton.md", BRIEF_MD.format(i=I))
        twin.write(SPEC, SPEC_MD.format(i=I, st="Ready"))
        twin.write(RUNF, RUN.format(i=I, st="Draft", plan="build", ok=" "))
        twin.run("tools/approve.py", "--gate", "strategy", "--id", I, "--no-commit")
        self.gates("approve", g["id"], "--no-commit")
        for p in (RUNF, SPEC):
            self.assertEqual(self.r.read(p).replace("Reviewer: PO", "Reviewer:"), twin.read(p).replace("Reviewer: PO", "Reviewer:"), p)

    # ------------------------------------------------------------ request-changes

    def test_request_changes_writes_the_draft_value_and_one_gates_line(self) -> None:
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Ready") + "## Gates\n\n- 2026-01-01 — changes requested by PO: old\n")
        # pending again: back to Draft by hand, as a Draft with an older line
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Draft") + "## Gates\n\n- 2026-01-01 — changes requested by PO: old\n")
        env = self.gates("request-changes", f"spec:{SPEC}", "--comment", "Clarify\nAC2", "--expect", "Draft")
        d = env["data"]
        self.assertIsNone(d["commit"])
        self.assertEqual(d["comment"], "Clarify AC2")
        text = self.r.read(SPEC)
        self.assertIn("## Status\nDraft\n", text)
        self.assertNotIn("Ready", text.split("## Gates")[0])
        lines = [x for x in text.split("## Gates")[1].splitlines() if x.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith("changes requested by PO: Clarify AC2"), lines)

    def test_request_changes_on_strategy_never_writes_an_approval(self) -> None:
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Ready"))
        self.r.write(RUNF, RUN.format(i=I, st="Draft", plan="build", ok=" "))
        self.gates("request-changes", f"strategy:{RUNF}", "--comment", "Split step 2")
        run = self.r.read(RUNF)
        self.assertIn("- [ ] Approved", run)
        self.assertIn("## Gates", run)
        self.assertNotIn("Strategy Approved", run)

    def test_request_changes_on_inception_toml_uses_a_comment_block(self) -> None:
        r = Repo()
        self.addCleanup(shutil.rmtree, r.dir, True)
        r.through_inception()
        r.write("PLAN.md", r.read("PLAN.md").replace("status: approved", "status: draft"))
        r.write("backlog/stories.toml", r.read("backlog/stories.toml").replace('status = "approved"', 'status = "draft"'))
        gid = "inception:backlog/stories.toml"
        env = json.loads(r.run("tools/gates.py", "request-changes", gid, "--comment", "Split EP-01").stdout)
        self.assertEqual(env["data"]["gate"], "inception")
        text = r.read("backlog/stories.toml")
        self.assertIn('status = "draft"', text)
        self.assertTrue(text.rstrip().endswith("changes requested by PO: Split EP-01"), text[-120:])
        self.assertIn("\n# Gates\n", text)

    # ------------------------------------------------------------ errors

    def test_errors_never_write(self) -> None:
        self.init_git()
        gid = f"spec:{SPEC}"
        self.assertEqual(self.error("approve", "nope"), "unknown_gate")
        self.assertEqual(self.error("approve", "spec:../outside.md"), "unknown_gate")
        self.assertEqual(self.error("approve", "spec:project.toml"), "unknown_gate")
        self.assertEqual(self.error("approve", f"spec:delivery/20-specs/SPEC-{I}-missing.md"), "unknown_gate")
        self.assertEqual(self.error("approve", gid, "--expect", "Ready"), "stale_gate")
        self.assertEqual(self.error("approve", gid, "--by", "Someone Else"), "bad_input")
        self.assertEqual(self.error("request-changes", gid), "comment_required")
        self.assertEqual(self.error("request-changes", gid, "--comment", "  "), "comment_required")
        self.assertEqual(self.error("approve"), "usage")
        self.assertEqual(self.error("bogus"), "usage")
        self.r.toml_set("project.toml", "project", "owner", "")
        self.assertEqual(self.error("approve", gid), "no_owner")
        self.r.toml_set("project.toml", "project", "owner", "PO")
        self.gates("approve", gid)
        self.assertEqual(self.error("approve", gid), "stale_gate")  # already resolved

    def test_invalid_transitions(self) -> None:
        self.r.write(SPEC, SPEC_MD.format(i=I, st="Ready"))
        self.r.write(RUNF, RUN.format(i=I, st="Tuning", plan="build", ok="x"))
        (g,) = [x for x in self.gates("list", "--json")["data"]["gates"] if x["gate"] == "tuning"]
        self.assertEqual(self.error("request-changes", g["id"], "--comment", "no"), "invalid_transition")
        self.r.write(f"analysis/20-analysis/ANALYSIS_DM0102_x.md", "---\nstatus: draft\n---\n# A\n")
        w = [x for x in self.gates("list", "--json")["data"]["gates"] if x["gate"] == "workshop"]
        for x in w:
            self.assertEqual(self.error("approve", x["id"]), "invalid_transition")

    # ------------------------------------------------------------ bytes, no git

    def test_crlf_and_no_git_are_preserved(self) -> None:
        raw = SPEC_MD.format(i=I, st="Draft").replace("\n", "\r\n")
        with open(os.path.join(self.r.dir, SPEC), "w", encoding="utf-8", newline="") as f:
            f.write(raw)
        g = self.gates("list", "--json")["data"]["gates"][0]
        self.assertTrue(g["since"])  # no git: the file's mtime
        d = self.gates("approve", g["id"])["data"]
        self.assertIsNone(d["commit"])
        with open(os.path.join(self.r.dir, SPEC), "rb") as f:
            self.assertEqual(f.read(), raw.replace("Draft", "Ready").encode())
        raw2 = SPEC_MD.format(i=I, st="Ready").replace("Ready", "Draft").replace("\n", "\r\n")
        with open(os.path.join(self.r.dir, SPEC), "w", encoding="utf-8", newline="") as f:
            f.write(raw2)
        self.gates("request-changes", g["id"], "--comment", "x")
        with open(os.path.join(self.r.dir, SPEC), "rb") as f:
            data = f.read()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn("## Gates".encode(), data)

    # ------------------------------------------------------------ guard

    def test_gate_guard_blocks_agents_from_gate_decisions(self) -> None:
        for cmd, code in ((f"python3 tools/gates.py approve spec:{SPEC}", 2), ("python3 tools/gates.py request-changes x --comment y", 2),
                          ("python3 tools/gates.py list --json", 0)):
            p = subprocess.run([sys.executable, "tools/gate_guard.py"], cwd=self.r.dir, env=self.r.env, capture_output=True, text=True,
                               input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))
            self.assertEqual(p.returncode, code, cmd)


if __name__ == "__main__":
    unittest.main()
