# Workflow targets (stdlib Python >= 3.11, no dependencies). Stack targets read project.toml [stack].
.PHONY: help next context check backlog agents usage approve claim sync-skeleton gates secrets hooks test-tools setup test lint run portal adopt

PY ?= python3
STACK = $(PY) -c "import tomllib,sys;print(tomllib.load(open('project.toml','rb'))['stack'].get(sys.argv[1],''))"

help:
	@echo "make next | context STEP=<step> IDS='<ID…>' | check | backlog | agents | usage DAYS=7 | approve ID=<ID> GATE=<gate> | test-tools | setup | test | lint | run | adopt TARGET=<repo>"

next:            ## next workflow step (deterministic)
	@$(PY) tools/next_step.py

context:         ## context budget of a step: make context STEP=analysis IDS="PR0101 PR0102"
	@$(PY) tools/context.py $(STEP) $(IDS)

check:           ## workflow consistency + adapters up to date
	@$(PY) tools/check_workflow.py

backlog:         ## regenerate Story files, epic pages, overview from backlog/stories.toml
	@$(PY) tools/gen_backlog.py

agents:          ## regenerate tool adapters from workflow/ + models.toml
	@$(PY) tools/render_agents.py

approve:         ## YOU pass a human gate, committed alone with Approved-by/at: GATE=spec|strategy|tuning|deviation:<n>|spike|refined ID=<ID> · GATE=inception FILE=<file> · GATE=stack
	@$(PY) tools/approve.py --gate "$(GATE)" $(if $(ID),--id "$(ID)") $(if $(FILE),--file "$(FILE)")

claim:           ## team use: claim a story (branch, claim in stories.toml, push): make claim ID=PR0101 [WORKTREE=1] [ME="name"]
	@$(PY) tools/claim.py "$(ID)" $(if $(WORKTREE),--worktree) $(if $(ME),--me "$(ME)")

sync-skeleton:   ## upgrade the workflow files to the latest skeleton (3-way, nothing written on conflict): [SKELETON=<path|url>] [ARGS="--dry-run | --keep <file> | --take <file>"]
	@$(PY) tools/sync_skeleton.py $(if $(SKELETON),--from "$(SKELETON)") $(ARGS)

gates:           ## quality gates of project.toml [gates] + [stack] test/lint, written into RUN §8: make gates ID=PR0101
	@$(PY) tools/quality_gates.py "$(ID)"

secrets:         ## secret scan of the repository (code and artifacts); make secrets ARGS=--branch
	@$(PY) tools/secret_scan.py $(ARGS)

hooks:           ## install the git pre-commit hook: secret scan of the staged content (gitleaks too, when installed)
	@printf '#!/bin/sh\n# installed by make hooks\n%s tools/secret_scan.py --staged || exit 1\nif command -v gitleaks >/dev/null 2>&1; then gitleaks protect --staged --no-banner || exit 1; fi\n' "$(PY)" > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit && echo "pre-commit hook installed"

usage:           ## agent sessions, tier share, context peaks and supervision signals from local logs: make usage DAYS=30
	@$(PY) tools/usage.py --days $(or $(DAYS),7)

test-tools:      ## tests of the workflow tools
	@$(PY) -m unittest discover -s tools/tests -q

setup test lint: ## stack commands, defined by /architecture in project.toml [stack]
	@cmd="$$($(STACK) $@)"; if [ -z "$$cmd" ]; then echo "[stack] $@ not defined yet: run /architecture"; exit 1; fi; echo "$$cmd"; sh -c "$$cmd"

run:             ## start the app locally and open it in the browser: project.toml [stack] run / url
	@$(PY) tools/launch.py

portal:          ## start the agentic portal for this repository (project.toml [portal] version); python tools/portal.py without make
	@$(PY) tools/portal.py

adopt:           ## install the workflow into an existing repository: make adopt TARGET=../my-app [ARGS="--prefix MA"]
	@if [ -z "$(TARGET)" ]; then echo "usage: make adopt TARGET=<path of the existing repository> [ARGS='--prefix MA --dry-run']"; exit 1; fi
	@$(PY) tools/adopt.py "$(TARGET)" $(ARGS)
