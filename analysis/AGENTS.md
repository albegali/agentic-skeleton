# AGENTS.md — ANALYSIS

Analyst mode: backlog analysis, refinement preparation, `Analysis`, `Refined Story`, backlog consolidation. Follow `analysis/AGENT_GUIDE.md`.

- Never create `Brief`, `Spec`, `RUN`, never implement code.
- A Refined Story may feed developer mode only when the user explicitly asks for that transition.
- Write only inside `analysis/`; read `reference/` through `tools/context.py`. The only exceptions:
  - `backlog/stories.toml` (then `make backlog`): a story that arrives only in chat (`AGENT_GUIDE.md` §5.1), and backlog changes the owner decided in workshop minutes (`/refine`);
  - ADRs and `reference/architecture/architecture.md`: only to apply an owner decision recorded in workshop minutes (`/refine`), with a revision line citing them.
  Anything else outside `analysis/` (an undecided ADR change, requirements, the plan) goes back to product mode as an open point.
