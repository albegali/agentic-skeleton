# Step requirements — FR and NFR (product mode)

**Command**: `/requirements [sources…]` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py requirements` (includes the kickoff sources recorded in `project.toml`) + any further sources passed as arguments (transcripts, documents, existing specs). If there are no sources and the vision is thin, ask for sources before writing.

## Procedure
1. Extract candidate requirements from vision and sources. For each, keep the **source** (file + section or quote) or mark it `assumption`.
2. Write `reference/product/functional-requirements.md` with the template: requirements grouped by capability, IDs `FR-01…` (stable, never reused), each with statement, rationale, source, priority (MoSCoW), acceptance hints, UI flag (`ui: yes|no`).
3. Write `reference/product/non-functional-requirements.md`: `NFR-01…` grouped by quality attribute (security, privacy, performance, availability, accessibility, observability, maintainability, compliance, cost), each **measurable** where possible (target + how to verify).
4. List **open questions** and **conflicts** between sources at the end of each file, by impact.
5. If requirements already exist, update in place: never renumber; deprecated items keep their ID with `status: deprecated`.
6. Run `make check`.

Rules: one requirement per ID; no solution design (that belongs to `/architecture`); no story slicing (that belongs to `/backlog`).

**Chat**: counts (FR, NFR, Must), top 5 high-impact open questions.
**Gate**: the owner sets `status: approved` in both files' frontmatter.
