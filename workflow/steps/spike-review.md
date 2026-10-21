# Step spike-review — spike findings review (human)

1. Read `delivery/40-spikes/SPIKE-<ID>-*.md`.
2. Accepted: `make approve ID=<ID> GATE=spike` (`## Status` → `Accepted`); add the follow-up stories you want with `/backlog <follow-ups from SPIKE-<ID>>` and plan them in `PLAN.md`; delete the `spike/<id>` branch.
3. Not enough: write what is missing under "Open questions" and rerun `/spike <ID> <new time-box>`.

Then `make next`.
