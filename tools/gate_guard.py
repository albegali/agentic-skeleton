#!/usr/bin/env python3
"""Agent hook (Claude Code PreToolUse): keep human gates and mode boundaries out of the agent's reach.

Rendered into .claude/settings.json by tools/render_agents.py. Reads the hook event on stdin; exit 2 blocks the tool
call and its stderr goes back to the agent. Blocks:
  - an edit that passes a human gate (RUN §2 Approved, Spec → Ready, status approved/accepted, `decided = true`,
    tuning acceptance, deviation approval), unless the human's latest prompt is the explicit gate command for it
    (`/run <ID> approve`, `/run <ID> approve-deviation <n>`, `/persist <ID>`);
  - a write outside the paths of the current mode (taken from the latest workflow command in the transcript);
  - shell commands that run the human approval, rewrite or delete history and branches, bypass protection, or read
    secrets (.env);
  - destructive shell commands: `rm -r` of the repository root, `.git`, a parent or a path outside the repository (the
    system temp dirs excepted) or of a target it cannot resolve (`$VAR`, top-level glob); `chmod|chown -R` and
    `find … -delete` outside the repository; `git clean -x` at the root without `-n`; `sudo`, `mkfs`, `shred`,
    `dd of=/dev/…`, `diskutil erase…`, `curl|wget … | sh`;
  - an edit or write outside the repository, except the system temp dirs, the agent's own dir (`~/.claude/`) and the
    directories in `project.toml [guard] write_paths`;
  - a full read (`Read` without offset/limit, or a bare `cat`/`head`/`tail`/`less`/`more`) of a text file longer than
    `project.toml` `[context] max_read_lines` (default 400): the agent is sent to `tools/context.py --index`, a section,
    or an offset/limit read. Targeted reads, piped commands and small files pass.
Anything it cannot parse is allowed: the hook is a guard rail, `make check --git` in CI is the backstop.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import gates  # noqa: E402
import wf  # noqa: E402

COMMAND = re.compile(r"<command-name>/?([\w:-]+)</command-name>(?:\s*<command-args>(.*?)</command-args>)?", re.S)
# where each mode may write with the edit tools (AGENTS.md §1; analyst exceptions in analysis/AGENTS.md)
MODE_PATHS = {
    "analyst": ["analysis/*", "backlog/stories.toml", "reference/architecture/ADR-*.md", "reference/architecture/architecture.md"],
    "review": ["delivery/30-runs/RUN-*.md"],
    "journal": ["project-journal/*"],
}
AT = r"(?:^|[;&|(\n]|\$\()\s*(?:\w+=\S*\s+)*"  # command position: a mention inside a string or heredoc is not a run
ARGS = r"[^|;&\n]*"
SHELL_DENY = [
    (AT + r"(?:make\s+approve\b|python3?\s+\S*tools/approve\.py\b)", "approvals are run by the human (`make approve …`), never by an agent"),
    (AT + r"python3?\s+\S*tools/gates\.py\s+(?:approve|request-changes)\b",
     "gate decisions (`gates.py approve|request-changes`) are the human's (or the portal acting for the owner), never an agent's"),
    (AT + r"git\s+push\b" + ARGS + r"\s(-f|--force|--force-with-lease|--force-if-includes|--delete|-d)\b", "no force push or remote branch deletion"),
    (AT + r"git\s+push\b" + ARGS + r"\s\+\S", "no forced refspec (+branch)"),
    (AT + r"git\s+push\b" + ARGS + r"\s:\S", "no remote branch deletion (:branch)"),
    (AT + r"git\s+branch\b" + ARGS + r"\s(-D|--delete\s+--force)\b", "no forced branch deletion"),
    (AT + r"git\s+(?:switch\s+(?:-c|--create)|checkout\s+-[bB]|branch(?!\s+(?:-[dD]|--delete)\b))\b" + ARGS + r"\s(?:origin/)?(?:release|releases|develop|development|dev|staging|integration|next)(?:[/_.-]\S*)?(?=\s|$)",
     "trunk-based development: no long-lived branches (release/develop/staging/integration); a release is a tag on main"),
    (AT + r"git\s+reset\b" + ARGS + r"\s--hard\b", "no hard reset"),
    (AT + r"git\s+(?:filter-branch|filter-repo)\b|" + AT + r"git\s+rebase\b" + ARGS + r"\s(-i|--root)\b", "no history rewrite"),
    (AT + r"gh\s+pr\s+merge\b" + ARGS + r"\s--admin\b", "never bypass branch protection"),
    (AT + r"gh\s+api\b" + ARGS + r"\bprotection\b", "never change branch protection"),
    (AT + r"(?:cat|less|more|head|tail|source|\.|bat|strings|xxd|od|base64|cp|scp|grep|rg|awk|sed)(?=\s)" + ARGS
     + r"(?:^|[\s<'\"/=])\.env(?:\.(?!example\b|sample\b|template\b)[\w.-]+)?(?=$|[\s'\";|&>)])", "secrets: never read or print .env files"),
    (AT + r"(?:ba|z|da|k)?sh\s+(?:-c\s+)?[\"']?(?:\$\(|<\()\s*(?:curl|wget)\b", "no remote script run by a shell (curl|wget … | sh)"),
]


def last_command(transcript: str | None, sticky: bool = False) -> tuple[str | None, str]:
    """(command, args) of the human's latest prompt when it is a workflow command; (None, "") otherwise.
    sticky: the latest workflow command of the session, kept across free-text follow-ups and built-ins (`/compact`)."""
    if not transcript or not os.path.exists(transcript):
        return None, ""
    last: tuple[str | None, str] = (None, "")
    with open(transcript, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain") or d.get("userType", "external") != "external":
                continue
            c = (d.get("message") or {}).get("content")
            texts = [c] if isinstance(c, str) else [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
            if not any(t.strip() for t in texts):
                continue  # tool results
            m = next((COMMAND.search(t) for t in texts if COMMAND.search(t)), None)
            if sticky and not (m and m.group(1).split(":")[-1] in wf.workflow().get("commands", {})):
                continue
            last = (m.group(1).split(":")[-1], (m.group(2) or "").strip()) if m else (None, "")
    return last


def mode_of(command: str | None) -> str | None:
    return wf.workflow().get("commands", {}).get(command or "", {}).get("mode") if command else None


def after_edit(tool: str, inp: dict, before: str) -> str | None:
    if tool == "Write":
        return inp.get("content", "")
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old and old not in text:
            return None  # the edit will fail anyway
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


FORCE_DELETE = re.compile(r"^\s*git\s+branch\s+-D\s+([\w][\w./-]*)\s*$")


def merged_by_content(branch: str) -> bool:
    """True when merging `branch` into trunk changes nothing: its content is already in main (squash/rebase merge)."""
    import subprocess

    def git(*a: str) -> str | None:
        try:
            r = subprocess.run(["git", *a], cwd=wf.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    if branch in ("main", "master") or git("rev-parse", "--verify", "-q", f"refs/heads/{branch}") is None:
        return False
    trunk = next((t for t in ("origin/main", "main") if git("rev-parse", "--verify", "-q", t) is not None), None)
    merged = git("merge-tree", "--write-tree", trunk, branch) if trunk else None
    return bool(merged) and merged.split()[0] == git("rev-parse", f"{trunk}^{{tree}}")


MAX_READ_LINES = 400  # same as tools/context.py BIG
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ipynb", ".svg", ".ico", ".zip", ".gz", ".woff", ".woff2"}
FULL_READERS = {"cat", "head", "tail", "less", "more"}
SHELL_OPS = re.compile(r"[|;&<>`$()\n]")


def large_file(path: str) -> int | None:
    """Line count of a text file above the `[context] max_read_lines` threshold; None when it is small, missing or binary."""
    full = os.path.join(wf.ROOT, path) if not os.path.isabs(path) else path
    if os.path.splitext(full)[1].lower() in BINARY or not os.path.isfile(full):
        return None
    try:
        limit = int(wf.project().get("context", {}).get("max_read_lines", MAX_READ_LINES))
        with open(full, "rb") as f:
            head = f.read(8192)
            if b"\0" in head:
                return None
            lines = head.count(b"\n") + sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b""))
    except (OSError, ValueError):
        return None
    return lines if limit > 0 and lines > limit else None


def full_read_target(cmd: str) -> str | None:
    """The file of a bare `cat|head|tail|less|more <file>` (no flags, pipes, redirections or substitutions)."""
    if SHELL_OPS.search(cmd):
        return None
    try:
        words = shlex.split(cmd)
    except ValueError:
        return None
    if len(words) != 2 or words[0] not in FULL_READERS or words[1].startswith("-"):
        return None
    return words[1]


def deny_large(path: str, lines: int) -> None:
    deny(f"large read: {path} has {lines} lines. Do not read it whole: `python3 tools/context.py --index {path}` for its headings, "
         f"a cited section extract, or a targeted read with offset and limit (Read) / `sed -n 'A,Bp'`. "
         f"For a question that spans many files, ask the `reader` subagent (Claude Code, fast tier) instead. "
         f"The threshold is `[context] max_read_lines` in project.toml")


SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
WRAPPERS = {"env", "command", "nohup", "time", "exec"}
OPS = "();<>|&\n"
VAR = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
GLOB = re.compile(r"[*?[]")


def without_heredocs(cmd: str) -> str:
    """The command without heredoc bodies (data, not a run), unless the heredoc feeds a shell."""
    out, pos = [], 0
    for m in re.finditer(r"(?<!<)<<-?[ \t]*(['\"]?)(\w+)\1", cmd):
        eol = cmd.find("\n", m.end())
        if m.start() < pos or eol < 0:
            continue
        end = re.compile(rf"^[ \t]*{m.group(2)}[ \t]*$", re.M).search(cmd, eol + 1)
        first = cmd[cmd.rfind("\n", 0, m.start()) + 1:m.start()].split()[:1]
        if first and os.path.basename(first[0]) in SHELLS:
            continue  # the body runs
        out.append(cmd[pos:eol + 1])
        pos = end.end() if end else len(cmd)
    return "".join(out) + cmd[pos:]


def segments(cmd: str) -> list[tuple[list[str], str]]:
    """Simple commands as (words, operator after it); redirections dropped; quoted text stays one word."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=OPS)
    lex.whitespace, lex.whitespace_split = " \t\r", True
    segs, cur, skip = [], [], False
    try:
        for t in lex:
            if t and not t.strip(OPS):
                if "<" in t or ">" in t:
                    if cur and cur[-1].isdigit():
                        cur.pop()  # file descriptor (2>)
                    skip = True
                else:
                    segs.append((cur, t))
                    cur = []
            elif skip:
                skip = False
            else:
                cur.append(t)
    except ValueError:
        return []
    return segs + [(cur, "")]


