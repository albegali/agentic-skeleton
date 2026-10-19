# Step onboard — document an existing codebase as the baseline (product mode)

**Command**: `/onboard [focus areas, docs to read, constraints]` · **Tier**: deep · **Session**: fresh

**Precondition**: the workflow was installed with `tools/adopt.py` (`project.toml` → `origin = "brownfield"`). This step replaces kickoff → requirements → mockup → architecture: it describes the system **as it is**, not as it should be. Any kind of software qualifies; nothing below assumes a web app, a server or a cloud.

**Context**: `python3 tools/context.py onboard` (templates + repository map). Then open code **selectively** (budget: about 40 files; `grep` a symbol instead of reading directories; record what you could not cover as a gap). Never open `.env*`, credentials, keys, signing material (keystores, provisioning profiles, certificates), dumps or real data files.

## 1. Classify (no writes)
From the map's *Software type signals* and the root files, decide what the repository delivers. It can be several things (a monorepo, an app plus its backend, a library plus a demo app). Name each **deliverable**, its type and its target platforms:

| Type | Look at (examples, not a checklist) | Persistence / interfaces to find | Distribution to find |
|---|---|---|---|
| Web frontend | app bootstrap, router/states, views/components, build config, supported browsers | browser storage, calls to back ends | static hosting, CDN, embedded in a server |
| Service / backend / API | entry point, routing or handlers, API contracts, jobs/queues | DB schema or ORM models (latest state), caches, messaging | cloud on any provider, on-prem, containers, serverless |
| Mobile app | manifest / Info.plist, navigation, screens, permissions, min OS versions, native modules | local DB, keychain/keystore use, push, offline sync | app stores, enterprise/MDM, OTA updates |
| Desktop app | main window/process, menus, IPC, OS integrations, supported OSes | local files and formats, settings, local DB | installers, stores, auto-update, packages |
| Game | engine project settings, scenes/levels, core loop scripts, input, assets layout | save games, profiles | stores/launchers, consoles, web builds |
| Embedded / firmware / hardware | board/target config, HAL/drivers, RTOS tasks, interrupts, linker/memory layout | flash/EEPROM, protocols (serial, BLE, CAN, …) | flashing, OTA/DFU, manufacturing |
| Library / SDK / package | public API surface (exports, headers, public classes), versioning, examples | file formats, wire protocols | package registries, vendoring |
| Command-line tool | commands, flags, config files, exit codes | files read/written | binaries, package managers |
| Data / ML / analytics | pipelines/DAGs, notebooks, models, data contracts, schedules | datasets, feature stores, warehouses | jobs, model registries, reports |
| Infrastructure / platform code | modules/stacks, environments, state handling, policies | state backends | applied by pipelines or by hand |
| Extension / plugin | host application and its API version, manifest, permissions | host storage | host marketplace |
| Enterprise platform / legacy | platform objects/programs, batch jobs, integrations | platform DB | platform transports/deploys |

Keep track of the evidence (file paths) for each fact. The **mockup** step does not apply: the existing UI, if any, is the behavior reference.

## 2. Interview (1 round, grouped questions)
Skip what the arguments already answer. Ask only what the code cannot tell: the product's purpose and its users (end users, developers for a library, operators for infrastructure); the owner's goals for the next 3–6 months; supported platforms and versions that matter; known pain points and tech debt; frozen or sensitive areas (compliance, safety, legacy, other teams); whether the main technology choices are still endorsed.

## 3. Write
Every artifact is a draft (`status: draft`, ADRs `status: proposed`), in the project language, from `inception/templates/`:
- `reference/architecture/architecture.md` — current state, for each deliverable: §1 software type, target platforms, users and external systems; §2 building blocks with **package path** and **package rules** filled; §3 data and persistence of whatever kind (none is a valid answer); §4 integrations and interfaces (APIs, IPC, devices, protocols, file formats, host APIs); §5 security, privacy, permissions; §6 observability (logs, crash reporting, telemetry, or none); §7 build, environments and distribution; §8 testing strategy with the real commands, including manual or device testing if that is the practice; §9 *Conventions for agents* from the observed patterns (where new code goes, naming, error handling, what never to touch: generated code, vendored dirs, applied migrations, signed or binary assets). Cite paths; mark inferences as **assumption**.
- `reference/architecture/ADR-001-<slug>.md`… — one **retroactive** ADR per decision already built into the code that is costly to reverse (language, framework or engine, UI toolkit, persistence, auth, target platforms, distribution channel, integration style, key libraries); max 8. *Context* starts with "Retroactive: documented from the code on <date>" and lists the evidence; *Options* = as built vs. the realistic alternative; *Decision* = what the code does.
- `<package>/AGENTS.md` for each building block with its own conventions (≤ 40 lines: layout, patterns, commands, test rules, do-not list). If the package already has an `AGENTS.md` / `CLAUDE.md`, append a section; never rewrite the team's text.
- `reference/product/functional-requirements.md` — **FR index** of what the system does today, in the terms of its users (screens and flows for a UI, endpoints or jobs for a service, public API capabilities for a library, commands for a CLI, device functions for firmware, pipelines for data): frontmatter `status: draft`, `sources: [code]`; `## <capability area>` groups; one heading per capability:
  ```
  ### FR-01 — <capability>
  - **Statement**: The system <does …> (as built).
  - **Where**: `path/`, `path/file`
  - **Source**: code | docs | interview | assumption
  - **UI**: yes | no
  - **Status**: existing
  ```
  No `Priority` (existing capabilities are not backlog). Full statements and acceptance hints are written later, when a story changes that FR.
- `reference/project-summary.md` (≤ 60 lines; *Type and platforms* and *Stack* filled), `reference/domain/glossary.md` (domain terms from entities, enums, states, screens, commands), `reference/product/vision.md` (current product + direction from the interview; unknown sections say "unknown — to validate").
- `project.toml` `[stack]`: confirm or correct `summary`, `setup`, `test`, `lint` guessed by `adopt.py`; fill them when empty, plus `run` (start the app locally) and `url` when the app can be launched on this machine. A command may wrap a tool, an emulator or a device runner; if a step can only be done by hand (IDE build, store upload, hardware flashing), say so in `architecture.md` §8 and leave the command empty. Do not run commands unless the user agrees. Keep `decided = false`.
- `project-journal/context/<today>-onboard.md` — deliverables and types found, what was read, gaps not analysed, tech debt and risks with paths, test/CI gaps (if a pipeline exists, where to add `python3 tools/check_workflow.py`), **candidate work** for `/backlog` (proposals only, not stories).

## 4. Rules
No code changes, no refactoring, no formatting, no dependency updates. Never present intentions or assumptions as facts. No secrets or personal data in the artifacts. Then run `make check` (or `python3 tools/check_workflow.py`).

**Chat** (≤ 10 lines): deliverables and types, ADR list, FR count, top 3 risks, assumptions to validate, gaps.
**Gate**: the owner sets `status: approved` in `vision.md`, `functional-requirements.md`, `architecture.md`; ADRs `status: accepted`; `decided = true` in `project.toml` `[stack]`. Then `make next` → `/backlog <change requests, issues, notes>`.
