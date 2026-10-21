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
if os.environ.get("WF_TEST_TIMEOUT"):  # CI: a hung suite dumps every thread's stack (naming the test) and exits
    import faulthandler
    faulthandler.dump_traceback_later(float(os.environ["WF_TEST_TIMEOUT"]), exit=True)
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


# project state written by the workflow: removed from the copy (README.md and .gitkeep stay), see Repo.fresh
STATE_DIRS = ["analysis/10-stories", "analysis/20-analysis", "analysis/30-refined", "analysis/workshops", "analysis/output",
              "delivery/10-briefs", "delivery/20-specs", "delivery/30-runs", "reference", "backlog", "docs/sources",
              *(f"project-journal/{d}" for d in ("context", "decisions", "learnings", "metrics", "monthly", "risks", "weekly"))]
FRESH_KEYS = [("project", "initialized", False), ("inception", "sources", []), ("inception", "design", ""),
              ("stack", "decided", False), *(("stack", k, "") for k in ("summary", "setup", "test", "lint", "run", "url"))]


class Repo:
    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="wf-")
        shutil.copytree(SRC, self.dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "node_modules"))
        self.env = {**os.environ, "WF_ROOT": self.dir}
        self.fresh()

    def fresh(self) -> None:
        """Reset the copy to a fresh skeleton, so the tests also pass in a repository that already uses the workflow."""
        for d in STATE_DIRS:
            for base, _, names in os.walk(os.path.join(self.dir, d)):
                for n in names:
                    if n not in ("README.md", ".gitkeep"):
                        os.remove(os.path.join(base, n))
        if os.path.exists(os.path.join(self.dir, "PLAN.md")):
            os.remove(os.path.join(self.dir, "PLAN.md"))
        p = self.read("project.toml")
        for section, key, value in FRESH_KEYS:
            p = set_key(p, section, key, value)
        self.write("project.toml", p)

    def run(self, *args: str, ok: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
        try:
            r = subprocess.run([sys.executable, *args], cwd=self.dir, env=self.env, capture_output=True, text=True, encoding="utf-8",
                               timeout=timeout)
        except subprocess.TimeoutExpired as e:
            out = [x.decode("utf-8", "replace") if isinstance(x, bytes) else x or "" for x in (e.stdout, e.stderr)]
            raise AssertionError(f"{args} timed out after {timeout}s:\n{out[0]}\n{out[1]}") from None
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
        env = json.loads(self.run("tools/next_step.py", "--json", *a).stdout)
        assert env["contract"].startswith("1.") and env["tool"] in ("next", "next-story"), env
        return env["data"]

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
        self.assertEqual({s["id"]: s["stage"] for s in n["stories"]}, {"DM0101": "workshop", "DM0102": "analysis"})
        chk = json.loads(r.run("tools/check_workflow.py", "--json").stdout)["data"]
        self.assertTrue(chk["ok"])
        self.assertEqual(chk["counts"]["stories"], 2)
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('fr = ["FR-02"]', 'fr = ["FR-09"]'))
        bad = r.run("tools/check_workflow.py", "--json", ok=False)
        self.assertEqual(bad.returncode, 1)
        self.assertIn({"level": "error", "area": "backlog", "message": "DM0102: unknown FR-09"}, json.loads(bad.stdout)["data"]["issues"])
        bl = json.loads(r.run("tools/gen_backlog.py", "--json").stdout)["data"]
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


