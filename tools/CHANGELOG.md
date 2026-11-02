# Skeleton changelog

One heading per `tools/VERSION`, newest first (`make check` requires the current one). **Upgrade** lines say what a
project must do beyond `make sync-skeleton`.

## 1.25.1
- Branches of the upstream skeleton remote (#61): `make next` and `make check` reported `skeleton/main` and the skeleton's feature branches (fetched by `make sync-skeleton`) as stale story branches, and a skeleton branch whose name contains a project story ID (e.g. `feat/ap0105-…`) as a claim on that story. `wf.branch_refs()` now lists local branches and every remote except the one pointing at `[skeleton] source` (unless `main` tracks it: the skeleton itself); `story_branches()` and `stale_branches()` use it, and strip any of those remotes' prefix (not only `origin/`).
- `wf` git calls never wait for input (stdin closed, `GIT_TERMINAL_PROMPT=0`). CI: `WF_TEST_TIMEOUT` is the whole suite's deadline, raised from 300 to 600 s (the Windows suite takes ~5 min).
- **Upgrade**: nothing to do by hand. The workaround `git remote set-branches skeleton main` is no longer needed but harmless.

## 1.25.0
- Context checkpoint (#55): new Claude Code `PostToolUse` hook `tools/context_watch.py`. It reads the last ~256 KB of the session transcript, takes the context of the last main-chain call (input + cache read + cache write) and, past `project.toml [context] checkpoint_tokens` (default 80000, `0` = off), adds a message for the agent, once per crossing and again every +20k (state in the system temp dir, per session). During an executing `/run <ID>` (strategy approved): finish the plan step, record it in RUN §3, then ask the human for `/clear` + `/run <ID>`; another command: finish the step's output, then `/clear`; no command: `/clear` and `make next`. It never blocks and never touches a gate.
- RUN §3 Steps: one append-only checkpoint line per plan step, `- TSK-<ID>-01: done · files: … · tests: … · next: TSK-<ID>-02` (template and `workflow/steps/execute.md`); a resumed `/run` reads the context budget and the RUN's last §3 line. `make check` warns on an `Executing` RUN whose §3 lines do not start with a TSK ID of its §1 Plan (plans without TSK IDs are not checked; JSON contract unchanged).
- `gate_guard.last_command(…, sticky=True)`: the session's latest workflow command, kept across free-text follow-ups and built-ins (`/compact`), so "ok, continue" during a `/run` still gets the `/run` message. The guard itself keeps the latest-prompt behaviour.
- `render_agents.py`: renders the new hook next to `gate_guard.py`; an older entry of either hook is replaced, not duplicated.
- **Upgrade**: `make sync-skeleton` adds `[context] checkpoint_tokens` to `project.toml` and re-renders `.claude/settings.json`. Codex, Copilot and Cursor have no hooks: they keep the advisory rule in `workflow/steps/execute.md`.

## 1.24.0
- `tools/usage.py` / `/weekly` (#54): fixed prefix per tool, the median first-call context of the period's sessions (Claude Code: the first main-context call's input + cache read + cache write; Codex: the first `token_count` call) against the repository's always-loaded share (`wf.prefix_tokens()`). The text view gets one "Fixed prefix: first-call context median … of which this repository ~… (…%)" line per tool, `--json` a top-level `prefix` object (`repo_tokens`, `tools.<tool>.sessions|first_call_median|repo_share`).
- `docs/GUIDE.md` §9.1 "Trim your tool prefix": per-tool steps to trim MCP servers, skills, plugins and built-in tools (Claude Code, Codex CLI, Copilot in VS Code, Cursor), checked against the vendors' docs, "not documented" where they say nothing; how to read the `/weekly` line. §9's old pointer to `enabledMcpjsonServers` / `disabledMcpjsonServers` (project `.mcp.json` servers only) now points there.
- **Upgrade**: nothing to do by hand; to trim, follow `docs/GUIDE.md` §9.1 in your personal tool settings.

## 1.23.0
- Destructive-command guard (#44): `gate_guard.py` blocks `rm -r` (any flag order, `--recursive`) of the repository root, its `.git`, a parent, a path outside the repository or a target it cannot resolve (`$HOME`, other variables, a top-level glob); recursive deletes inside the repository (`build/`, `node_modules`, `.portal/`) and inside the system temp dirs (`/tmp`, `/private/tmp`, `/var/tmp`, `$TMPDIR`) pass. Also blocked: `chmod|chown|chgrp -R` and `find … -delete` outside the repository, `git clean -x` of the whole repository without `-n`/`--dry-run`, `sudo`/`doas`, `mkfs`, `shred`, `dd of=/dev/…`, `diskutil erase…`, `curl|wget … | sh` and `sh -c "$(curl …)"`. Commands are parsed per simple command (quotes respected, `cd` followed, heredoc bodies ignored unless fed to a shell): a mention in a string or heredoc is not a run.
- `gate_guard.py`: Edit/Write/MultiEdit outside the repository is blocked, except the system temp dirs, the agent's own dir (`~/.claude/`, `$CLAUDE_CONFIG_DIR`: memory, plans) and the directories listed in the new `project.toml [guard] write_paths` (`~` expanded, relative paths from the repository). `find -delete` of the whole repository without a filter is blocked.
- `.claude/settings.json` deny list: `sudo`, `mkfs`, `shred`, `diskutil eraseDisk|eraseVolume` (`rm -r` targets are resolved by the hook, not by prefix).
- `workflow/README.md`: harness map, the eight harness components (instructions, context, skills, memory, permissions, tools, checks, loop) with where each lives and whether it is enforced or advisory.
- **Upgrade**: `make sync-skeleton` (or `make agents`) re-renders the deny list in `.claude/settings.json`. `make sync-skeleton` adds `[guard] write_paths = []` to `project.toml`; list there any directory outside the repository agents must edit (e.g. the skeleton, when fixing it from a project session).

## 1.22.0
- Quiet success output (#48, from spike #43): `make test-tools` and the `[stack]` `make setup|test|lint` run through the new `tools/quiet.py`: on success only the `WARN` lines and the last summary lines (`Ran N tests in …s` / `OK`; unittest now runs with `-b`, so stray stdout of passing tests is dropped), on failure the full output; `V=1` restores the full, streamed output. `make check` and `make gates` already print one summary line per area or gate.
- Prefix budget: `make check` reports the always-loaded prefix (`AGENTS.md`, `CLAUDE.md`, the `.claude/commands` and `.claude/agents` descriptions) on the counts line as `prefix ~N/B tokens` and warns above `project.toml [context] prefix_budget` (default 2500, `0` = off). Not in the `--json` data (contract unchanged).
- Trimmed: `AGENTS.md` (same rules and section numbers, shorter wording; the `reader` subagent's per-tool support moved to `docs/GUIDE.md` §9), the rendered `CLAUDE.md` and the command/agent descriptions in `workflow/workflow.toml`: prefix ~2670 → ~2380 tokens.
- **Upgrade**: `make sync-skeleton` adds `[context] prefix_budget` to `project.toml` and re-renders the adapters. A project whose own `AGENTS.md`/`CLAUDE.md` rules exceed the budget gets a warning: shorten them, or raise the budget on purpose.

## 1.21.0
- `reader` subagent (#46, from spike #43): read-only (`Read`, `Grep`, `Glob`, no Bash) on the `fast` tier, rendered from `workflow.toml [agents.reader]` to `.claude/agents/reader.md` (and `.github/agents/reader.agent.md` for Copilot, where the renderer sets no tool list, so read-only is enforced in Claude Code only; Codex and Cursor have no subagents). It answers questions that span many files with bullets that lead with the exact name and `file:line`, no preamble or summary, "unsure" instead of guessing, no count without the items; the caller verifies the lines before editing. AGENTS.md §5 says when to use it (`/onboard`, `/analysis` of existing code, cross-file questions) and when not (editing, debugging, architecture, review judgments); CLAUDE.md names it as the exception to "no subagents".
- `gate_guard.py`: the large-read block message also points to the `reader` subagent.
- **Upgrade**: `make sync-skeleton` (or `make agents` after taking `workflow/workflow.toml`) renders the new agent.

## 1.20.0
- `tools/usage.py` / `/weekly` (#47, from spike #43): context cost share by tool-result kind. Every tool result still in the main context is charged on each later call (first send as a cache write ×1.25, then a cache read ×0.1) until `/clear`, `/compact` or a context drop; shares of the weighted main-context cost for full reads over `[context] max_read_lines`, small reads, targeted reads, `context.py` output, other Bash output, subagent results and other, plus the fixed prefix and output. `--json` gets a top-level `cost_share` object; the text view a "Context cost share" line. Claude Code only.
- **Upgrade**: nothing to do by hand.

## 1.19.0
- Large-read guard (#42): `gate_guard.py` blocks a full `Read` (no offset/limit) or a bare `cat|head|tail|less|more <file>` of a text file longer than `project.toml [context] max_read_lines` (default 400, `0` = off) and points the agent to `tools/context.py --index`, a section extract or an offset/limit read. Small, missing and binary files, targeted reads and piped commands pass. The hook matcher now includes `Read`; `make agents` replaces the older matcher of our hook instead of adding a second entry.
- `tools/usage.py` / `/weekly`: new column and total "large reads blocked" (from the guard's message in the session logs, Claude Code only).
- **Upgrade**: `make sync-skeleton` adds `[context]` to `project.toml` and re-renders `.claude/settings.json`. Codex, Copilot and Cursor have no hooks: they keep the AGENTS.md token rule only.

## 1.18.0
- Contract **1.1** (additive): `gates.py list --json` (every pending human gate, from the detection `next_step.py` uses, with `id` `<gate>:<artifact path>`, `field`, `current`, `proposed`, `since`, `age_days`), `gates.py approve <gate-id>` and `gates.py request-changes <gate-id> --comment …` (envelope tool `gates`, schema `schemas/gates.schema.json`; errors `unknown_gate`, `stale_gate`, `invalid_transition`, `no_owner`, `comment_required`, `usage`, `bad_input`). The approver is the `project.toml` owner. `approve` is the same edit and commit as `make approve` (shared code in `gates.py`); `request-changes` puts the gate's field back to its draft value and adds one line to the artifact's `## Gates` section (a `# Gates` comment block in TOML), without committing.
- `gates.py` writes atomically and keeps CRLF line endings (also for `make approve`); `approve.py` commits through `gates.commit_paths`, which also stages a not yet tracked artifact. `gate_guard.py` blocks agents from `gates.py approve|request-changes`.
- Templates that can receive a request-changes line get a `## Gates` section.
- **Upgrade**: nothing to do by hand.

## 1.17.3
- `/close` (#39): after a squash merge `git branch -D <story-branch>` is allowed by `gate_guard.py` when the branch's content is already in `main` (`git merge-tree` equals `main`'s tree); every other forced deletion stays blocked.

## 1.17.2
- `check_workflow.py --git` (#37): a RUN already approved in the base branch is not checked against the current branch's commits, so a later branch (e.g. a skeleton upgrade) no longer fails with "code committed with the strategy approval" for every closed RUN.

## 1.17.1
- `make sync-skeleton` fixes (#35): the example templates are compared and written with the project's ID prefix; the Spec index is regenerated, never merged (`gen_backlog.py --spec-index`); a conflict is resolved with `ARGS="--keep <file>"` (your hand merge) or `--take <file>` (the skeleton's file); tool tests and `workflow-check.yml` are upgraded where the project has them, never added; new settings of a tool already in `models.toml [tools.<name>]` are added.
- `make check`: a Closed RUN whose §11 is the old `Addendum` (skeleton before 1.7.0) gets the "no §11 Review" warning, not a review-record error.
- Tool tests skip the installer/upgrader tests outside the skeleton and no longer assume the skeleton's own package rules or models.
- **Upgrade**: from 1.16.0 or 1.17.0 nothing to do by hand. From an older version, files patched locally while the skeleton shipped the same change (typically `tools/usage.py`, `tools/wf.py`, the weekly step/template, `workflow/workflow.toml`, `tools/README.md`, the Makefile, `tools/adopt.py`, `tools/tests/test_workflow.py`) conflict: `--take` them unless the change is yours alone.

## 1.17.0
- Trunk-based development (mandatory, `delivery/guide/git.md`): `main` is the only long-lived branch, a release is a tag; short-lived story branches updated from `origin/main` before `/persist` and `/close`.
- `gate_guard.py` blocks creating `release/*`, `develop`, `staging`, `integration` branches; `make next` and `make check` report branches with commits older than `[git] max_branch_age_days` (default 3) not in `main`.
- **Upgrade**: `make sync-skeleton` adds `max_branch_age_days` to `project.toml [git]`; delete any long-lived branch your project still has.

## 1.16.0
- Upgrade path: `make sync-skeleton` (3-way merge per file, nothing written on conflict, migrations, new settings added); `project.toml [skeleton] version/source`; this changelog.
- Cross-repo stories: `repo = "<name>"` on a story, RUN References `Upstream:`; pending owner actions in RUN `## Pending owner actions`, shown by `make next`.
- **Upgrade**: projects without `[skeleton] version` get it from their `tools/VERSION` on the first sync.

## 1.15.0
- Team use: `make claim`, `make next --me`, worktrees, claim checks; story branch created at `/brief`; commit points per phase; `[git] trailers = "agent"`.

## 1.14.0
- `tools/secret_scan.py`, `make secrets`, `make hooks`, gitleaks in CI; `/security-review` step for security-sensitive stories; `[gates]` + `make gates`.

## 1.13.0
- Codex skills in `.agents/skills/`, profiles in `.codex/config.toml`; Copilot `agent:` key and `.github/agents/`; next command per tool.
- **Upgrade**: remove the old links in `~/.codex/prompts` if you ran `make codex-prompts`.

## 1.12.0
- Human gates enforced: `make approve`, the `gate_guard.py` hook, approval-before-code in `check --git`.

## 1.11.0
- Traceable templates (Spec `Requirements:`, AC `→ test:`, RUN Branch/PR, tuning acceptance, facts in RUN §8), workshop template, generated Spec index.
- **Upgrade**: RUNs and Specs already written keep their format; new ones use the new templates.

## 1.10.0
- Session default model, `/run-deep` for L/XL stories, `tools/usage.py`.

## 1.9.0
- Context budgets count ADRs, package rules, minutes and the review diff.

## 1.8.0
- One source per rule; analyst write exceptions; `[git] trailers`.

## 1.7.0
- Separate `/close` step after the review; only the story's PR is merged.

## 1.6.0
- Bug, hotfix, chore, refactor and spike flows; quick track with one approval.

## 1.5.0
- RUN/Spec state machine: stopped, blocked, cancelled, scope change, split, skip analysis.

## 1.4.0
- Shared status vocabulary; unknown statuses block.

## 1.3.1
- Tooling fixes from edge-case probing.

## 1.3.0
- `--json` envelope for the read tools.

## 1.2.0
- Git sync at the end of `/persist`.

## 1.1.1
- `.portal/` ignored; launcher CI on macOS and Windows.

## 1.1.0
- Portal launcher (`make portal`).
