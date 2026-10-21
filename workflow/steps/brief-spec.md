# Step brief-spec — Brief and Spec of one story (developer mode)

**Command**: `/brief <ID>` · **Tier**: balanced · **Session**: fresh, one story

**Context**: `python3 tools/context.py brief-spec {ID}` — guide, Brief/Spec templates, the Refined Story (else Analysis, else Story), only the cited reference sections. Do not re-read `analysis/` beyond that.

**Prompt**
```
Explicit switch to developer mode for {ID}. Respect the budget printed by tools/context.py.
0. Be on the story branch `<id-lowercase>-<slug>` (already there after `make claim`; otherwise create it from an up-to-date main, delivery/guide/git.md).
1. Brief in delivery/10-briefs/ (Brief template): keep the original wording.
2. Spec in delivery/20-specs/ (Spec template): `Requirements:` = the story's fr/nfr in backlog/stories.toml (a different set is a decision: say so in chat), scope, AC each naming its test (`→ test: …`), tasks TSK-{ID}-NN, boundaries, quality gates, story-specific stop conditions only; constraints from the cited ADRs/NFRs. Do not copy the story statement.
3. `make backlog` (regenerates the Spec index), then commit Brief, Spec and index on the story branch (delivery/guide/git.md, commit points). Type refactor or NFR work: also follow delivery/guide/refactor-nfr.md.
Stop after the Spec (status Draft). Chat: 5 lines with scope, number of AC and tasks, open doubts.
```
