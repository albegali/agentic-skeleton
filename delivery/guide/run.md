# RUN rules (loaded by run-strategy / execute)

- A RUN is created for every Spec that enters execution; it is append-oriented and never rewrites past steps.
- §1 Execution Strategy is written **before any code**, with: required reads checked, plan in small verifiable steps, assumptions, risks/open questions, scoped `AGENTS.md` files read.
- §2 Human Approval: only a human ticks `Approved`; `/run <ID> approve` records it with reviewer (`project.toml` owner) and date.
- `Started at` is filled right before the first code or test change; `Completed at` when ready to close (updated if tuning follows).
- §3 Execution Log and §4 Verification: terse, append-only, one entry per plan step; if verification fails → status Tuning.
- §5 Tuning: within scope only, one entry per issue (issue, fix, impact, verified).
- §6 Deviations: what changed, why, scope impact (None / Minor / Requires approval). "Requires approval" stops the RUN.
- §7 Persistence, §8 Quality gates, §9 Outcome, §10 Next steps are completed by `/persist`. A RUN is never `Closed` before `Persisted`.
- §11 Addendum only after closure.
- Practical: prefer short RUNs; make tasks explicit; if it is not in the RUN, it did not happen.
