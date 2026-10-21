# Step tuning — human verification, tuning, persistence

The RUN is in `Tuning`: every plan step is done and the agent has stopped, or the review requested changes (RUN §11).

1. Verify the result against the AC yourself: `make run` (or `python tools/launch.py`, or the editor task **Run app**) starts the app and opens it in the browser.
2. For fixes **within scope** (including the review findings in RUN §11), in the same session: `/run {ID} tuning: <what to fix>` (L/XL: `/run-deep`). Use the command, not free text, so the pinned tier runs it.
3. A change of scope is not tuning: `/spec {ID} <change>` (Spec back to Draft, RUN Blocked until you approve the change).
4. When satisfied: `/persist {ID}` — persistence and reconciliation, RUN → Persisted, story PR opened and CI recorded; nothing merged.
5. Then, in fresh sessions: `/review-story {ID}` (RUN → Reviewed, or back to Tuning with findings) and `/close {ID}` (RUN → Closed, the story's PR merged). See `delivery/guide/git.md`.
