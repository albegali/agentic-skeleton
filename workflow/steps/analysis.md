# Step analysis — Analysis of the sprint's stories (analyst mode)

**Command**: `/analysis <ID…>` · **Tier**: balanced · **Session**: fresh, at most 4 related stories

**Context**: `python3 tools/context.py analysis {IDS}` — guide and template once, the Story files, only the FR/NFR/ADR sections the Story cites, and §6-7 of the Analysis of dependencies.

**Prompt**
```
Analyst mode. Create the Analysis for: {IDS}, one file each in analysis/20-analysis/, using exactly analysis/templates/ANALYSIS-template.md.
Respect the context budget printed by tools/context.py.
Separate facts, interpretations and assumptions; declare missing sources; do not invent requirements; rank the points to clarify by impact.
At the end run `make backlog` and write in chat only the high-impact workshop points, grouped by theme (max 15 lines).
Do not create Refined Story, Brief, Spec or RUN.
```
