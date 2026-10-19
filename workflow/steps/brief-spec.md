# Step brief-spec — Brief and Spec of one story (developer mode)

**Command**: `/brief <ID>` · **Tier**: balanced · **Session**: fresh, one story

**Context**: `python3 tools/context.py brief-spec {ID}` — guide, Brief/Spec templates, the Refined Story (else Analysis, else Story), only the cited reference sections. Do not re-read `analysis/` beyond that.

**Prompt**
```
Explicit switch to developer mode for {ID}. Respect the budget printed by tools/context.py.
1. Brief in delivery/10-briefs/ (Brief template): keep the original wording.
2. Spec in delivery/20-specs/ (Spec template): scope, AC, tasks TSK-{ID}-NN, boundaries, quality gates, stop conditions; constraints from the cited ADRs/NFRs.
3. Add the row to delivery/20-specs/README.md.
Stop after the Spec (status Draft). Chat: 5 lines with scope, number of AC and tasks, open doubts.
```