FIND_FILTERS = {"-name", "-iname", "-path", "-ipath", "-wholename", "-regex", "-iregex", "-type", "-newer", "-mtime", "-mmin",
                "-atime", "-amin", "-ctime", "-cmin", "-size", "-empty", "-perm", "-user", "-group"}


def temp_dirs() -> list[str]:
    return sorted({os.path.realpath(d) for d in ("/tmp", "/private/tmp", "/var/tmp", tempfile.gettempdir())})


def write_paths() -> list[str]:
    """Extra directories agents may write to: `project.toml [guard] write_paths` (`~` expanded, relative to the repository)."""
    paths = wf.project().get("guard", {}).get("write_paths") or []
    return [os.path.realpath(os.path.join(wf.ROOT, os.path.expanduser(p))) for p in paths if isinstance(p, str) and p.strip()]


def under(path: str, base: str) -> bool:
    return path.startswith(base.rstrip(os.sep) + os.sep)


def resolve(word: str, cwd: str | None) -> str | None:
    """Absolute path of a shell word (parent dir resolved through symlinks); None when it cannot be resolved."""
    known = {"TMPDIR": tempfile.gettempdir(), "CLAUDE_PROJECT_DIR": wf.ROOT, "PWD": cwd}
    if any(known.get(m.group(1) or m.group(2)) is None for m in VAR.finditer(word)):
        return None
    word = os.path.expanduser(VAR.sub(lambda m: known[m.group(1) or m.group(2)], word))
    if "$" in word or "`" in word or (not os.path.isabs(word) and cwd is None):
        return None
    head, last = os.path.split(os.path.normpath(os.path.join(cwd or "/", word)))
    return None if GLOB.search(head) else os.path.join(os.path.realpath(head), last)


