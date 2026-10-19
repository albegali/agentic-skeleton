# Step review — independent review (review mode)

**Command**: `/review-story <ID>` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py review {ID}` (runs `make check`), then `git diff` of the story only — not the whole code base.

**Prompt**
```
Review mode for {ID} (Reviewer role, delivery/AGENT_GUIDE.md §8). Check on the diff:
- Brief, Spec and RUN aligned;
- every AC covered by tests;
- scope creep;
- deviations documented;
- persistence done;
- no secrets or personal data in logs;
- package AGENTS.md rules and the cited ADRs/NFRs respected.

Do not modify code. Output: bullet list file:line → problem → request (max 20 lines). If all is fine, write "OK to close".
```
