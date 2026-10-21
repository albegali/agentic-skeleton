# AGENTS.md

Canonical rules for every AI agent working in this repository, whatever the tool (Claude Code, Codex CLI, GitHub Copilot, Cursor, …) or model. Tool-specific files (`CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/`) only point here.

## 1. Session start

1. Do **not** explore the repository to find out where the project stands: run `make next` (or `python3 tools/next_step.py`). The state lives in files and is computed by a script.
2. Pick the mode from the user's intent (table below). If it is ambiguous or mixed, stop and ask which mode leads.
3. Follow the step file named by `make next` or by the command: `workflow/steps/<step>.md`. Read **only** what `python3 tools/context.py <step> <ID…>` lists.

| Mode | For | Writes in | Guide |
|---|---|---|---|
| **product** | vision, requirements, mockup, architecture, backlog, release plan (inception); onboarding of an existing codebase | `reference/`, `backlog/`, `PLAN.md` | `workflow/steps/<step>.md` |
| **analyst** | Analysis, workshop preparation, Refined Story, backlog consolidation | `analysis/`; outside it only the exceptions in `analysis/AGENTS.md` | `analysis/AGENT_GUIDE.md` |
| **developer** | Brief, Spec, RUN, code, persistence | `delivery/`, code | `delivery/AGENT_GUIDE.md` |
| **review** | consistency Brief/Spec/RUN, scope creep, quality gates | RUN §11 and RUN status only | `workflow/steps/review.md` |
| **journal** | weekly / monthly project journal | `project-journal/` | `workflow/steps/weekly.md` |

## 2. Lifecycle

```
INCEPTION   kickoff → requirements → [mockup] → architecture → backlog → release plan   (each approved by a human)
            existing codebase: tools/adopt.py → onboard → backlog → release plan
ANALYSIS    Story → Analysis → workshop (human) → Refined Story   (skipped for bug, hotfix, chore, refactor, spike, XS, or skip_analysis = true)
DELIVERY    Brief → Spec (human: Ready) → RUN strategy (human: approve) → execute → tuning (human) → persist (gates, PR, CI) → [security review] → review → close (merge)
            quick track (bug, hotfix, chore, XS): Brief + Spec + RUN strategy → one approval → same as above; hotfixes first
            spike: findings note (human: Accepted) → follow-up stories; no code merged
```

The chain of one story shares one ID (`project.toml` → `id_prefix` + 4 digits, e.g. `PR0101`):
`STORY_PR0101_<slug>.md` → `ANALYSIS_PR0101_…` → `REFINED_PR0101_…` → `BRIEF-PR0101-<slug>.md` → `SPEC-PR0101-<slug>.md` → `RUN-PR0101.md`, tasks `TSK-PR0101-NN`.

## 3. Hard boundaries

- Analyst mode never creates Brief, Spec, RUN or code. Developer mode never requires a Refined Story to start; Brief is always developer-owned.
- No code without a RUN whose Execution Strategy is approved by a human (RUN §2). Never expand scope beyond the Spec.
- Agents never pass a human gate on their own: approvals of inception artifacts, workshop, Spec `Ready`, RUN strategy, tuning acceptance. A gate field flips only through `make approve …` (run by the human; a dedicated commit with `Approved-by`/`Approved-at`) or the explicit gate command the human types (`/run <ID> approve`, `/run <ID> approve-deviation <n>`, `/persist <ID>`). In Claude Code a hook (`tools/gate_guard.py`) blocks any other edit that passes a gate, writes outside the current mode, or runs risky git commands; `make check --git` in CI checks that the strategy approval was committed before the code.
- Owner decisions recorded in workshop minutes or given in chat **are** human approvals: apply their consequences without asking again. A decision given in chat is first written down verbatim (quote, date, who) in `project-journal/decisions/<YYYY-MM-DD>-<topic>.md`; the revision line cites that file. It never flips a gate field by itself (see above). An artifact already `approved`/`accepted` keeps its status when the change applied is one the owner decided; add a revision line citing the source. Only changes the owner has not decided go back to `draft`/`proposed`.
- End every step with the next command (written `/name`; in Codex the same skill is `$name`) and each pending human gate as `file → field → value` plus its `make approve …` command: the human never has to ask what comes next or how to approve.
- Templates in `inception/templates/`, `analysis/templates/`, `delivery/templates/` are authoritative: use them as they are.
- No secrets or personal data in logs, artifacts or prompts.
- Git: `delivery/guide/git.md` (single source). In short: **trunk-based development** — `main` is the only long-lived branch, no `release/*`/`develop`/integration branches (a release is a tag); one short-lived branch and one PR per story; `/persist` pushes and waits for CI, `/close` merges **only that story's PR** after the review; other branches are reported, never merged or deleted.

## 4. Language

- Write artifact **content** in the project language (`project.toml` → `language`; default `en`).
- Keep template **headings, frontmatter keys, status values and IDs in English** (`## Status`, `status: draft`, `FR-03`): scripts parse them.
- Chat replies follow the user's language.

## 5. Token discipline (applies to every step)

1. **Fresh session per step**, except the RUN chain of one story (strategy → approval → execution → tuning → persistence).
2. **The context budget is binding**: read only what `tools/context.py` prints. In long documents use the extracted sections, never the whole file.
3. **Scripts before the LLM**: state, naming, consistency and backlog views come from `make next`, `make check`, `make backlog`.
4. **Right tier** (single source; other files link here): `fast` for state, journal and closure, `balanced` for everything else, `deep` only for `/architecture`, `/onboard`, L/XL stories (`/run-deep`, routed by `make next`), or when the user asks. Mapping per vendor in `models.toml`.
5. **No subagents by default**: only for genuinely independent workstreams.
6. **Short output**: artifacts follow templates without restating sources; chat gets a few lines, the content is in the files.
7. **Do not re-read** what you just wrote; read guides and templates once per session.
8. **Resume from files**: if a session breaks, start again from `make next`.

## 6. Where things are

| What | Where |
|---|---|
| Project settings (name, ID prefix, language, stack commands) | `project.toml` |
| Model per tier and vendor | `models.toml` |
| Steps, commands, context budgets (single source) | `workflow/` |
| Vision, requirements, mockup map | `reference/product/` |
| Architecture, ADRs | `reference/architecture/` |
| Glossary, domain | `reference/domain/` |
| Backlog source of truth | `backlog/stories.toml` (→ `make backlog`) |
| Release plan | `PLAN.md` |
| Project memory | `project-journal/` |

Packages with their own `AGENTS.md` (created by `/architecture`) add local rules: read them before writing a RUN strategy that touches the package.
