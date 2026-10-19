---
artifact_type: plan
status: draft            # draft | approved
owner: <product owner>
last_updated: YYYY-MM-DD
---

# PLAN — release plan

> Living document, owned by the PO. Agents read it and do not change it, except the "Status" column after reconciliation.

## 1. Objective
<What the first release must achieve.>

## 2. Releases

| Release | Content | Target | Exit criterion |
|---|---|---|---|
| R1 | EP-01, EP-02 | YYYY-MM-DD | … |

## 3. Sprints

> Parsed by `tools/next_step.py`: keep the 4 columns; list story IDs or epic IDs (EP-xx) in the last one. Order inside a sprint = development order.

| Sprint | Dates | Goal | Stories |
|---|---|---|---|
| S0 | DD/MM – DD/MM | Analysis | Analysis and workshops of S1–S2 |
| S1 | DD/MM – DD/MM | Foundations | PR0101 |

## 4. Risks and assumptions
- …

## 5. Decisions pending
- …
