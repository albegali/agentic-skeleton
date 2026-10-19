# AGENTS.md

Canonical rules for every AI agent working in this repository, whatever the tool (Claude Code, Codex CLI, GitHub Copilot, Cursor, …) or model. Tool-specific files (`CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/`) only point here.

## 1. Session start

1. Do **not** explore the repository to find out where the project stands: run `make next` (or `python3 tools/next_step.py`). The state lives in files and is computed by a script.
2. Pick the mode from the user's intent (table below). If it is ambiguous or mixed, stop and ask which mode leads.
3. Follow the step file named by `make next` or by the command: `workflow/steps/<step>.md`. Read **only** what `python3 tools/context.py <step> <ID…>` lists.

| Mode | For | Writes in | Guide |
|---|---|---|---|
| **product** | vision, requirements, mockup, architecture, backlog, release plan (inception) | `reference/`, `backlog/`, `PLAN.md` | `workflow/steps/<step>.md` |
| **analyst** | Analysis, workshop preparation, Refined Story, backlog consolidation | `analysis/` | `analysis/AGENT_GUIDE.md` |
| **developer** | Brief, Spec, RUN, code, persistence | `delivery/`, code | `delivery/AGENT_GUIDE.md` |
| **review** | consistency Brief/Spec/RUN, scope creep, quality gates | nothing (report only) | `workflow/steps/review.md` |
| **journal** | weekly / monthly project journal | `project-journal/` | `workflow/steps/weekly.md` |

## 2. Lifecycle

```
INCEPTION   kickoff → requirements → [mockup] → architecture → backlog → release plan   (each approved by a human)
ANALYSIS    Story → Analysis → workshop (human) → Refined Story
DELIVERY    Brief → Spec (human: Ready) → RUN strategy (human: approve) → execute → tuning (human) → persist → review → Closed
```

The chain of one story shares one ID (`project.toml` → `id_prefix` + 4 digits, e.g. `PR0101`):
`STORY_PR0101_<slug>.md` → `ANALYSIS_PR0101_…` → `REFINED_PR0101_…` → `BRIEF-PR0101-<slug>.md` → `SPEC-PR0101-<slug>.md` → `RUN-PR0101.md`, tasks `TSK-PR0101-NN`.

## 3. Hard boundaries

- Analyst mode never creates Brief, Spec, RUN or code. Developer mode never requires a Refined Story to start; Brief is always developer-owned.
- No code without a RUN whose Execution Strategy is approved by a human (RUN §2). Never expand scope beyond the Spec.
- Agents never pass a human gate on their own: approvals of inception artifacts, workshop, Spec `Ready`, RUN strategy, tuning acceptance.
- Templates in `inception/templates/`, `analysis/templates/`, `delivery/templates/` are authoritative: use them as they are.
- No secrets or personal data in logs, artifacts or prompts.

## 4. Language

- Write artifact **content** in the project language (`project.toml` → `language`; default `en`).
- Keep template **headings, frontmatter keys, status values and IDs in English** (`## Status`, `status: draft`, `FR-03`): scripts parse them.
- Chat replies follow the user's language.

## 5. Token discipline (applies to every step)

1. **Fresh session per step**, except the RUN chain of one story (strategy → approval → execution → tuning → persistence).
2. **The context budget is binding**: read only what `tools/context.py` prints. In long documents use the extracted sections, never the whole file.
3. **Scripts before the LLM**: state, naming, consistency and backlog views come from `make next`, `make check`, `make backlog`.
4. **Right tier**: `fast` for state and journal, `balanced` for analysis, code and review, `deep` only for architecture, L/XL stories, or when the user asks. Mapping per vendor in `models.toml`.
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
