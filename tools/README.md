# Workflow tools

Stdlib Python ≥ 3.11, no dependencies. Every script resolves the repository root from its own location (or `$WF_ROOT`).

| Script | Make | What |
|---|---|---|
| `next_step.py` | `make next` | Next step from the files: inception gates, then sprints of `PLAN.md` and the stage of each story. `--json`, or one story: `next_step.py PR0101`. |
| `context.py` | `make context STEP=… IDS=…` | Context budget of a step: files to read, only the cited FR/NFR sections, ADR files, dependency excerpts, command outputs. `--index <file>` prints headings only; `--package-rules` lists package `AGENTS.md`. |
| `gen_backlog.py` | `make backlog` | `backlog/stories.toml` → `analysis/10-stories/`, `reference/backlog/epics/`, overview. `--deps` compact dependency list; `--csv` generic tracker import. |
| `check_workflow.py` | `make check` | Consistency: requirements, ADRs, backlog (prefix, epics, deps, cycles, FR coverage), artifact chain, adapters freshness. |
| `render_agents.py` | `make agents` | `workflow/workflow.toml` + `models.toml` → Claude Code / Codex / Copilot / Cursor adapters and `workflow/STEPS.md`. `--check` for CI. |
| `init_project.py` | (via `/kickoff`) | Writes `project.toml` / `models.toml` settings, re-prefixes template examples, renders adapters. |
| `rename_id.py` | — | Replace a story ID everywhere (e.g. adopting tracker IDs). |
| `wf.py` | — | Shared helpers. |

Tests: `make test-tools` (unittest, fixture repositories in temp dirs).

## Adding a step or a command
1. Add `[steps.<id>]` and/or `[commands.<name>]` to `workflow/workflow.toml` (tier, budget, body).
2. Write `workflow/steps/<id>.md` (procedure, prompt, chat output limit, gate).
3. If the step changes the lifecycle, teach `next_step.py` when to recommend it.
4. `make agents && make check && make test-tools`.

## Tracker adapters
`project.toml` → `tracker = "local"` keeps everything in the repository. To sync with an external tracker (Azure DevOps, Jira, GitHub Issues, Linear), add `tools/trackers/<name>.py` that reads `backlog/stories.toml` and the delivery artifacts and pushes/pulls through the tracker API; adopt the tracker IDs with `rename_id.py`. Keep it out of the agents' default permissions: syncing is an outward-facing action that a human triggers.
