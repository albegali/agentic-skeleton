# Git rules (single source)

Every other file links here instead of restating the rule.

## Branch
- One branch per story: `<id-lowercase>-<slug>` (e.g. `pr0101-login`), created from an up-to-date `main` before the first change of the RUN. Spikes use `spike/<id-lowercase>` and are never merged.
- Commit and push only at the end of `/persist` and `/close`, or when the user asks. The review's RUN §11 entry is committed by the next of the two.
- Attribution: `project.toml` `[git] trailers`. `none` (default) → no `Co-Authored-By:` trailer and no "Generated with …" line in commit messages or PR bodies, even if the tool adds them by default; `tool` → keep the tool's default lines.

## `/persist` — the story's PR, nothing merged
1. Commit on the story branch and push it.
2. Open a pull request to `main` if none is open (`gh pr create --fill`); no remote → skip 2-4 and write `CI: none (no remote)` in RUN §8.
3. Wait for the required checks: `gh pr checks <pr> --required --watch` (no required checks configured: `gh pr checks <pr> --watch`).
4. Record the result in RUN §8 (`CI: green|red — <PR URL>`) and RUN References `Branch` / `PR`, commit and push it.
CI red → RUN stays `Persisted`, report; the fix goes through `/run <ID> tuning: …`.

## `/close` — merge this story's PR only
1. Commit the closure (RUN `Closed`, Brief closed) on the story branch and push it.
2. `gh pr checks <pr> --required --watch`, then `gh pr merge <pr> --<method> --delete-branch` with `<method>` from `project.toml` `[git] merge` (default `squash`). Never `--admin`: a protection rule that blocks the merge is reported, not bypassed.
3. `git switch main && git pull --ff-only`, delete the local story branch, then re-verify `main`: `make check` and `make test`.
4. List the other open branches (`git branch -a --no-merged main`) and report them. **Never merge or delete a branch that is not this story's.**
No remote: `git switch main && git merge --squash <branch> && git commit -m "<ID>: <title>"`, then step 3 without the pull.
The merge commit is not written back into the RUN (`main` may be protected): the RUN's `PR` is the record (`gh pr view <PR> --json mergeCommit`; no remote: `git log --grep <ID> main`).

Stop and report, merging nothing, on: CI red, a merge conflict, a protection rule that blocks the merge, or a red `main` after the merge (the RUN stays `Closed`; the fix is a new bug story).

## Recommended repository settings
Protect `main`: require a pull request, require the CI status checks to pass, optionally require one approving review (then the human approves the PR before `/close`). Enable "Automatically delete head branches".
