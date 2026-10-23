---
phase: 01-walking-skeleton-hosting-verification
plan: 02
subsystem: config
tags: [pydantic-settings, SecretStr, typer, dotenv, fail-fast, env-example]

requires:
  - phase: 01-walking-skeleton-hosting-verification
    plan: 01
    provides: uv workspace, pinned dependencies (pydantic 2.12.5, pydantic-settings, typer), ruff/mypy/pytest configuration
provides:
  - khetsetu_backend.config (Settings with 13 fields, AppEnv, LogLevel, DatasetMode, SettingProblem, SettingsError, load_settings, env_var_name)
  - khetsetu_backend.logging_setup.configure_logging (idempotent, stdlib only)
  - khetsetu CLI with `config check` (exit 0 valid, exit 2 invalid) and the `khetsetu` console script
  - Committed .env.example documenting all 13 settings, HF_TOKEN blank
  - docs/configuration.md reference, root README.md, backend/README.md
  - Hermetic test environment (conftest.py hermetic_environment, isolated_cwd)
  - Drift tests tying Settings, .env.example and docs/configuration.md together
affects: [01-03, 01-04, 01-05, 01-06, 01-07]

# Uncommitted at user request, so commits is a measured 0
commits: 0
plan_head_before: df765d608436fe10f308cc2c062ed55d29b83279
plan_head_after: df765d608436fe10f308cc2c062ed55d29b83279

actuals:
  tokens: 9900   # chars/4 over the 14 files written/edited (39,563 chars), excluding uv.lock
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "Env var name (not Python field) is what users see: errors map pydantic locations back through Settings.model_fields"
    - "SettingsError is built from each error's location and message only, never str(ValidationError) and never the input"
    - "No global settings object: load_settings() once at startup, pass the object down"
    - "Template/model/docs lockstep enforced by tests that derive names from Settings.model_fields"

key-files:
  created:
    - backend/src/khetsetu_backend/config.py
    - backend/src/khetsetu_backend/logging_setup.py
    - backend/src/khetsetu_backend/cli.py
    - .env.example
    - conftest.py
    - README.md
    - backend/README.md
    - docs/configuration.md
    - backend/tests/test_backend_config.py
    - backend/tests/test_backend_cli.py
    - backend/tests/test_backend_env_example.py
    - backend/tests/test_backend_logging.py
    - backend/tests/test_backend_docs.py
  modified:
    - backend/pyproject.toml

key-decisions:
  - "Env var names are the contract: KHETSETU_ prefix for app settings; HF_TOKEN and HF_SPACE_ID (alias SPACE_ID) stay unprefixed per Hugging Face convention"
  - "SettingsError renders `ENV_VAR: message` lines; the Space guard message states the rule and the line prefix names KHETSETU_DATASET_MODE"
  - "dataset_revision pattern requires an alphanumeric first character so a value can never look like a command-line option"
  - "Short rejected values (like 0) legitimately occur inside pydantic messages, so the rejected-value-not-echoed assertion only applies to values longer than 3 characters; the secret leak test covers the real risk"

patterns-established:
  - "Pattern 1: tests that call load_settings use env_file=None or the isolated_cwd fixture"
  - "Pattern 2: add a setting = field + .env.example entry + docs row; two tests fail otherwise"

requirements-completed: [FND-01]

coverage:
  - id: D1
    description: "Missing or invalid KHETSETU_APP_ENV fails immediately, names the variable, lists local/ci/space, and does not echo the rejected value"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_config.py#test_missing_app_env_names_the_variable_and_says_required, #test_invalid_app_env_lists_allowed_values_without_echoing_input"
        status: pass
    human_judgment: false
  - id: D2
    description: "Several invalid settings are reported in one error, each by env var name; invalid values for port, sizes, repo id, revision, model, space id and log level are each named exactly"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_config.py#test_invalid_value_names_the_exact_variable (10 cases), #test_several_problems_are_reported_in_one_error"
        status: pass
    human_judgment: false
  - id: D3
    description: "cp .env.example .env then `khetsetu config check` gives a valid configuration (exit 0, HF_TOKEN=(unset)); a missing setting exits 2 naming the variable, proven through the installed console script"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_cli.py (4 tests, including the subprocess console-script test)"
        status: pass
      - kind: integration
        ref: "manual run of .venv/bin/khetsetu in a clean temp directory: template exit 0; two bad settings exit 2 naming both; space+blocking exit 2 naming KHETSETU_DATASET_MODE"
        status: pass
    human_judgment: false
  - id: D4
    description: "HF_TOKEN is a SecretStr absent from repr, str, model_dump, model_dump_json, CLI output and error text; .env.example ships it blank"
    requirement: FND-02
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_config.py#test_secret_never_appears_in_any_rendering, backend/tests/test_backend_env_example.py#test_secret_settings_are_blank_in_the_template"
        status: pass
    human_judgment: false
  - id: D5
    description: "A deployed Space (KHETSETU_APP_ENV=space) cannot be configured with blocking dataset mode; effective dataset mode is blocking locally and off on ci and space"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_config.py#test_space_cannot_use_blocking_dataset_mode, #test_effective_dataset_mode (5 cases)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every Settings field has an entry in .env.example and a row in docs/configuration.md; tests fail on drift; the template loads as a valid configuration"
    requirement: FND-02
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_env_example.py (5 tests), backend/tests/test_backend_docs.py (3 tests)"
        status: pass
    human_judgment: false
  - id: D7
    description: "configure_logging sets the root level from settings and is idempotent (no duplicate handler)"
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_logging.py (2 tests)"
        status: pass
    human_judgment: false
  - id: D8
    description: "Secret scan of the repository (the other half of FND-02)"
    requirement: FND-02
    verification:
      - kind: other
        ref: "not in this plan: delivered by plan 01-03"
        status: skipped
    human_judgment: false

