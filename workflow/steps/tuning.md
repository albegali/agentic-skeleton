# Step tuning — human verification, tuning, persistence

The RUN is in `Tuning`: every plan step is done and the agent has stopped.

1. Verify the result against the AC yourself: `make run` (or `python tools/launch.py`, or the editor task **Run app**) starts the app and opens it in the browser.
2. For fixes **within scope**, in the same session: `/run {ID} tuning: <what to fix>`.
3. A change of scope is not tuning: `/spec {ID} <change>` (Spec back to Draft, RUN Blocked until you approve the change).
4. When satisfied: `/persist {ID}` — persistence and reconciliation, RUN to Persisted then Closed, `make check`.
5. For an independent review before closure: `/review-story {ID}` in a fresh session.
