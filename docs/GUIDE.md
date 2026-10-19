# Guide — starting a new project from agentic-skeleton

This guide walks you from an empty fork to a running delivery loop: setting up the repository, the inception phase, the story loop, team routines, customization and troubleshooting.

It assumes you know git and have used at least one AI coding tool. You do not need to know the skeleton's internals: the [README](../README.md) gives the overview, and this guide covers the practice.

---

## Contents

1. [How the skeleton works in 2 minutes](#1-how-the-skeleton-works-in-2-minutes)
2. [Prerequisites](#2-prerequisites)
3. [Create your project repository](#3-create-your-project-repository)
4. [Set up your agent tools](#4-set-up-your-agent-tools)
5. [Inception: from idea to release plan](#5-inception-from-idea-to-release-plan)
6. [The story loop: analysis and delivery](#6-the-story-loop-analysis-and-delivery)
7. [Routines and cheat sheet](#7-routines-and-cheat-sheet)
8. [Working as a team with different tools](#8-working-as-a-team-with-different-tools)
9. [Keeping token costs low](#9-keeping-token-costs-low)
10. [Handling change](#10-handling-change)
11. [Customizing the skeleton](#11-customizing-the-skeleton)
12. [Pulling skeleton updates into your project](#12-pulling-skeleton-updates-into-your-project)
13. [Troubleshooting](#13-troubleshooting)
14. [FAQ](#14-faq)

---

## 1. How the skeleton works in 2 minutes

**Agents do the work; humans hold the gates; files hold the state.**

```
INCEPTION  /kickoff → /requirements → /mockup → /architecture → /backlog → /release-plan
ANALYSIS   per story:  /analysis → workshop (you) → /refine
DELIVERY   per story:  /brief → Spec review (you) → /run (strategy) → approve (you) → execution → tuning (you) → /persist → /review-story
JOURNAL    weekly:     /weekly
```

Three ideas carry everything else:

- **`make next` is the navigator.** A script reads the repository files and tells you the next step, the command to type, and the model to use with each of your tools. No AI reads the repository to work out where you are.
- **Each step has a context budget.** `tools/context.py <step> <IDs>` prints exactly what the agent may read: whole files, plus only the requirement sections a story cites. Agents are told to read nothing else.
- **One neutral source, many tools.** Steps and commands are defined once in `workflow/workflow.toml`. `make agents` renders them as slash commands for Claude Code, Codex CLI, GitHub Copilot and Cursor. Each step declares a tier (`fast`, `balanced` or `deep`), and `models.toml` maps each tier to a concrete model per tool.

Every story keeps one ID along its whole chain, for example `CP0101`:

```
backlog/stories.toml → STORY_CP0101_… → ANALYSIS_CP0101_… → REFINED_CP0101_… → BRIEF-CP0101-… → SPEC-CP0101-… → RUN-CP0101.md
```

---

## 2. Prerequisites

| Need | Why | Check |
|---|---|---|
| Python ≥ 3.11 | workflow tools (stdlib only, nothing to install) | `python3 --version` |
| `make` | entry points | `make --version` |
| git | versioning, `git diff` for reviews | `git --version` |
| At least one agent tool | Claude Code, Codex CLI, GitHub Copilot (VS Code) or Cursor | see §4 |

You also need someone in the **product owner** role who approves artifacts, and source material for your idea: a brief, meeting transcripts, existing specs, or simply your own notes.

---

## 3. Create your project repository

Pick one of three ways for a new project, or Option D to bring the workflow into a codebase that already exists.

### Option A — GitHub template (recommended for teams)

One-time setup by the skeleton maintainer:

```bash
cd agentic-skeleton
gh repo create <org>/agentic-skeleton --private --source . --push
gh repo edit <org>/agentic-skeleton --template
```

For each new project:

```bash
gh repo create <org>/my-project --private --template <org>/agentic-skeleton --clone
cd my-project
```

The new repository starts with a clean history.

### Option B — fork / clone with an upstream remote (to pull skeleton updates)

```bash
git clone <skeleton-url> my-project
cd my-project
git remote rename origin skeleton          # keep the skeleton as "skeleton"
git remote add origin <your-project-url>   # your project's own remote
git push -u origin main
```

Choose this option if you plan to merge future skeleton improvements (see §12).

### Option C — plain copy (quickest, local)

```bash
cp -r ~/projects/agentic-skeleton ~/projects/my-project
cd ~/projects/my-project
rm -rf .git && git init -b main && git add -A && git commit -m "chore: start from agentic-skeleton"
```

### Option D — an existing codebase (brownfield)

Any repository, any stack or age, any kind of software: web frontends and back ends on any cloud or on-prem, mobile and desktop apps, games, firmware, libraries and SDKs, CLIs, data/ML pipelines, infrastructure code, extensions, enterprise or legacy platforms, or a monorepo mixing them. The installer makes no assumption about language, framework, build tool, hosting or CI. The repository map reports *signals* for each kind (an `AndroidManifest.xml`, an `.xcodeproj`, `platformio.ini`, `*.tf`, …), and `/onboard` classifies each deliverable and adapts what it reads and documents: screens and navigation for a UI, endpoints for a service, the public API for a library, commands for a CLI, boards and protocols for firmware, and the distribution channel (stores, installers, registries, deployments, flashing). Run the installer **from the skeleton** and point it at the existing repository (commit or stash there first):

```bash
cd ~/projects/agentic-skeleton
make adopt TARGET=../my-app ARGS="--dry-run"                      # see the plan, nothing written
make adopt TARGET=../my-app ARGS="--name 'My App' --prefix MA"    # install
cd ../my-app && git add -A && git diff --cached --stat             # review, then commit
make next                                                          # → /onboard
```

What `tools/adopt.py` does, deterministically and without overwriting anything:

| In the target | Effect |
|---|---|
| workflow files (`tools/`, `workflow/`, templates, guides, `project.toml`, `models.toml`) | copied where absent; an existing *different* file is a conflict and nothing is written (rename or move it, rerun); your READMEs are kept |
| `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` | yours stay; a block between `<!-- agentic-workflow:begin/end -->` is appended (and kept up to date by `make agents`) |
| `.claude/settings.json` | union of your permissions and the workflow ones |
| `Makefile` | yours gets `include workflow.mk`; targets you already define win (`test`, `lint`, `setup`), other clashes are installed as `wf-<name>` (e.g. `make wf-check`) |
| `project.toml` | `origin = "brownfield"`, `[stack]` guessed from the manifests when recognisable (otherwise empty), `decided = false` |
| CI | untouched; add `python3 tools/check_workflow.py` to your pipeline if you want the gate |

Not installed: the skeleton's own tests (`tools/tests`) and the installer itself.

Then, in a fresh session in the target, **`/onboard`** (deep tier) documents the system *as it is*, from a cheap repository map (`python3 tools/context.py --repo-map`) and a selective read of the code, plus one short interview round for what the code cannot tell:

- `reference/architecture/architecture.md` (current state) and **retroactive ADRs** for the decisions already in the code;
- an `AGENTS.md` per package with the conventions actually in use;
- an **FR index** in `functional-requirements.md`: one `### FR-xx` per existing capability (`Status: existing`, where it lives in the code); full statements are written later, when a story changes that capability;
- `project-summary.md`, `glossary.md`, a `vision.md` of the current product and its direction;
- `project-journal/context/<date>-onboard.md`: gaps, tech debt, risks, candidate work.

You approve them like any inception artifact (vision, FR index, architecture, ADRs, `decided = true`); `make next` then goes to `/backlog` with your change requests, `/release-plan`, and the normal story loop. No walking skeleton: the system already runs.

### Verify

```bash
make check        # → OK
make test-tools   # → OK
make next         # → Recommended step: kickoff   (Option D: onboard)
```

For Option D run `make check` and `make next` in the target (there is no `make test-tools` there).

---

## 4. Set up your agent tools

The adapters are already generated for all four tools. You can narrow the list during `/kickoff`.

| Tool | What to do once | How you run a command |
|---|---|---|
| **Claude Code** | Open the folder (`claude` in the terminal or the IDE extension). `.claude/commands/` and `.claude/settings.json` are picked up automatically. | `/next`, `/kickoff …` |
| **Codex CLI** | `make codex-prompts` links the prompts into `~/.codex/prompts` (Codex reads prompts only from there). `AGENTS.md` is read natively. | `/prompts:next`, `/prompts:kickoff …` |
| **GitHub Copilot** (VS Code) | Open the folder; prompt files in `.github/prompts/` show up in Copilot Chat in agent mode. If they don't, enable prompt files in the VS Code settings (`chat.promptFiles`). | `/next`, `/kickoff` |
| **Cursor** | Open the folder; `.cursor/commands/` and `.cursor/rules/workflow.mdc` are picked up. | `/next`, `/kickoff` |

**Models.** Claude Code and Copilot switch model automatically, because each command pins one. Codex and Cursor print `> Recommended model: …` at the top of the command: select that model before you send it (in Codex, `codex -m <model>` or `/model`).

> The OpenAI and Google model names in `models.toml`, and the Copilot labels, are suggestions marked `verify`. Run `/choose-models` (§5.2) before real work.

**Permissions (Claude Code).** `.claude/settings.json` pre-allows the read-only workflow commands (`make next`, `make check`, `python3 tools/…`, `git diff/log/status`) and denies `git push --force`, `terraform apply` and reading `.env`. Personal additions belong in `.claude/settings.local.json`, which is not generated.

---

## 5. Inception: from idea to release plan

Inception turns an idea into an approved backlog and plan. Every step:

1. runs in a **fresh session** with the command `make next` names;
2. writes artifacts with `status: draft`;
3. waits for **your approval**: you edit the status to `approved` (or `accepted` for ADRs).

Run `make next` (or `/next`) after each step; it never skips a gate.

### 5.1 `/kickoff` — settings and vision

```
/kickoff "Course Planner" docs/brief.md notes/meeting-2026-10-10.md
```

The agent:
1. asks, in one message, only what the arguments and sources don't say: name, description, **ID prefix** (2–3 letters, e.g. `CP`), **artifact language** (`en` by default; for example `it`), **owner**, mockup on/off, tools in use;
2. runs `tools/init_project.py`, which updates `project.toml` and `models.toml`, records the source files (and which one is an existing design, if any) so later steps load them without you passing them again, re-prefixes the template examples and regenerates the adapters;
3. runs a short interview (at most 2 rounds) about problem, users, outcomes, scope, constraints and stakeholders;
4. writes `reference/product/vision.md`, `reference/project-summary.md`, `reference/documentation/stakeholders.md`, `reference/domain/glossary.md`, and a kickoff record in `project-journal/context/`.

Statements that come neither from you nor from the sources are marked as **assumptions**.

**Your gate.** Read `vision.md`. Correct it directly, or rerun `/kickoff` with your notes. Then set `status: approved`.

> You can also run the deterministic part by hand:
> `python3 tools/init_project.py --name "Course Planner" --prefix CP --language it --owner "Jane Doe" --tools claude-code,copilot`

**Choosing the language.** With `language = "it"`, the content of every artifact is written in Italian. Headings, frontmatter keys, statuses and IDs stay in English, because the scripts parse them. Chat replies follow the language you write in.

### 5.2 `/choose-models` — optional, recommended once

```
/choose-models
```

It shows a table of tier × tool, asks which model to use per tier, updates `models.toml` and runs `make agents`. Rules of thumb:

| Tier | Used for | Pick |
|---|---|---|
| `fast` | `/next`, `/weekly`, `/choose-models` | the vendor's small, cheap model |
| `balanced` | requirements, mockup, backlog, analysis, coding, review | the vendor's mid model, strong at coding |
| `deep` | `/architecture`, L/XL stories when you ask | the vendor's largest model |

You can also edit `models.toml` by hand and run `make agents`.

### 5.3 `/requirements` — FR and NFR

```
/requirements transcripts/workshop-1.md docs/legacy-spec.pdf
```

Output:
- `reference/product/functional-requirements.md`: `### FR-01 — …` headings, each with statement, rationale, source, priority (MoSCoW), UI flag and acceptance hints;
- `reference/product/non-functional-requirements.md`: `### NFR-01 — …` with a measurable target and a verification method;
- open questions and conflicts between sources, by impact.

IDs are stable: they are never renumbered or reused. The headings matter: `context.py` uses them to extract single requirements later.

**Your gate.** Approve both files. This is the cheapest moment to cut scope.

### 5.4 `/mockup` — clickable mockup (skip it with `--no-mockup` at kickoff)

```
/mockup                  # all requirements with UI: yes
/mockup FR-03 FR-07      # only some
```

Output: one self-contained HTML file in `reference/mockup/` (open it in a browser) and `reference/product/mockup-reference.md`, which maps screens and render functions to FRs and separates normative from illustrative behavior.

Already have a design (an HTML mockup, a prototype, exported frames)? Pass it to `/kickoff` among the sources: it is recorded as `design` in `project.toml`, and `/mockup` maps it to the FRs instead of building a new one, adding screens only for requirements the design does not cover.

Use the mockup with stakeholders: their feedback is the best input for refining requirements. **Your gate:** approve the map.

### 5.5 `/architecture` — stack and decisions (deep tier)

```
/architecture "Azure hosting, team knows Python and React, SSO with Entra ID"
```

The agent derives the architectural drivers from the NFRs, proposes at most 2 options per open decision, asks you to confirm the decisions that are costly to reverse, and writes:
- `reference/architecture/ADR-001-<slug>.md`, … (`status: proposed`);
- `reference/architecture/architecture.md`;
- `AGENTS.md` stubs in the planned package folders (for example `server/AGENTS.md`), with local conventions for agents;
- the `[stack]` commands in `project.toml` (`setup`, `test`, `lint`), which feed `make setup/test/lint`.

It does **not** scaffold code: the walking skeleton is the first story.

**Your gate.** Set each ADR to `accepted`, set `architecture.md` to `approved`, and set `decided = true` in `project.toml` `[stack]`.

### 5.6 `/backlog` — epics and stories

```
/backlog
```

Output: `backlog/stories.toml`, the **single source of the backlog**:

```toml
[[story]]
id = "CP0101"            # prefix + epic (2 digits) + story (2 digits)
epic = "EP-01"
slug = "walking-skeleton"
title = "Walking skeleton"
as_a = "development team"
i_want = "an empty service with build, tests, CI and a health endpoint"
so_that = "every later story has its place ready"
priority = "Must"
release = "R1"
size = "M"
fr = []
nfr = ["NFR-05"]
deps = []
ac = [["the cloned repository", "I run `make setup && make test`", "the tests pass"]]
```

The agent then runs `make backlog`, which generates `analysis/10-stories/STORY_*.md`, the epic pages and the overview, and `make check`, which catches unknown FRs, dependency cycles and Must FRs no story covers.

> Never hand-edit `analysis/10-stories/`: edit `stories.toml` and run `make backlog`. Stories that already have an Analysis are not overwritten.

**Your gate.** Set `status = "approved"` at the top of `stories.toml`.

### 5.7 `/release-plan` — releases and sprints

```
/release-plan "2-week sprints from 2026-11-16, ~3 stories per sprint, pilot by March"
```

Output: `PLAN.md` with releases and the sprint table. Keep the table's shape: `next_step.py` parses it.

```
| Sprint | Dates          | Goal        | Stories                  |
|--------|----------------|-------------|--------------------------|
| S0     | 20/10 – 13/11  | Analysis    | Analysis and workshops S1–S2  |
| S1     | 16/11 – 27/11  | Foundations | CP0101, CP0102, CP0103   |
| S2     | 30/11 – 11/12  | Core        | EP-02                    |
```

You can list story IDs or whole epics (`EP-02`). The order inside a sprint is the development order.

**Your gate.** Set `status: approved`. From now on, `make next` drives the story loop.

### Inception checklist

- [ ] `vision.md` approved
- [ ] FR and NFR approved
- [ ] mockup map approved (if enabled)
- [ ] ADRs accepted, `architecture.md` approved, `[stack] decided = true`
- [ ] `backlog/stories.toml` approved, `make check` OK
- [ ] `PLAN.md` approved
- [ ] first commit of the inception artifacts

---

## 6. The story loop: analysis and delivery

### 6.1 Analysis (runs one sprint ahead)

| Step | Who | Command | Output |
|---|---|---|---|
| Analysis | agent (analyst) | `/analysis CP0101 CP0102` (at most 4 related stories) | `analysis/20-analysis/ANALYSIS_*.md`: functional analysis plus workshop questions ranked by impact |
| Workshop | **you + team** | — | minutes in `project-journal/notes/YYYY-MM-DD-workshop-<topic>.md` |
| Refined Story | agent (analyst) | `/refine CP0101 CP0102 project-journal/notes/2026-11-05-workshop-auth.md` | `analysis/30-refined/REFINED_*.md`: scope, confirmed AC, decisions, handoff notes, outcome |

The Analysis chat reply lists only the high-impact questions: that is your workshop agenda. The Refined Story outcome is one of *ready*, *ready with open points* or *not ready*; "not ready" sends the story back to the workshop.

### 6.2 Delivery (one story at a time)

| Step | Who | Command | What happens |
|---|---|---|---|
| Brief + Spec | agent (developer) | `/brief CP0101` | Brief (frozen request) and Spec (the contract: scope, AC, tasks `TSK-CP0101-NN`, boundaries, quality gates, stop conditions). Status Draft. |
| Spec review | **you** | `/spec CP0101 <changes>` if needed | set `## Status` → `Ready` |
| Strategy | agent | `/run CP0101` | RUN §1: plan in small steps, assumptions, risks, package rules read. **No code.** |
| Approval | **you** | `/run CP0101 approve` (same session) | recorded in RUN §2, then execution starts |
| Execution | agent | (continues) or `/run CP0101` to resume | code and tests step by step, RUN §3-4 updated |
| Tuning | **you** → agent | `/run CP0101 tuning: the export ignores filters` | in-scope fixes, logged in RUN §5 |
| Persistence | agent | `/persist CP0101` | Spec §11 and reference docs reconciled; RUN → Persisted → Closed; `make check` |
| Review | agent, fresh eyes | `/review-story CP0101` | `file:line → problem → request`, or "OK to close" |

Rules agents follow, and that you can hold them to:
- no code before the strategy is approved;
- nothing beyond the Spec: out-of-scope work stops or becomes a logged deviation;
- the RUN is append-only: if it is not in the RUN, it did not happen;
- a RUN is never Closed before it is Persisted.

### 6.3 A typical day

```text
$ make next
Current sprint: S1 (16/11 – 27/11) — Foundations
  CP0101   execute       [agent] RUN Executing
  CP0102   spec-approval  [human] Spec draft: human review, status → Ready
→ Recommended step: execute CP0101
  Run: /run CP0101 (fresh session)
  Tier: balanced → claude-code: sonnet · copilot: Claude Sonnet 5.5
```

1. Run the recommended command in a fresh session.
2. Meanwhile, clear your own gates (here: review Spec CP0102).
3. When the agent stops (strategy written, step done, stop condition), act, then run `make next` again.

---

## 7. Routines and cheat sheet

### Cadence

| When | What |
|---|---|
| Every step | fresh session · `make next` · run the command |
| Sprint start | check `PLAN.md`; `make next` proposes Analysis for the next sprint |
| Mid-sprint | workshop for the next sprint's stories → `/refine` |
| Weekly | `/weekly` (fast tier) → `project-journal/weekly/<date>.md`; `make next` reminds you after 7 days |
| Monthly | write `project-journal/monthly/YYYY-MM.md` from `templates/monthly.md` (with an agent if you like) |
| Before merge | `make check` and `make test` (the CI templates run `make check` and `make test-tools`) |

Drop quick notes in `project-journal/notes/current-week.md` during the week: `/weekly` consolidates them.

### Cheat sheet

| I want to… | Do |
|---|---|
| know what's next | `make next` · `/next` |
| see one story's state | `python3 tools/next_step.py CP0104` |
| see what an agent may read | `make context STEP=analysis IDS="CP0104"` |
| check consistency | `make check` |
| regenerate the backlog views | `make backlog` |
| change models | `/choose-models` or edit `models.toml` → `make agents` |
| add a story | add it to `backlog/stories.toml` → `make backlog` → add it to `PLAN.md` |
| ask for a bigger model on a hard story | `/run CP0207` + "use the deep tier" |
| resume a broken session | fresh session → `make next` (the state is in the files) |

---

## 8. Working as a team with different tools

- Everyone shares the same **files**, so mixing tools is safe: one person on Claude Code, another on Copilot, a third on Codex.
- `AGENTS.md` is the only rule set. `CLAUDE.md`, `.github/copilot-instructions.md` and `.cursor/rules/workflow.mdc` just point to it.
- Commit the generated adapters, so teammates get the commands without running anything.
- Enable only the tools the team uses (`/kickoff`, or `enabled = false` in `models.toml` → `make agents`). Disabled tools' files are removed.
- **One story, one owner, one RUN.** Avoid two agents on the same story at the same time. Different stories in parallel are fine if their dependencies are closed.
- Human gates are people's decisions: agree on who approves what (usually the PO for inception and Spec, the tech lead for RUN strategies) and record it in `reference/documentation/stakeholders.md`.

---

## 9. Keeping token costs low

What the skeleton already does for you:
- state computed by a script, not by an LLM reading files (`make next`);
- per-step context budgets (`tools/context.py`), with requirement **sections** instead of whole documents;
- thin commands that point to step files, which load only when used;
- a slim delivery guide, with RUN, hotfix and refactor sections loaded on demand;
- the `fast` tier for routing and the journal, `deep` only for architecture.

What you should do:
1. **Start a fresh session for every step** (`/clear` in Claude Code, a new chat elsewhere). The only exception is the `/run` chain of one story.
2. If the execution session gets past about half the context, start fresh and run `/run <ID>`: the RUN is the memory.
3. Keep stories small (S/M). Split XL stories in `/backlog`.
4. Don't paste long logs or whole files into the chat: point to the path.
5. Batch related stories in `/analysis` (at most 4) and `/refine` (same workshop).
6. Don't ask for the deep tier by default; use it when a story is genuinely hard.
7. Keep `reference/project-summary.md` under 60 lines: every step reads it.

---

## 10. Handling change

| Situation | What to do |
|---|---|
| New or changed requirement | rerun `/requirements <source>`: IDs are never renumbered, and deprecated items keep their ID; approve; then `/backlog` for the stories affected |
| New story mid-project | add it to `stories.toml` (next free ID in its epic) → `make backlog` → put it in a sprint in `PLAN.md` |
| Story turns out too big | stop at the Spec, split it in `stories.toml`, update `PLAN.md` |
| Decision reversed | new ADR with `status: accepted` and the old one `superseded by ADR-xxx`; mention it in the weekly |
| Clarification after the Brief is frozen | add an Brief Addendum (§8) and update the Spec; never rewrite the original intent |
| Production bug | hotfix flow: Brief (Hotfix) → RUN → Spec reconciliation (`delivery/guide/hotfix.md`) |
| Refactor or NFR work | normal flow with the extra fields in `delivery/guide/refactor-nfr.md` |
| Adopting an external tracker | rename IDs with `python3 tools/rename_id.py CP0101 4512`; add a tracker adapter (`tools/README.md`) |

---

## 11. Customizing the skeleton

| Change | Where | Then |
|---|---|---|
| Step procedure or prompt | `workflow/steps/<step>.md` | — (read at run time) |
| Command text, tier, args, context budget | `workflow/workflow.toml` | `make agents && make check` |
| New command or step | `workflow/workflow.toml` + `workflow/steps/<id>.md` (+ `next_step.py` if it changes the lifecycle) | `make agents && make check && make test-tools` |
| Artifact structure | templates in `inception/`, `analysis/`, `delivery/` | keep the headings and keys the scripts parse (`## Status`, `status:`, `### FR-nn`, `# 1. Execution Strategy`, `- [x] Approved`) |
| Package rules for agents | `<package>/AGENTS.md` | listed by `context.py --package-rules` |
| Models | `models.toml` | `make agents` |
| Stack commands | `project.toml` `[stack]` | `make setup / test / lint` |
| CI | `.github/workflows/workflow-check.yml` or `azure-pipelines-workflow.yml` | add your build and test jobs next to `make check` |

Never edit generated files (`.claude/commands`, `.codex/prompts`, `.github/prompts`, `.cursor/commands`, `CLAUDE.md`, `workflow/STEPS.md`): `make check` flags them as stale and `make agents` overwrites them.

---

## 12. Pulling skeleton updates into your project

If you used Option B (§3), the skeleton is a remote:

```bash
git fetch skeleton
git merge skeleton/main
make agents && make check && make test-tools
```

What to expect in the merge:

| Skeleton-owned (take theirs unless you customized it) | Project-owned (keep yours) |
|---|---|
| `tools/`, `workflow/steps/`, `workflow/workflow.toml`, templates, `AGENTS.md`, guides, `Makefile` | `project.toml`, `models.toml`, `reference/`, `backlog/`, `PLAN.md`, `analysis/` and `delivery/` artifacts, `project-journal/` |

Resolve generated files by running `make agents` rather than merging them by hand. With Options A or C, compare the skeleton's `tools/` and `workflow/` against yours and copy over what you want.

---

## 13. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `make next` keeps saying `kickoff` | `project.toml` has `initialized = false` or `vision.md` is missing: run `/kickoff` or `tools/init_project.py` |
| `make adopt`: "Conflicts — nothing written" | the target has its own file at a workflow path (e.g. `workflow/workflow.toml`): rename or move it, rerun |
| `make check` in an adopted repo runs your own `check` | your Makefile defines `check`: the workflow one is `make wf-check` (same for `next`, `backlog`, …) |
| `make next` stuck on `approve` | it lists the files still in draft; for the architecture, also check ADR statuses and `[stack] decided = true` |
| `make next` says "plan completed or dependencies open" | the stories left in the sprint wait for open dependencies; check `python3 tools/next_step.py <ID>` |
| A story never appears in `make next` | it is not in any sprint of `PLAN.md`, or the row doesn't match the 4-column shape |
| `make check`: `stale adapter` | someone edited a generated file, or `workflow.toml` / `models.toml` changed: `make agents` |
| `make check`: `unknown FR-xx` | a story cites a requirement that doesn't exist (or isn't a `### FR-xx` heading) |
| `make check`: `dependency cycle` | fix `deps` in `stories.toml` |
| `make check`: `status … without recorded approval` | a RUN moved past Draft without `- [x] Approved` in §2 |
| Codex: `/prompts:next` not found | run `make codex-prompts`, then restart Codex |
| Copilot: wrong or unknown model | the labels in `models.toml` `[tools.copilot] models` must match your Copilot model picker; fix them, then `make agents` |
| Copilot: prompts not listed | use agent mode in Copilot Chat; enable prompt files in the VS Code settings |
| `make setup/test/lint`: "not defined yet" | run `/architecture`, or fill `project.toml` `[stack]` |
| `tomllib` not found | Python < 3.11: upgrade |

---

## 14. FAQ

**Do I have to do the whole inception?**
No, but `make next` follows it in order. For a small project, keep each artifact short. For an existing codebase use §3 Option D: `make adopt` + `/onboard` replace kickoff → architecture.

**Can I skip the Analysis/Refined Story and go straight to development?**
Yes. Developer mode never requires a Refined Story: `/brief <ID>` works from the Story alone. The analysis is there to cut ambiguity before you pay for code.

**Does it work with tools other than the four supported?**
Any tool that reads `AGENTS.md` can follow the rules. For slash commands, add a renderer to `tools/render_agents.py` and a `[tools.<name>]` entry in `models.toml`.

**Can agents approve things on their own?**
No. Approvals are explicit edits that people make: statuses, `decided = true`, `- [x] Approved`, Spec `Ready`. Agents are instructed to stop at every gate.

**Where do secrets go?**
In `.env` (git-ignored, and denied to Claude Code by default) or your secret manager. Never in artifacts, prompts or logs.

**How do I measure whether this works?**
Use the project journal: the weekly has a section on the agent-supervised model (accelerations, rework, supervision effort, token and cost signals), and the monthly consolidates the patterns.
