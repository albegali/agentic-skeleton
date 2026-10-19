# Step kickoff — project setup and vision (product mode)

**Command**: `/kickoff [name] [sources…]` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py kickoff`, plus the source files passed as arguments (brief, transcript, notes). Nothing else.

## Procedure
1. **Settings** (deterministic). Ask, in one message, only what is missing from the arguments and sources:
   - project name and one-line description;
   - story ID prefix (2–3 uppercase letters, default from the name);
   - artifact language (default `en`; any ISO code, e.g. `it`);
   - product owner name (the human approver);
   - include the mockup step? (default yes for products with a UI);
   - which agent tools the team uses (Claude Code, Codex CLI, Copilot, Cursor).
   Then run `python3 tools/init_project.py --name … --prefix … --language … --owner … [--no-mockup] [--tools claude-code,codex,…]`.
2. **Interview** (max 2 rounds, grouped questions). Cover: problem and why now; type of software and target platforms (web, mobile, desktop, embedded, library, CLI, data, …); target users and their jobs; desired outcomes and success metrics; scope boundaries (in / out / later); constraints (deadlines, budget, regulations, systems to integrate, data sensitivity); key stakeholders and decision makers. Prefer what the sources already say; ask only for gaps.
3. **Write** from `inception/templates/`:
   - `reference/product/vision.md` (frontmatter `status: draft`);
   - `reference/project-summary.md` (≤ 60 lines: the context every later step reads);
   - `reference/documentation/stakeholders.md`;
   - `reference/domain/glossary.md` (terms that already appeared);
   - a context entry in `project-journal/context/<today>-kickoff.md` (sources, decisions taken at kickoff).
4. Mark every statement that is not from the user or the sources as an **assumption**. Do not invent metrics, users or deadlines.

**Chat**: 5 lines: one-line vision, top 3 assumptions to validate, next step (`approve vision.md` → `/requirements`).
**Gate**: the owner sets `status: approved` in `vision.md`.
