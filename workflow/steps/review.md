# Step review — independent review (review mode)

**Command**: `/review-story <ID>` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py review {ID}` (runs `make check`), then the story's diff only: `git diff main...HEAD` on the story branch (or `gh pr diff <pr>`, PR URL in RUN §8) — not the whole code base.

**Prompt**
```
Review mode for {ID} (Reviewer role, delivery/AGENT_GUIDE.md §8). The RUN is Persisted. Check on the diff:
- Brief, Spec and RUN aligned;
- every AC covered by tests;
- scope creep;
- deviations documented;
- persistence done;
- CI green on the story's PR (RUN §8 `CI:`);
- no secrets or personal data in logs;
- package AGENTS.md rules and the cited ADRs/NFRs respected.

Do not modify code or any other artifact. Append a `### Review #n` entry to RUN §11 (Date, Reviewer = review agent,
Outcome, Findings as `file:line → problem → request`, max 20 lines), then set the RUN status:
- nothing blocking → Outcome `ok-to-close`, RUN `Reviewed`;
- otherwise → Outcome `changes-requested`, RUN `Tuning`.
Chat: the outcome and the next command — `/close {ID}`, or `/run {ID} tuning: <findings>` then `/persist {ID}`.
```
