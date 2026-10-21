# Step human-gate — your turn

`make next` found only human actions. For each listed ID or file:

| State | What to do | Then |
|---|---|---|
| `approve` | Review the inception artifact; `make approve GATE=inception FILE=<file>` (`workflow/steps/approve.md`) | `make next` |
| `workshop` | Refinement workshop and minutes (`workflow/steps/workshop.md`) | `/refine <ID> <minutes>` |
| `spike-review` | Review the spike findings; status → `Accepted`, add the follow-ups (`workflow/steps/spike-review.md`) | `/backlog <follow-ups>` |
| `spec-approval` | Review the Spec; `make approve ID=<ID> GATE=spec` | `/run <ID>` |
| `run-approval` | Approve or revise the strategy (quick track: the approval covers the Spec too) | `/run <ID> approve` (or `make approve ID=<ID> GATE=strategy`, then `/run <ID>`) |
| `tuning` | Verify, tune (review findings in RUN §11 or the security review in RUN §8, if any), persist (`workflow/steps/tuning.md`) | `/run <ID> tuning: …` · `/persist <ID>` |
| `blocked` (RUN) | Read the RUN §6 deviation the detail names; approve it, or change the Spec / cancel | `/run <ID> approve-deviation <n>` · `/spec <ID> <change>` · `/run <ID> cancel: <reason>` |
| `blocked` (Spec) | Unblock the Spec (decision, dependency) and set it back to `Ready`, or fix the unknown status value the detail names | `make next` |
| `stopped` | You stopped the RUN at its approval: resume with a new strategy, or drop the story | `/run <ID> revise: <what>` · `/run <ID> cancel: <reason>` |

Dropping a story is your decision: `/run <ID> cancel: <reason>` records it (story `status = "cancelled"` in `backlog/stories.toml`, RUN and Spec `Cancelled`). A cancelled or superseded story counts as done for the sprint order; `make check` warns about stories that still depend on it.

Meanwhile the analyst can work ahead: `make next` proposes it when later sprints miss Analysis.
