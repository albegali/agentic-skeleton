# Step spec-approval — Spec review (human)

1. Read the Spec.
2. If it is fine, set `## Status` to `Ready`; otherwise write your requests in "10. Notes / Clarifications" and run `/spec <ID>` (it applies the §10 requests; extra changes can follow the ID).

Then `make next`, which proposes `/run <ID>`.
