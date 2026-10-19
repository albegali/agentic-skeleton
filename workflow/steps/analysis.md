# Step analysis — Analysis of the sprint's stories (analyst mode)

**Command**: `/analysis <ID…>` · **Tier**: balanced · **Session**: fresh, at most 4 related stories

**Context**: `python3 tools/context.py analysis {IDS}` — guide and template once, the Story files, only the FR/NFR/ADR sections the Story cites, and §6-7 of the Analysis of dependencies.

**Prompt**
```
Analyst mode. Create the Analysis for: {IDS}, one file each in analysis/20-analysis/, using exactly analysis/templates/ANALYSIS-template.md.
Respect the context budget printed by tools/context.py.
Separate facts, interpretations and assumptions; declare missing sources; do not invent requirements; rank the points to clarify by impact.
Functional points: only business/functional questions the PO must answer (move technical points that need a business trade-off here, phrased as the business question).
Technical points: give a proposal for each (resolution, rationale, alternatives, confidence), consistent with the cited ADRs; it stands unless the team overrides it.
At the end run `make backlog` and write in chat only the high-impact functional questions for the PO, grouped by theme, then one line per high-impact technical proposal (max 15 lines).
Do not create Refined Story, Brief, Spec or RUN.
```
