# Step execute — execution (developer mode)

**Command**: `/run <ID>` (resumes where it stopped) · **Tier**: balanced · **Session**: the strategy's session if under ~50% of the context; otherwise a fresh one with `/run <ID>`: the RUN is the memory

**Token rules**:
- implement one plan step at a time;
- run only the tests relevant to the step; the full suite once, at the end;
- never paste full test output in chat: outcome and failures only;
- update RUN §3-4 append-only and tersely.

**Status** (RUN `## Status`):
- before the first code or test change: `Executing`, fill `Started at`;
- every plan step done and §4 filled (pass or fail): `Tuning`, then stop: the human verifies;
- stop condition (`delivery/AGENT_GUIDE.md` §9) or a deviation with `Scope impact: Requires approval`: add a `### Deviation #n` entry to §6 (what, why, plan impact), set `Blocked`, stop and print `/run {ID} approve-deviation <n>`.

**Prompt (resume)**
```
Developer mode, {ID}. Resume execution from delivery/30-runs/RUN-{ID}.md: read the approved strategy and the last recorded step, then continue within the Spec scope. Set Executing at the first change, Tuning when every plan step is done, Blocked (with a §6 deviation) on a stop condition.
```
