# Refined Story Template

Use this template to create or update a `Refined Story` once refinement evidence exists.

The `Refined Story` contains:
- the user story consolidated after refinement;
- confirmed decisions and facts;
- acceptance criteria ready for the Brief;
- residual points to carry into the Brief without blocking intake.

Naming: `analysis/30-refined/REFINED_<ID>_<short_title>.md`

Minimum inputs: the Story, the Analysis, the workshop minutes (`analysis/workshops/`, template `analysis/templates/WORKSHOP-template.md`).

Keep it short, mainly functional, oriented to Brief intake.

```md
---
artifact_type: refined
us_id: STORY_<ID>
title: <Short title>
roadmap_phase: <R1 | R2 | … | unknown>
status: draft | refined | approved   # agent: draft → refined (outcome ready*); owner only: approved (optional)
source_files:
  - analysis/10-stories/STORY_<ID>_<short_title>.md
  - analysis/20-analysis/ANALYSIS_<ID>_<short_title>.md
workshop_evidence:
  - analysis/workshops/WORKSHOP_YYYY-MM-DD_<ID>.md
related_references:
  - reference/architecture/ADR-...
last_updated: YYYY-MM-DD
---

# Refined Story <ID> - <Short title>

## 1. References

- Missing sources: <none, or what was not available>

## 2. Refined User Story

Only if the workshop changed the statement: the new statement (then also update `backlog/stories.toml` and run `make backlog`). Otherwise: "Unchanged: see the Story."

## 3. Scope

### In scope

- ...

### Out of scope

- ...

## 4. Confirmed Information

### Facts

- <Requirements or constraints confirmed by sources and refinement>

### Decisions confirmed during refinement

- ...

### Residual assumptions

- ...

## 5. Confirmed Acceptance Criteria

- <Final, testable acceptance criteria>

## 6. Remaining Open Points

Only the residual points to carry into the Brief or to handle before intake. Say explicitly if a point blocks readiness.

### Functional

- ...

### Technical

- ...

## 7. Brief Handoff Notes

### Candidate Brief Tasks

- <First list of tasks or analysis areas for the Brief, possibly feeding the Spec>

### Boundaries to respect

- ...

## 8. Refinement Outcome

<Keep exactly one line; the code in backticks is parsed by tools/next_step.py and stays in English, the text follows the project language:>
- `ready` Story ready for Brief intake
- `ready-with-open-points` Story ready with residual open points to track
- `not-ready` Story not ready and requires further refinement

---

## Revisions

> One line per change after `refined`: date, what, source.
```