duration: 15min
completed: 2026-10-24
status: complete
---

# Phase 1 Plan 02: Typed settings, fail-fast config check and .env.example Summary

**pydantic-settings `Settings` (13 fields, SecretStr token, Space guard) with a `khetsetu config check` CLI that exits 2 naming every bad environment variable, plus a committed `.env.example`, a configuration reference and drift tests that keep all three in lockstep**

## Performance

- **Duration:** ~15 min (start time was not captured; estimated)
- **Completed:** 2026-10-24
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 TDD, Task 3 auto)
- **Files created:** 13, modified: 1 (`backend/pyproject.toml`)
- **Commits:** 0 (user instruction: "do not commit changes, i will commit myself")

## Accomplishments

- FND-01: `load_settings()` turns a missing or invalid `KHETSETU_APP_ENV` (or any of the other 12 settings) into a `SettingsError` that lists every problem at once as `ENV_VAR: message`. Messages are assembled only from each pydantic error's location and message, so neither a rejected value nor a secret can be echoed. Pydantic locations are mapped back to environment variable names (alias when present, else `KHETSETU_` plus the upper-cased field).
- Tracer: `.env` to `Settings` to `khetsetu config check` worked end to end first (two settings, six behaviours, including a real subprocess call to the installed `khetsetu` console script), then the model was completed. The tracer feedback gate (automated `<verify>` re-run) passed before expansion.
- Secret handling (T-01-03): `HF_TOKEN` is `SecretStr | None`; `redacted_items()` shows only `(set)`/`(unset)`; a runtime-built dummy token is proven absent from `repr`, `str`, `model_dump`, `model_dump_json`, CLI output (valid and invalid) and error text.
- Input validation (T-01-04): range constraints on port and sizes, regex on repo id, revision (sha or ref, no leading dash), Space id and model id; blocking dataset mode is rejected when `KHETSETU_APP_ENV=space`.
- FND-02 template half (T-01-05): `.env.example` documents all 13 settings under six headings, `HF_TOKEN=` is blank, and tests assert exact set equality between model, template and `docs/configuration.md`.
- Hermetic tests: root `conftest.py` scrubs `KHETSETU_*`, `HF_TOKEN`, `HF_SPACE_ID`, `SPACE_ID`, `HF_HUB_OFFLINE` for every test and provides `isolated_cwd`.

## Task Commits

No commits were made, by the user's instruction, overriding the plan's per-task commit protocol. All work is in the working tree in plan order.

1. **Task 1 (tracer): `.env` to Settings to `config check`** - uncommitted (8 tests green before expansion)
2. **Task 2 (TDD): full model, redaction, Space guard, logging, template test** - uncommitted (red first: collection failed on the missing `logging_setup`, then 40 green)
3. **Task 3: onboarding docs and docs drift test** - uncommitted (76 tests total green)

**Plan metadata:** not committed.

Suggested commit grouping for the user, staging explicit paths only (never `git add -A`; `data/`, `build/` and unrelated edits must stay out): (a) `backend/pyproject.toml`, `conftest.py`, `backend/src/khetsetu_backend/{config,cli}.py`, `.env.example`, `backend/tests/test_backend_{config,cli}.py`; (b) `backend/src/khetsetu_backend/logging_setup.py`, `backend/tests/test_backend_{env_example,logging}.py`; (c) `README.md`, `backend/README.md`, `docs/configuration.md`, `backend/tests/test_backend_docs.py`. Note `.env.example` and `uv.lock` must not be git-ignored (verified by the plan 01-01 hygiene tests).

## Files Created/Modified

- `backend/src/khetsetu_backend/config.py` - `Settings`, enums, `SettingsError`, `load_settings`, `env_var_name`
- `backend/src/khetsetu_backend/logging_setup.py` - `configure_logging`
- `backend/src/khetsetu_backend/cli.py` - `app`, `config_app`, `config check`
- `backend/pyproject.toml` - added `[project.scripts] khetsetu = "khetsetu_backend.cli:app"`
- `.env.example`, `docs/configuration.md`, `README.md`, `backend/README.md` - onboarding documents
- `conftest.py` - hermetic fixtures
- `backend/tests/test_backend_{config,cli,env_example,logging,docs}.py` - 41 new tests (76 total in the repo)

