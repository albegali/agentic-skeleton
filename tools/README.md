# Workflow tools

Stdlib Python ≥ 3.11, no dependencies. Every script resolves the repository root from its own location (or `$WF_ROOT`).

| Script | Make | What |
|---|---|---|
| `next_step.py` | `make next` | Next step from the files: inception gates, then sprints of `PLAN.md` and the stage of each story. `--json`, or one story: `next_step.py PR0101`. |
| `context.py` | `make context STEP=… IDS=…` | Context budget of a step with a token estimate: files to read, kickoff sources, only the cited FR/NFR sections, ADR files, dependency excerpts, command outputs. `--index <file>` prints headings only (Markdown or HTML); `--package-rules` lists package `AGENTS.md`. |
| `gen_backlog.py` | `make backlog` | `backlog/stories.toml` → `analysis/10-stories/`, `reference/backlog/epics/`, overview. `--deps` compact dependency list; `--csv` generic tracker import. |
| `check_workflow.py` | `make check` | Consistency: requirements, ADRs, backlog (prefix, epics, deps, cycles, FR coverage), artifact chain, adapters freshness. |
| `render_agents.py` | `make agents` | `workflow/workflow.toml` + `models.toml` → Claude Code / Codex / Copilot / Cursor adapters and `workflow/STEPS.md`. Files the project already owns (`CLAUDE.md`, `copilot-instructions.md`, `.claude/settings.json`) are merged, not overwritten. `--check` for CI. |
| `init_project.py` | (via `/kickoff`) | Writes `project.toml` / `models.toml` settings (incl. kickoff `--sources` and `--design`), re-prefixes template examples, renders adapters. |
| `adopt.py` | `make adopt TARGET=…` | Installs the workflow into an existing repository without overwriting its files (marked blocks in `AGENTS.md` / `CLAUDE.md`, `include workflow.mk`, permissions union), detects the `[stack]` commands, sets `origin = "brownfield"`. Conflicts → nothing written. `--dry-run` prints the plan. Not installed in the target. |
| `repo_map.py` | `context.py --repo-map` | Cheap map of the codebase for `/onboard`: languages, tree with sizes, manifests, CI/infra, docs, entry points, tests, largest files, git hot spots. No file contents. |
| `rename_id.py` | — | Replace a story ID everywhere (e.g. adopting tracker IDs). |
| `wf.py` | — | Shared helpers. |

Tests: `make test-tools` (unittest, fixture repositories in temp dirs).

## JSON contract
For portals, CI and agents that prefer structured output (fewer tokens than the text views). Every `--json` output is one compact JSON object with `"schema": 1`; fields are only added within a schema version, a breaking change bumps it (`wf.SCHEMA`).

| Command | Top-level fields |
|---|---|
| `next_step.py --json` | `step`, `ids`, `owner`, `why`, `phase`, `tier`, `models`, `command`, `weekly_due`, `current_sprint`, `next_sprint`, `human_gates`; inception: `files`, `after` when an approval is pending; delivery: `stories` (`id`, `stage`, `detail`, `owner` for every backlog story), `optional` |
| `next_step.py <ID> --json` | `step`, `ids`, `why`, `owner`, `deps`, `deps_done` |
| `check_workflow.py --json` | `ok`, `errors`, `warnings`, `counts`, `issues` (`level`, `area`: inception/backlog/chain/adapters, `message`); exit code as the text view |
| `gen_backlog.py --json` | `status`, `epics`, `stories` (TOML fields + `artifacts`: paths of story/analysis/refined/brief/spec/run or null); writes nothing |
| `context.py <step> [IDs] --json` | `step`, `tier`, `ids`, `needs_ids`, `read` (`path`, `lines`, `tokens`, `long`), `missing`, `design`, `sections`, `dependencies`, `runs`, `tokens` (estimate of the whole budget) |
| `context.py --index <file> --json` · `--package-rules --json` | `file`, `headings` · `rules` |
| `repo_map.py --json` (= `context.py --repo-map --json`) | `name`, counts, `languages`, `other_types`, `signals`, `dirs`, `root_files`, `docs`, `migrations`, `entry_points`, `tests`, `source_sizes`, `git` (`commits`, `first`, `last`, `authors`, `churn_180d`) or null, `stack` |

## Kickoff sources and existing design
`project.toml [inception]` records `sources` (brief, transcripts, notes) and `design` (an existing mockup or prototype), written by `init_project.py --sources … --design …` during `/kickoff`. Budgets with `sources = true` (requirements, mockup, architecture) read the sources; `design = true` (mockup) points to the design's outline (`context.py --index`, which also outlines HTML) so `/mockup` maps it instead of rebuilding it. `make check` warns when a recorded file is missing.

## Adding a step or a command
1. Add `[steps.<id>]` and/or `[commands.<name>]` to `workflow/workflow.toml` (tier, budget, body).
2. Write `workflow/steps/<id>.md` (procedure, prompt, chat output limit, gate).
3. If the step changes the lifecycle, teach `next_step.py` when to recommend it.
4. `make agents && make check && make test-tools`.

## Tracker adapters
`project.toml` → `tracker = "local"` keeps everything in the repository. To sync with an external tracker (Azure DevOps, Jira, GitHub Issues, Linear), add `tools/trackers/<name>.py` that reads `backlog/stories.toml` and the delivery artifacts and pushes/pulls through the tracker API; adopt the tracker IDs with `rename_id.py`. Keep it out of the agents' default permissions: syncing is an outward-facing action that a human triggers.
