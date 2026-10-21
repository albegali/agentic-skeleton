# Workshop minutes Template

Written by the humans who ran the workshop (or by an agent from their notes, then confirmed by them). `/refine` reads it with `--with <file>`.

Naming: `analysis/workshops/WORKSHOP_<YYYY-MM-DD>_<ID>[-<ID>…].md` (the stories discussed, max 4).

Owner decisions recorded here are approvals (AGENTS.md §3): `/refine` applies their consequences without asking again.

```md
# Workshop minutes — <YYYY-MM-DD> — <ID>, <ID>

- **Participants**: <name (role)>, …
- **Input**: §7 of the Analyses in `analysis/20-analysis/`
- **Technical proposals**: all stand as written in the Analyses, except the overrides below.

## Overrides of technical proposals

| Story | Proposal | Owner decision |
|---|---|---|
| <ID> | <proposal from Analysis §7> | <decision and its consequence> |

## Answers to functional points

| Story | Question | Owner answer |
|---|---|---|
| <ID> | <question from Analysis §7> | <answer> |

## Consequences noted (to handle in /refine)

- <change to an ADR, architecture, backlog (split, order "X before Y"), requirement: who decided it>

## Open points

| Story | Point | Owner | Blocks readiness |
|---|---|---|---|
| <ID> | <point> | <name> | yes / no |
```
