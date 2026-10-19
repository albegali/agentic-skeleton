"""End-to-end tests of the workflow tools on a temporary copy of the skeleton (stdlib unittest)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(SRC, "tools"))
from init_project import set_key  # noqa: E402

FR = """---
status: {st}
---
# Functional requirements
## Capability
### FR-01 — Create item
- **Statement**: The system shall create items.
- **Priority**: Must
- **UI**: yes
### FR-02 — Export
- **Statement**: The system shall export items.
- **Priority**: Should
## Open questions
"""
NFR = "---\nstatus: {st}\n---\n# NFR\n## Security\n### NFR-01 — Auth\n- **Target**: SSO\n"
STORIES = """status = "{st}"
[[epic]]
id = "EP-01"
name = "Foundations"
description = "x"
[[story]]
id = "DM0101"
epic = "EP-01"
slug = "walking-skeleton"
title = "Walking skeleton"
priority = "Must"
size = "M"
fr = ["FR-01"]
nfr = ["NFR-01"]
deps = []
ac = [["a", "b", "c"]]
[[story]]
id = "DM0102"
epic = "EP-01"
slug = "export"
title = "Export"
priority = "Should"
size = "S"
fr = ["FR-02"]
deps = ["DM0101"]
ac = [["a", "b", "c"]]
"""
PLAN = "---\nstatus: {st}\n---\n# PLAN\n| Sprint | Dates | Goal | Stories |\n|---|---|---|---|\n| S1 | 01/01 – 14/01 | Foundations | DM0101, DM0102 |\n"
ANALYSIS_MD = "---\nartifact_type: analysis\nstatus: workshop-ready\n---\n# Analysis\n## 6. Ambiguities\n- dep note {i}\n## 7. Workshop\n- [High impact] x\n"
REFINED_MD = "---\nartifact_type: refined\nstatus: refined\n---\n# Refined Story\n## 8. Refinement Outcome\n- Story ready for Brief intake\n"
BRIEF_MD = "# BRIEF-{i}\n## Status\nCaptured\n"
SPEC_MD = "# SPEC-{i}\n## References\n- Brief: BRIEF-{i}\n## Status\n{st}\n"
RUN = """# RUN-{i}
## Status
{st}
# 1. Execution Strategy (Agent)
### Plan
- Step 1: {plan}
# 2. Human Approval
- [{ok}] Approved
# 7. Persistence / Reconciliation
- [{ok}] Spec updated
"""


class Repo:
    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="wf-")
        shutil.copytree(SRC, self.dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        self.env = {**os.environ, "WF_ROOT": self.dir}

    def run(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, *args], cwd=self.dir, env=self.env, capture_output=True, text=True)
        if ok and r.returncode != 0:
            raise AssertionError(f"{args} failed:\n{r.stdout}\n{r.stderr}")
        return r

    def write(self, p: str, t: str) -> None:
        full = os.path.join(self.dir, p)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(t)

    def read(self, p: str) -> str:
        with open(os.path.join(self.dir, p), encoding="utf-8") as f:
            return f.read()

    def next(self, *a: str) -> dict:
        return json.loads(self.run("tools/next_step.py", "--json", *a).stdout)

    def toml_set(self, f: str, section: str, key: str, value) -> None:
        self.write(f, set_key(self.read(f), section, key, value))

    def init(self) -> None:
        self.run("tools/init_project.py", "--name", "Demo", "--prefix", "DM", "--language", "it", "--owner", "PO")

    def through_inception(self) -> None:
        self.init()
        self.write("reference/product/vision.md", "---\nstatus: approved\n---\n# Vision\n")
        self.write("reference/product/functional-requirements.md", FR.format(st="approved"))
        self.write("reference/product/non-functional-requirements.md", NFR.format(st="approved"))
        self.write("reference/product/mockup-reference.md", "---\nstatus: approved\n---\n| a | renderA | FR-01 |\n")
        self.write("reference/architecture/architecture.md", "---\nstatus: approved\n---\n# Arch\n")
        self.write("reference/architecture/ADR-001-stack.md", "---\nstatus: accepted\n---\n# ADR-001\n")
        self.toml_set("project.toml", "stack", "decided", True)
        self.write("backlog/stories.toml", STORIES.format(st="approved"))
        self.write("PLAN.md", PLAN.format(st="approved"))

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.r = Repo()

    def tearDown(self) -> None:
        self.r.cleanup()

    def test_fresh_skeleton_is_consistent_and_starts_with_kickoff(self):
        self.assertEqual(self.r.next()["step"], "kickoff")
        self.r.run("tools/check_workflow.py")
        self.r.run("tools/render_agents.py", "--check")

    def test_init_project_updates_settings_and_adapters(self):
        self.r.run("tools/init_project.py", "--name", "Demo", "--prefix", "DM", "--language", "it", "--tools", "claude-code,codex")
        p = self.r.read("project.toml")
        self.assertIn('id_prefix = "DM"', p)
        self.assertIn('language = "it"', p)
        self.assertIn("initialized = true", p)
        self.assertIn("# story IDs", p)  # comments preserved
        self.assertIn("DM0101", self.r.read("inception/templates/stories.toml"))
        self.assertFalse(os.path.exists(os.path.join(self.r.dir, ".cursor/commands/next.md")))
        self.assertTrue(os.path.exists(os.path.join(self.r.dir, ".codex/prompts/next.md")))
        self.r.run("tools/check_workflow.py")
        bad = self.r.run("tools/init_project.py", "--name", "x", "--prefix", "toolong", ok=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_inception_gates_in_order(self):
        r = self.r
        r.init()
        self.assertEqual(r.next()["step"], "kickoff")
        r.write("reference/product/vision.md", "---\nstatus: draft\n---\n")
        n = r.next()
        self.assertEqual((n["step"], n["after"]), ("approve", "kickoff"))
        r.write("reference/product/vision.md", "---\nstatus: approved   # draft | approved\n---\n")
        self.assertEqual(r.next()["step"], "requirements")
        r.write("reference/product/functional-requirements.md", FR.format(st="approved"))
        r.write("reference/product/non-functional-requirements.md", NFR.format(st="draft"))
        self.assertEqual(r.next()["step"], "approve")
        r.write("reference/product/non-functional-requirements.md", NFR.format(st="approved"))
        self.assertEqual(r.next()["step"], "mockup")
        r.toml_set("project.toml", "inception", "mockup", False)
        self.assertEqual(r.next()["step"], "architecture")
        r.write("reference/architecture/architecture.md", "---\nstatus: approved\n---\n")
        r.write("reference/architecture/ADR-001-stack.md", "---\nstatus: proposed\n---\n")
        n = r.next()
        self.assertEqual(n["step"], "approve")
        self.assertIn("reference/architecture/ADR-001-stack.md", n["files"])
        r.write("reference/architecture/ADR-001-stack.md", "---\nstatus: accepted\n---\n")
        self.assertEqual(r.next()["files"], ["project.toml [stack] decided = true"])
        r.toml_set("project.toml", "stack", "decided", True)
        self.assertEqual(r.next()["step"], "backlog")
        r.write("backlog/stories.toml", STORIES.format(st="draft"))
        self.assertEqual(r.next()["step"], "approve")
        r.write("backlog/stories.toml", STORIES.format(st="approved"))
        self.assertEqual(r.next()["step"], "plan")
        r.write("PLAN.md", PLAN.format(st="approved"))
        n = r.next()
        self.assertEqual((n["phase"], n["step"], n["ids"]), ("delivery", "analysis", ["DM0101", "DM0102"]))
        self.assertEqual(n["command"], "/analysis DM0101 DM0102")
        self.assertEqual(n["models"]["claude-code"], "sonnet")

    def test_story_chain_to_closure(self):
        r = self.r
        r.through_inception()
        i = "DM0101"
        r.write(f"analysis/20-analysis/ANALYSIS_{i}_walking_skeleton.md", ANALYSIS_MD.format(i=i))
        r.write("analysis/20-analysis/ANALYSIS_DM0102_export.md", ANALYSIS_MD.format(i="DM0102"))
        self.assertEqual(r.next()["step"], "human-gate")
        r.write(f"analysis/30-refined/REFINED_{i}_walking_skeleton.md", REFINED_MD)
        self.assertEqual((r.next()["step"], r.next()["ids"]), ("brief-spec", [i]))
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Draft"))
        self.assertEqual(r.next(i)["step"], "spec-approval")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Ready"))
        self.assertEqual(r.next()["step"], "run-strategy")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Draft", plan="build", ok=" "))
        self.assertEqual(r.next(i)["step"], "run-approval")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Executing", plan="build", ok="x"))
        self.assertEqual(r.next()["step"], "execute")
        r.run("tools/check_workflow.py")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Closed", plan="build", ok="x"))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        self.assertEqual(r.next(i)["step"], "done")
        self.assertEqual(r.next("DM0102")["step"], "workshop")
        r.run("tools/check_workflow.py")

    def test_check_detects_errors(self):
        r = self.r
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('deps = []', 'deps = ["DM0102"]').replace('fr = ["FR-02"]', 'fr = ["FR-09"]'))
        r.write("delivery/30-runs/RUN-DM0101.md", RUN.format(i="DM0101", st="Executing", plan="x", ok=" "))
        out = r.run("tools/check_workflow.py", ok=False)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("dependency cycle", out.stdout)
        self.assertIn("unknown FR-09", out.stdout)
        self.assertIn("without recorded approval", out.stdout)
        self.assertIn("SPEC-DM0101 missing", out.stdout)

    def test_stale_adapter_detected(self):
        with open(os.path.join(self.r.dir, ".claude/commands/next.md"), "a") as f:
            f.write("manual edit\n")
        out = self.r.run("tools/check_workflow.py", ok=False)
        self.assertIn("stale adapter", out.stdout)
        self.r.run("tools/render_agents.py")
        self.r.run("tools/check_workflow.py")

    def test_context_extracts_only_cited_sections(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        self.assertTrue(os.path.exists(os.path.join(r.dir, "analysis/10-stories/STORY_DM0102_export.md")))
        r.write("analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md", ANALYSIS_MD.format(i="DM0101"))
        out = r.run("tools/context.py", "analysis", "DM0102").stdout
        self.assertIn("analysis/10-stories/STORY_DM0102_export.md", out)
        self.assertIn("### FR-02 — Export", out)
        self.assertNotIn("FR-01 — Create item", out)
        self.assertIn("Dependency DM0101", out)
        self.assertIn("dep note DM0101", out)
        self.assertNotIn("[High impact] x\n\n### FR", out.split("Dependency")[0])
        idx = r.run("tools/context.py", "--index", "reference/product/functional-requirements.md").stdout
        self.assertIn("### FR-02 — Export", idx)
        self.assertNotIn("Statement", idx)
        warn = r.run("tools/context.py", "analysis").stdout
        self.assertIn("needs story IDs", warn)

    def test_context_lists_cited_files_and_architecture_sections(self):
        r = self.r
        r.through_inception()
        r.write("reference/architecture/architecture.md", "---\nstatus: approved\n---\n# Arch\n## 5. Security\nsec body\n## 6. Observability\nhealth body\n## 7. Build\n")
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace(
            'ac = [["a", "b", "c"]]', 'ac = [["a", "b", "c"]]\nnotes = "Health per architecture §6. Tokens per reference/product/mockup-reference.md and reference/product/missing.md."', 1))
        r.run("tools/gen_backlog.py")
        out = r.run("tools/context.py", "analysis", "DM0101").stdout
        self.assertIn("- read reference/product/mockup-reference.md (", out)
        self.assertIn("- reference/product/missing.md: missing", out)
        self.assertIn("### architecture §6", out)
        self.assertIn("health body", out)
        self.assertNotIn("sec body", out)

    def test_gen_backlog_regenerates_stories_and_reports_drift(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        r.write("analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md", ANALYSIS_MD.format(i="DM0101"))
        self.assertIn("Story written 0, unchanged 2", r.run("tools/gen_backlog.py").stdout)
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('title = "Walking skeleton"', 'title = "Skeleton v2"', 1)
                .replace('title = "Export"', 'title = "Export v2"', 1))
        out = r.run("tools/gen_backlog.py").stdout
        self.assertIn("Story written 2, unchanged 0", out)
        self.assertIn("Changed after Analysis (align Analysis/Refined Story): DM0101\n", out)
        self.assertIn("# Skeleton v2", r.read("analysis/10-stories/STORY_DM0101_walking_skeleton.md"))
        r.write("analysis/10-stories/STORY_DM0102_export.md", "# Hand-written story\n")
        out = r.run("tools/gen_backlog.py").stdout
        self.assertIn("hand-written, not overwritten: DM0102", out)
        self.assertEqual("# Hand-written story\n", r.read("analysis/10-stories/STORY_DM0102_export.md"))
        self.assertIn("| DM0101 |", r.read("analysis/output/consolidated/backlog_overview.md"))
        deps = r.run("tools/gen_backlog.py", "--deps").stdout
        self.assertIn("DM0102 [EP-01 Should S ] Export v2 ← DM0101", deps)

    def test_kickoff_sources_and_design_reach_the_budgets(self):
        r = self.r
        r.write("docs/brief.md", "# Brief\nWhy now.\n")
        r.write("docs/proto.html", "<title>Proto</title><h1>Home</h1><div><h2>Orders <b>list</b></h2></div>")
        r.run("tools/init_project.py", "--name", "Demo", "--prefix", "DM", "--sources", "docs/brief.md", "docs/proto.html",
              "--design", "docs/proto.html")
        p = r.read("project.toml")
        self.assertIn('sources = ["docs/brief.md"]', p)
        self.assertIn('design = "docs/proto.html"', p)
        self.assertIn("# kickoff sources", p)  # comment kept
        req = r.run("tools/context.py", "requirements").stdout
        self.assertIn("- docs/brief.md (", req)
        self.assertNotIn("proto.html", req)
        mock = json.loads(r.run("tools/context.py", "mockup", "--json").stdout)
        self.assertEqual(mock["design"], "docs/proto.html")
        self.assertIn("docs/brief.md", [x["path"] for x in mock["read"]])
        self.assertGreater(mock["tokens"], 0)
        self.assertEqual(r.run("tools/context.py", "--index", "docs/proto.html").stdout.split("\n")[:3],
                         ["title: Proto", "# Home", "## Orders list"])
        os.remove(os.path.join(r.dir, "docs/brief.md"))
        self.assertIn("source not found: docs/brief.md", r.run("tools/check_workflow.py").stdout)
        self.assertNotEqual(r.run("tools/init_project.py", "--name", "x", "--prefix", "DM", "--sources", "nope.md", ok=False).returncode, 0)

    def test_json_contract(self):
        r = self.r
        r.through_inception()
        r.write("analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md", ANALYSIS_MD.format(i="DM0101"))
        n = r.next()
        self.assertEqual(n["schema"], 1)
        self.assertEqual({s["id"]: s["stage"] for s in n["stories"]}, {"DM0101": "workshop", "DM0102": "analysis"})
        chk = json.loads(r.run("tools/check_workflow.py", "--json").stdout)
        self.assertTrue(chk["ok"])
        self.assertEqual(chk["counts"]["stories"], 2)
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('fr = ["FR-02"]', 'fr = ["FR-09"]'))
        bad = r.run("tools/check_workflow.py", "--json", ok=False)
        self.assertEqual(bad.returncode, 1)
        self.assertIn({"level": "error", "area": "backlog", "message": "DM0102: unknown FR-09"}, json.loads(bad.stdout)["issues"])
        bl = json.loads(r.run("tools/gen_backlog.py", "--json").stdout)
        self.assertEqual(bl["stories"][0]["artifacts"]["analysis"], "analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md")
        self.assertIsNone(bl["stories"][1]["artifacts"]["spec"])
        self.assertFalse(os.path.exists(os.path.join(r.dir, "analysis/10-stories/STORY_DM0102_export.md")))  # --json writes nothing
        r.write("backlog/stories.toml", STORIES.format(st="approved"))
        r.run("tools/gen_backlog.py")
        ctx = json.loads(r.run("tools/context.py", "analysis", "DM0102", "--json").stdout)
        self.assertEqual([s["ref"] for s in ctx["sections"]], ["FR-02"])
        self.assertEqual(ctx["dependencies"][0]["id"], "DM0101")
        rm = json.loads(r.run("tools/context.py", "--repo-map", "--json").stdout)
        self.assertIn("tools/wf.py", rm["source_sizes"])
        self.assertIn("languages", rm)

    def test_rename_id(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        r.run("tools/rename_id.py", "DM0102", "DM0199")
        self.assertIn('id = "DM0199"', r.read("backlog/stories.toml"))
        self.assertTrue(os.path.exists(os.path.join(r.dir, "analysis/10-stories/STORY_DM0199_export.md")))
        self.assertIn("DM0199", r.read("PLAN.md"))


LEGACY = {  # a 10-year-old AngularJS frontend, no backend, its own rules and tooling
    "bower.json": '{"name": "legacy", "dependencies": {"angular": "1.5.8"}}',
    "Gruntfile.js": "module.exports = function (grunt) {};\n",
    "app/index.html": "<html ng-app='legacy'></html>\n",
    "app/scripts/app.js": "angular.module('legacy', []);\n" * 30,
    "app/scripts/controllers/orders.js": "angular.module('legacy').controller('OrdersCtrl', function () {});\n",
    "test/spec/orders.spec.js": "describe('orders', function () {});\n",
    "tools/build.sh": "#!/bin/sh\ngrunt build\n",
    "AGENTS.md": "# Team rules\nUse tabs.\n",
    "CLAUDE.md": "# Our Claude notes\nNever touch app/vendor.\n",
    ".claude/settings.json": '{"permissions": {"allow": ["Bash(grunt test)"]}, "model": "opus"}',
    "Makefile": "test:\n\tgrunt test\ncheck:\n\tgrunt jshint\n",
}


class LaunchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.r = Repo()
        self.r.env["BROWSER"] = "true"  # webbrowser runs `true <url>`: nothing opens

    def tearDown(self) -> None:
        self.r.cleanup()

    def test_run_not_defined(self):
        out = self.r.run("tools/launch.py", ok=False)
        self.assertEqual(out.returncode, 1)
        self.assertIn("run not defined", out.stdout)

    def test_starts_and_waits_for_url(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.r.write("serve_once.py", "import http.server as h, sys\n"
                     f"h.HTTPServer(('127.0.0.1', {port}), h.SimpleHTTPRequestHandler).handle_request()\n")
        self.r.toml_set("project.toml", "stack", "run", f'"{sys.executable}" serve_once.py')
        self.r.toml_set("project.toml", "stack", "url", f"http://127.0.0.1:{port}/")
        out = self.r.run("tools/launch.py", "--timeout", "20")
        self.assertIn(f"http://127.0.0.1:{port}/", out.stdout)

    def test_returns_the_app_exit_code(self):
        self.r.toml_set("project.toml", "stack", "run", f'"{sys.executable}" -c "raise SystemExit(3)"')
        self.assertEqual(self.r.run("tools/launch.py", ok=False).returncode, 3)


class AdoptTest(unittest.TestCase):
    """tools/adopt.py on an existing repository, then the brownfield path of next_step."""

    def setUp(self) -> None:
        self.r = Repo()
        self.t = tempfile.mkdtemp(prefix="app-")
        for p, body in LEGACY.items():
            full = os.path.join(self.t, p)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(body)
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.name", "Pat Owner"], ["config", "user.email", "p@example.com"],
                    ["add", "-A"], ["commit", "-qm", "legacy"]):
            subprocess.run(["git", *cmd], cwd=self.t, check=True, capture_output=True)
        self.env = {k: v for k, v in os.environ.items() if k != "WF_ROOT"}

    def tearDown(self) -> None:
        self.r.cleanup()
        shutil.rmtree(self.t, ignore_errors=True)

    def adopt(self, *a: str, ok: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, "tools/adopt.py", self.t, *a], cwd=self.r.dir, env=self.env, capture_output=True, text=True)
        if ok and r.returncode != 0:
            raise AssertionError(f"adopt failed:\n{r.stdout}\n{r.stderr}")
        return r

    def tool(self, *a: str, ok: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, *a], cwd=self.t, env=self.env, capture_output=True, text=True)
        if ok and r.returncode != 0:
            raise AssertionError(f"{a} failed:\n{r.stdout}\n{r.stderr}")
        return r

    def read(self, p: str) -> str:
        with open(os.path.join(self.t, p), encoding="utf-8") as f:
            return f.read()

    def write(self, p: str, body: str) -> None:
        with open(os.path.join(self.t, p), "w", encoding="utf-8") as f:
            f.write(body)

    def test_dry_run_writes_nothing(self):
        out = self.adopt("--dry-run").stdout
        self.assertIn("dry run", out)
        self.assertFalse(os.path.exists(os.path.join(self.t, "project.toml")))

    def test_adopt_keeps_the_project_files_and_starts_with_onboard(self):
        self.adopt("--name", "Legacy Shop", "--tools", "claude-code,copilot")
        self.assertTrue(self.read("AGENTS.md").startswith("# Team rules\nUse tabs."))
        self.assertIn("agentic-workflow:begin", self.read("AGENTS.md"))
        self.assertTrue(self.read("CLAUDE.md").startswith("# Our Claude notes"))
        self.assertIn("@AGENTS.md", self.read("CLAUDE.md"))
        settings = json.loads(self.read(".claude/settings.json"))
        self.assertEqual(settings["model"], "opus")
        self.assertIn("Bash(grunt test)", settings["permissions"]["allow"])
        self.assertIn("Bash(make next)", settings["permissions"]["allow"])
        self.assertEqual(self.read("tools/build.sh"), LEGACY["tools/build.sh"])
        self.assertTrue(self.read("Makefile").startswith(LEGACY["Makefile"]))
        mk = self.read("workflow.mk")
        self.assertIn("wf-check:", mk)
        self.assertNotIn("\ntest", mk)
        self.assertNotIn("test-tools", mk)
        self.assertNotIn("adopt:", mk)
        self.assertIn("| wf-check |", mk)
        self.assertIn("run /onboard", mk)
        for absent in ("tools/adopt.py", "tools/tests", ".github/workflows", "README.md", ".cursor"):
            self.assertFalse(os.path.exists(os.path.join(self.t, absent)), absent)
        p = self.read("project.toml")
        self.assertIn('origin = "brownfield"', p)
        self.assertIn('id_prefix = "LS"', p)
        self.assertIn('owner = "Pat Owner"', p)
        self.assertIn('test = "make test"', p)
        self.tool("tools/check_workflow.py")
        n = json.loads(self.tool("tools/next_step.py", "--json").stdout)
        self.assertEqual((n["step"], n["models"]["claude-code"]), ("onboard", "opus"))
        m = self.tool("tools/context.py", "onboard").stdout
        self.assertIn("app/scripts/app.js", m)
        self.assertIn("bower.json", m)
        self.assertNotIn("workflow/steps", m.split("## $")[1])
        # rendering again is stable (merge is idempotent)
        self.tool("tools/render_agents.py")
        self.tool("tools/render_agents.py", "--check")
        self.assertEqual(self.read("CLAUDE.md").count("agentic-workflow:begin"), 1)

    def test_brownfield_gates(self):
        self.adopt("--prefix", "LG")
        self.write("reference/product/vision.md", "---\nstatus: approved\n---\n")
        self.write("reference/product/functional-requirements.md", "---\nstatus: approved\n---\n### FR-01 — Orders\n- **Status**: existing\n")
        self.write("reference/architecture/architecture.md", "---\nstatus: draft\n---\n")
        n = json.loads(self.tool("tools/next_step.py", "--json").stdout)
        self.assertEqual((n["step"], n["after"]), ("approve", "onboard"))
        self.write("reference/architecture/architecture.md", "---\nstatus: approved\n---\n")
        self.assertEqual(json.loads(self.tool("tools/next_step.py", "--json").stdout)["files"], ["project.toml [stack] decided = true"])
        self.write("project.toml", set_key(self.read("project.toml"), "stack", "decided", True))
        self.assertEqual(json.loads(self.tool("tools/next_step.py", "--json").stdout)["step"], "backlog")
        self.tool("tools/check_workflow.py")

    def test_conflicts_and_guards(self):
        os.makedirs(os.path.join(self.t, "workflow"))
        self.write("workflow/workflow.toml", "# something else\n")
        subprocess.run(["git", "add", "-A"], cwd=self.t, check=True)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=self.t, check=True)
        out = self.adopt(ok=False)
        self.assertEqual(out.returncode, 2)
        self.assertIn("workflow/workflow.toml", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.t, "project.toml")))
        os.remove(os.path.join(self.t, "workflow/workflow.toml"))
        dirty = self.adopt(ok=False)
        self.assertIn("uncommitted changes", dirty.stderr)
        self.adopt("--allow-dirty")
        self.assertIn("already uses the workflow", self.adopt("--allow-dirty", ok=False).stderr)


# one minimal fixture per kind of software: (files, expected type signal, expected stack test command or "")
KINDS = {
    "legacy web frontend": ({"bower.json": "{}", "Gruntfile.js": "", "app/index.html": "", "app/scripts/app.js": "x\n"}, "Web frontend", ""),
    "backend on any cloud": ({"go.mod": "module x\n", "cmd/api/main.go": "package main\n", "template.yaml": "",
                              "infra/main.tf": "", "api/openapi.yaml": ""}, "Service / backend", "go test ./..."),
    "android app": ({"settings.gradle": "", "build.gradle": "", "gradlew": "", "app/build.gradle": "apply plugin: 'com.android.application'\n",
                     "app/src/main/AndroidManifest.xml": "", "app/src/main/java/x/MainActivity.kt": "class A\n",
                     "app/src/androidTest/java/x/ATest.kt": ""}, "Mobile — Android", "./gradlew test"),
    "ios app": ({"Shop.xcodeproj/project.pbxproj": "", "Shop/AppDelegate.swift": "class A {}\n", "Shop/Info.plist": "",
                 "ShopTests/ShopTests.swift": "", "fastlane/Fastfile": ""}, "Mobile / desktop — Apple (Xcode)", ""),
    "flutter app": ({"pubspec.yaml": "dependencies:\n  flutter:\n", "lib/main.dart": "void main() {}\n",
                     "test/widget_test.dart": ""}, "Mobile — cross-platform", "flutter test"),
    "desktop app": ({"package.json": '{"scripts": {"test": "jest"}}', "electron-builder.yml": "", "src/main.js": "x\n",
                     "installer/setup.iss": ""}, "Desktop", "npm test"),
    "qt desktop": ({"CMakeLists.txt": "", "src/mainwindow.ui": "", "src/main.cpp": "int main(){}\n", "resources.qrc": ""},
                   "Desktop", "ctest --test-dir build"),
    "unity game": ({"ProjectSettings/ProjectVersion.txt": "", "Assets/Scenes/Main.unity": "", "Assets/Scripts/Player.cs": "class P {}\n"},
                   "Game", ""),
    "firmware": ({"platformio.ini": "", "src/main.cpp": "void setup(){}\n", "include/board.h": ""}, "Embedded / firmware / hardware", "pio test"),
    "library": ({"pyproject.toml": "[tool.pytest]\n", "src/lib/__init__.py": "x = 1\n", "MANIFEST.in": "", "tests/test_lib.py": ""},
                "Library / package", "pytest"),
    "cli": ({"Cargo.toml": "", "src/main.rs": "fn main(){}\n"}, "", "cargo test"),
    "data pipeline": ({"dbt_project.yml": "", "models/orders.sql": "select 1\n", "notebooks/explore.ipynb": "{}"},
                      "Data / ML / analytics", ""),
    "infrastructure only": ({"main.tf": "", "modules/net/main.tf": "", "Pulumi.yaml": ""}, "Infrastructure / platform code", ""),
    "browser extension": ({"manifest.json": "{}", "background.js": "x\n", "popup.html": ""}, "Extension / plugin / app manifest", ""),
    "mainframe": ({"src/PAYROLL.cbl": "IDENTIFICATION DIVISION.\n", "jcl/RUN.jcl": ""}, "Enterprise platform", ""),
}


class SoftwareKindsTest(unittest.TestCase):
    """The repository map and the stack guess make no assumption on the kind of software."""

    def test_each_kind_is_recognised_and_mapped(self):
        import repo_map
        for kind, (files, label, test_cmd) in KINDS.items():
            with self.subTest(kind=kind):
                d = tempfile.mkdtemp(prefix="kind-")
                try:
                    for p, body in files.items():
                        full = os.path.join(d, p)
                        os.makedirs(os.path.dirname(full), exist_ok=True)
                        with open(full, "w", encoding="utf-8") as f:
                            f.write(body)
                    found = repo_map.signals(repo_map.codebase(d)[0]).get("type", {})
                    if label:
                        self.assertIn(label, found, f"{kind}: {sorted(found)}")
                    self.assertEqual(repo_map.detect_stack(d)["test"], test_cmd, kind)
                    out = repo_map.repo_map(d)  # renders whatever the kind, with or without git
                    self.assertIn("## Root files", out)
                finally:
                    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
