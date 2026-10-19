# Analysis Template

Use this template to create or update an `Analysis`.

The `Analysis` contains:
- the initial functional analysis;
- the points to clarify before the story is ready for development.

Naming: `analysis/20-analysis/ANALYSIS_<ID>_<short_title>.md`

Minimum inputs: `reference/project-summary.md`, `analysis/10-stories/STORY_<ID>_<short_title>.md`.
Additional inputs only when relevant (and listed by `tools/context.py`): related Analysis/Refined Story, cited FR/NFR/ADR sections.

Keep it mainly functional and limited to what the analysis needs.

```md
---
artifact_type: analysis
us_id: STORY_<ID>
title: <Short title>
roadmap_phase: <R1 | R2 | … | unknown>
status: draft | analyzed | workshop-ready | updated
source_files:
  - analysis/10-stories/STORY_<ID>_<short_title>.md
  - reference/project-summary.md
related_references:
  - reference/product/functional-requirements.md#FR-xx
  - reference/architecture/ADR-xxx-….md
last_updated: YYYY-MM-DD
---

# Analysis <ID> - <Short title>

## 1. References

- ID:
- Source story:
- Roadmap phase:
- Sources used:
- Missing sources:

## 2. Original User Story

### Story text

<Original text>

### Description

<Original description, if any>

## 3. Intent Understanding

### Functional goal

- ...

### Actors involved

- ...

### Expected outcome

- ...

## 4. Information Classification

### Facts

- <Requirements or constraints taken from sources: ADRs, specs, backlog, other Analysis/Refined Story, Brief, Spec, reference docs>

### Clarifications received

- <Clarifications from PO, BA, stakeholders or technical teams>

## 5. Original Acceptance Criteria

<Copy the original acceptance criteria exactly, or state that none were provided>

## 6. Ambiguities, Functional Gaps, and Technical Gaps to Clarify

### Functional ambiguities

- ...

### Functional gaps

- ...

### Technical gaps

- ...

### Dependencies or ownership points to clarify

- ...

## 7. Workshop Refinement Preparation

Points to resolve before the story is ready for development (input for Brief, Spec and delivery).

### Functional points to resolve

- [High impact] ...
- [Medium impact] ...
- [Low impact] ...

### Technical points to resolve

- [High impact] ...
- [Medium impact] ...
- [Low impact] ...

### Readiness outcome expected

- Story scope confirmed or reformulated
- Acceptance criteria clarified and testable
- High-impact functional points resolved
- High-impact technical points resolved or assigned to the correct owner
- Residual assumptions explicitly documented
```
