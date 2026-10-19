# Step execute — execution (developer mode)

**Command**: `/run <ID>` (resumes where it stopped) · **Tier**: balanced · **Session**: the strategy's session if under ~50% of the context; otherwise a fresh one with `/run <ID>`: the RUN is the memory

**Token rules**:
- implement one plan step at a time;
- run only the tests relevant to the step; the full suite once, at the end;
- never paste full test output in chat: outcome and failures only;
- update RUN §3-4 append-only and tersely.

**Prompt (resume)**
```
Developer mode, {ID}. Resume execution from delivery/30-runs/RUN-{ID}.md: read the approved strategy and the last recorded step, then continue within the Spec scope. Stop on a stop condition or deviation.
```
