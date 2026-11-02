# SPIKE-43 - Offload bulk reads and boilerplate to a cheap worker model

## References
- Story ID: #43 (skeleton issue; depends on #42, merged in 1.19.0)
- Time-box: half a day of agent work
- Branch (throwaway, never merged): `spike/43-offload-worker` (scripts in `spike/43/`)
- Started at (datetime): 2026-11-02 11:40
- Completed at (datetime): 2026-11-02 12:50

---

## Status
Accepted

Revision 2026-11-02: accepted by the owner in chat (`project-journal/decisions/2026-11-02-spike-43-offload-worker.md`).

---

# 1. Question

Spotify's shunt plugin reports ~90% fewer tokens by routing bulk file reads and boilerplate generation to a cheap worker
model. Does a `tools/offload.py` (worker tier in `models.toml`, off by default) pay off in this workflow, and can it be
done vendor-neutrally? Decision unblocked: build it (go), build a smaller variant, or drop it (no-go).

---

# 2. Approach

1. **Where the main agent's cost goes** (`spike/43/carry.py`): replayed 53 real Claude Code sessions (41 agentic-portal,
   built through the full workflow; 12 skeleton maintenance), 1,879 main-context API calls. Every tool result is
   classified (full Read of a file > 400 lines, small Read, `cat`/`sed` reads, `context.py`, other Bash, subagent) and
   charged its first send (cache write ×1.25) plus a cache read (×0.1) on every later call until `/clear`, compaction or
   a context drop; output ×5. Shares are of the whole weighted session cost.
2. **Bulk-read bench** (`spike/43/bench.py`, `score.py`): six skeleton tools (2,709 lines, ~52k tokens, numbered lines in
   `<file>` tags, as shunt sends them), three onboarding-style questions with ground truth from AST/regex (29 items:
   functions that run git, `project.toml` keys with defaults, `SHELL_DENY` reasons). Strict score: item named and exact
   line number. Workers: headless `claude -p` (no tools, no settings, custom system prompt) on Haiku 4.5 and Haiku 5.5,
   with and without thinking; local `ollama` `qwen2.5-coder:7b`.
3. Not tested: boilerplate generation (`code-write`); Codex as worker (not installed, no API keys on this machine).

---

# 3. Findings

**F1 — Large reads are ~1% of the cost of this workflow.** The context budgets (`context.py`, section extraction) already
do what shunt does: of 345 full file reads (Read or `cat`/`sed`/`head`/`tail`) in the main context, 14 were over 400 lines.

| Tool results (cost share) | agentic-portal (41 sessions) | skeleton (12) |
|---|---|---|
| Full reads > 400 lines (Read + `cat`) | **0.8%** | **1.5%** |
| Small reads (Read + `cat`/`sed` ≤ 400 lines) | 4.4% | 7.2% |
| `context.py` output | 0.5% | 0.7% |
| Other Bash output (tests, git, make) | 6.2% | 9.0% |

At a 200-line threshold, large reads are still only 3.1% (portal). Where the cost actually is (portal): cache reads 50%,
cache writes 31% (almost all incremental new content: model switches and >5 min gaps are 1.3%), output 18%; the fixed
prefix (system prompt, tool schemas, instructions) re-read on every call is ~23%. Median peak context per session 96k,
max 342k. Cost by command: `/run` 33%, unlabelled follow-ups 23%, `/persist` 11%, `/brief` 9%.
**Upper bound of an offload of large reads: ~1–3% of total cost.**

**F2 — The worker is accurate when configured right, and the token saving per read matches Spotify's.**

| Worker (headless) | Recall | Exact line | Latency / question | Output tokens |
|---|---|---|---|---|
| Haiku 4.5 (`haiku` alias), thinking on | 25/29 | 23/29 | 21–50 s | 2.4–6.1k (mostly thinking) |
| Haiku 4.5, thinking off (q1 only) | 6/8 | 4/8 | 2 s | 107 |
| **Haiku 5.5, thinking off** | **29/29** | **29/29** | **6–16 s** | 1.2–3.5k |
| qwen2.5-coder:7b (local, M-series laptop) | ~11/29 (corpus truncated at its 32k context) | 0/29 | 246–262 s | 74–246 |

On q1 Haiku 5.5 was stricter than the AST ground truth: it listed the two functions that reach git only through a nested
helper as indirect callers, with the right lines. The answer replaces ~52k corpus tokens with 0.1–3.5k: a **93–99% token saving on that read**. Counting fails: Haiku 5.5
and Sonnet 5.5 both answered "12 rules" for `SHELL_DENY` (11), so worker answers are leads, not facts — the main agent
must still read the exact section before editing (as Spotify also found).

