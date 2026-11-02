# Token economics

Where an agent's tokens go in this workflow, what the skeleton does about each part, and what is left to you. Numbers
below were measured on the maintainers' own projects (Claude Code logs); they describe those sessions, not yours. Run
`make usage` (or `/weekly`) to get your own.

## 1. Where tokens go

Every API call of an agent session re-sends everything in its context. Most of it is served from the prompt cache, at a
fraction of the input price, but it is paid again on every call until `/clear`, compaction or a context drop.

| Part | What it is | Grows with |
|---|---|---|
| Fixed prefix | tool system prompt, tool schemas (built-in and MCP), skill/plugin listings, `AGENTS.md`/`CLAUDE.md`, command descriptions | your tool setup; re-sent on every call |
| Carried context | earlier turns and tool results still in the session | session length × size of what was read |
| Tool output | file reads, `context.py`, Bash (tests, git, make), subagent results | what the agent reads; charged once when sent, then on every later call |
| Output tokens | the model's answers, edits and thinking | the work itself; priced highest per token |

Measured shares of the weighted session cost (cache write ×1.25, cache read ×0.1, output ×5 of the input price):

| Share | agentic-portal | skeleton | Source |
|---|---|---|---|
| Cache reads (carried context, incl. the prefix) | 50% | — | spike #43, 41 sessions |
| Cache writes (new content entering context) | 31% | — | spike #43, 41 sessions |
| Output | 18% | — | spike #43, 41 sessions |
| Fixed prefix (re-read on every call) | ~23% | — | spike #43, 41 sessions |
| Full reads of files > 400 lines | 0.8% | 1.5% | spike #43, 41 + 12 sessions |
| Small reads (≤ 400 lines) | 4.4% | 7.2% | spike #43 |
| `context.py` output | 0.5% | 0.7% | spike #43 |
| Other Bash output (tests, git, make) | 6.2% | 9.0% | spike #43 |

