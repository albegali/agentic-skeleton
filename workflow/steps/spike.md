# Step spike — time-boxed investigation (developer mode)

**Command**: `/spike <ID> [time-box]` · **Tier**: balanced · **Session**: fresh, one spike

A spike answers a question (feasibility, choice between options, estimate); it delivers knowledge, not product. No Brief, Spec or RUN.

**Context**: `python3 tools/context.py spike {ID}` — the spike template, project summary, the Story and its cited references; then only the code or docs the question needs.

**Prompt**
```
Developer mode, spike {ID}. Time-box: the argument, else the story's notes, else half a day of agent work.
Write delivery/40-spikes/SPIKE-{ID}-<slug>.md from delivery/templates/SPIKE-template.md: question, approach, findings with evidence,
recommendation, follow-up stories (proposed `[[story]]` entries, not yet in stories.toml).
Throwaway code only on a branch `spike/<id-lowercase>`: never merged, named in the note. Stop at the time-box with what you have.
Status Draft. Chat: answer and recommendation in at most 6 lines.
```
