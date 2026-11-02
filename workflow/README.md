# Workflow playbook

How to move the project forward with agents while spending as few tokens as possible. Rules for agents are in `AGENTS.md` §5; this page is for the humans driving the loop.

## The loop

```
make next  (or /next on the fast tier)  → tells: step, IDs, command, tier → model per tool
   ├─ agent step  → fresh session, run the command (its model is pinned or recommended)
   └─ human gate  → you act (approve, workshop, review), then make next again
```

`tools/next_step.py` reads only files: `project.toml`, the status of inception artifacts, `backlog/stories.toml`, the sprints of `PLAN.md`, and the presence/status of Analysis, Refined Story, Brief, Spec, RUN. No LLM reads the repository to find out where we are.

Full step table (generated): [`STEPS.md`](STEPS.md). Step procedures: [`steps/`](steps/). Source of truth: [`workflow.toml`](workflow.toml).

## Phases

| Phase | Steps | Human gates |
|---|---|---|
| Inception | `/kickoff` → `/requirements` → `/mockup` (optional) → `/architecture` → `/backlog` → `/release-plan` | approve each artifact (`status: approved`) |
| Inception, existing codebase | `make adopt TARGET=…` (from the skeleton) → `/onboard` → `/backlog` → `/release-plan` | approve the onboarding artifacts, then backlog and plan |
| Analysis | `/analysis` → workshop → `/refine` | workshop + minutes |
| Delivery | `/brief` → Spec review → `/run` (strategy) → `/run <ID> approve` → execution → `/run <ID> tuning: …` → `/persist` → `/review-story` → `/close` | Spec `Ready`, strategy approval, tuning acceptance |
| Journal | `/weekly` (fast tier) | — |

Order in delivery: analysis one sprint ahead; development one story at a time, in `PLAN.md` order, with dependencies closed. While you are on a human gate, `make next` proposes analysis work ahead.

## Choosing models

- Steps declare a **tier**; `models.toml` maps tier → model per vendor and tool. `/choose-models` walks you through it, `make agents` regenerates the adapters.
- Which tier each step uses: [`AGENTS.md`](../AGENTS.md) §5 rule 4 (the per-step table is in [`STEPS.md`](STEPS.md)). `make next` routes L/XL stories to `/run-deep <ID>` (same procedure, deep tier).
- Claude Code and Copilot pin the model per command (Claude Code: for that turn only; follow-ups run on the session default, the balanced tier in `.claude/settings.json`, so answer gates with the command, e.g. `/run <ID> approve`); Codex and Cursor print the recommended model at the top of the command: switch to it before running.

## Token rules

They are binding for agents and listed once, in [`AGENTS.md`](../AGENTS.md) §5. What they mean for you: open a fresh session per step (except the `/run` chain of one story), and resume from `make next`.

## Harness map

The eight components of an agent harness ([harness engineering](https://www.news.aakashg.com/p/harness-engineering)) and where each lives here. **Enforced** = a hook, `make check` or CI stops the agent or the PR; **advisory** = text the agent reads and is expected to follow. Hooks run in Claude Code only; Codex, Copilot and Cursor get the advisory part.

| Component | Where | Kind |
|---|---|---|
| Instructions | [`AGENTS.md`](../AGENTS.md) (canonical), [`CLAUDE.md`](../CLAUDE.md), [`.github/copilot-instructions.md`](../.github/copilot-instructions.md), [`.cursor/rules/`](../.cursor/rules/), package `AGENTS.md` such as [`analysis/AGENTS.md`](../analysis/AGENTS.md), step procedures in [`steps/`](steps/), templates in `inception/`, `analysis/`, `delivery/templates/` | advisory; adapters kept in sync by `make check` |
| Context | budgets per step in [`workflow.toml`](workflow.toml), printed by [`tools/context.py`](../tools/context.py); large-read guard (#42, `project.toml [context] max_read_lines`) in [`tools/gate_guard.py`](../tools/gate_guard.py); context checkpoint (#55, `[context] checkpoint_tokens`, RUN §3 lines) in [`tools/context_watch.py`](../tools/context_watch.py); context cost share by tool-result kind (#47) in [`tools/usage.py`](../tools/usage.py) | budgets advisory; large reads and the checkpoint enforced (hooks); cost share measured by `/weekly` |
| Skills | commands rendered from `workflow.toml` into [`.claude/commands/`](../.claude/commands/), [`.agents/skills/`](../.agents/skills/) (Codex), [`.codex/prompts/`](../.codex/prompts/) by [`tools/render_agents.py`](../tools/render_agents.py) | advisory; model pinned per command (Claude Code, Copilot) |
| Memory | state in files: [`project.toml`](../project.toml), `backlog/stories.toml` and `PLAN.md` (created by `/backlog` and `/release-plan`), Brief/Spec/RUN in `delivery/`; decisions and weeklies in [`project-journal/`](../project-journal/) | state enforced by `make check`; journal advisory |
| Permissions | [`.claude/settings.json`](../.claude/settings.json) allow/deny prefixes; [`tools/gate_guard.py`](../tools/gate_guard.py): human gates, mode paths, risky git/gh, `.env`, destructive commands (`rm -r` outside the repo, `sudo`, `dd`, `mkfs`, `curl\|sh`, …), writes outside the repo (#44) | enforced (hook) |
| Tools | [`Makefile`](../Makefile) targets and `tools/*.py` (stdlib), see [`tools/README.md`](../tools/README.md); `reader` subagent on the fast tier (#46) in [`.claude/agents/reader.md`](../.claude/agents/reader.md) | read-only `reader` enforced (tool list); use advisory |
| Checks | `make check` ([`tools/check_workflow.py`](../tools/check_workflow.py)), `check_workflow.py --git` (strategy approved before code) and secret scan in [CI](../.github/workflows/workflow-check.yml), `make hooks` pre-commit [`tools/secret_scan.py`](../tools/secret_scan.py), `make test-tools` | enforced (CI) |
| Loop | `make next` ([`tools/next_step.py`](../tools/next_step.py)) → step → human gate via `make approve` ([`tools/approve.py`](../tools/approve.py), [`tools/gates.py`](../tools/gates.py)); tier → model in [`models.toml`](../models.toml) | gates enforced (hook + CI); routing and tiers advisory |
