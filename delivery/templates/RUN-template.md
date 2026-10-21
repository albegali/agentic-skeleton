# RUN-<ID>

## References
- Story ID: <ID>
- Spec: SPEC-<ID>
- Started at (datetime):
  - Fill only when execution starts after human approval, immediately before the first code or test change.
- Completed at (datetime):
  - Fill only when the RUN is ready to close after verification, tuning and persistence.
  - If tuning or follow-up changes happen before closure, update this to the latest completion datetime.

---

## Status
Draft → Strategy Approved → Executing → Tuning → Persisted → Closed  ·  Stopped / Blocked / Cancelled

> A RUN MUST NOT be Closed before Persisted.
> Stopped: the human stopped it at §2 (resume with `/run <ID> revise: …`). Blocked: a §6 deviation awaits approval
> (`/run <ID> approve-deviation <n>`). Cancelled: the story was dropped (`/run <ID> cancel: …`); terminal.

---

# 1. Execution Strategy (Agent)

> MUST be written before any code.

### Required Reads
- [ ] Target Spec
- [ ] Scoped package `AGENTS.md` files, if applicable:
  - …
- [ ] `delivery/templates/RUN-template.md`

### Plan
- Step 1: …
- Step 2: …
- Step 3: …

### Assumptions
- …
- …

### Risks / Open Questions
- …
- …

### Scoped Agent Rules Check
- Applies: Yes / No
- Files read:
  - …
- Notes:
  - …

---

# 2. Human Approval

- [ ] Strategy reviewed
- [ ] Scope correctly understood
- [ ] No out-of-scope work detected

Decision:
- [ ] Approved
- [ ] Revisions requested
- [ ] Stopped

Notes:
- …

Reviewer:
Date:

---

# 3. Execution Log (Agent)

### Steps
- Step 1: …
- Step 2: …

### Changes (high-level)
- Code:
- Interfaces:
- Domain:
- Tests:
- Specs:

---

# 4. Verification

- Build: OK / FAIL
- Tests: OK / FAIL
- Interfaces / target platforms: OK / FAIL
- Manual (if any): OK / FAIL

Notes:
- …

If FAIL → move to Tuning.

---

# 5. Tuning Log (If needed)

> Only within scope.

### Entry #1
- Issue:
- Fix:
- Impact:
- Verified: Yes / No

### Entry #2
- …

---

# 6. Deviations

> One entry per deviation or stop condition. `Requires approval` sets the RUN to Blocked until a human approves it.

### Deviation #1
- What changed:
- Why:
- Plan impact:
- Scope impact: None / Minor / Requires approval
- Approved by:
- Date:

---

# 7. Persistence / Reconciliation

- [ ] Spec updated (if needed)
- [ ] Specs updated (if needed)
- [ ] Acceptance Criteria aligned

Summary:
- …

---

# 8. Quality Gates Check

- [ ] Acceptance criteria satisfied
- [ ] Tests passing
- [ ] No scope creep
- [ ] Persistence completed

---

# 9. Outcome

Tasks completed:
- TSK-...

Tasks deferred:
- …

Goal achieved:
- [ ] Yes
- [ ] Partial
- [ ] No

Summary:
- …

---

# 10. Next Steps

- Follow-ups:
- Risks:
- Improvements:

---

## Revisions

> Post-closure only: factual corrections (links, typos, recorded results), one line each with date and source.
> A change in behaviour is a new story with `supersedes = "<ID>"` in `backlog/stories.toml`, never a revision.

