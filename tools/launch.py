#!/usr/bin/env python3
"""Start the application locally for human verification (`make run`, or `python tools/launch.py` without make).

Reads project.toml [stack]:
  run = command that starts the app in the foreground (filled by /architecture or /onboard)
  url = optional address to open in the browser once it answers (e.g. "http://127.0.0.1:8000")
Ctrl+C stops the app. `--no-browser` skips opening the browser.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import webbrowser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _s in (sys.stdout, sys.stderr):  # prints → : a cp1252 console (Windows) must not crash
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


def stack() -> dict:
    with open(os.path.join(ROOT, "project.toml"), "rb") as f:
        return tomllib.load(f).get("stack", {})


LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # the app runs here: never ask a system proxy (macOS)


def wait_for(url: str, proc: subprocess.Popen, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            LOCAL.open(url, timeout=2).close()
            return True
        except urllib.error.HTTPError:
            return True  # it answers, even if not 2xx
        except OSError:
            time.sleep(0.5)
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--timeout", type=float, default=90, help="seconds to wait for url (default 90)")
    args = ap.parse_args(argv)
    s = stack()
    cmd, url = s.get("run", "").strip(), s.get("url", "").strip()
    if not cmd:
        print("[stack] run not defined yet: set it in project.toml (see /architecture or /onboard)")
        return 1
    print(f"$ {cmd}" + (f"\n→ {url}" if url else ""), flush=True)
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(cmd, shell=True, cwd=ROOT, **group)  # the project's own command, from project.toml
    try:
        if url and not args.no_browser:
            if wait_for(url, proc, args.timeout):
                webbrowser.open(url)
            elif proc.poll() is None:
                print(f"{url} not answering after {args.timeout:.0f}s: open it yourself when ready", flush=True)
        return proc.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if proc.poll() is None:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