## Decisions Made

- Env var names are fixed here because the Space, CI and docs will copy them: `KHETSETU_*` for app settings, `HF_TOKEN`, `HF_SPACE_ID` (alias `SPACE_ID`) for Hugging Face conventions.
- `env_var_name()` is public in `config.py` so the CLI, error mapping and docs test share one rule; the env-example test deliberately re-derives names independently from `model_fields`, so a bug in the helper cannot hide drift.
- The dataset revision pin is the sha named in the plan; plan 01-05 must pin files at that revision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy `pydantic-alias` error on `AliasChoices`**
- **Found during:** Task 2 (`uv run mypy`)
- **Issue:** `warn_required_dynamic_aliases = true` (set in plan 01-01) rejects `validation_alias=AliasChoices(...)` on `hf_space_id` with "Required dynamic aliases disallowed".
- **Fix:** one targeted `# type: ignore[pydantic-alias]` on that field, with a comment explaining the SPACE_ID alias. The strict setting stays on for the rest of the code.
- **Files modified:** `backend/src/khetsetu_backend/config.py`

**2. [Rule 1 - Test bug] rejected-value assertion false positive**
- **Found during:** Task 2 (first full run)
- **Issue:** asserting that the rejected value is absent from the error text fails for values like `0`, because pydantic's own message ("greater than 0") contains it.
- **Fix:** the assertion applies only to values longer than 3 characters; the secret-leak test covers the real risk. Documented in key-decisions.
- **Files modified:** `backend/tests/test_backend_config.py`

**3. [Rule 1 - Lint] PERF403, TC002, RUF100, S105 findings in new code**
- **Fix:** dictionary comprehension, `pytest` import moved under `TYPE_CHECKING`, an unused `noqa` removed, and one justified `# noqa: S105` on a test comparing the display string `"(set)"` to `HF_TOKEN`'s item. No rule was disabled globally.

### Plan-adherence deviations caused by the no-commit instruction

**4. Commit-based protocol not followed**
- Per-task commits, the final docs commit, and any acceptance criterion depending on history are unsatisfiable. Working-tree equivalents were verified: every behaviour test, the CLI acceptance runs, and all quality gates. `git log` is unchanged at `df765d6`; nothing is staged.

### Scope notes

- FND-02 is only partly delivered here (template, docs and drift tests); the secret scan arrives in plan 01-03. FND-02 is therefore NOT marked complete.
- The plan's README acceptance criterion "quickstart run in a fresh clone" cannot be run without a commit. Equivalent verified instead: the three quickstart commands were run in order against the working tree (and `config check` against a copy of `.env.example` in a clean directory) with exit 0.
- `.planning/REQUIREMENTS.md`: FND-04 line left untouched, as instructed.

---

**Total deviations:** 3 auto-fixed (1 Rule 3, 2 Rule 1) plus 1 commit-related adjustment
**Impact on plan:** configuration correctness only; no scope creep.

## Issues Encountered

- A shell quoting slip (unquoted path containing a space) in one manual verification command; rerun with quoting, no project impact.
- The pinned pydantic 2.12.5 (from plan 01-01) behaved as expected for `env_ignore_empty`, `frozen` and `AliasChoices`.

## User Setup Required

None. To use the CLI locally: `cp .env.example .env` then `uv run khetsetu config check`. No real `.env` was created in the repository by this plan.

## Known Stubs

None. Every setting is wired into `Settings`, the CLI output, the template and the docs. Settings whose consumers arrive in later plans (server, upload limits, dataset, LLM) are intentionally unused so far, not stubs.

## Threat Flags

None beyond the plan's register. T-01-03, T-01-04 and T-01-05 are mitigated and tested; T-01-SC unchanged (no new dependency; `uv sync --locked` clean).

## Next Phase Readiness

- Plan 01-03 can add the secret scan (covering `.env.example`), Makefile, CI, import-linter contracts and the coverage floor on a green base.
- Plan 01-04 must call `load_settings()` once at startup and `configure_logging(settings)`; add `app.py` to mypy `files`.
- Plan 01-05 reads `data_dir`, `dataset_repo_id`, `dataset_revision` and `effective_dataset_mode`.
- Plan 01-06 fills the four README markers (run the app, dataset, quality gates, deploy).
- Open item for the user: all files are uncommitted; see suggested staging above.

## Self-Check: PASSED

- All 13 created files and the modified `backend/pyproject.toml` exist on disk (checked with `git status --short --untracked-files=all`).
- Zero commits: `git log --oneline | head -1` is `df765d6`; `git rev-list --count df765d6..HEAD` is 0; nothing staged.
- Final gates exit 0: `uv sync --locked --all-packages`, `ruff check .`, `ruff format --check .`, `mypy` (16 source files), `pytest -q` (76 passed).
- No `print(` in `backend/src`; no `.env` created in the repository; `.env.example` contains the line `HF_TOKEN=`.

---
*Phase: 01-walking-skeleton-hosting-verification*
*Completed: 2026-10-24*
