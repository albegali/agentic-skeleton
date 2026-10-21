# Step review — independent review (review mode)

**Command**: `/review-story <ID>` · **Tier**: balanced · **Session**: fresh

**Context**: `python3 tools/context.py review {ID}` — Brief, Spec, RUN, the ADR/FR/NFR sections the Spec cites, the package `AGENTS.md` files, `make check`, and the size of the story diff with its `--stat`. Then the diff only, never the whole code base: in one go when the budget says so, otherwise file by file (`git diff main...HEAD -- <path>`).

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
