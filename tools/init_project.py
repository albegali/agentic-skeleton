#!/usr/bin/env python3
"""Deterministic project bootstrap (the scripted half of /kickoff).

  python3 tools/init_project.py --name "Course Planner" --prefix CP --language it --owner "Jane Doe" \
      [--description "…"] [--no-mockup] [--tools claude-code,codex,copilot,cursor] \
      [--sources docs/brief.md notes.md] [--design docs/prototype.html]

Updates project.toml and models.toml in place (comments preserved), rewrites the example IDs of the
inception templates with the new prefix, records the kickoff sources and the existing design (if any) so that
later steps load them through tools/context.py, and regenerates the tool adapters.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

TOOLS = ("claude-code", "codex", "copilot", "cursor")
EXAMPLE_FILES = ("inception/templates/stories.toml", "inception/templates/PLAN.md")


def set_key(text: str, section: str, key: str, value) -> str:
    """Replace `key = …` inside [section], keeping any trailing comment. Adds the key if absent."""
    lit = json.dumps(value, ensure_ascii=False) if isinstance(value, (str, list)) else str(value).lower()
    sec = re.search(rf"^\[{re.escape(section)}\]\s*$", text, re.M)
    if not sec:
        return text.rstrip() + f"\n\n[{section}]\n{key} = {lit}\n"
    end_m = re.search(r"^\[", text[sec.end():], re.M)
    end = sec.end() + end_m.start() if end_m else len(text)
    body = text[sec.end():end]
    string = r'"(?:[^"\\\n]|\\.)*"'  # escape-aware: `"Acme \"Next\""` is one string
    rx = re.compile(rf"^({re.escape(key)}\s*=\s*)(\[(?:{string}|[^\]\"\n])*\]|{string}|\S+)(.*)$", re.M)
    if rx.search(body):
        body = rx.sub(lambda m: m.group(1) + lit + m.group(3), body, count=1)
    else:
        body = f"\n{key} = {lit}" + body
    return text[:sec.end()] + body + text[end:]


def validate(prefix: str, language: str, tools: list[str]) -> str | None:
    """Error message for invalid project settings, or None (shared with tools/adopt.py, which checks before copying)."""
    if not re.fullmatch(r"[A-Z]{2,3}", prefix):
        return "--prefix must be 2-3 uppercase letters"
    if not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", language):
        return "--language must be an ISO code like en, it, pt-BR"
    if not tools or any(t not in TOOLS for t in tools):
        return f"--tools: choose among {', '.join(TOOLS)}"
    return None


def write_toml(p: str, text: str) -> None:
    """Write a TOML file only if it still parses: a broken project.toml would break every tool."""
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"{p}: the update would produce invalid TOML ({e}); nothing written")
    wf.write(p, text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--prefix", required=True, help="2-3 uppercase letters, e.g. CP")
    ap.add_argument("--language", default="en", help="ISO code of the artifact language, e.g. en, it, de, pt-BR")
    ap.add_argument("--owner", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--no-mockup", action="store_true")
    ap.add_argument("--tools", default=",".join(TOOLS))
    ap.add_argument("--sources", nargs="*", default=None, help="kickoff sources (brief, transcripts, notes), read by later inception steps")
    ap.add_argument("--design", default=None, help="existing design or prototype: /mockup maps it instead of building one")
    a = ap.parse_args()

    tools = [t.strip() for t in a.tools.split(",") if t.strip()]
    if err := validate(a.prefix, a.language, tools):
        sys.exit(err)
    def norm(x: str) -> str:  # recorded relative to the root, with `/` on every OS
        return wf.rel(os.path.abspath(x)) if os.path.isabs(x) else os.path.normpath(x).replace(os.sep, "/")
    srcs = [norm(x) for x in (a.sources or [])]
    design = norm(a.design) if a.design else None
    missing = [x for x in srcs + ([design] if design else []) if not wf.exists(x)]
    if missing:
        sys.exit(f"source not found (paths are relative to the repository root): {', '.join(missing)}")

    old_prefix = wf.prefix()
    p = wf.read("project.toml")
    for k, v in (("initialized", True), ("name", a.name), ("description", a.description), ("id_prefix", a.prefix),
                 ("language", a.language), ("owner", a.owner)):
        p = set_key(p, "project", k, v)
    p = set_key(p, "inception", "mockup", not a.no_mockup)
    if not wf.project().get("skeleton", {}).get("version") and wf.exists("tools/VERSION"):  # the version this project starts from
        p = set_key(p, "skeleton", "version", wf.read("tools/VERSION").strip())
    if a.sources is not None:
        p = set_key(p, "inception", "sources", [x for x in srcs if x != design])
    if design is not None:
        p = set_key(p, "inception", "design", design)
    m = wf.read("models.toml")
    for t in TOOLS:
        m = set_key(m, f"tools.{t}", "enabled", t in tools)
    write_toml("project.toml", p)
    write_toml("models.toml", m)

    if old_prefix != a.prefix:
        for f in EXAMPLE_FILES:
            if wf.exists(f):
                wf.write(f, re.sub(rf"\b{re.escape(old_prefix)}(\d{{4}})\b", rf"{a.prefix}\1", wf.read(f)))

    for c in (wf.project, wf.models):
        c.cache_clear()
    import render_agents  # after the config is written
    render_agents.main()
    print(f"initialized '{a.name}' · prefix {a.prefix} · language {a.language} · tools {', '.join(tools)}"
          f" · mockup {'on' if not a.no_mockup else 'off'}" + (f" · sources {len(srcs)}" if srcs else "")
          + (f" · design {design}" if design else ""))


if __name__ == "__main__":
    main()
