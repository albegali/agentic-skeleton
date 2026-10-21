# Workflow tools

Stdlib Python ≥ 3.11, no dependencies. Every script resolves the repository root from its own location (or `$WF_ROOT`).

| Script | Make | What |
|---|---|---|
| `wf.py` | — | Shared helpers; `version`, `plan`, `journal`, `story <ID>` print contract data (see JSON contract). |
| `next_step.py` | `make next` | Next step from the files: inception gates, then sprints of `PLAN.md` and the stage of each story. `--json`, or one story: `next_step.py PR0101`. Status values come from one vocabulary (`wf.STATUSES`, shared with `check_workflow.py`); case, emphasis, emoji and a trailing parenthetical are ignored, and an unknown value is a human `blocked` stage naming the file. |
| `launch.py` | `make run` | Starts the app with `project.toml [stack] run`, waits for `url` to answer, opens the browser; Ctrl+C stops it (whole process group). `--no-browser`. Works without make: `python tools/launch.py`. |
| `context.py` | `make context STEP=… IDS=…` | Context budget of a step with a token estimate: files to read, kickoff sources, only the cited FR/NFR sections and `architecture §N` sections, ADR files, other `reference/…` files cited by path, dependency excerpts, command outputs. `--index <file>` prints headings only (Markdown or HTML); `--package-rules` lists package `AGENTS.md`; `--with <file>` adds files passed to the step (minutes). Paths cited with an anchor (`file.md#FR-27`) and files whose sections were extracted are not listed again in full. The estimate counts ADRs, package rules and the story diff where the step declares them. |
| `gen_backlog.py` | `make backlog` | `backlog/stories.toml` → `analysis/10-stories/`, `reference/backlog/epics/`, overview. `--deps` compact dependency list; `--csv` generic tracker import. |
| `check_workflow.py` | `make check` | Consistency: requirements, ADRs, `stories.toml` schema, backlog (prefix, epics, deps, cycles, FR coverage), PLAN.md ↔ backlog (unknown/unplanned stories, dependency order, capacity, release dates, overdue sprints), artifact chain (statuses, approval, unchecked AC/gates on Done/Closed, template placeholders), adapters freshness. `--git` also flags closed artifacts changed later without a `## Revisions` line. |
| `render_agents.py` | `make agents` | `workflow/workflow.toml` + `models.toml` → Claude Code / Codex / Copilot / Cursor adapters and `workflow/STEPS.md`. Files the project already owns (`CLAUDE.md`, `copilot-instructions.md`, `.claude/settings.json`) are merged, not overwritten. `--check` for CI. |
| `init_project.py` | (via `/kickoff`) | Writes `project.toml` / `models.toml` settings (incl. kickoff `--sources` and `--design`), re-prefixes template examples, renders adapters. |
| `adopt.py` | `make adopt TARGET=…` | Installs the workflow into an existing repository without overwriting its files (marked blocks in `AGENTS.md` / `CLAUDE.md`, `include workflow.mk`, permissions union), detects the `[stack]` commands, sets `origin = "brownfield"`. Conflicts → nothing written. `--dry-run` prints the plan. Not installed in the target. |
| `portal.py` | `make portal` | Start the agentic portal for this repository: downloads the pinned release bundle, verifies it, caches it in `.portal/<version>/`, starts it and opens the browser. See "Portal launcher". |
| `repo_map.py` | `context.py --repo-map` | Cheap map of the codebase for `/onboard`: languages, tree with sizes, manifests, CI/infra, docs, entry points, tests, largest files, git hot spots. No file contents. |
| `approve.py` | `make approve ID=… GATE=…` | **Run by the human.** Passes a gate (`spec`, `strategy`, `tuning`, `deviation:<n>`, `spike`, `refined`, `inception FILE=…`, `stack`): sets the field and commits only those files with `Approved-by` / `Approved-at` trailers. `--no-commit` to set the field only. |
| `gate_guard.py` | (Claude Code hook) | PreToolUse hook rendered into `.claude/settings.json`: blocks agent edits that pass a gate (unless the human's latest prompt is the gate command: `/run <ID> approve`, `approve-deviation <n>`, `/persist <ID>`), writes outside the current mode's paths, risky git/gh commands, `make approve`, reading `.env`. Exit 2 = blocked. |
| `sync_skeleton.py` | `make sync-skeleton [SKELETON=…] [ARGS=…]` | Upgrades the project's workflow files: fetches the skeleton (path or URL, `[skeleton] source`) and runs its `adopt.py --upgrade`, passing `--dry-run`, `--keep <file>`, `--take <file>`. |
| `adopt.py --upgrade` · `upgrade.py` | (skeleton only) | 3-way merge per installed file against the skeleton commit of the recorded version (example templates compared with the project's ID prefix; tool tests and `workflow-check.yml` only where the project has them); nothing written on conflict, `--keep`/`--take <file>` resolve one; new `project.toml`/`models.toml` keys added (also in existing `[tools.<name>]`); `tools/migrations/<from>-<to>.py` run; `[skeleton] version/source` recorded; adapters re-rendered; Spec index regenerated. |
| `CHANGELOG.md` | — | One `## <version>` per `tools/VERSION` (checked by `make check`), with **Upgrade** notes. |
| `claim.py` | `make claim ID=… [WORKTREE=1]` | Team use: creates the story branch (optionally in a worktree), records `claimed_by` / `claimed_at` in `stories.toml` on it, commits and pushes. `next_step.py --me <name>` skips others' claims; `check_workflow.py` flags double, stale and multiple claims. |
| `secret_scan.py` | `make secrets`, `make hooks` | Stdlib secret scan of code **and** artifacts (keys, tokens, private keys, connection strings, high-entropy hard-coded passwords). `--staged` (pre-commit hook installed by `make hooks`), `--branch` (story files), paths, `--json`. Values masked; `secret-scan: ignore` on a line for documented fakes. CI also runs gitleaks. |
| `quality_gates.py` | `make gates ID=…` | Runs `[stack]` test/lint and `[gates]` typecheck, coverage (vs `coverage_min`), mutation, secrets; writes RUN §8 `### Gates` (pass/fail facts); exit 1 on a failure. `make check` refuses a Closed RUN with a failing gate. |
| `gates.py` | — | Gate detection and application shared by the two above and `check_workflow.py --git` (strategy approval committed before any code on the branch). |
| `usage.py` | `make usage DAYS=…` | Agent sessions of this repository from the local logs of Claude Code (`~/.claude/projects/…`) and Codex (`~/.codex/sessions`), split by workflow command (built-ins such as `/clear` are ignored): step, step tier vs main model, peak context (flagged over ~80k), prompts, interrupts, rejected tool calls, tokens; per model: calls, tokens, cost and share of cost; per tier: share of calls and cost. Counts only, never prompt text. `--since/--until`, `--json`. Used by `/weekly`. |
| `rename_id.py` | — | Replace a story ID everywhere (whole IDs only, both in the project format; `--dry-run` lists the changes). |
| `wf.py` | — | Shared helpers. |

Tests: `make test-tools` (unittest, fixture repositories in temp dirs).

## JSON contract
For portals, CI and agents that prefer structured output (fewer tokens than the text views). Contract **1.0**: every contract `--json` output is one compact object `{"contract": "1.0", "tool": "<name>", "data": {…}}`. On failure the tool prints `{"contract", "tool", "error": {"code", "message"}}` (no `data`) and exits non-zero; codes: `unknown_id`, `bad_input` (unreadable or malformed file), `usage`. Empty states are valid `data` with empty lists.

Versioning (semver on `contract`, `wf.CONTRACT_VERSION`): a minor version only adds fields; removing or changing a field bumps the major. Consumers accept the same major and any minor at or above the one they were built for. `python3 tools/wf.py version [--json]` reports the skeleton version (`tools/VERSION`, so it never collides with an application's own `VERSION`) and the contract version. JSON Schemas (2020-12) are in `schemas/`; `jsonschema` is only a test dependency (`WF_REQUIRE_JSONSCHEMA=1` in CI).

Migration from the former `"schema": 1` output: `next_step.py`, `check_workflow.py` and `gen_backlog.py --json` moved to the envelope (fields unchanged, now under `data`). Only `context.py` and `repo_map.py` still print the flat `"schema": 1` object; they are outside contract 1.0. Contract tools only read: they never write a file.

| Command (`tool`) | Fields of `data` |
|---|---|
| `wf.py version --json` (`version`) | `skeleton`, `contract` |
| `next_step.py --json` (`next`) | `step`, `ids`, `owner`, `why`, `phase`, `tier`, `models`, `command`, `weekly_due`, `current_sprint`, `next_sprint`, `human_gates`; inception: `files`, `after` when an approval is pending; delivery: `stories` (`id`, `stage`, `detail`, `owner` for every backlog story), `optional` |
| `next_step.py <ID> --json` (`next-story`) | `step`, `ids`, `why`, `owner`, `deps`, `deps_done` |
| `check_workflow.py --json` (`check`) | `ok`, `errors`, `warnings`, `counts`, `issues` (`level`, `area`: inception/backlog/chain/adapters, `message`); workflow errors are data (`ok: false`), exit code as the text view (1 on errors) |
| `gen_backlog.py --json` (`backlog`) | `status`, `epics`, `stories` (TOML fields + `artifacts`: paths of story/analysis/refined/brief/spec/run or null); writes nothing |
| `wf.py plan --json` (`plan`) | `releases` (`id`, `title` = Content, `goal` = Exit criterion, `target`, `sprints`: those whose stories have that `release` in `stories.toml`) from the `PLAN.md` release table; `sprints` (`sprint`, `dates`, `goal`, `ids`, `release` when known) |
| `wf.py journal --json` (`journal`) | `context` (text of `project-journal/context/*.md` except README, or null); `decisions`, `learnings`, `weekly`, `monthly`: `file`, `title` (first `# ` heading), `date` (frontmatter `date` or `YYYY-MM-DD` in the file name) |
| `wf.py story <ID> --json` (`story`) | `id`, `title`, `stage` (as `next_step.py`), `artifacts` (`kind`: story/analysis/refined/brief/spec/run, `path`, `status`), `tasks` (`id`, `title` from Spec §5; `status` `done`/`deferred` from RUN §9, ranges `TSK-X-01 to TSK-X-08` included, else `open`); unknown ID → error `unknown_id` |
| `context.py <step> [IDs] --json` · *flat, not in contract 1.0* | `step`, `tier`, `ids`, `needs_ids`, `read` (`path`, `lines`, `tokens`, `long`), `missing`, `design`, `cited` (`path`, `exists`, `lines`, `tokens`, `long`), `sections` (`ref`, `file`, `text`, `tokens`), `dependencies`, `runs`, `package_rules` (`path`, `lines`, `tokens`, `long`), `diff` (`base`, `files`, `stat`, `tokens`, `by_file`, or null), `tokens` (estimate of the whole budget) |
| `context.py --index <file> --json` · `--package-rules --json` · *flat* | `file`, `headings` · `rules` |
| `repo_map.py --json` (= `context.py --repo-map --json`) · *flat* | `name`, counts, `languages`, `other_types`, `signals`, `dirs`, `root_files`, `docs`, `migrations`, `entry_points`, `tests`, `source_sizes`, `git` (`commits`, `first`, `last`, `authors`, `churn_180d`) or null, `stack` |

## Portal launcher
`make portal` (or `python tools/portal.py` where make is missing, e.g. Windows). The launcher itself needs Python >= 3.11 and nothing else; the portal bundle may need a newer Python (`requires_python` in its manifest) and is run with a matching interpreter (`python3.<minor>`, or `py -3.<minor>` on Windows).

`project.toml`:
```toml
[portal]
version = "x.y.z"            # required: the pinned portal release
# source = "<owner>/<repo>"  # optional: GitHub repository whose Releases host the bundle
```
Flow: find the repository root (nearest `project.toml`) → if `.portal/run.json` points to a portal that answers `/api/health`, open it → else use `.portal/<version>/` if cached, or download `manifest.json` and the zip it names from `https://github.com/<source>/releases/download/v<version>/`, verify size and SHA-256 (abort with exit 2 on mismatch), extract safely (absolute, `..`, drive-letter and symlink entries are rejected) into `.portal/<version>.tmp`, rename → start the server on `127.0.0.1` (port 8765, else the next free one) and open the browser (`--no-browser` to skip). Ctrl+C stops it. Add `.portal/` to `.gitignore`.

`PORTAL_BUNDLE=<zip or directory>` skips the download (offline or development): a zip is verified when a `manifest.json` sits next to it; a directory is used as it is. Exit codes: 0 ok, 1 user/config error (no `project.toml`, missing or unknown version, no network and no cache, Python too old), 2 integrity error (checksum, unsafe archive, unsupported manifest).

Session token: on each start the launcher generates a 256-bit token, writes it to `.portal/token` (created with mode 0600; on Windows restricted to the current user with `icacls`, a warning if that fails), gives it to the server as `PORTAL_TOKEN` (environment only, never an argument) and opens `<url>/#token=<token>`, printing that URL once. A portal that is already running is opened with the token read from `.portal/token`; if the file is missing, empty or readable by other users the plain URL opens and a message explains how to restart. `.portal/token` is removed when the launcher exits; `run.json` never contains the token.

`manifest.json` (release asset, manifest format 1): `{"manifest": 1, "version": "x.y.z", "asset": "agentic-portal-x.y.z.zip", "size": <bytes>, "sha256": "<hex>", "requires_python": ">=3.14"}`. Unknown keys are ignored; a different `manifest` major makes the launcher stop. The bundle zip holds the `portal_server/` package at its root.

## Kickoff sources and existing design
`project.toml [inception]` records `sources` (brief, transcripts, notes) and `design` (an existing mockup or prototype), written by `init_project.py --sources … --design …` during `/kickoff`. Budgets with `sources = true` (requirements, mockup, architecture) read the sources; `design = true` (mockup) points to the design's outline (`context.py --index`, which also outlines HTML) so `/mockup` maps it instead of rebuilding it. `make check` warns when a recorded file is missing.

## Adding a step or a command
1. Add `[steps.<id>]` and/or `[commands.<name>]` to `workflow/workflow.toml` (tier, budget, body).
2. Write `workflow/steps/<id>.md` (procedure, prompt, chat output limit, gate).
3. If the step changes the lifecycle, teach `next_step.py` when to recommend it.
4. `make agents && make check && make test-tools`.

## Tracker adapters
`project.toml` → `tracker = "local"` keeps everything in the repository. To sync with an external tracker (Azure DevOps, Jira, GitHub Issues, Linear), add `tools/trackers/<name>.py` that reads `backlog/stories.toml` and the delivery artifacts and pushes/pulls through the tracker API; keep the workflow IDs and record the tracker's own ID as `tracker_id` in `stories.toml`. Keep it out of the agents' default permissions: syncing is an outward-facing action that a human triggers.
