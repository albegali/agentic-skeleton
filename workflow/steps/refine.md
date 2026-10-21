# Step refine — Refined Story after the workshop (analyst mode)

**Command**: `/refine <ID…> <minutes file>` · **Tier**: balanced · **Session**: fresh; stories of the same workshop together (max 4)

**Context**: `python3 tools/context.py refine {IDS} --with {MINUTES}` — guide, template, Story and Analysis, the minutes, the references the Analysis cites. Nothing else.

**Prompt**
```
Analyst mode. Create the Refined Story of {IDS} in analysis/30-refined/ with analysis/templates/REFINED-template.md.
Workshop evidence: {MINUTES}. If missing, stop.
Update the Analysis only if the workshop changes it. In the Refined Story keep facts, decisions, residual assumptions and open points separate; technical proposals from the Analysis not overridden in the minutes become decisions (mark them "proposal accepted by default"); unanswered high-impact functional points stay open and block readiness. Fill Brief Handoff Notes and Refinement Outcome (one line, starting with its English code `ready`, `ready-with-open-points` or `not-ready`).
Frontmatter `status`: the agent sets `refined` when the outcome is `ready` or `ready-with-open-points`, and leaves `draft` when it is `not-ready`. Only the owner sets `approved` (optional: `refined` already lets `/brief` start).
Owner decisions in the minutes are approvals. Apply their consequences in this session, keeping the artifacts approved/accepted and adding a revision line that cites {MINUTES}: ADR and architecture.md changes; backlog changes in backlog/stories.toml (a split story keeps its ID for the part others depend on, the rest takes the next free ID in its epic, and dependents get the new ID in deps; an ordering decided in the workshop, "X before Y", becomes X in Y's deps, never prose only), then `make backlog` and `make check`. Never ask the owner to re-approve what the minutes decide. A consequence the minutes do not decide stays an open point.
Chat: outcome per story (ready / ready with open points / not ready), artifacts changed, remaining human gates as `file → field → value`, and the next command.
```
