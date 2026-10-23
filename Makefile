.DEFAULT_GOAL := help

# Single source of truth for the quality gates (FND-04). CI calls these same targets, so a
# green `make check` locally means the CI quality job is green. No recipe hides a failure.

.PHONY: help sync lint type imports test secrets audit check hooks

help: ## List the available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/^([a-z]+):.*## (.*)$$/  \1\t\2/'

sync: ## Install the locked workspace into .venv
	uv sync --locked --all-packages

lint: ## ruff lint, then ruff format check
	uv run ruff check .
	uv run ruff format --check .

type: ## Strict mypy
	uv run mypy

imports: ## import-linter: frontend/backend/contracts boundaries
	uv run lint-imports

test: ## pytest with coverage (floor in pyproject.toml)
	uv run pytest --cov --cov-report=term-missing:skip-covered

secrets: ## gitleaks over the FULL git history (run scripts/install_gitleaks.sh first)
	scripts/gitleaks.sh history

audit: ## pip-audit over the exported runtime dependency set
	mkdir -p build
	uv export --locked --no-dev --no-hashes --no-emit-workspace --package khetsetu --output-file build/audit-requirements.txt
	uv run pip-audit --requirement build/audit-requirements.txt --no-deps --disable-pip --progress-spinner off

check: lint type imports test ## Every local quality gate (what the CI quality job runs)

hooks: ## Install the git pre-commit hooks (one-time per clone)
	uv run pre-commit install
