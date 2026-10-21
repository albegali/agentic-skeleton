# Step human-gate — your turn

`make next` found only human actions. For each listed ID or file:

| State | What to do | Then |
|---|---|---|
| `approve` | Review the inception artifact, set its status (`workflow/steps/approve.md`) | `make next` |
| `workshop` | Refinement workshop and minutes (`workflow/steps/workshop.md`) | `/refine <ID> <minutes>` |
| `spec-approval` | Review the Spec; status → `Ready` | `/run <ID>` |
| `run-approval` | Approve or revise the strategy | `/run <ID> approve` |
| `tuning` | Verify, tune, close (`workflow/steps/tuning.md`) | `/persist <ID>` |
| `blocked` (RUN) | Read the RUN §6 deviation the detail names; approve it, or change the Spec / cancel | `/run <ID> approve-deviation <n>` · `/spec <ID> <change>` · `/run <ID> cancel: <reason>` |
| `blocked` (Spec) | Unblock the Spec (decision, dependency) and set it back to `Ready`, or fix the unknown status value the detail names | `make next` |
| `stopped` | You stopped the RUN at its approval: resume with a new strategy, or drop the story | `/run <ID> revise: <what>` · `/run <ID> cancel: <reason>` |

Dropping a story is your decision: `/run <ID> cancel: <reason>` records it (story `status = "cancelled"` in `backlog/stories.toml`, RUN and Spec `Cancelled`). A cancelled or superseded story counts as done for the sprint order; `make check` warns about stories that still depend on it.

Meanwhile the analyst can work ahead: `make next` proposes it when later sprints miss Analysis.
