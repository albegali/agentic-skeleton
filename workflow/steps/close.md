# Step close — closure and merge of one story (developer mode)

**Command**: `/close <ID>` · **Tier**: fast · **Session**: fresh

**Context**: `python3 tools/context.py close {ID}`: `delivery/guide/git.md`, the RUN, the Brief, the open branches.

**Prompt**
```
Developer mode, closure of {ID}. Preconditions: RUN status `Reviewed` and the latest RUN §11 review `ok-to-close`;
otherwise stop and give the command that is missing (`make next {ID}`).
1. RUN: `Completed at` (now), status `Closed`. Brief: `Closed at`, `Derived Artifacts` (Spec, RUN, PR), status `Closed`.
2. `make check`: errors → stop and report.
3. Git: the `/close` part of `delivery/guide/git.md` — commit and push the closure, wait for the required checks, merge
   this story's PR only, update `main` locally, re-verify it (`make check`, `make test`).
   Never merge or delete another branch; never bypass branch protection.
Chat: outcome in 3 lines (PR merged, main green or not) and the other open branches, listed, untouched.
```

Stop and report without merging on: CI red, merge conflict, a protection rule that blocks the merge (e.g. a required
human review: approve the PR, then `/close {ID}` again). `main` red after the merge: report it; the fix is a new bug story.
