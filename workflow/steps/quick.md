# Step quick — quick track: Brief, Spec and RUN strategy, one approval (developer mode)

**Command**: `/quick <ID>` · **Tier**: balanced · **Session**: fresh, then stays open for approval and execution

For stories with `type = "bug" | "hotfix" | "chore"` or `size = "XS"` (`delivery/guide/quick.md`). Hotfixes are proposed by `make next` ahead of the sprint order, even when not in `PLAN.md`.

**Context**: `python3 tools/context.py quick {ID}` — quick guide, Brief/Spec/RUN templates, the Story, the package `AGENTS.md` files; then only the code files involved, found with grep/glob.

**Prompt**
```
Developer mode, quick track for {ID}. Follow delivery/guide/quick.md within the printed budget.
0. Be on the story branch (`make claim` or create it, delivery/guide/git.md).
1. Brief in delivery/10-briefs/ (Type from the story; for bug/hotfix §3 Impact is required).
2. Spec in delivery/20-specs/, short: bug/hotfix → root cause (or hypothesis) in §1, AC1 is a regression test that fails before the fix;
   chore → the preset regression gates of the guide in §7. Status Draft. `Requirements:` and AC `→ test:` as in the Spec template. `make backlog` (Spec index).
3. RUN in delivery/30-runs/ with §1 Execution Strategy only. No code.
Chat: root cause / change, AC count, plan in at most 6 lines; then stop: one approval covers Spec and strategy.
```

**Gate**: `/run {ID} approve` (Spec → In Progress, strategy approved, execution starts), or `/spec {ID} <changes>` / `/run {ID} revise: <what>`.
