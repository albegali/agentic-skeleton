# Step plan — releases and sprints (product mode)

**Command**: `/release-plan [constraints]` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py plan` (backlog overview and dependency list, no story files).

## Procedure
1. Ask only what is missing: sprint length (default 2 weeks), start date, team capacity (stories or points per sprint), fixed milestones.
2. Write `PLAN.md` from `inception/templates/PLAN.md`:
   - releases with goal, content (epics/stories), target date, exit criterion;
   - sprint table `| S<n> | dates | goal | story IDs |` — this exact shape is parsed by `tools/next_step.py`;
   - S0 = analysis of the first two sprints (Analysis + workshops); development starts with the walking skeleton;
   - respect dependencies (a story never precedes its deps); analysis runs one sprint ahead of development.
3. Keep `status: draft` in the frontmatter. Run `make next` to verify the plan parses.

**Chat**: releases with dates, sprint count, risks on capacity (max 6 lines).
**Gate**: the owner sets `status: approved` in `PLAN.md`. From here `make next` drives the analysis/delivery loop.