def target_problem(path: str | None, strict: bool = True) -> str | None:
    """Why a recursive change of `path` is refused; None inside the repository or a temp dir (strict: not the root)."""
    if path is None:
        return "a target it cannot resolve (variable, glob in a directory, unknown cwd)"
    root = os.path.realpath(wf.ROOT)
    glob = bool(GLOB.search(os.path.basename(path)))
    p = os.path.dirname(path) if glob else path
    if p == root and not strict:
        return None
    if p == root or under(root, p):
        return "the repository root or a parent of it" + (" (top-level glob)" if glob else "")
    if p == os.path.join(root, ".git"):
        return "the repository's .git"
    if os.path.realpath(p) in temp_dirs():
        return "a system temp dir itself"
    if under(p, root) or any(under(p, t) for t in temp_dirs()):
        return None
    return "a path outside the repository (only the repository and the system temp dirs)"


def destructive(cmd: str, cwd: str | None) -> str | None:
    """The rule a destructive shell command breaks; None when it is fine or cannot be parsed."""
    segs = segments(cmd)
    for i, (words, op) in enumerate(segs):
        while words and (re.match(r"\w+=", words[0]) or words[0] in WRAPPERS):
            words = words[1:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        flags = [a for a in args if a.startswith("-") and a != "-"]
        short = "".join(a[1:] for a in flags if not a.startswith("--"))
        paths = [a for a in args if a not in flags]
        recursive = "r" in short.lower() or "--recursive" in flags
        if name == "cd":
            cwd = resolve(paths[0], cwd) if paths and paths[0] != "-" else (os.path.expanduser("~") if not paths else None)
        elif name in ("sudo", "doas"):
            return "no sudo: an agent never runs commands as root"
        elif name.startswith(("mkfs", "newfs")) or name == "shred" or (name == "dd" and any(a.startswith("of=/dev/") for a in args)):
            return f"no disk or device wiping ({name})"
        elif name == "diskutil" and args and re.match(r"(?i)(erase|zerodisk|randomdisk|secureerase|partitiondisk|reformat)", args[0]):
            return "no disk erase (diskutil)"
        elif name in ("curl", "wget") and op in ("|", "|&") and i + 1 < len(segs):
            nxt = [w for w in segs[i + 1][0] if w not in WRAPPERS and w not in ("sudo", "doas") and not re.match(r"\w+=", w)]
            if nxt and os.path.basename(nxt[0]) in SHELLS:
                return "no remote script run by a shell (curl|wget … | sh)"
        elif name == "rm" and recursive:
            for t in paths:
                if why := target_problem(resolve(t, cwd)):
                    return f"rm -r of {why}: {t}"
        elif name in ("chmod", "chown", "chgrp") and ("R" in short or "--recursive" in flags):
            for t in paths if any(f.startswith("--reference") for f in flags) else paths[1:]:
                if why := target_problem(resolve(t, cwd), strict=False):
                    return f"{name} -R of {why}: {t}"
        elif name == "find" and "-delete" in args:
            starts = [a for a in args[:next((k for k, a in enumerate(args) if a[:1] in "-(!"), len(args))]] or ["."]
            for t in starts:
                if why := target_problem(resolve(t, cwd), strict=False):
                    return f"find -delete in {why}: {t}"
                if resolve(t, cwd) == os.path.realpath(wf.ROOT) and not FIND_FILTERS & set(args):
                    return f"find -delete of the whole repository without a filter (-name, -path, -type, …): {t}"
        elif name == "git" and args[:1] == ["clean"] and "x" in short.lower() and "n" not in short and "--dry-run" not in flags:
            spec = [resolve(p, cwd) for p in paths[1:]] or [os.path.realpath(cwd) if cwd else None]
            if os.path.realpath(wf.ROOT) in spec or None in spec:
                return "no `git clean -x` of the whole repository (it deletes untracked artifacts and .env); use -n first or a path"
    return None


def deny(reason: str) -> None:
    print(f"Blocked by the workflow guard (tools/gate_guard.py): {reason}", file=sys.stderr)
    sys.exit(2)


def check(event: dict) -> None:
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool == "Read":
        if inp.get("offset") is None and inp.get("limit") is None and (n := large_file(inp.get("file_path") or "")):
            deny_large(inp["file_path"], n)
        return
    if tool == "Bash":
        cmd = inp.get("command", "")
        run = without_heredocs(cmd)
        force = FORCE_DELETE.match(cmd)
        for rx, why in SHELL_DENY:
            if re.search(rx, run):
                if why == "no forced branch deletion" and force and merged_by_content(force.group(1)):
                    continue  # squash-merged story branch: `git branch -d` refuses it, but nothing is lost
                deny(f"{why}: `{cmd[:120]}`")
        if why := destructive(run, event.get("cwd") or wf.ROOT):
            deny(f"destructive command, {why}: `{cmd[:120]}`")
        target = full_read_target(cmd)
        if target and (n := large_file(target)):
            deny_large(target, n)
        return
    if tool not in ("Edit", "Write", "MultiEdit"):
        return
    full = inp.get("file_path") or ""
    rel = os.path.relpath(os.path.abspath(full), wf.ROOT).replace(os.sep, "/")
    if rel.startswith(".."):
        real, root = os.path.realpath(os.path.abspath(full)), os.path.realpath(wf.ROOT)
        if not under(real, root):
            agent = [os.path.realpath(d) for d in (os.path.expanduser("~/.claude"), os.environ.get("CLAUDE_CONFIG_DIR")) if d]
            if not any(real == d or under(real, d) for d in temp_dirs() + agent + write_paths()):
                deny(f"write outside the repository: {full}. Agents write only in the repository, the system temp dirs, "
                     f"the agent's own dir (~/.claude/) and `project.toml [guard] write_paths`; ask the human to add the "
                     f"directory there or to change the file")
            return
        rel = os.path.relpath(real, root).replace(os.sep, "/")
    command, args = last_command(event.get("transcript_path"))
    mode = mode_of(command)
    if mode in MODE_PATHS and not any(fnmatch.fnmatch(rel, pat) for pat in MODE_PATHS[mode]):
        deny(f"/{command} runs in {mode} mode, which writes only {', '.join(MODE_PATHS[mode])}; not {rel}")
    before = wf.read(rel) if wf.exists(rel) else ""
    after = after_edit(tool, inp, before)
    if after is None:
        return
    for g in gates.passed(rel, before, after):
        if not gates.allowed_by(g, command, args):
            what = f"{g['gate']} of {g['id']}" if g["id"] else f"{g['gate']} ({rel})"
            deny(f"this edit passes the human gate {what}. Agents never pass a gate: ask the human to run "
                 f"`{gates.hint(g)}`. Leave the field as it is and stop.")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    try:
        check(event)
    except (OSError, ValueError, KeyError):  # never break the agent on a parse problem
        return


if __name__ == "__main__":
    main()
