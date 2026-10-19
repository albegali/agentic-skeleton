# Story Template

Source user stories are **generated** by `make backlog` from `backlog/stories.toml`. Write one by hand only if a story arrives from outside the backlog, then add it to `stories.toml` too.

Naming: `analysis/10-stories/STORY_<ID>_<short_title>.md`

```md
# <User story title>

## User Story

As a <role>, I want <capability>, so that <benefit>.

## Description

- Epic: …
- Priority · Release · Size · Type
- Requirements: FR-xx, NFR-xx
- Depends on: …
- Notes: …
- Out of scope: …

## Acceptance Criteria

- Given …, when …, then ….
```
