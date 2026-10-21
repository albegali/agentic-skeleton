# Step weekly — project journal

**Command**: `/weekly` · **Tier**: fast · **Session**: fresh

**Context**: `python3 tools/context.py weekly` (template, current notes, git log of 7 days, workflow state, agent usage from `tools/usage.py`). Do not read artifacts in full.

**Prompt**
```
Prepare project-journal/weekly/<today>.md from project-journal/templates/weekly.md using only the printed budget. Facts separate from interpretations, verifiable metrics only, proposals marked as such. Model signals come only from the agent usage table: report the per-tier cost share, tier mismatches (✗), sessions over the context threshold, supervision counts and cost as printed, never estimate missing values. Then empty current-week.md, keeping its title.
```
