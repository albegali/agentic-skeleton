#!/usr/bin/env python3
"""Cheap, deterministic map of an existing codebase (input of /onboard), and stack command detection (used by adopt.py).

  python3 tools/repo_map.py            # same as: python3 tools/context.py --repo-map
  python3 tools/repo_map.py --json     # complete data (all files, churn, tests), schema in tools/README.md

Any kind of software: web, services, mobile, desktop, games, embedded, libraries, CLIs, data/ML, infrastructure,
extensions, or a mix. It prints languages, the directory tree with sizes, software-type signals, build / hosting /
infrastructure / CI files on any provider, interfaces and persistence, docs, root files, entry points, tests, the
largest files and git hot spots. Signals are hints for /onboard, not verdicts. Workflow files and vendored code are
left out. No file contents are printed.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import wf  # noqa: E402

# third-party code, never mapped (counted); build outputs are skipped only when walking without git
VENDORED = {"node_modules", "bower_components", "jspm_packages", "Pods", "Carthage", "vendor", "third_party", "third-party",
            "__pycache__", ".venv", "venv", ".git"}
BUILD_OUT = {"dist", "build", "target", "out", "bin", "obj", ".next", ".nuxt", ".dart_tool", "DerivedData", "Library", "Temp",
             "Intermediates", "Binaries", ".pio", ".gradle", ".terraform", "coverage", "htmlcov", ".idea", ".vscode",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".cache", ".expo"}
# workflow artifacts: never part of the codebase being mapped
WF_PREFIXES = ("workflow/", "inception/", "project-journal/", "backlog/", "analysis/10-stories/", "analysis/20-analysis/",
               "analysis/30-refined/", "analysis/output/", "analysis/templates/", "delivery/10-briefs/", "delivery/20-specs/",
               "delivery/30-runs/", "delivery/templates/", "delivery/guide/", "reference/product/", "reference/architecture/",
               "reference/domain/", "reference/documentation/", "reference/backlog/", "reference/mockup/")
WF_FILES = {"PLAN.md", "project.toml", "models.toml", "workflow.mk", "workflow/.installed"}
SOURCE_EXT = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
              ".ts": "TypeScript", ".tsx": "TypeScript", ".vue": "Vue", ".svelte": "Svelte", ".go": "Go", ".rs": "Rust",
              ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala", ".cs": "C#", ".fs": "F#", ".vb": "VB.NET",
              ".rb": "Ruby", ".php": "PHP", ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".swift": "Swift",
              ".m": "Objective-C", ".mm": "Objective-C++", ".dart": "Dart", ".c": "C", ".h": "C/C++ header", ".cpp": "C++",
              ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".ino": "Arduino", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
              ".bat": "Batch", ".tf": "Terraform", ".hcl": "HCL", ".bicep": "Bicep", ".r": "R", ".lua": "Lua", ".gd": "GDScript",
              ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "LESS", ".styl": "Stylus",
              ".graphql": "GraphQL", ".proto": "Protobuf", ".ipynb": "Notebook", ".coffee": "CoffeeScript", ".pug": "Pug",
              ".jade": "Jade", ".hbs": "Handlebars", ".ejs": "EJS", ".erb": "ERB", ".twig": "Twig", ".jsp": "JSP",
              ".aspx": "ASP.NET", ".cshtml": "Razor", ".razor": "Razor", ".xaml": "XAML", ".qml": "QML", ".cfm": "ColdFusion",
              ".pl": "Perl", ".groovy": "Groovy", ".clj": "Clojure", ".hs": "Haskell", ".ml": "OCaml", ".zig": "Zig",
              ".nim": "Nim", ".jl": "Julia", ".elm": "Elm", ".sol": "Solidity", ".v": "Verilog", ".sv": "SystemVerilog",
              ".vhd": "VHDL", ".cob": "COBOL", ".cbl": "COBOL", ".abap": "ABAP", ".pas": "Pascal", ".vbs": "VBScript",
              ".bas": "BASIC", ".asm": "Assembly", ".s": "Assembly", ".f90": "Fortran", ".apex": "Apex", ".cls": "Apex/VBA"}
GENERATED_RX = re.compile(r"\.min\.(js|css)$|\.bundle\.js$|\.g\.dart$|\.freezed\.dart$|\.pb\.(go|cc|h)$|_pb2(_grpc)?\.py$|"
                          r"\.generated\.|\.[Dd]esigner\.cs$|(^|/)(generated|gen)/")

# (category, label, patterns): a basename glob, or a path glob when it contains "/" (matched at any depth)
SIGNALS: list[tuple[str, str, list[str]]] = [
    ("type", "Web frontend", ["angular.json", ".angular-cli.json", "bower.json", "next.config.*", "nuxt.config.*", "vite.config.*",
                              "svelte.config.*", "ember-cli-build.js", "gatsby-config.*", "astro.config.*", "remix.config.*",
                              "webpack.config.*", "Gruntfile.*", "gulpfile.*", "index.html"]),
    ("type", "Service / backend", ["manage.py", "wsgi.py", "asgi.py", "*Application.java", "*Application.kt", "Startup.cs",
                                   "server.*", "application*.properties", "application*.y*ml", "appsettings*.json", "openapi*.*",
                                   "swagger*.*"]),
    ("type", "Mobile — Android", ["AndroidManifest.xml"]),
    ("type", "Mobile / desktop — Apple (Xcode)", ["*.xcodeproj/*", "*.xcworkspace/*", "Podfile", "Cartfile", "Info.plist",
                                                  "AppDelegate.*", "*App.swift"]),
    ("type", "Mobile — cross-platform", ["pubspec.yaml", "metro.config.*", "capacitor.config.*", "ionic.config.json", "config.xml",
                                         "eas.json"]),
    ("type", "Desktop", ["electron-builder.*", "forge.config.*", "tauri.conf.json", "*.pro", "*.ui", "App.xaml", "MainWindow.*",
                         "Package.appxmanifest", "*.wxs", "*.iss", "*.nsi", "*.desktop", "snapcraft.yaml", "*.vcxproj",
                         "*.qrc", "*.rc"]),
    ("type", "Game", ["ProjectSettings/ProjectVersion.txt", "*.unity", "*.uproject", "project.godot", "*.tscn", "*.gamemaker"]),
    ("type", "Embedded / firmware / hardware", ["platformio.ini", "*.ino", "sdkconfig*", "Kconfig", "west.yml", "prj.conf", "*.ioc",
                                               "*.ld", "*.dts", "*.dtsi", "*.v", "*.sv", "*.vhd", "*.xdc"]),
    ("type", "Library / package", ["*.gemspec", "*.nuspec", "*.podspec", "MANIFEST.in", ".npmignore", "*.cabal",
                                   "library.properties", "DESCRIPTION", "setup.py"]),
    ("type", "Command-line tool", ["cmd/*/main.go", "__main__.py", "cli.*", "bin/*"]),
    ("type", "Data / ML / analytics", ["*.ipynb", "dvc.yaml", "MLproject", "dbt_project.yml", "dags/*", "environment.y*ml",
                                       "*.pbix", "*.twb", "*.sas", "*.dvc"]),
    ("type", "Extension / plugin / app manifest", ["manifest.json", "plugin.xml", "*.vsixmanifest", "*.uplugin", "*.xpi", "*.oxt"]),
    ("type", "Infrastructure / platform code", ["*.tf", "Pulumi.y*ml", "cdk.json", "*.bicep", "Chart.yaml", "kustomization.y*ml",
                                                "ansible.cfg", "playbook*.y*ml", "Vagrantfile", "*.nomad"]),
    ("type", "Enterprise platform", ["sfdx-project.json", "*.abap", "*.cbl", "*.cob", "*.jcl", "*.bsp", "*.xsjs"]),
    ("build", "JavaScript / TypeScript", ["package.json", "pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json", "deno.json*",
                                          "tsconfig.json"]),
    ("build", "Python", ["pyproject.toml", "setup.cfg", "requirements*.txt", "Pipfile", "environment.y*ml", "tox.ini", "noxfile.py"]),
    ("build", "JVM / Android", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle*", "build.sbt", "build.xml"]),
    ("build", ".NET", ["*.sln", "*.csproj", "*.fsproj", "*.vbproj", "Directory.Build.props", "global.json"]),
    ("build", "Native (C/C++/other)", ["CMakeLists.txt", "meson.build", "configure.ac", "SConstruct", "conanfile.*", "vcpkg.json",
                                       "*.vcxproj", "Makefile", "*.mk", "BUILD.bazel", "WORKSPACE", "MODULE.bazel", "BUCK", "build.zig"]),
    ("build", "Other ecosystems", ["go.mod", "Cargo.toml", "Gemfile", "composer.json", "mix.exs", "rebar.config", "pubspec.yaml",
                                   "Package.swift", "stack.yaml", "dune-project", "elm.json", "Project.toml", "flake.nix",
                                   "default.nix", "justfile", "Taskfile.y*ml"]),
    ("run", "Containers", ["Dockerfile*", "docker-compose*.y*ml", "compose.y*ml", "Containerfile", ".devcontainer/*"]),
    ("run", "Hosting / serverless (any provider)", ["Procfile", "app.yaml", "host.json", "function_app.py", "template.y*ml",
                                                    "samconfig.toml", "serverless.y*ml", "firebase.json", "vercel.json", "netlify.toml",
                                                    "fly.toml", "render.yaml", "wrangler.toml", "appspec.yml", ".ebextensions/*",
                                                    "manifest.y*ml", "*.service", "nginx*.conf", "web.config", "*.pubxml"]),
    ("run", "Distribution (stores, installers, registries)", ["fastlane/*", "*.entitlements", "*.mobileprovision", "*.wxs", "*.iss",
                                                              "*.nsi", "snapcraft.yaml", "*.spec", "electron-builder.*",
                                                              ".npmrc", ".pypirc", "*.nuspec", "*.podspec", "*.gemspec"]),
    ("ci", "CI / release pipelines", [".github/workflows/*", ".gitlab-ci.yml", "azure-pipelines*.y*ml", "Jenkinsfile", ".circleci/*",
                                      "bitbucket-pipelines.yml", ".travis.yml", "appveyor.yml", ".buildkite/*", ".drone.yml",
                                      "buildspec.yml", "cloudbuild.y*ml", "bitrise.yml", "codemagic.yaml", ".woodpecker.y*ml",
                                      ".teamcity/*", ".semaphore/*", "Fastfile"]),
    ("api", "Interfaces, contracts, persistence", ["openapi*.*", "swagger*.*", "*.proto", "*.graphql", "*.wsdl", "*.xsd", "*.avsc",
                                                   "asyncapi*.*", "schema.prisma", "*.edmx", "*.xcdatamodeld/*", "alembic.ini",
                                                   "*.sql", "*.dbml", ".env.example", ".env.sample", "*.env.example"]),
]
CATEGORIES = {"type": "Software type signals (hints: confirm in /onboard; a repository can be several)",
              "build": "Build and dependencies", "run": "Runtime, hosting, distribution (any provider or channel)",
              "ci": "CI and release pipelines", "api": "Interfaces, contracts, persistence"}
DOCS = ["README*", "CONTRIBUTING*", "CHANGELOG*", "ARCHITECTURE*", "AGENTS.md", "CLAUDE.md", ".cursorrules",
        ".github/copilot-instructions.md", "docs/*", "doc/*", "adr/*", "*/adr/*", "decisions/*", "wiki/*"]
ENTRY = ["main.*", "Main.*", "app.*", "App.*", "index.*", "server.*", "manage.py", "wsgi.py", "asgi.py", "Program.*",
         "Startup.cs", "*Application.java", "*Application.kt", "MainActivity.*", "MainApplication.*", "AppDelegate.*",
         "*App.swift", "main.dart", "App.xaml.cs", "MainWindow.*", "cli.*", "__main__.py", "handler.*", "lambda_function.py",
         "function_app.py", "*.ino", "cmd/*/main.go", "src/main.rs", "src/lib.rs"]
TEST_RX = re.compile(r"(^|/)(tests?|__tests__|specs?|e2e|testing|androidTest|[\w.-]*[._-][Tt]ests?|[\w.-]*Tests?|integration[-_]?tests?)/|"
                     r"(^|/)test_[^/]+\.(py|c|cpp)$|_test\.(py|go|dart|c|cc|cpp|rs|exs)$|\.(test|spec)\.[a-z]+$|"
                     r"Tests?\.(java|kt|cs|swift|m|php)$|_spec\.rb$")
MAX_BYTES = 2_000_000


def tracked_files(root: str) -> tuple[list[str], int]:
    """(files of the codebase, number of vendored files left out)."""
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=True).stdout
        files = [f for f in out.splitlines() if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for d, dirs, names in os.walk(root):
            dirs[:] = sorted(x for x in dirs if x not in BUILD_OUT and x != ".git")
            files += [os.path.relpath(os.path.join(d, n), root) for n in names]
    kept = [f for f in files if not any(part in VENDORED for part in f.split("/")[:-1])]
    return sorted(kept), len(files) - len(kept)


def workflow_owned(root: str) -> set[str]:
    owned = set(WF_FILES)
    for manifest in ("workflow/.installed", "workflow/.generated"):
        p = os.path.join(root, manifest)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                owned |= {line.strip() for line in f if line.strip()}
    return owned


def codebase(root: str) -> tuple[list[str], int]:
    owned = workflow_owned(root)
    files, vendored = tracked_files(root)
    return [f for f in files if f not in owned and not f.startswith(WF_PREFIXES)], vendored


def count_lines(p: str) -> int:
    try:
        if os.path.getsize(p) > MAX_BYTES:
            return 0
        with open(p, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def match(f: str, patterns: list[str]) -> bool:
    base = os.path.basename(f)
    return any(fnmatch.fnmatchcase(f, p) or fnmatch.fnmatchcase(f, "*/" + p) if "/" in p else fnmatch.fnmatchcase(base, p)
               for p in patterns)


def signals(files: list[str], depth: int = 99) -> dict[str, dict[str, list[str]]]:
    """category → label → matching files (shallowest first)."""
    out: dict[str, dict[str, list[str]]] = defaultdict(dict)
    shallow = sorted((f for f in files if f.count("/") < depth), key=lambda f: (f.count("/"), f))
    for cat, label, pats in SIGNALS:
        hits = [f for f in shallow if match(f, pats)]
        if hits:
            out[cat][label] = hits
    return out


def git(root: str, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


def capped(items: list[str], n: int) -> list[str]:
    return items[:n] + ([f"… {len(items) - n} more"] if len(items) > n else [])


def examples(paths: list[str], n: int = 3) -> str:
    return ", ".join(paths[:n]) + (f" (+{len(paths) - n})" if len(paths) > n else "")


# ---------------------------------------------------------------- stack detection

def detect_stack(root: str) -> dict[str, str]:
    """Best guess of [stack] summary/setup/test/lint. A hint only: commands stay empty when there is no canonical one
    (Xcode schemes, game engines, IDE-driven builds, …); /onboard confirms or fills them."""
    def has(p: str) -> bool:
        return os.path.exists(os.path.join(root, p))

    def text(p: str) -> str:
        try:
            with open(os.path.join(root, p), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    make_targets = set(re.findall(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", text("Makefile"), re.M))
    langs: list[str] = []
    cmd = {"setup": "", "test": "", "lint": ""}

    def put(setup: str = "", test: str = "", lint: str = "") -> None:
        for k, v in (("setup", setup), ("test", test), ("lint", lint)):
            cmd[k] = cmd[k] or v

    if has("package.json"):
        pm = "pnpm" if has("pnpm-lock.yaml") else "yarn" if has("yarn.lock") else "bun" if has("bun.lockb") else "npm"
        langs.append(f"Node.js ({pm})" + (" + TypeScript" if has("tsconfig.json") else ""))
        try:
            scripts = json.loads(text("package.json")).get("scripts", {})
        except ValueError:
            scripts = {}
        put(setup=("npm ci" if has("package-lock.json") else "npm install") if pm == "npm" else f"{pm} install")
        if "test" in scripts:
            put(test=f"{pm} test")
        if "lint" in scripts:
            put(lint=f"{pm} run lint")
    if has("deno.json") or has("deno.jsonc"):
        langs.append("Deno")
        put(test="deno test", lint="deno lint")
    if has("pyproject.toml") or has("requirements.txt") or has("setup.py") or has("Pipfile"):
        py = text("pyproject.toml")
        runner = "uv run " if has("uv.lock") else "poetry run " if has("poetry.lock") else "pipenv run " if has("Pipfile") else ""
        langs.append("Python" + (f" ({runner.split()[0]})" if runner else ""))
        put(setup="uv sync" if has("uv.lock") else "poetry install" if has("poetry.lock") else "pipenv install --dev" if has("Pipfile")
            else "pip install -r requirements.txt" if has("requirements.txt") else "pip install -e .")
        if "pytest" in py or has("pytest.ini") or has("conftest.py") or "pytest" in text("requirements-dev.txt") + text("requirements.txt"):
            put(test=f"{runner}pytest")
        if "[tool.ruff" in py or has("ruff.toml") or has(".ruff.toml"):
            put(lint=f"{runner}ruff check .")
        elif has(".flake8") or "flake8" in text("setup.cfg"):
            put(lint=f"{runner}flake8")
    if has("pubspec.yaml"):
        fl = "flutter" in text("pubspec.yaml")
        langs.append("Flutter" if fl else "Dart")
        put(setup=f"{'flutter' if fl else 'dart'} pub get", test=f"{'flutter' if fl else 'dart'} test",
            lint="flutter analyze" if fl else "dart analyze")
    if has("go.mod"):
        langs.append("Go")
        put(setup="go mod download", test="go test ./...", lint="go vet ./...")
    if has("Cargo.toml"):
        langs.append("Rust")
        put(setup="cargo build", test="cargo test", lint="cargo clippy -- -D warnings")
    if has("Package.swift"):
        langs.append("Swift (SwiftPM)")
        put(setup="swift build", test="swift test")
    if any(f.endswith((".xcodeproj", ".xcworkspace")) for f in os.listdir(root)):
        langs.append("Xcode project — the test command needs a scheme")
    if has("pom.xml"):
        mvn = "./mvnw" if has("mvnw") else "mvn"
        langs.append("JVM (Maven)")
        put(setup=f"{mvn} -B -q -DskipTests install", test=f"{mvn} -B test")
    if has("build.gradle") or has("build.gradle.kts"):
        gr = "./gradlew" if has("gradlew") else "gradle"
        android = "com.android" in text("build.gradle") + text("build.gradle.kts") + text("app/build.gradle") + text("app/build.gradle.kts")
        langs.append("Android (Gradle)" if android else "JVM (Gradle)")
        put(setup=f"{gr} assemble", test=f"{gr} test", lint=f"{gr} lint" if android else f"{gr} check -x test")
    if has("build.sbt"):
        langs.append("Scala (sbt)")
        put(setup="sbt compile", test="sbt test")
    if any(f.endswith((".sln", ".csproj")) for f in os.listdir(root)):
        langs.append(".NET")
        put(setup="dotnet restore", test="dotnet test", lint="dotnet format --verify-no-changes")
    if has("Gemfile"):
        langs.append("Ruby")
        put(setup="bundle install", test="bundle exec rspec" if has("spec") else "bundle exec rake test")
        if "rubocop" in text("Gemfile"):
            put(lint="bundle exec rubocop")
    if has("composer.json"):
        langs.append("PHP")
        put(setup="composer install", test="vendor/bin/phpunit")
    if has("mix.exs"):
        langs.append("Elixir")
        put(setup="mix deps.get", test="mix test", lint="mix credo")
    if has("stack.yaml"):
        langs.append("Haskell (stack)")
        put(setup="stack build --only-dependencies", test="stack test")
    if has("platformio.ini"):
        langs.append("Embedded (PlatformIO)")
        put(setup="pio pkg install", test="pio test", lint="pio check")
    if has("MODULE.bazel") or has("WORKSPACE") or has("WORKSPACE.bazel"):
        langs.append("Bazel")
        put(setup="bazel build //...", test="bazel test //...")
    if has("CMakeLists.txt"):
        langs.append("C/C++ (CMake)")
        put(setup="cmake -S . -B build && cmake --build build", test="ctest --test-dir build")
    elif has("meson.build"):
        langs.append("C/C++ (Meson)")
        put(setup="meson setup build && meson compile -C build", test="meson test -C build")
    if has("project.godot"):
        langs.append("Godot")
    if has("ProjectSettings/ProjectVersion.txt"):
        langs.append("Unity — tests run through the editor CLI")
    if any(f.endswith(".uproject") for f in os.listdir(root)):
        langs.append("Unreal Engine")
    if any(f.endswith(".tf") for f in os.listdir(root)):
        langs.append("Terraform")
        put(lint="terraform fmt -check -recursive")
    # an existing Makefile target wins: the team already uses it
    for k, alts in (("setup", ("setup", "install", "bootstrap")), ("test", ("test",)), ("lint", ("lint",))):
        hit = next((t for t in alts if t in make_targets), None)
        if hit:
            cmd[k] = f"make {hit}"
    return {"summary": ", ".join(langs) + (" (detected from manifests, to be confirmed by /onboard)" if langs else ""), **cmd}


# ---------------------------------------------------------------- map

def repo_data(root: str = wf.ROOT) -> dict:
    """The map as data (complete lists; the text view caps them). Also the input of portals and analyzers."""
    files, vendored = codebase(root)
    generated = {f for f in files if GENERATED_RX.search(f)}
    lines = {f: count_lines(os.path.join(root, f)) for f in files
             if os.path.splitext(f)[1].lower() in SOURCE_EXT and f not in generated}
    name = (wf.project().get("project", {}).get("name") if os.path.abspath(root) == wf.ROOT else None) or os.path.basename(root)

    lang_files: Counter[str] = Counter()
    lang_lines: Counter[str] = Counter()
    for f, n in lines.items():
        lg = SOURCE_EXT[os.path.splitext(f)[1].lower()]
        lang_files[lg] += 1
        lang_lines[lg] += n
    other = Counter(os.path.splitext(f)[1].lower() or os.path.basename(f) for f in files if f not in lines)

    # directories up to depth 3 with file count and source lines
    dfiles: Counter[str] = Counter()
    dlines: Counter[str] = Counter()
    for f in files:
        parts = f.split("/")[:-1]
        for k in range(1, min(len(parts), 3) + 1):
            d = "/".join(parts[:k])
            dfiles[d] += 1
            dlines[d] += lines.get(f, 0)

    tests = [f for f in files if TEST_RX.search(f)]
    git_info = None
    if os.path.isdir(os.path.join(root, ".git")):
        log = git(root, "log", "--format=%ad %ae", "--date=short")
        rows = [r.split(" ", 1) for r in log.splitlines() if r]
        if rows:
            churn = Counter(f for f in git(root, "log", "--since=180 days ago", "--name-only", "--format=").splitlines()
                            if f and f in lines)
            git_info = {"commits": len(rows), "first": rows[-1][0], "last": rows[0][0],
                        "authors": len({r[1] for r in rows if len(r) > 1}), "churn_180d": dict(churn.most_common())}
    return {
        "name": name, "files": len(files), "source_files": len(lines), "source_lines": sum(lines.values()),
        "generated": len(generated), "vendored": vendored,
        "languages": [{"language": lg, "lines": n, "files": lang_files[lg]} for lg, n in lang_lines.most_common()],
        "other_types": dict(other.most_common()),
        "signals": signals(files),
        "dirs": [{"dir": d, "files": dfiles[d], "lines": dlines[d]} for d in dfiles],
        "root_files": [f for f in files if "/" not in f],
        "docs": sorted((f for f in files if match(f, DOCS)), key=lambda f: (f.count("/"), f)),
        "migrations": sorted({os.path.dirname(f) for f in files if re.search(r"(^|/)(migrations|migrate|alembic|db/migrate|flyway|liquibase)/", f)}),
        "entry_points": sorted((f for f in files if match(f, ENTRY) and f in lines and not TEST_RX.search(f)), key=lambda f: (f.count("/"), f)),
        "tests": tests,
        "source_sizes": dict(sorted(lines.items(), key=lambda x: -x[1])),
        "git": git_info,
        "stack": detect_stack(root),
    }


def repo_map(root: str = wf.ROOT) -> str:
    d = repo_data(root)
    out = [f"# Repository map — {d['name']}",
           f"{d['files']} files · {d['source_files']} source files · {d['source_lines']} source lines · {d['generated']} generated/minified · "
           f"{d['vendored']} vendored files not mapped (workflow files excluded; no contents shown)", ""]
    out += ["## Languages (lines · files)"] + [f"- {x['language']}: {x['lines']} · {x['files']}" for x in d["languages"][:10]]
    if d["other_types"]:
        out.append("- other file types (files): " + ", ".join(f"{e} {n}" for e, n in list(d["other_types"].items())[:15]))
    out.append("")

    for cat, title in CATEGORIES.items():
        rows = [f"- {label}: {examples(paths)}" for label, paths in d["signals"].get(cat, {}).items()]
        out += [f"## {title}"] + (rows or ["- none"]) + [""]

    dirs = {x["dir"]: x for x in d["dirs"]}
    children: dict[str, list[str]] = defaultdict(list)
    for k in dirs:
        children[k.rpartition("/")[0]].append(k)
    tree: list[str] = []

    def walk(parent: str, depth: int) -> None:
        for k in sorted(children.get(parent, []), key=lambda x: (-dirs[x]["lines"], -dirs[x]["files"], x))[:12]:
            tree.append(f"{'  ' * depth}- {k.rpartition('/')[2]}/ ({dirs[k]['files']} files, {dirs[k]['lines']} lines)")
            if depth < 2:
                walk(k, depth + 1)

    walk("", 0)
    out += ["## Directory tree (depth ≤ 3, largest first)"] + capped(tree, 45) + [""]
    rf = d["root_files"]
    out += ["## Root files", ", ".join(rf[:40]) + (f" … +{len(rf) - 40}" if len(rf) > 40 else "") or "- none", ""]
    out += ["## Docs and existing agent rules"] + (capped([f"- {f}" for f in d["docs"]], 12) or ["- none"]) + [""]
    if d["migrations"]:
        out += ["## Database migrations"] + capped([f"- {m}/" for m in d["migrations"]], 5) + [""]
    out += ["## Likely entry points"] + (capped([f"- {f}" for f in d["entry_points"]], 12) or ["- none found"]) + [""]

    tdirs = Counter("/".join(f.split("/")[:2]) if "/" in f else "." for f in d["tests"])
    out += [f"## Tests: {len(d['tests'])} files"] + capped([f"- {k} ({n})" for k, n in tdirs.most_common()], 8) + [""]
    out += ["## Largest source files (generated excluded)"] + [f"- {f} ({n} lines)" for f, n in list(d["source_sizes"].items())[:10]] + [""]

    g = d["git"]
    if g:
        out += ["## Git", f"- {g['commits']} commits · {g['first']} → {g['last']} · {g['authors']} authors"]
        if g["churn_180d"]:
            out.append("- most changed source files in the last 180 days: " +
                       ", ".join(f"{f} ({n})" for f, n in list(g["churn_180d"].items())[:8]))
        out.append("")
    out += ["## Stack commands detected (project.toml [stack] candidates)"] + [f"- {k}: {v or '—'}" for k, v in d["stack"].items()]
    return "\n".join(out)


if __name__ == "__main__":
    if "--json" in sys.argv:
        wf.dump_json(repo_data())
    else:
        print(repo_map())
