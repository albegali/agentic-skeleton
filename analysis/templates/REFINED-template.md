# Refined Story Template

Use this template to create or update a `Refined Story` once refinement evidence exists.

The `Refined Story` contains:
- the user story consolidated after refinement;
- confirmed decisions and facts;
- acceptance criteria ready for the Brief;
- residual points to carry into the Brief without blocking intake.

Naming: `analysis/30-refined/REFINED_<ID>_<short_title>.md`

Minimum inputs: the Story, the Analysis, refinement evidence (workshop minutes) from PO, BA, stakeholders or technical teams.

Keep it short, mainly functional, oriented to Brief intake.

```md
---
artifact_type: refined
us_id: STORY_<ID>
title: <Short title>
roadmap_phase: <R1 | R2 | … | unknown>
status: draft | refined | approved
source_files:
  - analysis/10-stories/STORY_<ID>_<short_title>.md
  - analysis/20-analysis/ANALYSIS_<ID>_<short_title>.md
workshop_evidence:
  - project-journal/notes/YYYY-MM-DD-workshop-<topic>.md
related_references:
  - reference/architecture/ADR-...
last_updated: YYYY-MM-DD
---

# Refined Story <ID> - <Short title>

## 1. References

- ID:
- Title:
- Roadmap phase:
- Sources used:
- Missing sources:
- Workshop evidence:

## 2. Refined User Story

### Refined story text

<Story consolidated after refinement>

### Refined description

<Refined description, if any>

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

<Keep exactly one line:>
- Story ready for Brief intake
- Story ready with residual open points to track
- Story not ready and requires further refinement
```
