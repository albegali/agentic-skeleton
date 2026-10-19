# Step backlog — epics and stories (product mode)

**Command**: `/backlog [scope]` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py backlog`.

## Procedure
1. Create `backlog/stories.toml` from `inception/templates/stories.toml` (or update it). It is the **single source** of the backlog: never hand-write files in `analysis/10-stories/`.
2. Epics: `EP-01…`, one capability each. The first epic is the technical foundations: **walking skeleton** first (the thinnest end-to-end slice for the product type: it builds, its tests run, and it produces a runnable, installable, deployable or publishable artifact on the target platform), then auth, infra, observability, as the ADRs require.
3. Stories: ID `<prefix><epic 2 digits><story 2 digits>` (e.g. `PR0101`); INVEST; `as_a / i_want / so_that`; 2–5 acceptance criteria as Given/When/Then; `fr` and `nfr` links (every Must FR covered by at least one story); `deps` (acyclic); `size` S/M/L/XL (split XL); `priority` MoSCoW; `release`.
4. Run `make backlog` (generates `analysis/10-stories/`, epic pages, overview) and `make check` (coverage of FR, unknown references, dependency cycles). Fix until green.
5. Keep `status = "draft"` at the top of `stories.toml`.

**Existing codebase** (`origin = "brownfield"` in `project.toml`): no walking skeleton, the system already runs. Stories come from the sources given as arguments (change requests, issues, notes) and from the candidate work in `project-journal/context/*-onboard.md` that the owner confirms. A story that changes an existing capability cites its baseline `FR-xx` (`Status: existing`) and rewrites that FR in full with a `Priority`; new capabilities get the next free FR ID. Read the `AGENTS.md` of the packages a story touches before sizing it.

**Chat**: epics × stories count, uncovered FRs (should be none), largest stories, questions (max 8 lines).
**Gate**: the owner sets `status = "approved"` in `backlog/stories.toml`.
