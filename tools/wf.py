"""Shared helpers for the workflow tools (stdlib only, Python >= 3.11).

The repository root is the parent of tools/, or $WF_ROOT when set (used by the tests).
"""
from __future__ import annotations

import glob
import json
import os
import re
import tomllib
from functools import lru_cache

ROOT = os.path.abspath(os.environ.get("WF_ROOT") or os.path.join(os.path.dirname(__file__), ".."))
TIERS = ("fast", "balanced", "deep")
SCHEMA = 1  # version of the --json outputs (tools/README.md "JSON contract"); bump on breaking changes only


def path(*p: str) -> str:
    return os.path.join(ROOT, *p)


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT)


def read(p: str) -> str:
    with open(p if os.path.isabs(p) else path(p), encoding="utf-8") as f:
        return f.read()


def write(p: str, text: str) -> None:
    full = p if os.path.isabs(p) else path(p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def exists(p: str) -> bool:
    return os.path.exists(path(p))


def matches(pattern: str) -> list[str]:
    return sorted(glob.glob(path(pattern), recursive=True))


def one(pattern: str) -> str | None:
    m = matches(pattern)
    return m[0] if m else None


def dump_json(obj: dict) -> None:
    """Print a --json result: {"schema": SCHEMA, **obj}, compact (machines read it, agents read fewer tokens)."""
    print(json.dumps({"schema": SCHEMA, **obj}, ensure_ascii=False, separators=(",", ":")))


def approx_tokens(chars: int) -> int:
    """Rough token estimate (≈ 4 characters per token) for context budgets."""
    return (chars + 3) // 4


def load_toml(p: str) -> dict:
    if not exists(p):
        return {}
    with open(path(p), "rb") as f:
        return tomllib.load(f)


@lru_cache(maxsize=None)
def project() -> dict:
    return load_toml("project.toml")


@lru_cache(maxsize=None)
def models() -> dict:
    return load_toml("models.toml")


@lru_cache(maxsize=None)
def workflow() -> dict:
    return load_toml("workflow/workflow.toml")


@lru_cache(maxsize=None)
def backlog() -> dict:
    return load_toml("backlog/stories.toml")


def prefix() -> str:
    return project().get("project", {}).get("id_prefix", "PR")


def sources() -> list[str]:
    """Kickoff sources recorded in project.toml [inception] sources (paths relative to the root)."""
    return list(project().get("inception", {}).get("sources", []))


def design() -> str:
    """Existing design (prototype, HTML mockup, exported frames) recorded in project.toml [inception] design."""
    return project().get("inception", {}).get("design", "")


def id_rx() -> str:
    """Regex (no anchors) matching a story ID, e.g. PR0101."""
    return rf"{re.escape(prefix())}\d{{4}}"


def stories() -> dict[str, dict]:
    return {s["id"]: s for s in backlog().get("story", [])}


# ---------------------------------------------------------------- markdown status

def front(text: str, key: str) -> str | None:
    """Value of `key:` in the YAML frontmatter (or anywhere at line start), without trailing comment."""
    m = re.search(rf"^{key}:\s*([^#\n]+)", text, re.M)
    return m.group(1).strip() if m else None


def md_status(text: str) -> str | None:
    """Value under a `## Status` heading; None while the template placeholder (with arrows) is still there."""
    m = re.search(r"^## Status\s*\n+([^\n]+)", text, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    return None if "→" in v else v


def artifact_status(p: str) -> str | None:
    """Status of an inception artifact: frontmatter `status:` (md) or top-level `status` (toml)."""
    if not exists(p):
        return None
    if p.endswith(".toml"):
        return load_toml(p).get("status")
    v = front(read(p), "status")
    return v.split("|")[0].strip() if v else None


# ---------------------------------------------------------------- models

def enabled_tools() -> dict[str, dict]:
    return {k: v for k, v in models().get("tools", {}).items() if v.get("enabled", True)}


def model_for(tool: str, tier: str) -> str:
    t = models().get("tools", {}).get(tool, {})
    if tier in t.get("models", {}):
        return t["models"][tier]
    return models().get("vendors", {}).get(t.get("vendor", ""), {}).get(tier, f"<{tier}>")


def tier_line(tier: str) -> str:
    tools = enabled_tools()
    return " · ".join(f"{k}: {model_for(k, tier)}" for k in tools) or f"<{tier}>"


# ---------------------------------------------------------------- plan

def sprints() -> list[dict]:
    """Rows `| S<n> | dates | goal | IDs |` of PLAN.md; EP-xx expands to the epic's stories."""
    if not exists("PLAN.md"):
        return []
    st = stories()
    out = []
    for line in read("PLAN.md").splitlines():
        m = re.match(r"^\|\s*(S\d+(?:\s*[–-]\s*S\d+)?)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|", line)
        if not m:
            continue
        ids: list[str] = []
        for tok in re.findall(rf"{id_rx()}|EP-\d{{2}}", m.group(4)):
            ids += [k for k, s in st.items() if s.get("epic") == tok] if tok.startswith("EP-") else [tok]
        out.append({"sprint": m.group(1), "dates": m.group(2).strip(), "goal": m.group(3).strip(),
                    "ids": list(dict.fromkeys(ids))})
    return out
