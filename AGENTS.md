# AGENTS.md

Canonical rules for every AI agent in this repository, whatever the tool or model. Tool files (`CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/`) only point here.

## 1. Session start

1. Do **not** explore the repository to find where the project stands: run `make next` (or `python3 tools/next_step.py`).
2. Pick the mode from the user's intent (table below). If ambiguous or mixed, stop and ask which mode leads.
3. Follow the step file named by `make next` or the command (`workflow/steps/<step>.md`). Read **only** what `python3 tools/context.py <step> <ID…>` lists.

| Mode | For | Writes in | Guide |
|---|---|---|---|
| **product** | inception (vision, requirements, mockup, architecture, backlog, release plan); onboarding an existing codebase | `reference/`, `backlog/`, `PLAN.md` | `workflow/steps/<step>.md` |
| **analyst** | Analysis, workshop preparation, Refined Story, backlog consolidation | `analysis/`; outside it only the exceptions in `analysis/AGENTS.md` | `analysis/AGENT_GUIDE.md` |
| **developer** | Brief, Spec, RUN, code, persistence | `delivery/`, code | `delivery/AGENT_GUIDE.md` |
| **review** | Brief/Spec/RUN consistency, scope creep, quality gates | RUN §11 and RUN status only | `workflow/steps/review.md` |
| **journal** | weekly / monthly journal | `project-journal/` | `workflow/steps/weekly.md` |

## 2. Lifecycle

```
INCEPTION   kickoff → requirements → [mockup] → architecture → backlog → release plan   (each approved by a human)
            existing codebase: tools/adopt.py → onboard → backlog → release plan
ANALYSIS    Story → Analysis → workshop (human) → Refined Story   (skipped for bug, hotfix, chore, refactor, spike, XS, or skip_analysis = true)
DELIVERY    Brief → Spec (human: Ready) → RUN strategy (human: approve) → execute → tuning (human) → persist (gates, PR, CI) → [security review] → review → close (merge)
            quick track (bug, hotfix, chore, XS): Brief + Spec + RUN strategy → one approval → same as above; hotfixes first
            spike: findings note (human: Accepted) → follow-up stories; no code merged
```

One story, one ID (`project.toml` `id_prefix` + 4 digits): `STORY_PR0101_<slug>.md` → `ANALYSIS_PR0101_…` → `REFINED_PR0101_…` → `BRIEF-PR0101-<slug>.md` → `SPEC-PR0101-<slug>.md` → `RUN-PR0101.md`, tasks `TSK-PR0101-NN`.

## 3. Hard boundaries

- Analyst mode never creates Brief, Spec, RUN or code. Developer mode never requires a Refined Story to start; the Brief is always developer-owned.
- No code without a RUN whose Execution Strategy a human approved (RUN §2). Never expand scope beyond the Spec.
- Agents never pass a human gate on their own: inception artifacts, workshop, Spec `Ready`, RUN strategy, tuning acceptance. A gate field flips only through `make approve …` (run by the human: a dedicated commit with `Approved-by`/`Approved-at`) or the gate command the human types (`/run <ID> approve`, `/run <ID> approve-deviation <n>`, `/persist <ID>`). The Claude Code hook `tools/gate_guard.py` blocks any other gate edit, writes outside the current mode and risky git commands; `make check --git` in CI checks that the strategy approval was committed before the code.
- Owner decisions in workshop minutes or in chat **are** human approvals: apply their consequences without asking again. A chat decision is first written down verbatim (quote, date, who) in `project-journal/decisions/<YYYY-MM-DD>-<topic>.md`, cited by the revision line; it never flips a gate field by itself. An `approved`/`accepted` artifact keeps its status for a change the owner decided (revision line citing the source); only changes the owner has not decided go back to `draft`/`proposed`.
- End every step with the next command (`/name`; `$name` in Codex) and each pending human gate as `file → field → value` with its `make approve …` command.
- Templates in `inception/templates/`, `analysis/templates/`, `delivery/templates/` are authoritative: use them as they are.
- No secrets or personal data in logs, artifacts or prompts.
- Git (`delivery/guide/git.md`): **trunk-based**, `main` the only long-lived branch (a release is a tag, no `release/*`/`develop`/integration branches); one short-lived branch and PR per story; `/persist` pushes and waits for CI; `/close` merges **only that story's PR** after the review; other branches are reported, never merged or deleted.

## 4. Language

Artifact **content** in the project language (`project.toml` `language`, default `en`). Template **headings, frontmatter keys, status values and IDs stay in English** (`## Status`, `status: draft`, `FR-03`): scripts parse them. Chat replies follow the user's language.

## 5. Token discipline (every step)

1. **Fresh session per step**, except the RUN chain of one story (strategy → approval → execution → tuning → persistence).
2. **The context budget is binding**: read only what `tools/context.py` prints; in long documents the extracted sections, never the whole file.
3. **Scripts before the LLM**: state, naming, consistency and backlog views come from `make next`, `make check`, `make backlog`.
4. **Right tier** (single source): `fast` for state, journal and closure, `balanced` for everything else, `deep` only for `/architecture`, `/onboard`, L/XL stories (`/run-deep`, routed by `make next`) or when the user asks. Models per vendor: `models.toml`.
5. **No subagents by default**, only for independent workstreams. Exception: the read-only `reader` subagent (fast tier) for questions that span many files (`/onboard`, `/analysis` of existing code, "where is X used"); its answers are `file:line` leads to verify. Not for editing (read the exact section yourself first), debugging, architecture or review judgments.
6. **Short output**: artifacts follow templates without restating sources; chat gets a few lines, the content is in the files.
7. **Do not re-read** what you just wrote; read guides and templates once per session.
8. **Resume from files**: after a broken session, start again from `make next`.

## 6. Where things are

`project.toml` settings (name, ID prefix, language, stack commands) · `models.toml` model per tier and vendor · `workflow/` steps, commands, context budgets · `reference/product/` vision, requirements, mockup map · `reference/architecture/` architecture, ADRs · `reference/domain/` glossary, domain · `backlog/stories.toml` backlog source of truth (→ `make backlog`) · `PLAN.md` release plan · `project-journal/` project memory. A package's own `AGENTS.md` (from `/architecture`) adds local rules: read it before a RUN strategy that touches the package.
