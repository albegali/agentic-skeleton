# Step human-gate — your turn

`make next` found only human actions. For each listed ID or file:

| State | What to do | Then |
|---|---|---|
| `approve` | Review the inception artifact, set its status (`workflow/steps/approve.md`) | `make next` |
| `workshop` | Refinement workshop and minutes (`workflow/steps/workshop.md`) | `/refine <ID> <minutes>` |
| `spec-approval` | Review the Spec; status → `Ready` | `/run <ID>` |
| `run-approval` | Approve or revise the strategy | `/run <ID> approve` |
| `tuning` | Verify, tune, close (`workflow/steps/tuning.md`) | `/persist <ID>` |
| `blocked` | Unblock the Spec (decision, dependency) | `make next` |

Meanwhile the analyst can work ahead: `make next` proposes it when later sprints miss Analysis.
