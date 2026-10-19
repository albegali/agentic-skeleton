# AGENT_GUIDE — DELIVERY (core)

Agent-supervised coding, RUN-centric. Three artifacts, three questions:

| Artifact | Folder | Answers | Lifecycle |
|---|---|---|---|
| **Brief** | `delivery/10-briefs/BRIEF-<ID>-<slug>.md` | *why* — frozen snapshot of the request | Captured → Refined into Spec / Superseded |
| **Spec** | `delivery/20-specs/SPEC-<ID>-<slug>.md` | *what is allowed* — the contract | Draft → Ready → In Progress → Done / Blocked |
| **RUN** | `delivery/30-runs/RUN-<ID>.md` | *what happened* — execution trace | Draft → Strategy Approved → Executing → Tuning → Persisted → Closed |

Tasks: `TSK-<ID>-NN`. IDs are stable for the life of the work item. Templates in `delivery/templates/` are authoritative.
Sections loaded only when needed: `delivery/guide/run.md` (RUN rules), `delivery/guide/hotfix.md`, `delivery/guide/refactor-nfr.md`.

## 1. Principles
1. Brief drives everything.
2. The Spec is the contract: agents decide *how*, never *what* beyond the Spec; assumptions and deviations are logged.
3. The RUN is the single execution truth: append-only, never rewritten. A Spec without a RUN is not executed, whatever the code says.
4. No silent scope creep: out-of-scope work stops or becomes a logged deviation.
5. Tuning refines without expanding scope.
6. Persistence before closure: a RUN is complete only when every impacted document matches the accepted implementation.

## 2. Brief
Co-authored with the agent at capture time (structure, slug, clarity), preserving the original wording, source reference, goal, constraints, context, capture and closure dates. Once it has produced a Spec it is **frozen**: later clarifications go in the Spec or in an Brief Addendum.

## 3. Spec
References the Brief; defines goal, value, scope / out of scope, testable AC, tasks, execution boundaries, quality gates, stop conditions, impacted areas. Keep it small and focused.

## 4. Context loading
Upstream (`analysis/`, Refined Story) feeds Brief and Spec. Once Brief, Spec and RUN exist, the working set is: `delivery/`, the impacted code and tests, and `reference/` sections only when needed. Do not reload `analysis/` unless the Spec leaves a business ambiguity, reconciliation needs refinement decisions, or the user asks.

## 5. Standard procedure
1. **Capture intent** (human + agent) → Brief.
2. **Create Spec** (human + agent) → status Draft; the human sets `Ready`.
3. **Start RUN** (agent): read the Spec, the package `AGENTS.md` files in scope, the RUN template; write §1 Execution Strategy listing the package rules read. **No code before a human approves the strategy** (RUN §2).
4. **Approval** (human): approve, revise or stop.
5. **Execute** (agent): implement, test, update reference docs if needed; log in RUN §3-4.
6. **Verify & tune** (human + agent): bug fixes, test improvements, small refactors, minimal changes needed to meet AC. No new features.
7. **Persistence** (agent): update Spec §11 and the reference docs to the final accepted state; do not copy execution history into the Spec.
8. **Close RUN**: quality gates met, persistence done, deviations documented; then close the Brief (Closed at, Derived Artifacts).

## 6. Index
`delivery/20-specs/README.md`: one row per Spec (`| ID | Title | Status | RUN |`), kept simple. No RUN index: RUNs are reached through their Spec.

## 7. Quality gates
Tests updated · build passes · public interfaces valid (API, UI, CLI, formats, library API) · no breaking change unless approved · tuning logged · persistence done · RUN complete.

## 8. Roles (modes of the same or different agents)
- **Spec agent** — Brief → Spec: clarifies ambiguity, scope, AC, tasks, gates, stop conditions. No code.
- **Execution agent** — runs an approved Spec through a RUN, within scope, through persistence.
- **Reviewer agent** — checks Brief/Spec/RUN alignment, scope creep, quality gates, persistence, open risks. Used before closing a RUN, in a fresh session. For small items one agent may play several roles, but the RUN states which.

## 9. Stop conditions
Ambiguity · breaking change · security uncertainty · architectural conflict (vs. ADRs) · out-of-scope work.

## 10. Final principle
If it is not in the Spec, it is not allowed. If it is not in the RUN, it did not happen. If it is not reconciled, it is not complete.
