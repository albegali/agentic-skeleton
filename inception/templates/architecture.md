---
artifact_type: architecture
status: draft            # draft | approved
adrs: [ADR-001]
last_updated: YYYY-MM-DD
---

# Architecture

## 1. Context
<Software type(s) and target platforms (web, service, mobile, desktop, game, embedded, library, CLI, data, infrastructure, extension, … · OS / devices / browsers / runtimes). Users, external systems, devices, trust boundaries. A Mermaid diagram is welcome.>

## 2. Building blocks
| Building block (app, service, library, module, firmware, …) | Responsibility | Technology | Package path | Package rules |
|---|---|---|---|---|
| … | … | … | `<path>/` | `<path>/AGENTS.md` |

## 3. Data and persistence (outline)
<Main entities, ownership, lifecycle, and where they live: database, local or device storage, files, external system, none. Details grow story by story.>

## 4. Integrations and interfaces
| External system / device / host | Direction | Protocol / API / format | Port / adapter | Owner | Phase |
|---|---|---|---|---|---|

## 5. Security and privacy
<AuthN/AuthZ, OS or device permissions, secrets and signing keys, personal data, logging rules (no PII in logs).>

## 6. Observability
<Logs, metrics, traces, crash reporting, telemetry, audit: as fits the product (none is a valid answer).>

## 7. Build, environments and distribution
<How it is built, which environments exist, and how it reaches its users: cloud or on-prem deployment (any provider), app stores, installers and auto-update, firmware flashing / OTA, package registries, … CI/CD and infrastructure as code, if any.>

## 8. Testing strategy
<Unit / integration / end-to-end / device or manual tests: what each layer proves, commands, target platforms covered.>

## 9. Conventions for agents
<Patterns to follow, where new code goes, what never to do.>