class EdgeCaseTest(unittest.TestCase):
    """Malformed or unusual input found by edge-case probing (issue #10)."""

    def setUp(self) -> None:
        self.r = Repo()

    def tearDown(self) -> None:
        self.r.cleanup()

    def test_init_project_rerun_keeps_valid_toml(self):
        r = self.r
        r.run("tools/init_project.py", "--name", 'Acme "Next" Portal', "--prefix", "DM", "--owner", "PO")
        r.run("tools/init_project.py", "--name", "Acme Portal", "--prefix", "DM", "--owner", "PO")
        import tomllib
        self.assertEqual(tomllib.loads(r.read("project.toml"))["project"]["name"], "Acme Portal")
        bad = r.run("tools/init_project.py", "--name", "x", "--prefix", "dm", ok=False)
        self.assertIn("--prefix", bad.stderr)

    def test_frontmatter_parsing(self):
        import wf
        self.assertIsNone(wf.front("---\nstatus:\ntitle: x\n---\n", "status"))  # empty value: not the next line's
        self.assertEqual(wf.front('---\nstatus: "approved"  # note\n---\n', "status"), "approved")
        self.assertEqual(wf.front("---\nstatus: 'refined'\n---\n", "status"), "refined")
        self.assertIsNone(wf.front("# Title\nstatus: approved\n", "status"))  # body line, no frontmatter
        self.assertIsNone(wf.front("---\ntitle: x\n---\nstatus: approved\n", "status"))
        r = self.r
        r.through_inception()
        r.write("reference/product/vision.md", '---\nstatus: "approved"\n---\n# Vision\n')
        self.assertEqual(r.next()["phase"], "delivery")

    def test_code_fences_are_not_headings(self):
        import wf
        fr = "### FR-01 — Install\n- **Statement**: x\n```bash\n# install deps\nmake setup\n```\n- **Priority**: Must\n### FR-02 — Next\n"
        sec = wf.heading_section(fr, r"\bFR-0*1\b")
        self.assertIn("**Priority**: Must", sec)
        self.assertNotIn("FR-02", sec)
        r = self.r
        r.write("notes.md", fr)
        self.assertNotIn("# install deps", r.run("tools/context.py", "--index", "notes.md").stdout)

    def test_fr_number_spellings_are_one_reference(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        r.write("analysis/10-stories/STORY_DM0102_export.md", "# Export\nCites FR-2 and FR-02.\n")
        ctx = json.loads(r.run("tools/context.py", "analysis", "dm0102", "--json").stdout)
        self.assertEqual(ctx["ids"], ["DM0102"])
        self.assertEqual([s["ref"] for s in ctx["sections"]], ["FR-2"])
        self.assertIn("Export", ctx["sections"][0]["text"])

    def test_task_id_ranges(self):
        import wf
        i = "DM0101"
        self.assertEqual(wf.task_ids("TSK-DM0101-01 - 03", i), {f"TSK-{i}-0{n}" for n in (1, 2, 3)})
        self.assertEqual(wf.task_ids("TSK-DM0101-02 to TSK-DM0101-04", i), {f"TSK-{i}-0{n}" for n in (2, 3, 4)})
        self.assertEqual(wf.task_ids("TSK-DM0101-01 – TSK-DM0101-02", i), {f"TSK-{i}-01", f"TSK-{i}-02"})
        self.assertEqual(wf.task_ids("TSK-DM0101-03 — 2 files changed", i), {f"TSK-{i}-03"})

    def test_rename_id_is_whole_word_and_validated(self):
        r = self.r
        r.through_inception()
        r.write("backlog/stories.toml", r.read("backlog/stories.toml").replace("DM0102", "DM0120"))
        r.write("PLAN.md", r.read("PLAN.md").replace("DM0102", "DM0120"))
        r.run("tools/gen_backlog.py")
        self.assertIn("unknown ID", r.run("tools/rename_id.py", "DM0112", "DM0199", ok=False).stderr)
        self.assertIn("not a story ID", r.run("tools/rename_id.py", "DM012", "DM0199", ok=False).stderr)
        self.assertIn("already exists", r.run("tools/rename_id.py", "DM0101", "DM0120", ok=False).stderr)
        self.assertIn("not a story ID", r.run("tools/rename_id.py", "DM0101", "21890", ok=False).stderr)
        before = r.read("backlog/stories.toml")
        self.assertIn("rename analysis/10-stories/STORY_DM0120_export.md", r.run("tools/rename_id.py", "DM0120", "DM0130", "--dry-run").stdout)
        self.assertEqual(r.read("backlog/stories.toml"), before)
        r.run("tools/rename_id.py", "DM0101", "DM0110")
        st = r.read("backlog/stories.toml")
        self.assertIn('id = "DM0110"', st)
        self.assertIn('id = "DM0120"', st)  # DM0101 → DM0110 leaves DM0120 alone
        self.assertTrue(os.path.exists(os.path.join(r.dir, "analysis/10-stories/STORY_DM0110_walking_skeleton.md")))
        r.run("tools/check_workflow.py")

    def test_bad_input_envelopes_name_the_file(self):
        r = self.r
        r.through_inception()
        for content in ("[[story]\nid = ", '[[story]]\nepic = "EP-01"\n'):
            r.write("backlog/stories.toml", content)
            for args, tool in ((["tools/next_step.py", "--json"], "next"), (["tools/next_step.py", "DM0101", "--json"], "next-story"),
                               (["tools/gen_backlog.py", "--json"], "backlog")):
                p = r.run(*args, ok=False)
                self.assertNotEqual(p.returncode, 0, args)
                env = json.loads(p.stdout)
                self.assertEqual((env["tool"], env["error"]["code"]), (tool, "bad_input"))
                self.assertIn("backlog/stories.toml", env["error"]["message"])
            p = r.run("tools/context.py", "analysis", "DM0101", "--json", ok=False)
            self.assertEqual(json.loads(p.stdout)["error"]["code"], "bad_input")

    def test_lowercase_ids_and_refined_outcome_codes(self):
        r = self.r
        r.through_inception()
        r.write("analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md", ANALYSIS_MD.format(i="DM0101"))
        refined = "---\nstatus: refined\n---\n# Refined\n## 8. Refinement Outcome\n- `{}` Storia {}\n"
        r.write("analysis/30-refined/REFINED_DM0101_walking_skeleton.md", refined.format("not-ready", "non pronta"))
        self.assertEqual(r.next("dm-0101")["step"], "workshop")
        r.write("analysis/30-refined/REFINED_DM0101_walking_skeleton.md", refined.format("ready", "pronta per il Brief"))
        self.assertEqual(r.next("dm0101")["step"], "brief-spec")

    def test_run_file_without_suffix_wins(self):
        r = self.r
        r.through_inception()
        r.write("delivery/30-runs/RUN-DM0101.md", RUN.format(i="DM0101", st="Closed", plan="x", ok="x"))
        r.write("delivery/30-runs/RUN-DM0101-addendum.md", RUN.format(i="DM0101", st="Draft", plan="x", ok=" "))
        self.assertEqual(r.next("DM0101")["step"], "done")

    def test_story_sentences_follow_the_project_language(self):
        r = self.r
        r.through_inception()  # language it
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('slug = "export"', 'slug = "export"\nas_a = "PO"\ni_want = "x"\nso_that = "y"'))
        r.run("tools/gen_backlog.py")
        body = r.read("analysis/10-stories/STORY_DM0102_export.md")
        self.assertIn("Come PO, voglio x, in modo da y.", body)
        self.assertIn("Dato a, quando b, allora c.", body)
        self.assertIn("## Acceptance Criteria", body)  # headings stay English

    def test_text_output_on_a_cp1252_console(self):
        r = self.r
        r.through_inception()
        r.env = {**r.env, "PYTHONIOENCODING": "cp1252"}
        self.assertIn("→", r.run("tools/next_step.py").stdout)
        for args in (["tools/next_step.py"], ["tools/context.py", "analysis", "DM0101"], ["tools/check_workflow.py"]):
            r.run(*args)  # no UnicodeEncodeError

    def test_weekly_due(self):
        r = self.r
        r.through_inception()
        self.assertTrue(r.next()["weekly_due"])  # initialized, no weekly yet
        import datetime as dt
        r.write(f"project-journal/weekly/{dt.date.today().isoformat()}.md", "# Week\n")
        self.assertFalse(r.next()["weekly_due"])
        r.write("project-journal/weekly/2000-01-01.md", "# Old\n")  # older files do not count
        self.assertFalse(r.next()["weekly_due"])

    def test_status_values_are_normalised_and_unknown_ones_block(self):
        r = self.r
        r.through_inception()
        i, spec, run = "DM0101", "delivery/20-specs/SPEC-DM0101-walking-skeleton.md", "delivery/30-runs/RUN-DM0101.md"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        for st, want in (("draft", "spec-approval"), ("DRAFT", "spec-approval"), ("**Ready**", "run-strategy"),
                         ("Ready ✅", "run-strategy"), ("Approved", "blocked"), ("Redy", "blocked")):
            r.write(spec, SPEC_MD.format(i=i, st=st))
            n = r.next(i)
            self.assertEqual(n["step"], want, st)
            if want == "blocked":
                self.assertEqual(n["owner"], "human")
                self.assertIn(f"{spec}: unknown status '{st}'", n["why"])
        r.write(spec, SPEC_MD.format(i=i, st="Ready"))
        for st in ("closed", "Closed ✅", "Closed (2026-10-19)", "`Closed`"):
            r.write(run, RUN.format(i=i, st=st, plan="build", ok="x"))
            self.assertEqual(r.next(i)["step"], "done", st)
        r.write(run, RUN.format(i=i, st="Finished", plan="build", ok="x"))
        self.assertEqual(r.next(i)["step"], "blocked")
        self.assertIn("invalid status 'Finished'", r.run("tools/check_workflow.py", ok=False).stdout)

    def test_strategy_and_approval_detection(self):
        r = self.r
        r.through_inception()
        i, run = "DM0101", "delivery/30-runs/RUN-DM0101.md"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Ready"))
        for plan, want in (("…", "run-strategy"), ("(TSK-01): …", "run-strategy"), ("(TSK-01): build the API", "run-approval")):
            r.write(run, RUN.format(i=i, st="Draft", plan=plan, ok=" ").replace("- Step 1: (", "- Step 1 ("))
            self.assertEqual(r.next(i)["step"], want, plan)
        r.write(run, RUN.format(i=i, st="Draft", plan="…", ok=" ") + "\nStrategy ready: yes\n")
        self.assertEqual(r.next(i)["step"], "run-approval")
        r.write(run, RUN.format(i=i, st="Draft", plan="build", ok="X"))
        self.assertEqual(r.next(i)["step"], "execute")  # [X] counts
        prose = RUN.format(i=i, st="Executing", plan="build", ok=" ") + "\n# 9. Outcome\n- [x] Approved by nobody\n"
        r.write(run, prose)  # a ticked "Approved" outside §2 is not an approval
        self.assertIn("without recorded approval", r.run("tools/check_workflow.py", ok=False).stdout)
        r.write(run, RUN.format(i=i, st="Draft", plan="build", ok=" ") + "\n# 9. Outcome\n- [x] Approved by nobody\n")
        self.assertEqual(r.next(i)["step"], "run-approval")

    def test_check_validates_every_artifact_status(self):
        r = self.r
        r.through_inception()
        r.write("reference/architecture/ADR-002-db.md", "---\nstatus: superseded by ADR-003\n---\n# ADR-002\n")
        r.write("reference/architecture/ADR-003-db.md", "---\nstatus: Accepted\n---\n# ADR-003\n")
        r.write("delivery/10-briefs/BRIEF-DM0101-walking-skeleton.md", "# BRIEF\n## Status\nClosed\n")
        r.run("tools/check_workflow.py")
        self.assertEqual(r.next()["phase"], "delivery")
        r.write("reference/product/vision.md", "---\nstatus: aproved\n---\n# Vision\n")
        r.write("analysis/20-analysis/ANALYSIS_DM0101_walking_skeleton.md", "---\nstatus: done\n---\n# A\n")
        r.write("delivery/10-briefs/BRIEF-DM0101-walking-skeleton.md", "# BRIEF\n## Status\nShipped\n")
        out = r.run("tools/check_workflow.py", ok=False).stdout
        for bad in ("reference/product/vision.md: invalid status 'aproved'", "ANALYSIS_DM0101_walking_skeleton.md: invalid status 'done'",
                    "BRIEF-DM0101-walking-skeleton.md: invalid status 'Shipped'"):
            self.assertIn(bad, out)
        n = r.next()
        self.assertEqual((n["step"], n["files"]), ("approve", ["reference/product/vision.md"]))
        self.assertIn("unknown status 'aproved'", n["why"])

    def check(self, ok: bool = True, *a: str) -> tuple[list[str], list[str]]:
        data = json.loads(self.r.run("tools/check_workflow.py", "--json", *a, ok=ok).stdout)["data"]
        return ([x["message"] for x in data["issues"] if x["level"] == "error"],
                [x["message"] for x in data["issues"] if x["level"] == "warning"])

    def test_backlog_schema_is_checked_before_anything_else(self):
        r = self.r
        r.through_inception()
        base = STORIES.format(st="approved")
        for toml, msg in ((base + '[[story]]\nepic = "EP-01"\n', "[[story]] #3: missing or invalid `id`"),
                          (base.replace('["DM0101"]\nac = [["a", "b", "c"]]', '["DM0101"]\nac = [["a", "b"]]'),
                           "DM0102: `ac` must be a list of [given, when, then] string triples"),
                          (base.replace('size = "S"', 'size = "XXL"'), "DM0102: size 'XXL' not in XS | S | M | L | XL")):
            r.write("backlog/stories.toml", toml)
            errors, _ = self.check(False)
            self.assertIn(f"backlog/stories.toml: {msg}", errors)
            out = r.run("tools/gen_backlog.py", ok=False)
            self.assertIn(msg, out.stderr)
            self.assertNotIn("Traceback", out.stderr)

    def test_done_and_closed_need_every_box(self):
        r = self.r
        r.through_inception()
        i = "DM0101"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        spec = SPEC_MD.format(i=i, st="Done") + "# 4. Acceptance Criteria\n- [x] AC1: a\n- [ ] AC2: b\n- [ ] AC3: c (deferred to DM0102)\n" \
            "# 7. Quality Gates\n- [x] Tests added\n- [ ] Build passes\n"
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", spec)
        run = RUN.format(i=i, st="Closed", plan="build", ok="x").replace("- [x] Spec updated", "- [ ] Spec updated") \
            + "# 8. Quality Gates Check\n- [x] Tests passing\n- [ ] No scope creep\n# 9. Outcome\n- [x] Yes\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", run)
        errors, _ = self.check(False)
        self.assertIn("SPEC-DM0101 Done with unchecked acceptance criteria: AC2: b", errors)
        self.assertIn("SPEC-DM0101 Done with unchecked quality gates: Build passes", errors)
        self.assertIn("RUN-DM0101: Closed with unchecked quality gates: No scope creep", errors)
        self.assertIn("RUN-DM0101: Closed without Persistence", errors)  # the [x] in §9 does not count for §7

    def test_plan_matches_the_backlog(self):
        r = self.r
        r.through_inception()
        stories = STORIES.format(st="approved") + '[[story]]\nid = "DM0103"\nepic = "EP-01"\nslug = "import"\ntitle = "Import"\n' \
            'priority = "Must"\nrelease = "R1"\nsize = "L"\ndeps = ["DM0102"]\nac = [["a", "b", "c"]]\n'
        r.write("backlog/stories.toml", stories.replace('size = "M"', 'size = "M"\nrelease = "R1"'))
        plan = ("---\nstatus: approved\nstart: 2099-01-05\ncapacity: 3\n---\n# PLAN\n| Release | Content | Target | Exit |\n|---|---|---|---|\n"
                "| R1 | EP-01 | 2099-01-20 | x |\n| Sprint | Dates | Goal | Stories |\n|---|---|---|---|\n"
                "| S1 | 05/01 – 16/01 | a | DM0103, DM0101, DM0199, EP-09 |\n| S2 | 19/01 – 30/01 | b | DM0102 |\n")
        r.write("PLAN.md", plan)
        errors, warnings = self.check(False)
        self.assertIn("PLAN.md: unknown story DM0199 (S1)", errors)
        self.assertIn("PLAN.md: unknown epic EP-09", errors)
        self.assertIn("PLAN.md: DM0103 (S1) depends on DM0102, planned later (S2)", warnings)
        self.assertIn("PLAN.md: S1 has 5 points, capacity 3", warnings)
        r.write("PLAN.md", plan.replace(", DM0199, EP-09", "").replace("| DM0102 |", "| — |").replace("2099", "2000"))
        errors, warnings = self.check()
        self.assertIn("PLAN.md: stories in no sprint: DM0102", warnings)
        self.assertIn("PLAN.md: S1 ended 2000-01-16 with open stories DM0103, DM0101: update the plan", warnings)
        r.write("PLAN.md", plan.replace(", DM0199, EP-09", "").replace("| DM0102 |", "| DM0102, DM0103 |")
                .replace("| DM0103, DM0101 |", "| DM0101 |"))
        _, warnings = self.check()
        self.assertIn("PLAN.md: Must story DM0103 planned in S2 (ends 2099-01-30), after R1 target 2099-01-20", warnings)
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('deps = ["DM0101"]', 'deps = ["DM0101", "DM0999"]'))
        self.assertFalse(r.next("DM0102")["deps_done"])  # an unknown dependency is never done

    def test_placeholders_and_revisions(self):
        r = self.r
        r.through_inception()
        i = "DM0101"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        run = RUN.format(i=i, st="Closed", plan="build", ok="x") + "# 3. Log\n- …\n```\n- …\n<Date>\n```\nUses `List<String>` and <Date>\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", run)
        _, warnings = self.check()
        self.assertIn("RUN-DM0101: 2 template placeholder(s) left (line 12, 17)", warnings)
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "closed"]):
            subprocess.run(["git", *cmd], cwd=r.dir, check=True, capture_output=True)
        r.write(f"delivery/30-runs/RUN-{i}.md", run + "\nlate edit\n")
        _, warnings = self.check(True, "--git")
        self.assertTrue(any(w.startswith("delivery/30-runs/RUN-DM0101.md: changed after closure") for w in warnings), warnings)
        r.write(f"delivery/30-runs/RUN-{i}.md", run + "\nlate edit\n## Revisions\n- 2026-10-21: late edit (owner)\n")
        _, warnings = self.check(True, "--git")
        self.assertFalse(any("changed after closure" in w for w in warnings), warnings)
        self.assertFalse(any("changed after closure" in w for w in self.check()[1]))  # opt-in only

    def test_run_stops_blocks_and_resumes(self):
        r = self.r
        r.through_inception()
        i = "DM0101"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="In Progress"))
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Tuning", plan="build", ok="x"))
        self.assertEqual(r.next(i)["step"], "tuning")
        stopped = RUN.format(i=i, st="Draft", plan="build", ok=" ").replace("# 7.", "- [x] Stopped\n# 7.")
        r.write(f"delivery/30-runs/RUN-{i}.md", stopped)
        n = r.next(i)
        self.assertEqual((n["step"], n["owner"]), ("stopped", "human"))
        self.assertIn("/run DM0101 revise:", n["why"])
        dev = "# 6. Deviations\n### Deviation #1\n- What changed: x\n- Scope impact: Minor\n" \
              "### Deviation #2\n- What changed: y\n- Scope impact: Requires approval\n- Approved by:\n- Date:\n"
        blocked = RUN.format(i=i, st="Blocked", plan="build", ok="x").replace("# 7.", dev + "# 7.")
        r.write(f"delivery/30-runs/RUN-{i}.md", blocked)
        n = r.next(i)
        self.assertEqual((n["step"], n["owner"]), ("blocked", "human"))
        self.assertIn("approve-deviation 2", n["why"])
        self.assertIn("human-gate.md", r.run("tools/next_step.py", i).stdout)
        r.run("tools/check_workflow.py")
        r.write(f"delivery/30-runs/RUN-{i}.md", blocked.replace("- Approved by:", "- Approved by: PO"))
        _, warnings = self.check()
        self.assertIn("RUN-DM0101: Blocked without a §6 deviation awaiting approval (`Scope impact: Requires approval`)", warnings)
        # a Spec changed after the approval: the human reviews it first, then approves the deviation
        r.write(f"delivery/30-runs/RUN-{i}.md", blocked)
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Draft"))
        self.assertEqual(r.next(i)["step"], "spec-approval")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Blocked"))
        self.assertEqual(r.next(i)["step"], "blocked")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Ready"))
        self.assertIn("approve-deviation 2", r.next(i)["why"])
        r.write(f"delivery/30-runs/RUN-{i}.md", blocked.replace("Blocked", "Executing", 1).replace("- Approved by:", "- Approved by: PO"))
        self.assertEqual(r.next(i)["step"], "execute")

    def test_cancelled_superseded_and_skipped_stories(self):
        r = self.r
        r.through_inception()
        stories = STORIES.format(st="approved")
        r.write("backlog/stories.toml", stories.replace('size = "S"', 'size = "S"\nskip_analysis = true'))
        self.assertEqual(r.next("DM0102")["step"], "brief-spec")
        self.assertEqual(r.next("DM0101")["step"], "analysis")
        # a cancelled story counts as done: the sprint moves on, its dependant is warned
        r.write("backlog/stories.toml", stories.replace('size = "M"', 'size = "M"\nstatus = "cancelled"'))
        self.assertEqual((r.next("DM0101")["step"], r.next("DM0101")["owner"]), ("done", "done"))
        self.assertTrue(r.next("DM0102")["deps_done"])
        n = r.next()
        self.assertEqual((n["step"], n["ids"]), ("analysis", ["DM0102"]))
        _, warnings = self.check()
        self.assertIn("DM0102: depends on cancelled story DM0101: drop the dependency or cancel DM0102", warnings)
        r.write("delivery/10-briefs/BRIEF-DM0101-walking-skeleton.md", BRIEF_MD.format(i="DM0101"))
        r.write("delivery/20-specs/SPEC-DM0101-walking-skeleton.md", SPEC_MD.format(i="DM0101", st="In Progress"))
        r.write("delivery/30-runs/RUN-DM0101.md", RUN.format(i="DM0101", st="Executing", plan="build", ok="x"))
        _, warnings = self.check()
        self.assertIn("RUN-DM0101: story cancelled but RUN Executing: set the RUN to Cancelled", warnings)
        r.write("delivery/30-runs/RUN-DM0101.md", RUN.format(i="DM0101", st="Cancelled", plan="build", ok=" "))
        r.write("delivery/20-specs/SPEC-DM0101-walking-skeleton.md", SPEC_MD.format(i="DM0101", st="Cancelled"))
        _, warnings = self.check()
        self.assertFalse(any("RUN-DM0101" in w for w in warnings), warnings)
        # superseded: the successor is named; links must exist
        sup = stories.replace('size = "M"', 'size = "M"\nstatus = "superseded"').replace('slug = "export"', 'slug = "export"\nsupersedes = "DM0101"')
        r.write("backlog/stories.toml", sup)
        self.assertEqual(r.next("DM0101")["why"], "story superseded by DM0102")
        r.write("backlog/stories.toml", sup.replace('supersedes = "DM0101"', 'split_from = "DM0199"'))
        errors, warnings = self.check(False)
        self.assertIn("DM0102: `split_from` names unknown story DM0199", errors)
        self.assertIn('DM0101: superseded, but no story has `supersedes` or `split_from` = "DM0101"', warnings)
        r.write("backlog/stories.toml", stories.replace('size = "M"', 'size = "M"\nstatus = "dropped"\nskip_analysis = "yes"'))
        errors, _ = self.check(False)
        self.assertIn("backlog/stories.toml: DM0101: status 'dropped' not in open | cancelled | superseded", errors)
        self.assertIn("backlog/stories.toml: DM0101: `skip_analysis` must be true or false", errors)

    def test_invalid_settings_json_is_reported(self):
        r = self.r
        r.write(".claude/settings.json", "{not json")
        out = r.run("tools/render_agents.py", ok=False)
        self.assertIn("invalid JSON", out.stderr)


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
                     f"s = h.HTTPServer(('127.0.0.1', {port}), h.SimpleHTTPRequestHandler)\n"
                     "print('app listening', flush=True)\ns.handle_request()\nprint('app served one request', flush=True)\n")
        self.r.toml_set("project.toml", "stack", "run", f'"{sys.executable}" serve_once.py')
        self.r.toml_set("project.toml", "stack", "url", f"http://127.0.0.1:{port}/")
        out = self.r.run("tools/launch.py", "--timeout", "120", timeout=180)  # a cold macOS runner needs >20 s to start python; never hang
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
        r = subprocess.run([sys.executable, "tools/adopt.py", self.t, *a], cwd=self.r.dir, env=self.env, capture_output=True, text=True, encoding="utf-8")
        if ok and r.returncode != 0:
            raise AssertionError(f"adopt failed:\n{r.stdout}\n{r.stderr}")
        return r

    def tool(self, *a: str, ok: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, *a], cwd=self.t, env=self.env, capture_output=True, text=True, encoding="utf-8")
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

    def test_invalid_arguments_fail_before_copying(self):
        for args in (("--prefix", "ma", "--dry-run"), ("--prefix", "ma"), ("--language", "Italian"), ("--tools", "vim")):
            out = self.adopt(*args, ok=False)
            self.assertNotEqual(out.returncode, 0, args)
            self.assertIn(f"--{args[0][2:]}", out.stderr)
            self.assertFalse(os.path.exists(os.path.join(self.t, "project.toml")), args)
            self.assertFalse(os.path.exists(os.path.join(self.t, "tools/wf.py")), args)

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
        self.assertIn("portal:", mk)
        self.assertIn(".portal/", self.read(".gitignore").splitlines())
        self.assertIn("run /onboard", mk)
        for absent in ("tools/adopt.py", "tools/tests", ".github/workflows", "README.md", ".cursor"):
            self.assertFalse(os.path.exists(os.path.join(self.t, absent)), absent)
        p = self.read("project.toml")
        self.assertIn('origin = "brownfield"', p)
        self.assertIn('id_prefix = "LS"', p)
        self.assertIn('owner = "Pat Owner"', p)
        self.assertIn('test = "make test"', p)
        self.tool("tools/check_workflow.py")
        n = json.loads(self.tool("tools/next_step.py", "--json").stdout)["data"]
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
        n = json.loads(self.tool("tools/next_step.py", "--json").stdout)["data"]
        self.assertEqual((n["step"], n["after"]), ("approve", "onboard"))
        self.write("reference/architecture/architecture.md", "---\nstatus: approved\n---\n")
        self.assertEqual(json.loads(self.tool("tools/next_step.py", "--json").stdout)["data"]["files"], ["project.toml [stack] decided = true"])
        self.write("project.toml", set_key(self.read("project.toml"), "stack", "decided", True))
        self.assertEqual(json.loads(self.tool("tools/next_step.py", "--json").stdout)["data"]["step"], "backlog")
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
