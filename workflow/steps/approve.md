# Step approve — human approval of an inception artifact

No agent. `make next` names the file waiting for you.

1. Read the artifact (vision, requirements, mockup map, architecture/ADRs, backlog, plan).
2. If it is fine, set its status: `status: approved` in the frontmatter (`status = "approved"` in `backlog/stories.toml`; ADRs `status: accepted`; `decided = true` in `project.toml` after the architecture).
3. Otherwise rerun the step's command with your changes, e.g. `/requirements add FR for exports; NFR-04 target is 2s`.

Then `make next` (or `/next`).
