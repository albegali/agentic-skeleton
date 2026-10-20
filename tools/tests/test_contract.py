"""Contract 1.x tests: every published schema validates its samples, the tools emit valid envelopes.

`jsonschema` is a test/CI dependency only (the tools themselves stay stdlib). Without it these tests are skipped
locally; CI installs it and fails if it is missing (WF_REQUIRE_JSONSCHEMA=1).
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import unittest

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    jsonschema = None

sys.path.insert(0, os.path.dirname(__file__))
from test_workflow import BRIEF_MD, RUN, SPEC_MD, STORIES, Repo  # noqa: E402
import wf  # noqa: E402  (tools/ is on sys.path via test_workflow)

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMAS = os.path.join(SRC, "schemas")
NAMES = ["version", "next", "next-story", "backlog", "check", "plan", "journal", "story"]
C = "1.0"

SAMPLES = {
    "version": {"skeleton": "1.0.0", "contract": C},
    "next": {"step": "kickoff", "owner": "agent", "ids": [], "why": "x", "phase": "inception", "tier": "balanced",
             "models": {"claude-code": "sonnet"}, "command": "/kickoff", "weekly_due": False, "current_sprint": None,
             "next_sprint": None, "human_gates": []},
    "next-story": {"step": "done", "ids": ["AP0101"], "why": "x", "owner": "human", "deps": [], "deps_done": True},
    "backlog": {"status": None, "epics": [], "stories": []},
    "check": {"ok": True, "errors": 0, "warnings": 0, "counts": {"stories": 0}, "issues": []},
    "plan": {"releases": [], "sprints": []},
    "journal": {"context": None, "decisions": [], "learnings": [], "weekly": [], "monthly": []},
    "story": {"id": "AP0101", "artifacts": [{"kind": "story", "path": "analysis/10-stories/STORY_AP0101_x.md", "status": None}],
              "tasks": [{"id": "TSK-AP0101-01"}]},
}

# AP0109 read tools: contract name -> command (before the arguments and --json)
READ_TOOLS = {"backlog": ["tools/gen_backlog.py"], "check": ["tools/check_workflow.py"], "plan": ["tools/wf.py", "plan"],
              "journal": ["tools/wf.py", "journal"], "story": ["tools/wf.py", "story"]}


def load(name: str) -> dict:
    with open(os.path.join(SCHEMAS, f"{name}.schema.json"), encoding="utf-8") as f:
        return json.load(f)


@unittest.skipIf(jsonschema is None and not os.environ.get("WF_REQUIRE_JSONSCHEMA"), "jsonschema not installed")
class ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(jsonschema, "WF_REQUIRE_JSONSCHEMA is set but jsonschema is missing")
        reg = Registry()
        for name in ["envelope", *NAMES]:
            s = load(name)
            reg = reg.with_resource(s["$id"], Resource.from_contents(s))
        self.registry = reg

    def validate(self, name: str, doc: dict) -> None:
        jsonschema.validate(doc, load(name), registry=self.registry, cls=jsonschema.Draft202012Validator)

    def invalid(self, name: str, doc: dict) -> None:
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(name, doc)

    def test_all_schemas_are_listed_and_valid(self) -> None:
        files = sorted(os.path.basename(p)[:-len(".schema.json")] for p in glob.glob(os.path.join(SCHEMAS, "*.schema.json")))
        self.assertEqual(files, sorted(["envelope", *NAMES]))
        for n in files:
            jsonschema.Draft202012Validator.check_schema(load(n))

    def test_samples_validate_in_envelope_and_alone(self) -> None:
        for name, data in SAMPLES.items():
            env = {"contract": C, "tool": name, "data": data}
            self.validate(name, env)
            self.validate("envelope", env)

    def test_extra_fields_are_allowed_and_wrong_types_rejected(self) -> None:
        for name, data in SAMPLES.items():
            self.validate(name, {"contract": "1.7", "tool": name, "data": {**data, "added_later": 1}})
        self.invalid("check", {"contract": C, "tool": "check", "data": {**SAMPLES["check"], "ok": "yes"}})
        self.invalid("version", {"contract": C, "tool": "version", "data": {"skeleton": "1.0.0"}})
        self.invalid("next", {"contract": C, "tool": "backlog", "data": SAMPLES["next"]})  # wrong tool name

    def test_contract_major_is_pinned_to_1(self) -> None:
        # a major bump in the tools must come with new schemas (and this test): the emitted major must match the published one
        self.assertEqual(wf.CONTRACT_VERSION.split(".")[0], "1", "contract major changed: publish new schemas")
        self.assertEqual(C, wf.CONTRACT_VERSION)
        for name, data in SAMPLES.items():
            self.invalid(name, {"contract": "2.0", "tool": name, "data": data})
            self.invalid(name, {"contract": "1", "tool": name, "data": data})
        self.invalid("envelope", {"contract": "2.0", "tool": "x", "data": {}})

    def test_error_envelope(self) -> None:
        err = {"contract": C, "tool": "next", "error": {"code": "boom", "message": "failed"}}
        self.validate("envelope", err)
        self.invalid("envelope", {**err, "data": {}})                       # error and data are exclusive
        self.invalid("envelope", {"contract": C, "tool": "next", "error": {"code": "boom"}})
        self.invalid("envelope", {"contract": C, "tool": "next"})

    def test_empty_states_are_valid(self) -> None:
        for name in ("backlog", "plan", "journal"):
            self.validate(name, {"contract": C, "tool": name, "data": SAMPLES[name]})

    def test_tools_emit_valid_envelopes(self) -> None:
        r = Repo()
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        r.through_inception()
        env = json.loads(r.run("tools/next_step.py", "--json").stdout)
        self.assertEqual((env["contract"], env["tool"]), (C, "next"))
        self.validate("next", env)
        self.validate("envelope", env)
        story = json.loads(r.run("tools/next_step.py", "DM0101", "--json").stdout)
        self.assertEqual(story["tool"], "next-story")
        self.validate("next-story", story)
        self.validate("envelope", story)

    def emit(self, r: Repo, name: str, *args: str, ok: bool = True) -> dict:
        """Run the tool of contract `name` with --json; assert the envelope validates and return it."""
        p = r.run(*READ_TOOLS[name], *args, "--json", ok=ok)
        self.assertEqual(len(p.stdout.strip().splitlines()), 1, p.stdout)
        env = json.loads(p.stdout)
        self.assertEqual((env["contract"], env["tool"]), (C, name))
        self.validate("envelope", env)
        if "data" in env:
            self.validate(name, env)
        return env

    def test_read_tools_emit_valid_envelopes(self) -> None:
        r = Repo()
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('size = "M"', 'size = "M"\nrelease = "R1"'))
        r.write("PLAN.md", r.read("PLAN.md") + "\n| Release | Content | Target | Exit criterion |\n|---|---|---|---|\n"
                "| R1 | EP-01 | 2026-01-31 | Items exported |\n")
        r.write("project-journal/context/kickoff.md", "# Kickoff\nScope.\n")
        r.write("project-journal/weekly/2026-01-09.md", "# Weekly - 2026-01-09\n")
        r.write("project-journal/decisions/use-toml.md", "---\ndate: 2026-01-05\n---\n# Use TOML\n")
        r.write("delivery/10-briefs/BRIEF-DM0101-walking-skeleton.md", BRIEF_MD.format(i="DM0101"))
        r.write("delivery/20-specs/SPEC-DM0101-walking-skeleton.md", SPEC_MD.format(i="DM0101", st="Ready")
                + "# 5. Tasks\n- `TSK-DM0101-01` Server\n- `TSK-DM0101-02` Client\n- `TSK-DM0101-03` Docs\n# 6. Boundaries\n")
        r.write("delivery/30-runs/RUN-DM0101.md", RUN.format(i="DM0101", st="Persisted", plan="x", ok="x")
                + "# 9. Outcome\nTasks completed:\n- TSK-DM0101-01 to TSK-DM0101-02\nTasks deferred:\n- TSK-DM0101-03\n"
                "Goal achieved:\n# 10. Next Steps\n")

        bl = self.emit(r, "backlog")["data"]
        self.assertEqual([s["id"] for s in bl["stories"]], ["DM0101", "DM0102"])
        self.assertEqual(bl["stories"][0]["artifacts"]["spec"], "delivery/20-specs/SPEC-DM0101-walking-skeleton.md")
        self.assertTrue(self.emit(r, "check")["data"]["ok"])
        plan = self.emit(r, "plan")["data"]
        self.assertEqual(plan["releases"], [{"id": "R1", "title": "EP-01", "goal": "Items exported", "target": "2026-01-31",
                                             "sprints": ["S1"]}])
        self.assertEqual(plan["sprints"][0]["release"], "R1")
        j = self.emit(r, "journal")["data"]
        self.assertEqual(j["context"], "# Kickoff\nScope.")
        self.assertEqual(j["weekly"], [{"file": "project-journal/weekly/2026-01-09.md", "title": "Weekly - 2026-01-09",
                                        "date": "2026-01-09"}])
        self.assertEqual(j["decisions"][0]["date"], "2026-01-05")
        st = self.emit(r, "story", "DM0101")["data"]
        self.assertEqual((st["title"], st["stage"]), ("Walking skeleton", "review"))
        self.assertEqual([(a["kind"], a["status"]) for a in st["artifacts"]], [("brief", "Captured"), ("spec", "Ready"), ("run", "Persisted")])
        self.assertEqual([(t["id"], t["title"], t["status"]) for t in st["tasks"]],
                         [("TSK-DM0101-01", "Server", "done"), ("TSK-DM0101-02", "Client", "done"), ("TSK-DM0101-03", "Docs", "deferred")])
        self.assertEqual(self.emit(r, "story", "DM0102")["data"]["tasks"], [])

    def test_read_tools_empty_state(self) -> None:
        r = Repo()  # fresh skeleton: no stories, no PLAN.md, no journal entries
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        self.assertEqual(self.emit(r, "backlog")["data"], {"status": None, "epics": [], "stories": []})
        self.assertEqual(self.emit(r, "plan")["data"], {"releases": [], "sprints": []})
        self.assertEqual(self.emit(r, "journal")["data"],
                         {"context": None, "decisions": [], "learnings": [], "weekly": [], "monthly": []})
        self.emit(r, "check", ok=False)  # valid envelope whatever the exit code of an empty workflow

    def test_read_tools_errors(self) -> None:
        r = Repo()
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('fr = ["FR-02"]', 'fr = ["FR-09"]'))
        p = r.run("tools/check_workflow.py", "--json", ok=False)
        self.assertEqual(p.returncode, 1)  # workflow errors: success envelope, exit 1 kept for scripts
        env = json.loads(p.stdout)
        self.validate("check", env)
        self.assertFalse(env["data"]["ok"])
        self.assertGreater(env["data"]["errors"], 0)
        env = self.emit(r, "story", "ZZ9999", ok=False)
        self.assertEqual(env["error"]["code"], "unknown_id")
        r.write("backlog/stories.toml", "[[story]\nid = ")
        for name, args in (("backlog", ()), ("check", ()), ("plan", ()), ("story", ("DM0101",))):
            p = r.run(*READ_TOOLS[name], *args, "--json", ok=False)
            self.assertNotEqual(p.returncode, 0, name)
            env = json.loads(p.stdout)
            self.assertNotIn("data", env)
            self.assertEqual((env["tool"], env["error"]["code"]), (name, "bad_input"))
            self.validate("envelope", env)

    def test_version_command(self) -> None:
        r = Repo()
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        env = json.loads(r.run("tools/wf.py", "version", "--json").stdout)
        self.validate("version", env)
        self.validate("envelope", env)
        with open(os.path.join(SRC, "tools", "VERSION"), encoding="utf-8") as f:
            self.assertEqual(env["data"]["skeleton"], f.read().strip())
        self.assertIn("contract 1.0", r.run("tools/wf.py", "version").stdout)

    def test_failure_prints_error_envelope_and_exits_non_zero(self) -> None:
        r = Repo()
        self.addCleanup(__import__("shutil").rmtree, r.dir, True)
        r.through_inception()
        p = r.run("tools/next_step.py", "ZZ9999", "--json", ok=False)
        self.assertNotEqual(p.returncode, 0)
        env = json.loads(p.stdout)
        self.assertNotIn("data", env)
        self.assertEqual(env["error"]["code"], "unknown_id")
        self.validate("envelope", env)


if __name__ == "__main__":
    unittest.main()
