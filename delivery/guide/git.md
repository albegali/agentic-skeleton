# Git rules (single source)

Every other file links here instead of restating the rule.

## Trunk-based development (mandatory)
`main` is the trunk and the only long-lived branch. The framework never creates or accepts anything else.
- **Short-lived story branches**: one story = one branch from an up-to-date `main`, merged back within days. Stories are sliced small enough for that (L/XL are split in the backlog, not kept open); unfinished behaviour hides behind a feature flag, not behind a long branch.
- **No long-lived branches**: no `release/*`, `develop`, `staging`, or integration branches, and no merging of story branches into each other or into anything but `main`. A release is a **tag on `main`** (`git tag vX.Y.Z`), never a branch; a release plan (`PLAN.md`) groups stories, not branches.
- **Stay on the trunk**: before `/persist` (and again before `/close` if `main` moved) the story branch is brought up to date with `git fetch` and `git rebase origin/main` (branch not pushed yet) or `git merge origin/main` (already pushed: agents never force-push); the squash merge keeps `main` linear either way. Conflicts → stop and report. A branch with unmerged commits older than 3 days is reported by `/next` and `/close` as stale: finish it, split the story, or drop it.
- **Sequential merges**: the PR is squash-merged into `main` (or rebase), keeping a linear history; `/close` of story B waits for the `/close` of story A when they touch the same files. Parallel stories (worktrees) must not depend on each other's unmerged code: if B needs A, B starts after A is merged.
- **Hotfix**: a normal short branch from `main`, merged first; a fix for a released version is a new tag on `main`, not a maintenance branch.
- **`main` is always green**: a red `main` is fixed before any new story is merged.

## Branch
- One branch per story: `<id-lowercase>-<slug>` (e.g. `pr0101-login`), created from an up-to-date `main` at `/brief` (or `/quick`), so the Brief, Spec and RUN live on it. In a team, `make claim ID=<ID> [WORKTREE=1]` creates it, records the claim and pushes it: a pushed story branch is a claim (`make next --me <name>` skips others' stories). Spikes use `spike/<id-lowercase>` and are never merged.
- Parallel stories: one worktree per story (`make claim … WORKTREE=1` → `../<repo>-<id>`), one agent session per worktree.

## Commit points
- Inception and analysis steps commit their artifacts at the end of the step, on their own branch with a PR (`inception/<step>`, `analysis/<ids>`), or on `main` when it is not protected and you work alone. They never ride along in a story branch.
- Brief and Spec: committed on the story branch at the end of `/brief` (or `/quick`).
- Commit and push only at the end of `/persist` and `/close`, or when the user asks. One exception: the strategy approval is committed alone (RUN + Spec, `Approved-by`/`Approved-at` trailers) before any code — by `make approve` or by `/run <ID> approve`; CI (`check_workflow.py --git`) fails a branch whose code precedes it. The review's RUN §11 entry is committed by the next of the two.
- Attribution: `project.toml` `[git] trailers`. `none` (default) → no `Co-Authored-By:` trailer and no "Generated with …" line in commit messages or PR bodies, even if the tool adds them by default; `agent` → no co-author line, but an `Agent: <tool>/<model>` trailer, so agent and human commits can be told apart; `tool` → keep the tool's default lines.

## `/persist` — the story's PR, nothing merged
1. Update the branch from `origin/main` (see Trunk-based development), commit on the story branch and push it.
2. Open a pull request to `main` if none is open (`gh pr create --fill`); no remote → skip 2-4 and write `CI: none (no remote)` in RUN §8.
3. Wait for the required checks: `gh pr checks <pr> --required --watch` (no required checks configured: `gh pr checks <pr> --watch`).
4. Record the result in RUN §8 (`CI: green|red — <PR URL>`) and RUN References `Branch` / `PR`, commit and push it.
CI red → RUN stays `Persisted`, report; the fix goes through `/run <ID> tuning: …`.

## `/close` — merge this story's PR only
1. If `main` moved since `/persist`, update the branch from `origin/main` again. Commit the closure (RUN `Closed`, Brief closed) on the story branch and push it.
2. `gh pr checks <pr> --required --watch`, then `gh pr merge <pr> --<method> --delete-branch` with `<method>` from `project.toml` `[git] merge` (default `squash`). Never `--admin`: a protection rule that blocks the merge is reported, not bypassed.
3. `git switch main && git pull --ff-only`, delete the local story branch, then re-verify `main`: `make check` and `make test`.
4. List the other open branches (`git branch -a --no-merged main`) and report them. **Never merge or delete a branch that is not this story's.**
No remote: `git switch main && git merge --squash <branch> && git commit -m "<ID>: <title>"`, then step 3 without the pull.
The merge commit is not written back into the RUN (`main` may be protected): the RUN's `PR` is the record (`gh pr view <PR> --json mergeCommit`; no remote: `git log --grep <ID> main`).

Stop and report, merging nothing, on: CI red, a merge conflict, a protection rule that blocks the merge, or a red `main` after the merge (the RUN stays `Closed`; the fix is a new bug story).

## Recommended repository settings
Protect `main`: require a pull request, require the CI status checks to pass, optionally require one approving review (then the human approves the PR before `/close`). Enable "Automatically delete head branches".