The first four rows are billing categories; the fixed prefix is part of the cache reads, not added to them. The spike
replayed 53 Claude Code sessions (1,879 main-context calls) on 2026-11-02: 41 from
agentic-portal (a greenfield project built through this workflow), 12 of skeleton
maintenance. Findings: [SPIKE-43](https://github.com/albegali/agentic-skeleton/blob/spike/43-offload-worker/delivery/40-spikes/SPIKE-43-offload-worker.md).

`tools/usage.py` (1.20.0) now computes the same split. Run on 2026-11-02 over the last 30 days (2026-10-03 → 2026-11-02):

| `make usage DAYS=30` | agentic-portal (41 sessions, 82 commands) | skeleton (13 sessions) |
|---|---|---|
| Fixed prefix | 22.8% | 20.4% |
| Output | 18.4% | 19.3% |
| Full reads > 400 lines | 0.8% | 1.3% |
| Small reads | 5.5% | 7.8% |
| `context.py` output | 0.5% | 0.4% |
| Other Bash output | 5.1% | 7.9% |

**The prefix is mostly not the repository's.** On the spike sessions the first call carried a median of ~50k tokens;
the skeleton's own always-loaded files (`AGENTS.md`, `CLAUDE.md`, command and agent descriptions) are ~2.4k of them,
about 5% ([#54](https://github.com/albegali/agentic-skeleton/issues/54)). The rest is the tool's system prompt and the
schemas and listings of your user-level MCP servers, skills and plugins.

Other measured facts (spike #43, agentic-portal): median peak context per session 96k tokens, max 342k; cost by command
`/run` 33%, unlabelled follow-ups 23%, `/persist` 11%, `/brief` 9%.

## 2. What the skeleton does

**Enforced** = a hook, `make check` or CI stops the agent or warns; **advisory** = a rule the agent reads. Hooks run in
Claude Code only. Full map of the harness: [workflow/README.md § Harness map](../workflow/README.md#harness-map).

| Lever | Mechanism | Kind | File |
|---|---|---|---|
| Scripts before the LLM | state, naming, consistency and backlog views come from scripts, not from an agent reading files | advisory (rule); the scripts are deterministic | [`tools/next_step.py`](../tools/next_step.py), [`tools/check_workflow.py`](../tools/check_workflow.py), [`AGENTS.md`](../AGENTS.md) §5.3 |
| Context budgets | each step declares what to read; `context.py` prints it, with requirement and architecture **sections** instead of whole files, and a token estimate | advisory | [`workflow/workflow.toml`](../workflow/workflow.toml), [`tools/context.py`](../tools/context.py) |
| Fresh session per step | `/clear` between steps (except the `/run` chain of one story); state lives in files, so nothing is lost | advisory | [`AGENTS.md`](../AGENTS.md) §5.1 |
| Model tiers | steps declare `fast` / `balanced` / `deep`; `models.toml` maps tier → model per vendor; Claude Code and Copilot pin the model per command | pinned per command (Claude Code, Copilot); advisory elsewhere | [`models.toml`](../models.toml), [`AGENTS.md`](../AGENTS.md) §5.4 |
| Large-read guard (1.19.0) | blocks a full read of a text file over `[context] max_read_lines` (default 400) and points to `context.py --index`, a section or an offset/limit read | enforced (hook) | [`tools/gate_guard.py`](../tools/gate_guard.py), `project.toml [context]` |
| `reader` subagent (1.21.0) | read-only (`Read`, `Grep`, `Glob`) on the fast tier for questions that span many files; returns `file:line` leads, so the main context does not load the files | tools enforced (Claude Code); when to use it advisory | [`.claude/agents/reader.md`](../.claude/agents/reader.md), [`AGENTS.md`](../AGENTS.md) §5.5 |
| Quiet output (1.22.0) | `make test-tools`, `make setup`, `make test` and `make lint` print a short summary on success, everything on failure (`V=1` for full) | built in (Makefile targets) | [`tools/quiet.py`](../tools/quiet.py) |
| Prefix budget (1.22.0) | `make check` reports the always-loaded prefix as `prefix ~N/B tokens` and warns above `[context] prefix_budget` (default 2500) | enforced (warning) | [`tools/check_workflow.py`](../tools/check_workflow.py), `project.toml [context]` |
| Measurement (1.19.0, 1.20.0) | `/weekly` reports peak context, tier mismatches, blocked large reads and the cost share by tool-result kind | measured | [`tools/usage.py`](../tools/usage.py) |

## 3. How to read `/weekly`

`/weekly` takes its model signals from `tools/usage.py` (`make usage DAYS=7` prints the same table). Claude Code and
Codex keep local logs; Copilot and Cursor do not, so they are not counted.

| Signal | Where | What to do when it is high |
|---|---|---|
| Context cost share | line "Context cost share": full reads, small and targeted reads, `context.py`, other Bash, subagent results, other, fixed prefix, output | full reads rising: the guard is off or bypassed; small reads or Bash high: read sections, keep command output quiet; fixed prefix high: trim your tool prefix (below) |
| Tier mismatch (✗) | a command run on a model of another tier than the step declares | answer gates with the command (`/run <ID> approve`), not free text, so the pinned model runs them |
| Peak context (⚠) | sessions over 80k tokens in one call | `/clear` and resume with the step's command |
| Large reads blocked | count of reads the guard stopped | expected to be low; many means the agent keeps trying whole files |
| Per tier | share of calls and cost per tier | deep-tier cost outside `/architecture`, `/onboard` and L/XL stories is worth a look |
| Fixed prefix vs repository (#54) | first-call context and the repository's share of it | when the first call is far above the repository's share, see [GUIDE.md](GUIDE.md), section *Trim your tool prefix* |

The fixed-prefix line comes with [#54](https://github.com/albegali/agentic-skeleton/issues/54); older versions only show
the fixed-prefix share in the cost-share line.

## 4. What you can do yourself

| Action | How |
|---|---|
| Trim your tool prefix | disable MCP servers, skills and plugins this project does not use: [GUIDE.md](GUIDE.md), section *Trim your tool prefix* (per tool) |
| Choose models per tier | `/choose-models`, or edit [`models.toml`](../models.toml) and run `make agents`; use `deep` only where the step asks for it |
| Start a fresh session per step | `/clear` (Claude Code) or a new chat, except within the `/run` chain of one story; resume from `make next` |
| Ask the `reader` for cross-file questions | "where is X used", `/onboard`, `/analysis` of existing code; verify its `file:line` leads before editing |
| Keep project instructions short | `AGENTS.md`, `CLAUDE.md` and package `AGENTS.md` are re-sent on every call; watch `prefix ~N/B` in `make check` |

More habits (small stories, no pasted logs, short project summary): [GUIDE.md §9](GUIDE.md#9-keeping-token-costs-low).

## 5. What we tried and dropped

**Offloading reads to an external worker model** (spike #43, accepted no-go). A `tools/offload.py` would send bulk file
reads to a cheap model and return only its answer. Per read it works: on a 52k-token corpus a Haiku 5.5 worker found
29/29 items with exact lines and returned 0.1–3.5k tokens, a 93–99% saving on that read. It was dropped because:

- large reads were ~1% of cost here (table above): the context budgets had already removed most of them, so the upper
  bound of the saving was ~1–3% of a session;
- each vendor needs its own backend and credentials, while the tiers today need none;
- headless `claude -p` as transport added a hidden side call, an unused 1-hour cache write and model-alias surprises;
- worker answers are leads (both Haiku 5.5 and Sonnet 5.5 miscounted a list), so the main agent still reads the section.

The `reader` subagent is the cheaper native equivalent. Where it might still pay off: brownfield `/onboard` and
`/analysis` of a large existing codebase, the read-heavy steps the greenfield logs did not cover. That is re-measured in
[#49](https://github.com/albegali/agentic-skeleton/issues/49).

## 6. Measured result

**Pending.** The before/after on real delivery with 1.19.0–1.23.0 (agentic-portal stories) is being measured in
[#56](https://github.com/albegali/agentic-skeleton/issues/56). No numbers until then.
