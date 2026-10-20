#!/usr/bin/env python3
"""Start the agentic portal for this repository (`make portal`, or `python tools/portal.py` without make).

Reads project.toml [portal]:
  version = "x.y.z"            the pinned portal release (required)
  source  = "<owner>/<repo>"   GitHub repository whose Releases host the bundle (default: the portal repository)
Downloads manifest.json and the bundle zip it names from GitHub Releases, verifies size and SHA-256, caches the
bundle in .portal/<version>/ (gitignored) and starts it for this repository. A portal already running for the
repository is opened instead. PORTAL_BUNDLE=<zip or directory> skips the download (offline or development use).
The launcher generates the session token, keeps it in .portal/token (readable by the current user only), gives it to the
server as PORTAL_TOKEN and opens <url>/#token=<token>; a reused portal opens with the token read from that file.
Ctrl+C stops the portal. `--no-browser` skips opening the browser. Exit codes: 0 ok, 1 user/config error, 2 integrity error.
"""
import sys

if sys.version_info < (3, 11):  # before anything newer than 3.11 can fail to import: say what is needed
    sys.exit("portal.py needs Python 3.11 or newer (found %d.%d)" % sys.version_info[:2])

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
import webbrowser
import zipfile

DEFAULT_SOURCE = "albegali/agentic-portal"
DEFAULT_PORT = 8765
HOST = "127.0.0.1"
VERSION_RX = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")
SHA_RX = re.compile(r"^[0-9a-f]{64}$")


class LauncherError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def find_root(start: str) -> str:
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "project.toml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise LauncherError(1, "no project.toml found here or in a parent directory: run from a workflow repository")
        d = parent


def portal_config(root: str) -> dict:
    with open(os.path.join(root, "project.toml"), "rb") as f:
        cfg = tomllib.load(f).get("portal", {})
    version = str(cfg.get("version", "")).strip()
    if not version:
        raise LauncherError(1, 'project.toml [portal] version is missing: add\n[portal]\nversion = "x.y.z"')
    if not VERSION_RX.match(version):
        raise LauncherError(1, "project.toml [portal] version %r is not a valid version" % version)
    source = str(cfg.get("source", "")).strip() or DEFAULT_SOURCE
    if not re.match(r"^[\w.-]+/[\w.-]+$", source):
        raise LauncherError(1, "project.toml [portal] source must look like <owner>/<repo>, got %r" % source)
    return {"version": version, "source": source}


# ---- manifest and download -------------------------------------------------------------------------------------

def parse_manifest(raw: bytes, version: "str | None" = None) -> dict:
    try:
        m = json.loads(raw)
        major = int(m["manifest"])
    except (ValueError, KeyError, TypeError):
        raise LauncherError(2, "manifest.json is not valid (expected {\"manifest\": 1, ...})")
    if major != 1:
        raise LauncherError(2, "manifest format %s is not supported by this launcher (needs 1): update tools/portal.py" % major)
    try:
        asset, size, sha = m["asset"], m["size"], str(m["sha256"]).lower()
    except KeyError as e:
        raise LauncherError(2, "manifest.json lacks %s" % e)
    if not isinstance(asset, str) or asset != os.path.basename(asset) or not asset.endswith(".zip"):
        raise LauncherError(2, "manifest.json asset must be a plain .zip file name")
    if not isinstance(size, int) or size < 0 or not SHA_RX.match(sha):
        raise LauncherError(2, "manifest.json size or sha256 is invalid")
    if version and str(m.get("version", version)) != version:
        raise LauncherError(2, "manifest.json is for version %s, not %s" % (m.get("version"), version))
    m["sha256"] = sha
    return m


