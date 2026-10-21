# Step run-approval — strategy approval (human)

In the same session as the strategy (context already loaded):

```
/run {ID} approve        (L/XL stories: /run-deep {ID} approve)
```

Use the command, not a free-text "ok": the command runs on its pinned tier, and it is the only way the agent may record the approval (a hook blocks it otherwise). The agent commits the approval alone, before any code. Alternatively approve yourself with `make approve ID={ID} GATE=strategy`, then `/run {ID}`.

The command records the approval in RUN §2 (reviewer, date), sets the Spec to `In Progress` and starts execution. To ask for changes: `/run {ID} revise: <what>`. To stop: tick `Stopped` in RUN §2 (resume later with `revise:`), or drop the story with `/run {ID} cancel: <reason>`.