**F3 — Money per read: the worker wins only when the main agent would otherwise carry the whole corpus.** Relative prices
derived from the logged per-model costs (newer client): Haiku ≈ 1/6.5 of Sonnet, ≈ 1/11 of Opus per weighted token
(verify against the price list). A main-agent full read costs T × (1.25 + 0.1 × k) for k later calls (k ≈ 15 on
average here, ≈ 2.75 T); a worker call costs about T × 2 at Haiku price (1-hour cache write, see F4) plus the side call.
That is ~80% less than Sonnet reading it and ~90% less than Opus — for that read, i.e. **≤ 1–3% of a session** (F1).

**F4 — Headless `claude -p` is a poor transport for a worker.**
- Every call also sends the whole prompt to Haiku 4.5 in a hidden side call (52k input, 13 output, ~$0.05).
- The prompt is written with a 1-hour cache TTL (2× write) that a one-shot call never reuses.
- The `haiku` alias resolved to Haiku 4.5, not 5.5; thinking is on unless `MAX_THINKING_TOKENS=0` (6× latency, 40× output).
- The CLI on `PATH` (2.1.181) lagged the IDE's: it rejects Opus 5.5 and reports a fallback price for 5.5 models
  (Haiku 5.5 and Sonnet 5.5 cost the same $0.383 for the same tokens), so its `total_cost_usd` cannot compare models.
- `--bare` skips subscription login: a clean call needs an API key.

**F5 — Vendor neutrality has a high fixed cost.** A worker needs a backend and credentials per vendor (Anthropic API key or
CLI, `codex exec` or OpenAI key, a local model); Copilot and Cursor expose none. The skeleton's tiers today need no
credentials at all. Claude Code already has the native equivalent: a subagent pinned to the fast tier (`.claude/agents/*.md`
`model:`), which can search instead of receiving a pre-concatenated corpus, and whose transcript `usage.py` can count.

**F6 — Boilerplate generation (`code-write`) was not measured.** In this workflow code is written inside an approved RUN,
task by task, with tuning: the "write straight to disk, never seen by the main agent" pattern conflicts with the RUN's
review of every change, and Spotify could not quantify it either.

---

# 4. Recommendation

**No-go for `tools/offload.py`** in the skeleton. The saving it targets is ~1–3% of the cost of this workflow (F1), for a
new credential-bearing dependency per vendor (F5), a fragile transport (F4) and answers that still need verification (F2).
The 90% is real per read, but the context budgets already removed most of those reads.

Do instead, cheaper and aimed at where the cost is:
1. **Reader subagent on the fast tier** (Claude Code; Codex where subagents exist): `.claude/agents/reader.md` rendered by
   `render_agents.py` with the `fast` model, read-only tools, the bulk-reader output rules (names + file:line, no prose).
   The #42 block message points to it for questions that span many files. `/onboard` and `/analysis` of an existing
   codebase are the only read-heavy steps: re-measure there.
2. **Attack the real cost centres** (F1): small `cat`/`sed` reads (4–7%) and other Bash output (6–9%) — e.g. quieter
   `make test-tools`/`make check` output on success; the fixed prefix (~23%) — keep AGENTS.md/CLAUDE.md and skill
   listings short; long `/run` sessions (33%) and unlabelled follow-ups (23%).
3. **Per-read accounting in `usage.py`**: add `carry.py`'s classification (cost share by tool-result kind) so `/weekly` shows
   where context cost goes, and so this decision can be revisited with brownfield data.

---

# 5. Follow-up Stories

Proposed as skeleton issues (the skeleton has no `stories.toml`):

- title: Reader subagent on the fast tier for multi-file questions (Claude Code), pointed to by the large-read guard · type: feature · size: S · deps: #42
- title: `usage.py`: context cost share by tool-result kind (reads, context.py, Bash, subagents) for `/weekly` · type: feature · size: S · deps: —
- title: Cut tool-output and prefix tokens: quiet success output of `make check`/`make test-tools`, size budget for AGENTS.md/CLAUDE.md and command listings · type: chore · size: M · deps: usage.py cost share
- title: Re-measure offload on a brownfield `/onboard` (go/no-go revisited with data) · type: spike · size: S · deps: reader subagent

---

# 6. Open Questions

- Brownfield `/onboard` and `/analysis` were not in the logs (agentic-portal is greenfield): the one place F1 may not hold.
- Exact per-model prices: F3 uses ratios derived from logged costs; verify against the vendor price list.
- Does a Haiku-5.5 reader subagent keep F2's accuracy when it searches the repository itself instead of receiving the files?

---

## Gates

> Changes requested at a human gate (`gates.py request-changes`), one line each: `YYYY-MM-DD — changes requested by <owner>: <comment>`. Leave empty otherwise.
