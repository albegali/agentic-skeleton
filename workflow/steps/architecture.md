# Step architecture — stack and decisions (product mode)

**Command**: `/architecture [constraints]` · **Tier**: deep · **Session**: fresh

**Context**: `python3 tools/context.py architecture` (NFRs in full, FR index only: open single FRs by ID when needed).

## Procedure
1. Identify the **architecturally significant drivers**: NFR targets, integrations, data sensitivity, scale, team skills, hosting constraints, user constraints given as arguments.
2. Propose **2 options max** per open decision (stack, hosting, persistence, auth, AI provider if any, integration style), each with trade-offs against the drivers; recommend one. Ask the user to confirm the decisions that are costly to reverse before writing.
3. Write:
   - `reference/architecture/ADR-001-<slug>.md`… from `inception/templates/adr.md` (`status: proposed`), one decision each;
   - `reference/architecture/architecture.md` from the template: context, containers/modules, data model outline, integrations (ports & adapters), security and privacy, observability, environments, testing strategy;
   - an `AGENTS.md` stub in each package directory you plan (e.g. `server/AGENTS.md`, `client/AGENTS.md`) with local conventions: layout, patterns, commands, test rules. **Do not scaffold code** here: the walking skeleton is the first story.
4. Update `project.toml` `[stack]`: `summary`, `setup`, `test`, `lint` commands (they feed `make setup/test/lint`), keep `decided = false` until the ADRs are accepted.
5. Add to `reference/domain/glossary.md` any new term.

**Chat**: decisions table (decision → choice → ADR), risks, questions (max 10 lines).
**Gate**: the owner sets ADRs to `status: accepted`, `architecture.md` to `status: approved`, and `decided = true` in `project.toml`.
