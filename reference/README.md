# reference/

Shared knowledge, read by every mode **through `tools/context.py`** (never browsed in full).

| Folder | Content | Written by |
|---|---|---|
| `project-summary.md` | ≤ 60-line context every step reads | `/kickoff` |
| `product/` | `vision.md`, `functional-requirements.md`, `non-functional-requirements.md`, `mockup-reference.md` | `/kickoff`, `/requirements`, `/mockup` |
| `mockup/` | single-file clickable HTML mockup | `/mockup` |
| `architecture/` | `architecture.md`, `ADR-NNN-*.md`, data model, integrations | `/architecture`, then `/persist` keeps them current |
| `domain/` | `glossary.md`, domain contracts | all modes |
| `documentation/` | `stakeholders.md`, other shared docs | `/kickoff`, humans |
| `backlog/` | generated epic pages (`make backlog`) | tools |
