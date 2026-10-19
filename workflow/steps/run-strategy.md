# Step run-strategy — execution strategy (developer mode)

**Command**: `/run <ID>` · **Tier**: balanced (deep for L/XL stories or new architecture: say so in the prompt) · **Session**: fresh, then stays open for approval and execution

**Context**: `python3 tools/context.py run-strategy {ID}` — the Spec, the RUN template, the cited ADRs, the package `AGENTS.md` files; then only the code files involved, found with grep/glob, never a full repository exploration.

**Prompt**
```
Developer mode, {ID}. Create delivery/30-runs/RUN-{ID}.md and fill only section 1, Execution Strategy, within the printed budget.
Plan in small verifiable steps, assumptions, risks, package rules read.
Do not write code. Chat: the plan in at most 8 lines, then stop and wait for approval.
```
