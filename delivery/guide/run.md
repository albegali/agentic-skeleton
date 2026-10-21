# RUN rules (loaded by run-strategy / execute)

- A RUN is created for every Spec that enters execution; it is append-oriented and never rewrites past steps.
- §1 Execution Strategy is written **before any code**, with: required reads checked, plan in small verifiable steps, assumptions, risks/open questions, scoped `AGENTS.md` files read.
- §2 Human Approval: only a human ticks `Approved`; `/run <ID> approve` records it with reviewer (`project.toml` owner) and date.
- `Started at` is filled right before the first code or test change; `Completed at` when ready to close (updated if tuning follows).
- Status: `Executing` at the first change; `Tuning` when every plan step is done and §4 is filled (pass or fail): the human verifies.
- §3 Execution Log and §4 Verification: terse, append-only, one entry per plan step.
- §5 Tuning: within scope only, one entry per issue (issue, fix, impact, verified).
- §6 Deviations: one `### Deviation #n` per deviation or stop condition (what changed, why, plan impact, scope impact None / Minor / Requires approval). "Requires approval" sets the RUN to `Blocked` and stops; `/run <ID> approve-deviation <n>` records the human approval and resumes.
- A Spec changed after the strategy approval goes back to `Draft` and blocks the RUN with a deviation (`/spec`); the strategy is re-approved through that deviation.
- `Stopped` (human, §2) resumes with `revise:`; `Cancelled` (`/run <ID> cancel: …`) is terminal.
- §7 Persistence, §8 Quality gates (with the `CI:` line), §9 Outcome, §10 Next steps are completed by `/persist` (RUN `Persisted`). §11 Review is written by `/review-story` only (`Reviewed`, or back to `Tuning`). `/close` sets `Closed`: never before `Persisted` and an `ok-to-close` review.
- A tuning request on a `Persisted` or `Reviewed` RUN sets it back to `Tuning`: `/persist` and the review run again.
- After closure only `## Revisions` lines (factual corrections). A behaviour change is a new story with `supersedes`.
- Practical: prefer short RUNs; make tasks explicit; if it is not in the RUN, it did not happen.
