# Step tuning — human verification, tuning, persistence

1. Verify the result against the AC yourself: `make run` (or `python tools/launch.py`, or the editor task **Run app**) starts the app and opens it in the browser.
2. For fixes **within scope**, in the same session: `/run {ID} tuning: <what to fix>`.
3. When satisfied: `/persist {ID}` — persistence and reconciliation, RUN to Persisted then Closed, `make check`.
4. For an independent review before closure: `/review-story {ID}` in a fresh session.
