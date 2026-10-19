# agentic-skeleton

A repository skeleton for **agent-supervised software development**: AI agents do the work step by step, humans hold the gates, and every step is traceable in files.

- **Whole lifecycle**: inception (vision, requirements, mockup, architecture, backlog, release plan) → analysis (Analysis, workshop, Refined Story) → delivery (Brief, Spec, RUN, code, persistence, review) → project journal.
- **Model and vendor agnostic**: one neutral source (`workflow/workflow.toml`) is rendered into commands for **Claude Code, OpenAI Codex CLI, GitHub Copilot and Cursor**. Steps declare a tier (`fast` / `balanced` / `deep`); you choose the model per tier and vendor in `models.toml`.
- **Token-frugal by design**: a deterministic script computes the state (`make next`), another prints the exact context of each step (`tools/context.py`), commands are thin, sessions are short.
- **Stack neutral**: `/architecture` proposes the stack, writes the ADRs, and wires `make setup/test/lint`.
- **Any kind of software, new or existing**: web, services on any cloud or on-prem, mobile, desktop, games, firmware, libraries, CLIs, data, infrastructure. `make adopt TARGET=<repo>` installs the workflow into any existing repository without overwriting its files, and `/onboard` documents the codebase as the baseline (architecture, retroactive ADRs, package rules, FR index).
- **English by default**; `/kickoff` can set another language for the artifacts.

## Prerequisites

| Need | Why | Check |
|---|---|---|
| Python ≥ 3.11 | workflow tools (stdlib only, nothing to install) | `python3 --version` |
| `make` | entry points (`make next`, `make check`, …) | `make --version` |
| git | versioning, `git diff` for reviews | `git --version` |
| At least one agent tool | Claude Code, OpenAI Codex CLI, GitHub Copilot (VS Code) or Cursor, with an active plan or API key | see [docs/GUIDE.md §4](docs/GUIDE.md#4-set-up-your-agent-tools) |

You also need someone in the **product owner** role who approves artifacts, and source material for your idea: a brief, meeting transcripts, existing specs, or simply your own notes.

## Quick start

Full walkthrough (fork, tool setup, inception, story loop, team routines, troubleshooting): **[docs/GUIDE.md](docs/GUIDE.md)**.

```bash
cp -r agentic-skeleton my-project && cd my-project && rm -rf .git && git init
make next          # → /kickoff
```

Then in your agent tool:

| Step | Command | You do |
|---|---|---|
| 1 | `/kickoff "My project" brief.md` | answer the setup questions (name, ID prefix, language, owner, tools) and the short interview; approve `vision.md` |
| 2 | `/choose-models` (optional) | pick a model per tier for each tool |
| 3 | `/requirements transcript.md spec.pdf` | approve FR / NFR |
| 4 | `/mockup` | review the clickable HTML mockup; approve the map |
| 5 | `/architecture` | confirm decisions; accept ADRs; set `decided = true` |
| 6 | `/backlog` | approve `backlog/stories.toml` |
| 7 | `/release-plan` | approve `PLAN.md` |
| 8… | `/next` and follow it | workshops, Spec review, strategy approval, tuning |

**Existing codebase?** From the skeleton: `make adopt TARGET=../my-app ARGS="--dry-run"`, then without `--dry-run`; commit in the target, then `/onboard` → `/backlog` → `/release-plan` → `/next`. See [docs/GUIDE.md §3 Option D](docs/GUIDE.md#option-d--an-existing-codebase-brownfield).

Every agent step runs in a **fresh session**. `/next` (or `make next`) always tells you the next command, its tier and the model to use for each of your tools.

## Repository map

```
AGENTS.md                 canonical rules for every agent (tool-neutral)
project.toml              name, ID prefix, language, owner, stack commands
models.toml               tier → model per vendor / tool
workflow/                 workflow.toml (steps, commands, agents) · steps/*.md · STEPS.md (generated) · README.md (playbook)
inception/templates/      vision, requirements, mockup map, ADR, architecture, stories.toml, PLAN.md
analysis/                 Story (generated) · Analysis · Refined Story · templates · guide
delivery/                 Brief · Spec · RUN · templates · guide (core + on-demand sections)
reference/                product, architecture, domain, mockup — read via tools/context.py
backlog/stories.toml      backlog source of truth (created by /backlog)
PLAN.md                   release plan (created by /release-plan)
project-journal/          weekly / monthly memory of the project
tools/                    next_step, context, check_workflow, gen_backlog, render_agents, init_project, rename_id, adopt, repo_map (+ tests)
.claude/ .codex/ .github/prompts/ .cursor/   generated adapters — do not edit, run `make agents`
```

## Make targets

| Target | What |
|---|---|
| `make next` | next step, deterministic |
| `make context STEP=analysis IDS="PR0101"` | context budget of a step |
| `make check` | workflow consistency + adapters up to date (CI) |
| `make backlog` | regenerate Story files and views from `backlog/stories.toml` |
| `make agents` | regenerate the tool adapters after editing `workflow/` or `models.toml` |
| `make test-tools` | tests of the workflow tools |
| `make setup / test / lint` | stack commands from `project.toml [stack]` |
| `make codex-prompts` | link the Codex prompts into `~/.codex/prompts` |
| `make adopt TARGET=<repo>` | install the workflow into an existing repository (run from the skeleton; `ARGS="--dry-run"` first) |

## Tool notes

| Tool | Commands | Model per command | Rules file |
|---|---|---|---|
| Claude Code | `.claude/commands/` (`/next`, …), subagents in `.claude/agents/` | pinned (frontmatter `model`) | `CLAUDE.md` → `AGENTS.md` |
| Codex CLI | `.codex/prompts/` → `make codex-prompts`, then `/prompts:next` | recommended at the top of the prompt (`codex -m <model>`) | `AGENTS.md` (native) |
| GitHub Copilot | `.github/prompts/*.prompt.md` (`/next` in chat) | pinned (frontmatter `model`; check the labels of your Copilot plan) | `.github/copilot-instructions.md` → `AGENTS.md` |
| Cursor | `.cursor/commands/` (`/next`) | recommended at the top of the command | `.cursor/rules/workflow.mdc` → `AGENTS.md` |

Model names change often: the non-Anthropic defaults in `models.toml` are marked `verify`. Run `/choose-models` at the start of each project.

## Customizing

- **Add or change a step / command**: edit `workflow/workflow.toml` and `workflow/steps/<step>.md`, then `make agents && make check && make test-tools` (see `tools/README.md`).
- **External tracker** (Azure DevOps, Jira, …): see "Tracker adapters" in `tools/README.md`.
- **Hotfix / refactor / NFR work**: `delivery/guide/`.

## Origin

Extracted from a real project that ran this workflow: the analyst / developer / review split, the Brief → Spec → RUN chain, the human gates and the project journal come from there. Added here: the inception phase, the neutral workflow source with multi-tool adapters, model tiers, context budgets computed by script, a slimmer delivery guide, and tests for the tools.
