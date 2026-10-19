#!/usr/bin/env python3
"""Deterministic project bootstrap (the scripted half of /kickoff).

  python3 tools/init_project.py --name "Course Planner" --prefix CP --language it --owner "Jane Doe" \
      [--description "…"] [--no-mockup] [--tools claude-code,codex,copilot,cursor]

Updates project.toml and models.toml in place (comments preserved), rewrites the example IDs of the
inception templates with the new prefix, and regenerates the tool adapters.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

TOOLS = ("claude-code", "codex", "copilot", "cursor")
EXAMPLE_FILES = ("inception/templates/stories.toml", "inception/templates/PLAN.md")


def set_key(text: str, section: str, key: str, value) -> str:
    """Replace `key = …` inside [section], keeping any trailing comment. Adds the key if absent."""
    lit = json.dumps(value, ensure_ascii=False) if isinstance(value, str) else str(value).lower()
    sec = re.search(rf"^\[{re.escape(section)}\]\s*$", text, re.M)
    if not sec:
        return text.rstrip() + f"\n\n[{section}]\n{key} = {lit}\n"
    end_m = re.search(r"^\[", text[sec.end():], re.M)
    end = sec.end() + end_m.start() if end_m else len(text)
    body = text[sec.end():end]
    rx = re.compile(rf"^({re.escape(key)}\s*=\s*)(\"[^\"]*\"|\S+)(.*)$", re.M)
    if rx.search(body):
        body = rx.sub(lambda m: m.group(1) + lit + m.group(3), body, count=1)
    else:
        body = f"\n{key} = {lit}" + body
    return text[:sec.end()] + body + text[end:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--prefix", required=True, help="2-3 uppercase letters, e.g. CP")
    ap.add_argument("--language", default="en", help="ISO code of the artifact language, e.g. en, it, de, pt-BR")
    ap.add_argument("--owner", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--no-mockup", action="store_true")
    ap.add_argument("--tools", default=",".join(TOOLS))
    a = ap.parse_args()

    if not re.fullmatch(r"[A-Z]{2,3}", a.prefix):
        sys.exit("--prefix must be 2-3 uppercase letters")
    if not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", a.language):
        sys.exit("--language must be an ISO code like en, it, pt-BR")
    tools = [t.strip() for t in a.tools.split(",") if t.strip()]
    bad = [t for t in tools if t not in TOOLS]
    if bad or not tools:
        sys.exit(f"--tools: choose among {', '.join(TOOLS)}")

    old_prefix = wf.prefix()
    p = wf.read("project.toml")
    for k, v in (("initialized", True), ("name", a.name), ("description", a.description), ("id_prefix", a.prefix),
                 ("language", a.language), ("owner", a.owner)):
        p = set_key(p, "project", k, v)
    p = set_key(p, "inception", "mockup", not a.no_mockup)
    wf.write("project.toml", p)

    m = wf.read("models.toml")
    for t in TOOLS:
        m = set_key(m, f"tools.{t}", "enabled", t in tools)
    wf.write("models.toml", m)

    if old_prefix != a.prefix:
        for f in EXAMPLE_FILES:
            if wf.exists(f):
                wf.write(f, re.sub(rf"\b{re.escape(old_prefix)}(\d{{4}})\b", rf"{a.prefix}\1", wf.read(f)))

    for c in (wf.project, wf.models):
        c.cache_clear()
    import render_agents  # after the config is written
    render_agents.main()
    print(f"initialized '{a.name}' · prefix {a.prefix} · language {a.language} · tools {', '.join(tools)}"
          f" · mockup {'on' if not a.no_mockup else 'off'}")


if __name__ == "__main__":
    main()
