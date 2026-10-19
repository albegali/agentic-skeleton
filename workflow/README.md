# Workflow playbook

How to move the project forward with agents while spending as few tokens as possible. Rules for agents are in `AGENTS.md` §5; this page is for the humans driving the loop.

## The loop

```
make next  (or /next on the fast tier)  → tells: step, IDs, command, tier → model per tool
   ├─ agent step  → fresh session, run the command (its model is pinned or recommended)
   └─ human gate  → you act (approve, workshop, review), then make next again
```

`tools/next_step.py` reads only files: `project.toml`, the status of inception artifacts, `backlog/stories.toml`, the sprints of `PLAN.md`, and the presence/status of Analysis, Refined Story, Brief, Spec, RUN. No LLM reads the repository to find out where we are.

Full step table (generated): [`STEPS.md`](STEPS.md). Step procedures: [`steps/`](steps/). Source of truth: [`workflow.toml`](workflow.toml).

## Phases

| Phase | Steps | Human gates |
|---|---|---|
| Inception | `/kickoff` → `/requirements` → `/mockup` (optional) → `/architecture` → `/backlog` → `/release-plan` | approve each artifact (`status: approved`) |
| Inception, existing codebase | `make adopt TARGET=…` (from the skeleton) → `/onboard` → `/backlog` → `/release-plan` | approve the onboarding artifacts, then backlog and plan |
| Analysis | `/analysis` → workshop → `/refine` | workshop + minutes |
| Delivery | `/brief` → Spec review → `/run` (strategy) → `/run <ID> approve` → execution → `/run <ID> tuning: …` → `/persist` → `/review-story` | Spec `Ready`, strategy approval, tuning acceptance |
| Journal | `/weekly` (fast tier) | — |

Order in delivery: analysis one sprint ahead; development one story at a time, in `PLAN.md` order, with dependencies closed. While you are on a human gate, `make next` proposes analysis work ahead.

## Choosing models

- Steps declare a **tier**; `models.toml` maps tier → model per vendor and tool. `/choose-models` walks you through it, `make agents` regenerates the adapters.
- Defaults: `fast` for `/next`, `/weekly`, `/choose-models`; `balanced` for everything else; `deep` for `/architecture` and `/onboard`. Ask for deep explicitly on L/XL stories (`/run <ID>` + "use the deep tier").
- Claude Code and Copilot pin the model per command; Codex and Cursor print the recommended model at the top of the command: switch to it before running.

## Token rules (summary of AGENTS.md §5)

1. Fresh session per step (except the `/run` chain of one story).
2. Read only what `tools/context.py` prints; long docs by section.
3. Scripts before the LLM (`make next`, `make check`, `make backlog`).
4. Right tier; deep only when needed.
5. No subagents by default.
6. Short chat output; the content lives in files.
7. No re-reading of what was just written.
8. Resume from `make next`.
