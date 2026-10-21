# Quick track: bug, hotfix, chore, XS

For `type = "bug" | "hotfix" | "chore"` or `size = "XS"` in `backlog/stories.toml`. No Analysis or workshop (unless `skip_analysis = false`). Same artifacts as the standard flow — Brief, Spec, RUN — written in one session (`/quick <ID>`), with **one human approval** covering the Spec and the RUN strategy (`/run <ID> approve`). Execution, tuning, persistence, review and closure are unchanged.

## Bug and hotfix
- **Brief**: `Type: Bug` or `Hotfix`, urgency, §3 Impact (who is affected, what is broken), reproduction steps, external reference.
- **Spec**: §1 root cause (or hypothesis to confirm in step 1 of the RUN); **AC1 is a regression test** that fails before the fix and passes after; scope limited to the fix.
- **Hotfix**: production-impacting and urgent. `make next` proposes open hotfixes before anything in `PLAN.md`; a hotfix need not be planned. The RUN strategy may be short; the approval may be given in chat (recorded in RUN §2).
- **Persistence**: the corrected behaviour becomes accepted behaviour: Spec §11 and reference docs reconciled before closure.

## Chore (dependency, security, tooling upgrades)
Spec §7 starts from these preset regression gates (add, never drop without a reason):
- [ ] Full test suite green
- [ ] Build and lint pass
- [ ] App starts and the smoke path works (`make run`)
- [ ] No public interface change (API, CLI, formats), or the change is listed and approved
- [ ] Release notes / advisories of each upgraded package read; breaking changes listed in the RUN
- [ ] Lockfile diff limited to the intended packages

## XS stories
Any type with `size = "XS"`: one approval; otherwise the standard rules apply.

## Never on the quick track
New features beyond the story, unrelated refactors, scope expansion, unapproved breaking changes. If the fix needs more, record a deviation (RUN §6, Blocked) or move the story to the standard flow (`size` up, Spec back to Draft).
