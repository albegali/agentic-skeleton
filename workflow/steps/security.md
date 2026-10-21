# Step security — security review of a sensitive story (review mode)

**Command**: `/security-review <ID>` · **Tier**: balanced · **Session**: fresh

**When**: `make next` routes a `Persisted` RUN here, before `/review-story`, when the story is security-sensitive: `security = true` in `backlog/stories.toml`, a cited NFR under Security or Privacy, or a security keyword in the Spec (auth, tokens, passwords, secrets, permissions, personal data…). `security = false` opts out.

**Context**: `python3 tools/context.py security {ID}` — Spec, RUN, the cited ADR/NFR sections, package `AGENTS.md` files, the secret scan of the story's files, the size and `--stat` of the story diff. Then the diff (file by file when the budget says so), never the whole code base.

**Prompt**
```
Review mode, security review of {ID}. On the diff check:
- authentication and authorisation on every new entry point; least privilege;
- input validation and output encoding (injection, XSS, path traversal, deserialisation);
- secrets: none in code, config, tests, logs or artifacts (the scan above; also read what it cannot see);
- personal data: collected only as the Spec says, protected in storage and transit, not logged;
- dependencies added: known vulnerabilities, licence, maintenance;
- the cited Security/Privacy NFRs and ADRs met, with the verification they name.
Do not modify code or any other artifact. Write RUN §8 `### Security review` (replace it if present): Date, Reviewer = security review agent,
Outcome `ok` or `changes-requested`, Findings as `file:line → risk → request` (max 20 lines).
- ok → RUN stays Persisted; next `/review-story {ID}`.
- changes-requested → RUN `Tuning`; next `/run {ID} tuning: <findings>`, then `/persist {ID}`.
Chat: the outcome and the next command.
```
