"""End-to-end tests of the workflow tools on a temporary copy of the skeleton (stdlib unittest)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# the installer and the upgrader are never installed in a project (a template clone may carry them): tested only with both
SKELETON_ONLY = unittest.skipUnless(all(os.path.exists(os.path.join(SRC, "tools", f)) for f in ("adopt.py", "upgrade.py")),
                                    "needs tools/adopt.py and tools/upgrade.py (skeleton only)")
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
              "delivery/10-briefs", "delivery/20-specs", "delivery/30-runs", "delivery/40-spikes", "reference", "backlog", "docs/sources",
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

    def test_large_stories_route_to_the_deep_command(self):
        r = self.r
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('size = "M"', 'size = "L"', 1))
        i = "DM0101"
        r.write(f"analysis/30-refined/REFINED_{i}_walking_skeleton.md", REFINED_MD)
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Ready"))
        n = r.next()
        self.assertEqual((n["step"], n["command"], n["tier"], n["models"]["claude-code"]), ("run-strategy", f"/run-deep {i}", "deep", "opus"))
        cmd = r.read(".claude/commands/run-deep.md")
        self.assertIn("model: opus", cmd)
        self.assertIn("approve-deviation", cmd)  # same body as /run
        r.write("backlog/stories.toml", STORIES.format(st="approved"))
        self.assertEqual((r.next()["command"], r.next()["tier"]), (f"/run {i}", "balanced"))

    def test_session_default_model_is_the_balanced_tier(self):
        r = self.r
        self.assertEqual(json.loads(r.read(".claude/settings.json"))["model"], "sonnet")
        own = {"model": "claude-opus-5-5", "permissions": {"allow": ["Bash(ls)"]}}
        r.write(".claude/settings.json", json.dumps(own))
        r.run("tools/render_agents.py")
        s = json.loads(r.read(".claude/settings.json"))
        self.assertEqual(s["model"], "claude-opus-5-5")  # chosen by the project: kept
        self.assertIn("Bash(make next)", s["permissions"]["allow"])
        self.assertIn("session default model 'claude-opus-5-5' is not the balanced tier 'sonnet'", r.run("tools/check_workflow.py").stdout)
        r.write(".claude/settings.json", json.dumps({"permissions": {}}))
        r.run("tools/render_agents.py")
        self.assertEqual(json.loads(r.read(".claude/settings.json"))["model"], "sonnet")

    def test_usage_splits_sessions_by_command_and_reports_tier_shares(self):
        r = self.r
        home = os.path.join(r.dir, ".home")
        r.env.update(CLAUDE_CONFIG_DIR=os.path.join(home, "claude"), CODEX_HOME=os.path.join(home, "codex"))
        slug = "".join(c if c.isalnum() else "-" for c in os.path.abspath(r.dir))
        msg = lambda i, model, out, ctx=100: {"type": "assistant", "sessionId": "s1", "timestamp": "2026-10-14T09:00:%02dZ" % i, "requestId": f"q{i}",
                                              "message": {"id": f"m{i}", "model": model, "usage": {"input_tokens": 1, "output_tokens": out,
                                                          "cache_creation_input_tokens": 10, "cache_read_input_tokens": ctx}}}
        user = lambda content, i=0, **k: {"type": "user", "sessionId": "s1", "userType": "external", "timestamp": "2026-10-14T09:00:%02dZ" % i,
                                          "message": {"role": "user", "content": content}, **k}
        claude = [user("<command-name>/clear</command-name>"), user("<command-name>/weekly</command-name>", 1),
                  user([{"type": "text", "text": "<!-- step body -->"}], isMeta=True),
                  msg(2, "claude-opus-5-5", 50), msg(2, "claude-opus-5-5", 50), msg(3, "claude-haiku-5-5", 5),
                  user([{"type": "tool_result", "content": "The user doesn't want to proceed with this tool use. The tool use was rejected"}]),
                  user([{"type": "text", "text": "[Request interrupted by user]"}]), user([{"type": "text", "text": "go on"}], 4),
                  user("<command-name>/run</command-name>", 5), msg(6, "claude-sonnet-5-5", 30, ctx=90_000),
                  {"type": "cost-state", "sessionId": "s1", "totalCostUSD": 3.0,
                   "modelUsage": {"claude-opus-5-5": {"costUSD": 2.0}, "claude-sonnet-5-5": {"costUSD": 0.9}, "claude-haiku-5-5": {"costUSD": 0.1}}}]
        codex = [{"type": "session_meta", "timestamp": "2026-10-15T10:00:00Z", "payload": {"id": "c1", "cwd": r.dir}},
                 {"type": "turn_context", "payload": {"model": "gpt-5-codex"}},
                 {"type": "event_msg", "payload": {"type": "user_message", "message": "/prompts:analysis DM0101"}},
                 {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
                     "input_tokens": 900, "cached_input_tokens": 600, "output_tokens": 70}, "last_token_usage": {"input_tokens": 900}}}}]
        other = [{**codex[0], "payload": {"id": "c2", "cwd": "/elsewhere"}}, *codex[1:]]
        r.write(f".home/claude/projects/{slug}/s1.jsonl", "\n".join(map(json.dumps, claude)) + "\n")
        r.write(".home/codex/sessions/2026/10/15/rollout-a.jsonl", "\n".join(map(json.dumps, codex)) + "\n")
        r.write(".home/codex/sessions/2026/10/15/rollout-b.jsonl", "\n".join(map(json.dumps, other)) + "\n")
        data = json.loads(r.run("tools/usage.py", "--since", "2026-10-12", "--until", "2026-10-19", "--json").stdout)
        weekly, run, cx = data["rows"]
        self.assertEqual((weekly["step"], weekly["tier"], weekly["main"], weekly["main_tier"], weekly["mismatch"]),
                         ("weekly", "fast", "claude-opus-5-5", "deep", True))  # /clear neither labels nor splits
        self.assertEqual((weekly["prompts"], weekly["interrupts"], weekly["rejected"]), (2, 1, 1))
        self.assertEqual(weekly["models"]["claude-opus-5-5"]["output"], 50)  # duplicate message counted once
        self.assertEqual((run["step"], run["mismatch"], run["over"], run["cost"]), ("run", False, True, None))
        self.assertEqual((cx["step"], cx["main"], cx["models"]["gpt-5-codex"]["cache_read"], cx["peak"]), ("analysis", "gpt-5-codex", 600, 900))
        self.assertAlmostEqual(data["models"]["claude-opus-5-5"]["cost_share"], 2.0 / 3.0)
        self.assertAlmostEqual(data["tiers"]["deep"]["cost_share"], 2.0 / 3.0)
        out = r.run("tools/usage.py", "--since", "2026-10-12", "--until", "2026-10-19").stdout
        self.assertIn("2 sessions, 3 commands", out)
        self.assertIn("deep 25% of calls, 67% of cost", out)
        self.assertIn("No sessions", r.run("tools/usage.py", "--since", "2026-11-01", "--until", "2026-11-07").stdout)

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

    def test_check_validates_git_settings(self):
        r = self.r
        r.toml_set("project.toml", "git", "trailers", "co-author")
        r.toml_set("project.toml", "git", "merge", "ff")
        out = r.run("tools/check_workflow.py", ok=False).stdout
        self.assertIn("[git] trailers = 'co-author'", out)
        self.assertIn("[git] merge = 'ff'", out)
        r.toml_set("project.toml", "git", "trailers", "tool")
        r.toml_set("project.toml", "git", "merge", "rebase")
        r.run("tools/check_workflow.py")

    def test_adapters_follow_each_tools_conventions(self):
        r = self.r
        skill = r.read(".agents/skills/brief/SKILL.md")
        self.assertTrue(skill.startswith("---\nname: brief\ndescription: "))
        self.assertIn("Use only when the user types $brief.", skill)
        models = tomllib.loads(r.read("models.toml"))  # the project's own choice in a project created from the skeleton
        tier = lambda tool, t: models["tools"][tool].get("models", {}).get(t) or models["vendors"][models["tools"][tool]["vendor"]][t]  # noqa: E731
        self.assertIn(f'[profiles.deep]\nmodel = "{tier("codex", "deep")}"', r.read(".codex/config.toml"))
        prompt = r.read(".github/prompts/run.prompt.md")
        self.assertIn("agent: 'agent'", prompt)
        self.assertNotIn("mode:", prompt)
        self.assertEqual(prompt.count("Arguments"), 1)
        self.assertIn("model: ", r.read(".github/agents/reviewer.agent.md"))
        self.assertIn(tier("cursor", "balanced"), r.read(".cursor/commands/brief.md"))
        n = r.next()
        self.assertEqual((n["commands"]["claude-code"], n["commands"]["codex"]), ("/kickoff", "$kickoff"))
        r.write(".codex/config.toml", 'model = "my-own"\n')  # the project's own Codex config is kept
        r.run("tools/render_agents.py")
        self.assertEqual(r.read(".codex/config.toml"), 'model = "my-own"\n')
        r.run("tools/check_workflow.py")

    def test_pending_owner_actions_changelog_and_upstream(self):
        r, i = self.r, "DM0101"
        check = lambda: EdgeCaseTest.check(self, False)  # noqa: E731
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('size = "M"', 'size = "M"\nrepo = "skeleton"', 1))
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        review = "# 11. Review\n### Review #1\n- Date: 2026-10-21\n- Reviewer: review agent\n- Outcome: `ok-to-close`\n"
        run = (RUN.format(i=i, st="Closed", plan="build", ok="x") + "# 9. Outcome\nGoal achieved:\n- [x] Yes\n- [ ] Partial\n" + review
               + "## Pending owner actions\n- [ ] tag v1.2.0 — owner: PO — since: 2026-10-20\n- [x] release notes — owner: PO — since: 2026-10-20\n")
        r.write(f"delivery/30-runs/RUN-{i}.md", run)
        self.assertEqual(r.next()["pending"], [{"id": i, "action": "tag v1.2.0 — owner: PO — since: 2026-10-20"}])
        errors, warnings = check()
        self.assertIn(f"RUN-{i}: Closed with Goal achieved `Yes` while owner actions are pending: tag v1.2.0 — owner: PO — since: 2026-10-20 (use Partial, or do them)", errors)
        self.assertIn(f"RUN-{i}: story in repo 'skeleton': record the upstream commit or tag in RUN References `Upstream:`", warnings)
        r.write("tools/VERSION", "99.0.0\n")
        r.toml_set("project.toml", "skeleton", "version", "98.0.0")
        errors, warnings = check()
        self.assertIn("tools/CHANGELOG.md has no `## 99.0.0` entry for tools/VERSION", errors)
        self.assertTrue(any("[skeleton] version 98.0.0 but the workflow files are 99.0.0" in w for w in warnings))

    def test_a_run_from_before_the_review_step_is_only_warned(self):
        r, i = self.r, "DM0101"
        r.through_inception()
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        old = RUN.format(i=i, st="Closed", plan="build", ok="x") + "# 9. Outcome\nGoal achieved:\n- [x] Yes\n"
        for tail in ("", "# 11. Addendum (Post-Closure Only)\nCI green after closure.\n"):  # old template: no §11, or §11 Addendum
            with self.subTest(tail=tail[:20]):
                r.write(f"delivery/30-runs/RUN-{i}.md", old + tail)
                errors, warnings = EdgeCaseTest.check(self, False)
                self.assertFalse([e for e in errors if "review record" in e], errors)
                self.assertTrue(any(f"RUN-{i}: Closed without a §11 Review (RUN from a skeleton before 1.7.0" in w for w in warnings))
        r.write(f"delivery/30-runs/RUN-{i}.md", old + "# 11. Review\n")
        self.assertIn(f"RUN-{i}: Closed without a review record (§11 latest `### Review #n` with Date and Outcome `ok-to-close`)",
                      EdgeCaseTest.check(self, False)[0])

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

    def test_context_counts_what_the_step_really_reads(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        r.write("analysis/30-refined/REFINED_DM0101_walking_skeleton.md",
                "---\nstatus: refined\nsource_files:\n  - reference/product/functional-requirements.md#FR-01\n---\n# R\nFR-01, ADR-001\n")
        b = json.loads(r.run("tools/context.py", "brief-spec", "DM0101", "--json").stdout)
        self.assertEqual(b["cited"], [])  # the FR file is cited by anchor and its section is already extracted
        adr = next(s for s in b["sections"] if s["ref"] == "ADR-001")
        self.assertGreater(adr["tokens"], 0)
        self.assertGreaterEqual(b["tokens"], sum(x["tokens"] for x in b["read"] + b["sections"]))
        r.write("pkg/api/AGENTS.md", "# api rules\n" + "rule\n" * 50)
        r.write("delivery/20-specs/SPEC-DM0101-walking-skeleton.md", SPEC_MD.format(i="DM0101", st="Ready") + "FR-01\n")
        ex = json.loads(r.run("tools/context.py", "execute", "DM0101", "--json").stdout)
        rules = [x["path"] for x in ex["package_rules"]]  # in a project: also its own packages' rules
        self.assertIn("pkg/api/AGENTS.md", rules)
        self.assertFalse(set(rules) & {"AGENTS.md", "analysis/AGENTS.md", "delivery/AGENTS.md"}, rules)
        self.assertIn("FR-01", [s["ref"] for s in ex["sections"]])
        r.write("project-journal/notes/2026-10-01-workshop-x.md", "minutes\n")
        rf = json.loads(r.run("tools/context.py", "refine", "DM0101", "--with", "project-journal/notes/2026-10-01-workshop-x.md", "--json").stdout)
        self.assertIn("project-journal/notes/2026-10-01-workshop-x.md", [x["path"] for x in rf["read"]])
        self.assertEqual(rf["ids"], ["DM0101"])
        rv = json.loads(r.run("tools/context.py", "review", "DM0101", "--json").stdout)
        self.assertIn("diff", rv)  # null outside a git repository with a main branch

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
        for plan, want in (("- TSK-DM0101-01: …", "run-strategy"), ("- TSK-DM0101-01: build the API", "run-approval")):  # 1.11 template
            r.write(run, RUN.format(i=i, st="Draft", plan="x", ok=" ").replace("- Step 1: x", plan))
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

    def test_traceability_facts_and_spec_index(self):
        r = self.r
        r.through_inception()
        r.run("tools/gen_backlog.py")
        i = "DM0101"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        spec = ("# SPEC-{i} - Walking skeleton\n## References\n- Brief: BRIEF-{i}\n- Requirements: {req}\n## Status\nDone\n"
                "# 4. Acceptance Criteria\n- [x] AC1: works → test: tests/test_app.py::test_works\n- [x] AC2: fast\n")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", spec.format(i=i, req="FR-1, NFR-01, FR-28"))
        review = "# 11. Review\n### Review #1\n- Date: 2026-10-21\n- Reviewer: review agent\n- Outcome: `ok-to-close`\n"
        facts = "# 8. Quality Gates Check\n- AC: 2/2 met\n- Tests: {tests}\n- Out-of-scope changes: none\n- CI: {ci}\n"
        run = RUN.format(i=i, st="Closed", plan="build", ok="x") + "Tuning accepted by:\nDate:\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", run + facts.format(tests="make test → pass (12)", ci="green — https://x/pr/1") + review)
        errors, warnings = self.check()
        self.assertIn(f"SPEC-{i}: Requirements differ from backlog/stories.toml; only in the Spec: FR-28 (align one of them)", warnings)
        self.assertTrue(any(w.startswith(f"SPEC-{i} Done with AC naming no test") and "AC2" in w for w in warnings), warnings)
        self.assertIn("delivery/20-specs/README.md out of date: run `make backlog`", warnings)
        self.assertNotIn(f"RUN-{i}: Persisted", " ".join(warnings))
        self.assertIn(f"RUN-{i}: Closed without `Tuning accepted by` (§5): record who accepted the result and when", warnings)
        r.run("tools/gen_backlog.py")
        self.assertIn(f"| [{i}](SPEC-{i}-walking-skeleton.md) | Walking skeleton | Done | Closed |", r.read("delivery/20-specs/README.md"))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", spec.format(i=i, req="FR-01, NFR-1"))
        r.write(f"delivery/30-runs/RUN-{i}.md", run.replace("Tuning accepted by:", "Tuning accepted by: PO") + facts.format(tests="make test → fail (1)", ci="green / red / none (no remote) — <PR URL>") + review)
        errors, warnings = self.check(False)
        self.assertNotIn("Requirements differ", " ".join(warnings))
        self.assertIn(f"RUN-{i}: Closed with failing tests in §8: make test → fail (1)", errors)
        self.assertIn(f"RUN-{i}: Closed without the `CI:` fact in §8", errors)
        self.assertNotIn("Tuning accepted", " ".join(warnings))

    def test_review_then_close(self):
        r = self.r
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('size = "M"', 'size = "M"\nsecurity = false', 1))  # no security step
        i = "DM0101"
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        review = "# 11. Review\n### Review #1\n- Date: 2026-10-21\n- Reviewer: review agent\n- Outcome: `{o}`\n"
        # persisted → review (agent); the review asks for changes → back to Tuning (human), findings named
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Persisted", plan="build", ok="x"))
        self.assertEqual((r.next(i)["step"], r.next(i)["owner"]), ("review", "agent"))
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Tuning", plan="build", ok="x") + review.format(o="changes-requested"))
        n = r.next(i)
        self.assertEqual((n["step"], n["owner"]), ("tuning", "human"))
        self.assertIn("review #1 requested changes", n["why"])
        # Reviewed with an ok-to-close review → close, recommended ahead of other work in the sprint
        ok = RUN.format(i=i, st="Reviewed", plan="build", ok="x") + review.format(o="changes-requested") \
            + "### Review #2\n- Date: 2026-10-22\n- Reviewer: review agent\n- Outcome: `ok-to-close`\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", ok)
        self.assertEqual((r.next(i)["step"], r.next(i)["owner"]), ("close", "agent"))
        self.assertEqual((r.next()["step"], r.next()["ids"]), ("close", [i]))
        self.assertIn("/close DM0101", r.run("tools/next_step.py").stdout)
        self.assertNotIn(f"RUN-{i}", " ".join(self.check()[0]))
        # Reviewed or Closed without an ok-to-close review: an error, and the review runs again
        for st, rec in (("Reviewed", ""), ("Reviewed", review.format(o="changes-requested")),
                        ("Closed", review.format(o="`ok-to-close` / `changes-requested`")), ("Closed", review.replace("2026-10-21", "").format(o="ok-to-close"))):
            r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st=st, plan="build", ok="x") + rec)
            self.assertIn(f"RUN-{i}: {st} without a review record (§11 latest `### Review #n` with Date and Outcome `ok-to-close`)",
                          self.check(False)[0], (st, rec))
            if st == "Reviewed":
                self.assertEqual(r.next(i)["step"], "review")
        # a RUN closed before §11 existed: a warning only
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Closed", plan="build", ok="x"))
        errors, warnings = self.check()
        self.assertTrue(any(w.startswith(f"RUN-{i}: Closed without a §11 Review") for w in warnings), warnings)
        self.assertEqual(r.next(i)["step"], "done")

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

    def test_quick_track_hotfix_first_and_spikes(self):
        r = self.r
        r.through_inception()
        hotfix = '[[story]]\nid = "DM0103"\nepic = "EP-01"\nslug = "crash"\ntitle = "Crash"\ntype = "hotfix"\nsize = "S"\n' \
                 'ac = [["a", "b", "c"]]\n'
        stories = STORIES.format(st="approved").replace('slug = "export"', 'slug = "export"\ntype = "bug"') + hotfix
        r.write("backlog/stories.toml", stories)
        self.assertEqual(r.next("DM0102")["step"], "quick")
        n = r.next()  # unplanned hotfix ahead of the sprint, and not reported as unplanned
        self.assertEqual((n["step"], n["ids"], n["command"]), ("quick", ["DM0103"], "/quick DM0103"))
        self.assertFalse(any("stories in no sprint" in w for w in self.check()[1]))
        i = "DM0103"
        r.write(f"delivery/10-briefs/BRIEF-{i}-crash.md", BRIEF_MD.format(i=i))
        self.assertEqual(r.next(i)["step"], "quick")
        r.write(f"delivery/20-specs/SPEC-{i}-crash.md", SPEC_MD.format(i=i, st="Draft"))
        self.assertEqual(r.next(i)["step"], "quick")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Draft", plan="fix", ok=" "))
        n = r.next()  # one approval covers Spec and strategy; meanwhile the agent goes on with the sprint
        self.assertEqual((n["step"], n["human_gates"][0]["id"], n["human_gates"][0]["stage"]), ("analysis", i, "run-approval"))
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Executing", plan="fix", ok="x"))
        r.write(f"delivery/20-specs/SPEC-{i}-crash.md", SPEC_MD.format(i=i, st="In Progress"))
        self.assertEqual((r.next()["step"], r.next()["ids"]), ("execute", [i]))
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Closed", plan="fix", ok="x"))
        self.assertEqual(r.next()["ids"], ["DM0101"])  # back to the sprint order
        # XS goes quick whatever the type; skip_analysis = false keeps the analysis
        r.write("backlog/stories.toml", stories.replace('size = "M"', 'size = "XS"'))
        self.assertEqual(r.next("DM0101")["step"], "quick")
        r.write("backlog/stories.toml", stories.replace('type = "bug"', 'type = "bug"\nskip_analysis = false'))
        self.assertEqual(r.next("DM0102")["step"], "analysis")
        # spike: findings note, human review, accepted = done
        r.write("backlog/stories.toml", stories.replace('type = "bug"', 'type = "spike"'))
        self.assertEqual(r.next("DM0102")["step"], "spike")
        ctx = r.run("tools/context.py", "spike", "DM0102").stdout
        self.assertIn("SPIKE-template.md", ctx)
        r.write("delivery/40-spikes/SPIKE-DM0102-export.md", "# SPIKE-DM0102\n## Status\nDraft\n")
        self.assertEqual((r.next("DM0102")["step"], r.next("DM0102")["owner"]), ("spike-review", "human"))
        r.write("delivery/40-spikes/SPIKE-DM0102-export.md", "# SPIKE-DM0102\n## Status\nAccepted\n")
        self.assertEqual(r.next("DM0102")["step"], "done")
        r.write("delivery/40-spikes/SPIKE_DM0102.md", "# x\n## Status\nDone\n")
        r.write("delivery/40-spikes/SPIKE-DM0102-other.md", "# x\n## Status\nDone\n")
        r.write("backlog/stories.toml", stories.replace('type = "bug"', 'type = "task"'))
        errors, _ = self.check(False)
        self.assertIn("Spike note naming: delivery/40-spikes/SPIKE_DM0102.md", errors)
        self.assertIn("delivery/40-spikes/SPIKE-DM0102-other.md: invalid status 'Done' (expected Draft | Accepted)", errors)
        self.assertIn("backlog/stories.toml: DM0102: type 'task' not in feature | technical | bug | hotfix | chore | refactor | spike",
                      errors)

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


class GateTest(unittest.TestCase):
    """Human gates: the agent hook, `make approve` and the approval-before-code check."""

    def setUp(self) -> None:
        self.r = Repo()
        self.r.through_inception()
        self.i = "DM0101"
        r, i = self.r, self.i
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Ready"))
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Draft", plan="build", ok=" ").replace("- [ ] Approved\n", "- [ ] Approved\nReviewer:\nDate:\n"))

    def tearDown(self) -> None:
        self.r.cleanup()

    def guard(self, tool: str, inp: dict, prompt: str | None = None) -> subprocess.CompletedProcess:
        ev = {"tool_name": tool, "tool_input": inp}
        if prompt is not None:
            tr = os.path.join(self.r.dir, ".transcript.jsonl")
            with open(tr, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "user", "userType": "external", "message": {"role": "user", "content": prompt}}) + "\n")
            ev["transcript_path"] = tr
        return subprocess.run([sys.executable, "tools/gate_guard.py"], cwd=self.r.dir, env=self.r.env, input=json.dumps(ev),
                              capture_output=True, text=True, encoding="utf-8")

    def test_guard_blocks_gate_edits_unless_the_human_typed_the_gate_command(self):
        r, i = self.r, self.i
        run = os.path.join(r.dir, f"delivery/30-runs/RUN-{i}.md")
        tick = {"file_path": run, "old_string": "- [ ] Approved", "new_string": "- [x] Approved"}
        blocked = self.guard("Edit", tick)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn(f"make approve ID={i} GATE=strategy", blocked.stderr)
        self.assertEqual(self.guard("Edit", tick, "ok, go ahead").returncode, 2)  # free text is not the gate command
        cmd = "<command-message>run</command-message>\n<command-name>/run</command-name>\n<command-args>{}</command-args>"
        self.assertEqual(self.guard("Edit", tick, cmd.format(f"{i} approve")).returncode, 0)
        self.assertEqual(self.guard("Edit", tick, cmd.format("DM0102 approve")).returncode, 2)
        self.assertEqual(self.guard("Edit", {**tick, "new_string": "- [ ] Approved\n"}).returncode, 0)  # no gate passed
        spec = os.path.join(r.dir, f"delivery/20-specs/SPEC-{i}-walking-skeleton.md")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Draft"))
        self.assertEqual(self.guard("Write", {"file_path": spec, "content": SPEC_MD.format(i=i, st="Ready")}).returncode, 2)
        vision = os.path.join(r.dir, "reference/product/vision.md")
        r.write("reference/product/vision.md", "---\nstatus: draft\n---\n# Vision\n")
        edit = {"file_path": vision, "old_string": "status: draft", "new_string": "status: approved"}
        self.assertIn("make approve GATE=inception FILE=reference/product/vision.md", self.guard("Edit", edit).stderr)
        edit = {"file_path": os.path.join(r.dir, "project.toml"), "old_string": "decided = true", "new_string": "decided = true"}
        self.assertEqual(self.guard("Edit", edit).returncode, 0)

    def test_guard_keeps_each_mode_in_its_paths_and_blocks_risky_shell(self):
        r = self.r
        analysis = "<command-name>/analysis</command-name>\n<command-args>DM0101</command-args>"
        w = lambda p: {"file_path": os.path.join(r.dir, p), "content": "x\n"}
        self.assertEqual(self.guard("Write", w("analysis/20-analysis/ANALYSIS_DM0101_x.md"), analysis).returncode, 0)
        self.assertIn("analyst mode", self.guard("Write", w("delivery/10-briefs/BRIEF-DM0101-x.md"), analysis).stderr)
        review = "<command-name>/review-story</command-name>\n<command-args>DM0101</command-args>"
        self.assertEqual(self.guard("Write", w("src/app.py"), review).returncode, 2)
        self.assertEqual(self.guard("Write", w("src/app.py"), "<command-name>/run</command-name>").returncode, 0)
        for cmd, code in (("make approve ID=DM0101 GATE=spec", 2), ("git push --force-with-lease", 2), ("gh pr merge 4 --admin --squash", 2),
                          ("cat .env", 2), ("git switch -c release/1.17.0", 2), ("git checkout -b develop", 2), ("git branch staging", 2),
                          ("git switch -c pr0101-login", 0), ("git branch -d release/1.16.0", 0), ("git branch --list", 0), ("git push -u origin dm0101-x", 0), ("python3 - <<'EOF'\nprint('make approve')\nEOF", 0)):
            self.assertEqual(self.guard("Bash", {"command": cmd}).returncode, code, cmd)

    def git(self, *a: str) -> str:
        return subprocess.run(["git", *a], cwd=self.r.dir, capture_output=True, text=True, check=True).stdout

    def test_stale_branches_are_reported_by_check_and_next(self):
        r = self.r
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Pat Owner")
        self.git("config", "user.email", "pat@example.org")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("switch", "-qc", "dm0101-old")
        old = "2020-01-01T00:00:00"
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "old work", "--date", old], cwd=r.dir, check=True,
                       env={**r.env, "GIT_COMMITTER_DATE": old})
        self.git("switch", "-q", "main")
        self.git("switch", "-qc", "dm0102-fresh")
        self.git("commit", "-q", "--allow-empty", "-m", "fresh work")
        self.git("switch", "-q", "main")
        out = r.run("tools/check_workflow.py").stdout
        self.assertIn("branch dm0101-old", out)
        self.assertNotIn("dm0102-fresh", out)

    def test_make_approve_commits_the_gate_alone_and_ci_checks_the_order(self):
        r, i = self.r, self.i
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Pat Owner")
        self.git("config", "user.email", "pat@example.org")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("switch", "-qc", "dm0101-walking-skeleton")
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Draft"))
        r.run("tools/approve.py", "--gate", "spec", "--id", i.lower(), "--no-commit")
        self.assertIn("Ready", r.read(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md"))
        self.assertIn("already passed", r.run("tools/approve.py", "--gate", "spec", "--id", i, ok=False).stderr)
        r.write("src/app.py", "print('hi')\n")  # untracked code: not part of the approval commit
        out = r.run("tools/approve.py", "--gate", "strategy", "--id", i).stdout
        self.assertIn(f"approve(strategy): {i}", out)
        body = self.git("log", "-1", "--format=%B")
        self.assertIn("Approved-by: Pat Owner <pat@example.org>", body)
        self.assertIn("Approved-at: ", body)
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split()),
                         [f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", f"delivery/30-runs/RUN-{i}.md"])
        run = r.read(f"delivery/30-runs/RUN-{i}.md")
        self.assertIn("- [x] Approved", run)
        self.assertIn("Reviewer: Pat Owner", run)
        self.assertIn("Strategy Approved", run)
        self.git("add", "src/app.py")
        self.git("commit", "-qm", "code")
        ok = json.loads(r.run("tools/check_workflow.py", "--json", "--git", ok=False).stdout)["data"]["issues"]
        self.assertFalse([x for x in ok if "strategy approval" in x["message"]], ok)
        # code committed together with the approval: an error in CI
        self.git("reset", "-q", "--hard", "main")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Executing", plan="build", ok="x"))
        r.write("src/app.py", "print('hi')\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "everything at once")
        issues = json.loads(r.run("tools/check_workflow.py", "--json", "--git", ok=False).stdout)["data"]["issues"]
        msgs = " ".join(x["message"] for x in issues)
        self.assertIn(f"RUN-{i}: code committed with the strategy approval", msgs)
        self.assertIn("has no `Approved-by:` trailer", msgs)
        # the RUN approved on main already: a later branch (e.g. a skeleton upgrade) is not tied to its approval
        self.git("update-ref", "refs/heads/main", "HEAD")
        r.write("tools/extra.py", "print('upgrade')\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "later code")
        later = json.loads(r.run("tools/check_workflow.py", "--json", "--git", ok=False).stdout)["data"]["issues"]
        self.assertFalse([x for x in later if "strategy approval" in x["message"]], later)

    def test_hook_is_rendered_once_and_kept_next_to_the_projects_own(self):
        r = self.r
        s = json.loads(r.read(".claude/settings.json"))
        self.assertIn("gate_guard.py", json.dumps(s["hooks"]))
        own = {"type": "command", "command": "echo mine"}
        s["hooks"]["PreToolUse"].append({"matcher": "Read", "hooks": [own]})
        r.write(".claude/settings.json", json.dumps(s))
        r.run("tools/render_agents.py")
        s = json.loads(r.read(".claude/settings.json"))
        self.assertEqual(len(s["hooks"]["PreToolUse"]), 2)
        self.assertEqual(json.dumps(s).count("gate_guard.py"), 1)


class SecurityTest(unittest.TestCase):
    """Secret scan, the security review step and the quality gates."""

    def setUp(self) -> None:
        self.r = Repo()

    def tearDown(self) -> None:
        self.r.cleanup()

    def test_secret_scan_finds_keys_in_code_and_artifacts(self):
        r = self.r
        aws = "AKIA" + "QWERTYUIOPASDFGH"  # built at runtime: the repository itself must scan clean
        gh = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
        pw = "Zx9!qR7#" + "vL2@pW5k"
        r.write("src/config.py", f'AWS = "{aws}"\npassword = "{pw}"\nexample_token = "changeme-please"\n')
        r.write("delivery/30-runs/RUN-DM0101.md", f"# RUN\nused token {gh} to test\nkey {aws}  # secret-scan: ignore\n")
        out = r.run("tools/secret_scan.py", "--json", "src/config.py", "delivery/30-runs/RUN-DM0101.md", ok=False)
        self.assertEqual(out.returncode, 1)
        found = {(f["file"], f["line"], f["rule"]) for f in json.loads(out.stdout)["findings"]}
        self.assertEqual(found, {("src/config.py", 1, "AWS access key"), ("src/config.py", 2, "hard-coded password"),
                                 ("delivery/30-runs/RUN-DM0101.md", 2, "GitHub token")})
        self.assertNotIn(aws, out.stdout)  # values are masked
        r.run("tools/secret_scan.py", "tools/wf.py")

    def test_security_sensitive_story_gets_a_security_review_before_the_review(self):
        r, i = self.r, "DM0101"
        r.through_inception()
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done") + "Users log in with a password.\n")
        run = RUN.format(i=i, st="Persisted", plan="build", ok="x")
        r.write(f"delivery/30-runs/RUN-{i}.md", run)
        n = r.next(i)
        self.assertEqual((n["step"], n["owner"]), ("security", "agent"))
        self.assertIn("cites NFR-01 (Security/Privacy)", n["why"])
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('nfr = ["NFR-01"]\n', "", 1))
        self.assertIn("mentions 'password'", r.next(i)["why"])
        sec = "### Security review\n- Date: 2026-10-21\n- Reviewer: security review agent\n- Outcome: `{}`\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", run + sec.format("ok"))
        self.assertEqual(r.next(i)["step"], "review")
        r.write(f"delivery/30-runs/RUN-{i}.md", RUN.format(i=i, st="Tuning", plan="build", ok="x") + sec.format("changes-requested"))
        self.assertIn("security review requested changes", r.next(i)["why"])
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('size = "M"', 'size = "M"\nsecurity = false', 1))
        r.write(f"delivery/30-runs/RUN-{i}.md", run)
        self.assertEqual(r.next(i)["step"], "review")  # opted out
        self.assertIn("security-review", r.read(".claude/commands/security-review.md") + "security-review")

    def test_make_gates_writes_facts_and_blocks_closing_on_a_failure(self):
        r, i = self.r, "DM0101"
        r.through_inception()
        r.write("t_ok.py", "print('12 passed')\n")  # scripts, not `python -c "…%…"`: cmd.exe expands % and quotes differently
        r.write("t_cov.py", "print('TOTAL 71' + chr(37))\n")
        r.toml_set("project.toml", "stack", "test", f'"{sys.executable}" t_ok.py')
        r.toml_set("project.toml", "gates", "coverage", f'"{sys.executable}" t_cov.py')
        r.toml_set("project.toml", "gates", "coverage_min", 80)
        r.toml_set("project.toml", "gates", "secrets", False)
        r.write(f"delivery/10-briefs/BRIEF-{i}-walking-skeleton.md", BRIEF_MD.format(i=i))
        r.write(f"delivery/20-specs/SPEC-{i}-walking-skeleton.md", SPEC_MD.format(i=i, st="Done"))
        review = "# 11. Review\n### Review #1\n- Date: 2026-10-21\n- Reviewer: review agent\n- Outcome: `ok-to-close`\n"
        run = RUN.format(i=i, st="Closed", plan="build", ok="x") + "# 8. Quality Gates Check\n- Tests: x\n- CI: green — https://x/pr/1\n"
        r.write(f"delivery/30-runs/RUN-{i}.md", run + review)
        out = r.run("tools/quality_gates.py", i, ok=False)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        t = r.read(f"delivery/30-runs/RUN-{i}.md")
        self.assertIn("- coverage: ", t, out.stdout + out.stderr)
        self.assertIn("→ fail (71% (min 80%))", t)
        self.assertIn("→ pass (12 passed)", t)
        self.assertIn(f'- Tests: "{sys.executable}" t_ok.py → pass', t)
        self.assertIn(f"RUN-{i}: Closed with failing gates (§8 Gates): coverage", r.run("tools/check_workflow.py", ok=False).stdout)
        r.toml_set("project.toml", "gates", "coverage_min", 70)
        r.run("tools/quality_gates.py", i)
        self.assertEqual(r.read(f"delivery/30-runs/RUN-{i}.md").count("### Gates"), 1)
        self.assertNotIn("failing gates", r.run("tools/check_workflow.py").stdout)


class TeamTest(unittest.TestCase):
    """Team use: claims, the per-person next step, worktrees."""

    def setUp(self) -> None:
        self.r = Repo()
        r = self.r
        r.through_inception()
        r.write("backlog/stories.toml", STORIES.format(st="approved").replace('deps = ["DM0101"]', "deps = []"))
        r.write("analysis/30-refined/REFINED_DM0101_walking_skeleton.md", REFINED_MD)
        r.write("analysis/30-refined/REFINED_DM0102_export.md", REFINED_MD)
        for a in (("init", "-q", "-b", "main"), ("config", "user.name", "Ada"), ("config", "user.email", "ada@example.org"),
                  ("add", "-A"), ("commit", "-qm", "base")):
            self.git(*a)

    def tearDown(self) -> None:
        self.r.cleanup()

    def git(self, *a: str) -> str:
        return subprocess.run(["git", *a], cwd=self.r.dir, capture_output=True, text=True, check=True).stdout

    def test_claim_creates_the_branch_and_others_skip_the_story(self):
        r = self.r
        out = r.run("tools/claim.py", "dm0101").stdout
        self.assertIn("DM0101 claimed by Ada on branch dm0101-walking-skeleton", out)
        self.assertEqual(self.git("branch", "--show-current").strip(), "dm0101-walking-skeleton")
        self.assertIn('id = "DM0101"\nclaimed_by = "Ada"\nclaimed_at = "', r.read("backlog/stories.toml"))
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "claim(DM0101): Ada")
        r.run("tools/check_workflow.py")
        n = r.next("--me", "Bob")
        self.assertEqual((n["step"], n["ids"], n["claimable"]), ("brief-spec", ["DM0102"], ["DM0102"]))
        self.assertEqual(r.next("--me", "ada")["ids"], ["DM0101"])  # names compare case-insensitively
        self.assertIn("is claimed by Ada", r.run("tools/claim.py", "DM0101", "--me", "Bob", ok=False).stderr)
        self.git("switch", "-q", "main")
        self.git("branch", "dm0101-other-try")
        r.write("backlog/stories.toml", r.read("backlog/stories.toml").replace('id = "DM0101"\n', 'id = "DM0101"\nclaimed_by = "Ada"\n', 1))
        warnings = json.loads(r.run("tools/check_workflow.py", "--json").stdout)["data"]["issues"]
        self.assertIn("DM0101: claimed twice, on branches dm0101-other-try, dm0101-walking-skeleton (Ada)", [w["message"] for w in warnings])

    def test_worktree_claim_leaves_the_current_checkout_alone(self):
        r = self.r
        out = r.run("tools/claim.py", "DM0102", "--worktree").stdout
        wt = os.path.join(os.path.dirname(r.dir), os.path.basename(r.dir) + "-dm0102")
        self.addCleanup(shutil.rmtree, wt, True)
        self.assertIn(f"in worktree {wt}", out)
        self.assertEqual(self.git("branch", "--show-current").strip(), "main")
        with open(os.path.join(wt, "backlog/stories.toml"), encoding="utf-8") as f:
            self.assertIn('claimed_by = "Ada"', f.read())
        self.assertEqual(r.next("--me", "Bob")["claimable"], ["DM0101"])


@SKELETON_ONLY
class UpgradeTest(unittest.TestCase):
    """make sync-skeleton / adopt.py --upgrade: a 3-way merge against the version the project records."""

    def setUp(self) -> None:
        self.skel = Repo()  # the skeleton at 9.0.0, then 9.1.0
        self.addCleanup(self.skel.cleanup)
        s = self.skel
        s.write("tools/VERSION", "9.0.0\n")
        s.write("tools/CHANGELOG.md", "# Skeleton changelog\n\n## 9.0.0\n- base\n")
        for a in (("init", "-q", "-b", "main"), ("config", "user.name", "S"), ("config", "user.email", "s@example.org"),
                  ("add", "-A"), ("commit", "-qm", "9.0.0")):
            self.git(s.dir, *a)
        self.proj = tempfile.mkdtemp(prefix="wf-proj-")  # a project cloned at 9.0.0, then changed locally
        self.addCleanup(shutil.rmtree, self.proj, True)
        shutil.copytree(s.dir, self.proj, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        self.edit(self.proj, "workflow/steps/weekly.md", "\nLocal note.\n")
        # upstream changes for 9.1.0
        self.edit(s.dir, "workflow/steps/close.md", "\nUpstream change.\n")
        s.write("tools/VERSION", "9.1.0\n")
        s.write("tools/CHANGELOG.md", "# Skeleton changelog\n\n## 9.1.0\n- next\n\n## 9.0.0\n- base\n")
        s.write("project.toml", s.read("project.toml") + "\n[newsec]\nflag = true\n")
        s.write("tools/migrations/9.0.0-9.1.0.py", "print('migrated')\n")
        os.remove(os.path.join(s.dir, "workflow/steps/spike-review.md"))
        for a in (("add", "-A"), ("commit", "-qm", "9.1.0")):
            self.git(s.dir, *a)

    @staticmethod
    def git(cwd: str, *a: str) -> str:
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout

    @staticmethod
    def edit(root: str, p: str, add: str) -> None:
        with open(os.path.join(root, p), "a", encoding="utf-8") as f:
            f.write(add)

    def upgrade(self, ok: bool = True, *a: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k != "WF_ROOT"}
        r = subprocess.run([sys.executable, os.path.join(self.skel.dir, "tools/adopt.py"), self.proj, "--upgrade", *a],
                           capture_output=True, text=True, encoding="utf-8", env=env)  # the tools print UTF-8 on every console
        self.assertEqual(r.returncode == 0, ok, r.stdout + r.stderr)
        return r

    def read(self, p: str) -> str:
        with open(os.path.join(self.proj, p), encoding="utf-8") as f:
            return f.read()

    def test_upgrade_takes_upstream_keeps_local_changes_and_records_the_version(self):
        out = self.upgrade(True, "--dry-run").stdout
        self.assertIn("skeleton 9.0.0 → 9.1.0", out)
        self.assertNotIn("Upstream change.", self.read("workflow/steps/close.md"))
        out = self.upgrade().stdout
        self.assertIn("Upstream change.", self.read("workflow/steps/close.md"))
        self.assertIn("Local note.", self.read("workflow/steps/weekly.md"))
        self.assertFalse(os.path.exists(os.path.join(self.proj, "workflow/steps/spike-review.md")))
        self.assertIn("migration 9.0.0-9.1.0.py: migrated", out)
        p = tomllib.loads(self.read("project.toml"))
        self.assertEqual((p["skeleton"]["version"], p["newsec"]["flag"]), ("9.1.0", True))
        self.assertEqual(self.read("tools/VERSION").strip(), "9.1.0")

    def test_a_conflict_writes_nothing(self):
        self.edit(self.proj, "workflow/steps/close.md", "\nLocal change too.\n")
        out = self.upgrade(False).stdout
        self.assertIn("Conflicts — nothing written", out)
        self.assertIn("workflow/steps/close.md", out)
        self.assertEqual(self.read("tools/VERSION").strip(), "9.0.0")

    def commit_skeleton(self) -> None:
        for a in (("add", "-A"), ("commit", "-qm", "more for 9.1.0")):
            self.git(self.skel.dir, *a)

    def test_a_conflict_resolved_by_hand_is_kept_or_replaced(self):
        self.edit(self.proj, "workflow/steps/close.md", "\nLocal change too.\n")
        self.assertIn("--keep <file>", self.upgrade(False).stdout)
        self.assertIn("does not manage", self.upgrade(False, "--keep", "nope.md").stderr)
        self.assertIn("same file", self.upgrade(False, "--keep", "workflow/steps/close.md", "--take", "workflow/steps/close.md").stderr)
        self.upgrade(True, "--keep", "workflow/steps/close.md")  # the project's merge is the resolution
        self.assertIn("Local change too.", self.read("workflow/steps/close.md"))
        self.assertNotIn("Upstream change.", self.read("workflow/steps/close.md"))

    def test_take_replaces_the_local_change(self):
        self.edit(self.proj, "workflow/steps/close.md", "\nLocal change too.\n")
        self.assertIn("--take: local changes replaced", self.upgrade(True, "--take", "workflow/steps/close.md").stdout)
        self.assertIn("Upstream change.", self.read("workflow/steps/close.md"))
        self.assertNotIn("Local change too.", self.read("workflow/steps/close.md"))

    def test_example_templates_use_the_project_prefix_and_the_spec_index_is_regenerated(self):
        p = self.proj
        with open(os.path.join(p, "project.toml"), encoding="utf-8") as f:
            text = set_key(f.read(), "project", "id_prefix", "DM")
        with open(os.path.join(p, "project.toml"), "w", encoding="utf-8") as f:
            f.write(text)
        for t in ("inception/templates/stories.toml", "inception/templates/PLAN.md"):  # as init_project.py writes them
            with open(os.path.join(p, t), encoding="utf-8") as f:
                text = f.read().replace("PR01", "DM01")
            with open(os.path.join(p, t), "w", encoding="utf-8") as f:
                f.write(text)
        os.makedirs(os.path.join(p, "delivery/20-specs"), exist_ok=True)
        with open(os.path.join(p, "delivery/20-specs/SPEC-DM0101-walking-skeleton.md"), "w", encoding="utf-8") as f:
            f.write("# SPEC-DM0101 - Walking skeleton\n## Status\nDone\n")
        with open(os.path.join(p, "delivery/20-specs/README.md"), "w", encoding="utf-8") as f:
            f.write("# Spec index\n\n| DM0101 | kept by hand |\n")
        self.edit(self.skel.dir, "inception/templates/stories.toml", "\n# upstream note\n")
        self.edit(self.skel.dir, "delivery/20-specs/README.md", "\nupstream wording\n")
        self.commit_skeleton()
        out = self.upgrade().stdout
        self.assertIn("regenerated delivery/20-specs/README.md", out)
        stories = self.read("inception/templates/stories.toml")
        self.assertIn('id = "DM0101"', stories)
        self.assertIn("# upstream note", stories)
        self.assertNotIn("PR0101", stories)
        index = self.read("delivery/20-specs/README.md")
        self.assertIn("| [DM0101](SPEC-DM0101-walking-skeleton.md) | Walking skeleton | Done | — |", index)
        self.assertNotIn("upstream wording", index)

    def test_tool_tests_and_tool_settings_are_upgraded_where_the_project_has_them(self):
        self.edit(self.skel.dir, "tools/tests/test_portal.py", "\n# upstream test change\n")
        self.skel.write("tools/tests/test_new.py", "# a new upstream test\n")
        self.edit(self.skel.dir, ".github/workflows/workflow-check.yml", "\n# upstream CI change\n")
        self.edit(self.skel.dir, "tools/adopt.py", "\n# upstream installer change\n")
        m = self.skel.read("models.toml")
        self.skel.write("models.toml", m.replace("[tools.cursor]\n", "[tools.cursor]\nnewopt = true   # new setting\n", 1))
        self.commit_skeleton()
        self.upgrade()
        self.assertIn("# upstream test change", self.read("tools/tests/test_portal.py"))
        self.assertIn("# a new upstream test", self.read("tools/tests/test_new.py"))
        self.assertIn("# upstream CI change", self.read(".github/workflows/workflow-check.yml"))
        self.assertIn("# upstream installer change", self.read("tools/adopt.py"))
        models = tomllib.loads(self.read("models.toml"))
        self.assertIs(models["tools"]["cursor"]["newopt"], True)
        self.assertEqual(models["tools"]["cursor"]["vendor"], "anthropic")

    def test_tool_tests_and_ci_are_never_added(self):
        shutil.rmtree(os.path.join(self.proj, "tools/tests"))
        shutil.rmtree(os.path.join(self.proj, ".github/workflows"))
        for f in ("tools/adopt.py", "tools/upgrade.py"):
            os.remove(os.path.join(self.proj, f))
        self.upgrade()
        self.assertFalse(any(os.path.exists(os.path.join(self.proj, f)) for f in ("tools/adopt.py", "tools/upgrade.py")))
        self.assertFalse(os.path.exists(os.path.join(self.proj, "tools/tests")))
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".github/workflows/workflow-check.yml")))


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


@SKELETON_ONLY
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
