# Workflow targets (stdlib Python >= 3.11, no dependencies). Stack targets read project.toml [stack].
.PHONY: help next context check backlog agents test-tools setup test lint codex-prompts adopt

PY ?= python3
STACK = $(PY) -c "import tomllib,sys;print(tomllib.load(open('project.toml','rb'))['stack'].get(sys.argv[1],''))"

help:
	@echo "make next | context STEP=<step> IDS='<ID…>' | check | backlog | agents | test-tools | setup | test | lint | adopt TARGET=<repo>"

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

test-tools:      ## tests of the workflow tools
	@$(PY) -m unittest discover -s tools/tests -q

setup test lint: ## stack commands, defined by /architecture in project.toml [stack]
	@cmd="$$($(STACK) $@)"; if [ -z "$$cmd" ]; then echo "[stack] $@ not defined yet: run /architecture"; exit 1; fi; echo "$$cmd"; sh -c "$$cmd"

codex-prompts:   ## Codex CLI reads prompts from ~/.codex/prompts: link this project's prompts there
	@mkdir -p $${CODEX_HOME:-$$HOME/.codex}/prompts; for f in .codex/prompts/*.md; do ln -sf "$$PWD/$$f" "$${CODEX_HOME:-$$HOME/.codex}/prompts/$$(basename $$f)"; done; echo "linked: /prompts:<name> in Codex (last linked project wins on name clashes)"

adopt:           ## install the workflow into an existing repository: make adopt TARGET=../my-app [ARGS="--prefix MA"]
	@if [ -z "$(TARGET)" ]; then echo "usage: make adopt TARGET=<path of the existing repository> [ARGS='--prefix MA --dry-run']"; exit 1; fi
	@$(PY) tools/adopt.py "$(TARGET)" $(ARGS)
