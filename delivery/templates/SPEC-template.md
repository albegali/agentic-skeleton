# SPEC-<ID> - Title

## References
- Story ID: <ID> (statement: `analysis/10-stories/STORY_<ID>_*.md`, not copied here)
- Brief: BRIEF-<ID>
- RUN: RUN-<ID>
- Requirements: FR-xx, NFR-yy   (same set as `fr` / `nfr` of the story in `backlog/stories.toml`; `make check` compares them)

---

## Status
Draft → Ready → In Progress → Done  ·  Blocked / Cancelled

> Ready: set by the human. In Progress: set when the RUN strategy is approved. Done: set by `/persist`.
> A change after the RUN approval sets it back to Draft and blocks the RUN until the change is approved.

---

# 1. Goal

Describe the expected outcome.

---

# 2. User / Business Value

Why this story matters now, in one or two lines. The story statement is not repeated: see the Story.

---

# 3. Scope

Included:
- …

Out of scope:
- …

---

# 4. Acceptance Criteria

> One line per AC, naming the test that proves it: `→ test: <path>::<name>`, or `→ test: manual — <how>` when no automated test fits.

- [ ] AC1: … → test: …
- [ ] AC2: … → test: …

---

# 5. Tasks

- `TSK-<ID>-01` …
- `TSK-<ID>-02` …
- `TSK-<ID>-03` …

---

# 6. Execution Boundaries

The agent is allowed to:
- …

The agent is not allowed to:
- …

---

# 7. Quality Gates

- [ ] Tests added/updated
- [ ] Build passes
- [ ] Public interfaces updated if impacted (API, UI, CLI, file formats, protocols, library API)
- [ ] Domain invariants respected
- [ ] No breaking changes unless explicitly approved

---

# 8. Stop Conditions

The standard ones apply (`delivery/AGENT_GUIDE.md` §9). Story-specific ones only, or `none`:
- none

---

# 9. Impacted Areas

- Code:
- Interfaces (API, CLI, file formats, protocols, library API):
- Domain:
- UX:
- Platforms / distribution:
- Tests:
- Docs:

---

# 10. Notes / Clarifications

- …

---

# 11. Final Reconciliation

Facts written by `/persist` before Done (no checkboxes):

- Reconciled at:
- AC met: n/n (unmet ones listed with the reason)
- Tasks deferred: none / TSK-… → <new story ID>
- Spec changes since Ready: none / §… (Deviation #n)
- Reference docs updated: none / <paths>
---

## Revisions

> One line per change after approval or closure: date, what, source (minutes, owner decision, commit).