def fetch(url: str, dest: "str | None" = None) -> bytes:
    """GET url; to a file when dest is given (streamed). 404 -> exit 1 'not found'; network down -> exit 1."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            if dest is None:
                return r.read()
            with open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            return b""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise LauncherError(1, "not found: %s\nCheck [portal] version (and source) in project.toml: is that release published?" % url)
        raise LauncherError(1, "download failed (HTTP %s): %s" % (e.code, url))
    except OSError as e:
        raise LauncherError(1, "cannot reach %s (%s)\nNo cached portal for this version either: connect once to download it, "
                               "or set PORTAL_BUNDLE=<path>." % (url, e))


def verify_file(path: str, manifest: dict) -> None:
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    if n != manifest["size"] or h.hexdigest() != manifest["sha256"]:
        raise LauncherError(2, "integrity check failed for %s: size/SHA-256 do not match the manifest. Nothing was started or cached."
                            % manifest["asset"])


# ---- cache -----------------------------------------------------------------------------------------------------

def safe_extract(zip_path: str, dest: str) -> None:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise LauncherError(2, "the bundle is not a valid zip file")
    with zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", parts[0]):
                raise LauncherError(2, "unsafe path in bundle (%s): aborting" % info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise LauncherError(2, "symbolic link in bundle (%s): aborting" % info.filename)
        zf.extractall(dest)


def install(root: str, version: str, zip_path: str, manifest: dict) -> str:
    """Extract to .portal/<version>.tmp, then rename: a half-extracted bundle is never visible as the cache."""
    base = os.path.join(root, ".portal")
    final, tmp = os.path.join(base, version), os.path.join(base, version + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        safe_extract(zip_path, tmp)
        with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        shutil.rmtree(final, ignore_errors=True)
        os.replace(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def cached_manifest(bundle: str) -> "dict | None":
    p = os.path.join(bundle, "manifest.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            m = json.load(f)  # written by install() from an already verified manifest
    except ValueError:
        return None
    return m if isinstance(m, dict) else None


def local_bundle(root: str, path: str) -> "tuple[str, dict | None]":
    """PORTAL_BUNDLE: a directory is used as it is; a zip is verified against a sibling manifest.json when present."""
    path = os.path.abspath(path)
    if os.path.isdir(path):
        print("PORTAL_BUNDLE directory: used as is (not verified)")
        return path, cached_manifest(path)
    if not os.path.isfile(path):
        raise LauncherError(1, "PORTAL_BUNDLE %s does not exist" % path)
    mp = os.path.join(os.path.dirname(path), "manifest.json")
    manifest = None
    if os.path.isfile(mp):
        with open(mp, "rb") as f:
            manifest = parse_manifest(f.read())
        verify_file(path, manifest)
        print("PORTAL_BUNDLE zip verified against %s" % mp)
    else:
        print("PORTAL_BUNDLE zip: no manifest.json next to it, not verified")
    return install(root, "local", path, manifest or {"manifest": 1, "version": "local"}), manifest


def get_bundle(root: str, cfg: dict) -> "tuple[str, dict | None]":
    override = os.environ.get("PORTAL_BUNDLE", "").strip()
    if override:
        return local_bundle(root, override)
    version = cfg["version"]
    final = os.path.join(root, ".portal", version)
    if os.path.isfile(os.path.join(final, "manifest.json")):
        return final, cached_manifest(final)
    base = os.environ.get("PORTAL_RELEASE_BASE", "").rstrip("/") or \
        "https://github.com/%s/releases/download/v%s" % (cfg["source"], version)  # env: tests and mirrors only
    print("Downloading portal %s from %s" % (version, base), flush=True)
    manifest = parse_manifest(fetch(base + "/manifest.json"), version)
    os.makedirs(os.path.join(root, ".portal"), exist_ok=True)
    tmp = os.path.join(root, ".portal", version + ".download")
    try:
        fetch("%s/%s" % (base, manifest["asset"]), tmp)
        verify_file(tmp, manifest)
        return install(root, version, tmp, manifest), manifest
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---- interpreter, port, running instance -----------------------------------------------------------------------

def min_python(manifest: "dict | None") -> "tuple[int, int]":
    m = re.match(r"^\s*>=\s*(\d+)\.(\d+)", (manifest or {}).get("requires_python", "") or "")
    return (int(m.group(1)), int(m.group(2))) if m else (3, 11)


def python_ok(cmd: list, need: "tuple[int, int]") -> bool:
    try:
        code = "import sys; sys.exit(0 if sys.version_info >= (%d, %d) else 1)" % need
        return subprocess.run(cmd + ["-c", code], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def pick_python(need: "tuple[int, int]") -> list:
    if sys.version_info >= need:
        return [sys.executable]
    cands = [["python%d.%d" % need], ["python%d" % need[0]]]
    if os.name == "nt":
        cands.append(["py", "-%d.%d" % need])
    for c in cands:
        if shutil.which(c[0]) and python_ok(c, need):
            return c
    raise LauncherError(1, "the portal needs Python %d.%d or newer and none was found (running %d.%d). "
                           "Install it, then run the launcher again." % (need + sys.version_info[:2]))


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, port)) != 0


def pick_port() -> int:
    for p in range(DEFAULT_PORT, DEFAULT_PORT + 50):
        if port_free(p):
            return p
    raise LauncherError(1, "no free port between %d and %d" % (DEFAULT_PORT, DEFAULT_PORT + 49))


LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # the local portal: never through a proxy


def healthy(url: str, timeout: float = 0.5) -> bool:
    try:
        with LOCAL.open(url.rstrip("/") + "/api/health", timeout=timeout) as r:
            return json.loads(r.read()).get("status") == "ok"
    except (OSError, ValueError):
        return False


def run_file(root: str) -> str:
    return os.path.join(root, ".portal", "run.json")


def running_instance(root: str) -> "str | None":
    """URL of the portal already running for this repository, or None (a stale run.json is removed)."""
    p = run_file(root)
    try:
        with open(p, encoding="utf-8") as f:
            url = json.load(f)["url"]
    except (OSError, ValueError, KeyError, TypeError):
        url = None
    if url and healthy(url):
        return url
    if os.path.exists(p):
        os.remove(p)
    return None


def write_run_file(root: str, info: dict) -> None:
    p = run_file(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f)
    os.replace(tmp, p)


# ---- session token ---------------------------------------------------------------------------------------------

def token_file(root: str) -> str:
    return os.path.join(root, ".portal", "token")


def restrict_windows(path: str) -> None:
    """Best effort: only the current user may access the file; a failure is a warning, not an error."""
    user = os.environ.get("USERNAME", "")
    if os.environ.get("USERDOMAIN"):
        user = os.environ["USERDOMAIN"] + "\\" + user
    try:
        r = subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", "%s:F" % user], capture_output=True, text=True, timeout=20)
        ok = r.returncode == 0 and bool(user)
    except (OSError, subprocess.SubprocessError):
        ok = False
    if not ok:
        print("warning: could not restrict %s to the current user; protect it manually" % path, file=sys.stderr)


def write_token(root: str, token: str) -> None:
    p = token_file(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    try:
        os.remove(tmp)
    except OSError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # 0600 from creation: never readable by others
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    if os.name == "nt":
        restrict_windows(tmp)
    os.replace(tmp, p)


def read_token(root: str) -> "str | None":
    """The token of the running portal, or None when the file is missing, empty or accessible to other users."""
    p = token_file(root)
    try:
        if os.name != "nt" and os.stat(p).st_mode & 0o077:
            return None
        with open(p, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def remove_token(root: str) -> None:
    try:
        os.remove(token_file(root))
    except OSError:
        pass


def launch_url(url: str, token: "str | None") -> str:
    return "%s/#token=%s" % (url, token) if token else url


# ---- start -----------------------------------------------------------------------------------------------------

def supports_repo_flag(py: list, bundle: str) -> bool:
    try:
        r = subprocess.run(py + ["-m", "portal_server", "--help"], cwd=bundle, capture_output=True, text=True, timeout=20,
                           env={**os.environ, "PYTHONPATH": bundle})
        return "--repo" in r.stdout + r.stderr
    except (OSError, subprocess.SubprocessError):
        return False


def serve(root: str, bundle: str, manifest: "dict | None", cfg: dict, open_browser: bool, timeout: float = 60) -> int:
    py = pick_python(min_python(manifest))
    port = pick_port()
    cmd = py + ["-m", "portal_server", "--host", HOST, "--port", str(port)]
    if supports_repo_flag(py, bundle):
        cmd += ["--repo", root]
    token = secrets.token_urlsafe(32)
    env = {**os.environ, "PYTHONPATH": bundle, "PORTAL_TOKEN": token}  # token by environment, never by argument; a bundle without --repo reads the repository from the working directory
    url = "http://%s:%d" % (HOST, port)
    write_token(root, token)
    try:
        proc = subprocess.Popen(cmd, cwd=root, env=env)
    except BaseException:
        remove_token(root)
        raise
    stop = signal.SIGBREAK if os.name == "nt" else signal.SIGTERM
    signal.signal(stop, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))  # terminate = Ctrl+C: cleanup still runs
    try:
        deadline = time.monotonic() + timeout
        while proc.poll() is None and not healthy(url, 1):
            if time.monotonic() > deadline:
                raise LauncherError(1, "the portal did not answer on %s within %.0fs" % (url, timeout))
            time.sleep(0.2)
        if proc.poll() is not None:
            raise LauncherError(1, "the portal exited at startup (code %s)" % proc.returncode)
        write_run_file(root, {"pid": proc.pid, "port": port, "url": url, "version": cfg["version"],
                              "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        print("Portal %s for %s at %s (Ctrl+C to stop)" % (cfg["version"], root, url), flush=True)
        print("Open %s" % launch_url(url, token), flush=True)  # the one place the token is printed
        if open_browser:
            webbrowser.open(launch_url(url, token))
        return proc.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            os.remove(run_file(root))
        except OSError:
            pass
        remove_token(root)


def warn_gitignore(root: str) -> None:
    try:
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as f:
            if any(l.strip().lstrip("/").startswith(".portal") for l in f):
                return
    except OSError:
        pass
    print("note: .portal/ is not in .gitignore: add it so the cached bundle is not committed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = ap.parse_args(argv)
    try:
        root = find_root(os.getcwd())
        cfg = portal_config(root)
        url = running_instance(root)
        if url:
            token = read_token(root)
            print("Portal already running for this repository: %s" % url)
            if token:
                print("Open %s" % launch_url(url, token))
            else:
                print("The session token is not available; stop the running portal and run `make portal` again to open it signed in.")
            if not args.no_browser:
                webbrowser.open(launch_url(url, token))
            return 0
        bundle, manifest = get_bundle(root, cfg)
        warn_gitignore(root)
        return serve(root, bundle, manifest, cfg, not args.no_browser)
    except LauncherError as e:
        print("error: %s" % e, file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
