---
artifact_type: architecture
status: draft            # draft | approved
adrs: [ADR-001]
last_updated: YYYY-MM-DD
---

# Architecture

## 1. Context
<System context: users, external systems, trust boundaries. A Mermaid diagram is welcome.>

## 2. Building blocks
| Container / module | Responsibility | Technology | Package path | Package rules |
|---|---|---|---|---|
| … | … | … | `server/` | `server/AGENTS.md` |

## 3. Data model (outline)
<Main entities, ownership, lifecycle. Details grow story by story.>

## 4. Integrations
| External system | Direction | Protocol | Port / adapter | Owner | Phase |
|---|---|---|---|---|---|

## 5. Security and privacy
<AuthN/AuthZ, secrets, personal data, logging rules (no PII in logs).>

## 6. Observability
<Logs, metrics, traces, audit.>

## 7. Environments and delivery
<Environments, CI/CD, infrastructure as code.>

## 8. Testing strategy
<Unit / integration / e2e, what each layer proves, commands.>

## 9. Conventions for agents
<Patterns to follow, where new code goes, what never to do.>
