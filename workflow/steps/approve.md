# Step approve — human approval of an inception artifact

No agent. `make next` names the file waiting for you.

1. Read the artifact (vision, requirements, mockup map, architecture/ADRs, backlog, plan; after `/onboard`: vision, FR index, architecture, retroactive ADRs, package `AGENTS.md`).
2. If it is fine, set its status: `status: approved` in the frontmatter (`status = "approved"` in `backlog/stories.toml`; ADRs `status: accepted`; `decided = true` in `project.toml` after the architecture or the onboarding).
3. A revision applied by an agent from your recorded decisions (workshop minutes, chat) keeps the artifact approved: nothing to re-approve. The revision line names the source.
4. Otherwise rerun the step's command with your changes, e.g. `/requirements add FR for exports; NFR-04 target is 2s` or `/onboard the billing module was skipped`.

Then `make next` (or `/next`).
