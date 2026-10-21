# Step approve — human approval of an inception artifact

No agent. `make next` names the file waiting for you.

1. Read the artifact (vision, requirements, mockup map, architecture/ADRs, backlog, plan; after `/onboard`: vision, FR index, architecture, retroactive ADRs, package `AGENTS.md`).
2. If it is fine: `make approve GATE=inception FILE=<file>` (sets `status: approved`, `status = "approved"` in `backlog/stories.toml`, `status: accepted` for an ADR, and commits it with your name and the time); after the architecture or the onboarding also `make approve GATE=stack` (`decided = true`). Editing the field by hand works too, but leaves no approval commit.
3. A revision applied by an agent from your recorded decisions (workshop minutes, chat) keeps the artifact approved: nothing to re-approve. The revision line names the source.
4. Otherwise rerun the step's command with your changes, e.g. `/requirements add FR for exports; NFR-04 target is 2s` or `/onboard the billing module was skipped`.

Then `make next` (or `/next`).
