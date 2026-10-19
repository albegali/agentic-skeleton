# Hotfix procedure

Only for urgent or production-impacting issues. Flow: **Brief (Hotfix) → RUN → Spec (post-fix reconciliation)**.

- **Brief**: `Type: Hotfix`, urgency, affected behavior, user/production impact, expected fix direction, external reference if any.
- **RUN**: always created; `Mode: Hotfix`, short strategy, assumptions, verification, deviations, outcome. Execution may start after a lightweight human approval.
- **Reconciliation**: create/update a Spec if the corrected behavior becomes accepted behavior, update reference docs, document the final state, link the RUN. A hotfix RUN is not closed before reconciliation.
- **Never** in a hotfix: new features, unrelated refactors, scope expansion, unapproved breaking changes. If broader changes are needed, stop and open a normal Spec.
