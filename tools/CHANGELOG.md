# Skeleton changelog

One heading per `tools/VERSION`, newest first (`make check` requires the current one). **Upgrade** lines say what a
project must do beyond `make sync-skeleton`.

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
