---
phase: 01-walking-skeleton-hosting-verification
plan: 01
subsystem: infra
tags: [uv-workspace, hatchling, ruff, mypy-strict, pytest, gitignore, gradio-6.30.0, pydantic]

requires:
  - phase: none
    provides: first plan of the first phase
provides:
  - Root-anchored .gitignore keeping data/, secrets, weights and caches out of git
  - uv workspace (root app project khetsetu plus members contracts, backend, frontend) with one hash-pinned uv.lock
  - Importable, py.typed packages khetsetu_contracts, khetsetu_backend, khetsetu_frontend (all __version__ 0.1.0)
  - ruff, strict mypy (pydantic plugin), pytest and coverage configuration, one command each
  - Guard tests for OPS-03 (tests/test_repo_hygiene.py) and FND-06 dependency direction (tests/test_workspace.py)
  - Answer to the Space install-order question - gradio[oauth,mcp]==6.30.0 forces pydantic <=2.12.5
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07]

# Uncommitted at user request, so commits is a measured 0
commits: 0
plan_head_before: df765d608436fe10f308cc2c062ed55d29b83279
plan_head_after: df765d608436fe10f308cc2c062ed55d29b83279

actuals:
  tokens: 44600   # chars/4 over the 15 files written/edited (incl. uv.lock, ~162k chars)
  tasks: 3
  commits: 0

tech-stack:
  added: [uv workspace, hatchling, pydantic 2.12.5, pydantic-settings 2.16.1, pillow 12.3.0, typer 0.27.3, gradio 6.30.0, gradio-client 2.7.2, huggingface-hub 2.3.0, pyarrow, pyyaml, ruff, mypy, pytest, pytest-cov, import-linter, pre-commit, pip-audit, types-PyYAML]
  patterns:
    - "src layout per package with hatchling, single version source in __init__.py read by hatch"
    - "Root-anchored ignore rules so code package backend/src/khetsetu_backend/data/ stays trackable"
    - "Dependency direction asserted by a test that parses each pyproject (tomllib + packaging)"
    - "Tests relax S101/ANN/D/PLR2004 only via per-file-ignores; no global rule weakened"

key-files:
  created:
    - .gitignore
    - .python-version
    - pyproject.toml
    - uv.lock
    - backend/pyproject.toml
    - backend/src/khetsetu_backend/__init__.py
    - backend/src/khetsetu_backend/py.typed
    - contracts/pyproject.toml
    - contracts/src/khetsetu_contracts/__init__.py
    - contracts/src/khetsetu_contracts/py.typed
    - frontend/pyproject.toml
    - frontend/src/khetsetu_frontend/__init__.py
    - frontend/src/khetsetu_frontend/py.typed
    - contracts/tests/test_contracts_package.py
    - backend/tests/test_backend_package.py
    - frontend/tests/test_frontend_package.py
    - tests/test_repo_hygiene.py
    - tests/test_workspace.py
  modified: []

key-decisions:
  - "Added [tool.uv] constraint-dependencies pydantic>=2.11.10,<=2.12.5 because gradio[oauth,mcp]==6.30.0 (the Space install step) is unsatisfiable with pydantic 2.14.1"
  - "ruff extend-exclude of .claude and .planning: third-party skill scripts there are not project source"
  - "Kept the pre-existing root .gitignore unchanged; it already matched the plan rules"

patterns-established:
  - "Pattern 1: one lockfile for the whole phase; later plans do not edit dependency tables"
  - "Pattern 2: guard tests shell out to git (check-ignore --no-index) and skip when git or .git is absent"

requirements-completed: [FND-06, OPS-03]

coverage:
  - id: D1
    description: "data/, .env files, weights, parquet and caches are git-ignored while .env.example, uv.lock, .planning/ and backend/src/khetsetu_backend/data/ are not"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_ignored_paths and #test_not_ignored_paths (10 + 9 cases)"
        status: pass
    human_judgment: false
  - id: D2
    description: "No commit ever tracked data/ or weight/secret files; working tree shows no untracked data/; index holds no forbidden files"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_history_never_tracked_data, #test_working_tree_has_no_untracked_data, #test_index_has_no_forbidden_files"
        status: pass
    human_judgment: false
  - id: D3
    description: "uv workspace with exactly contracts, backend, frontend members syncs from uv.lock with --locked --all-packages"
    requirement: FND-06
    verification:
      - kind: integration
        ref: "uv sync --locked --all-packages"
        status: pass
      - kind: unit
        ref: "tests/test_workspace.py#test_workspace_members_are_the_three_packages"
        status: pass
    human_judgment: false
  - id: D4
    description: "Dependency direction enforced: contracts is a leaf, backend and frontend depend on contracts only, frontend never on backend, root depends on all three and is unpackaged; gradio==6.30.0 exact, pillow >=12,<13"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "tests/test_workspace.py (7 tests)"
        status: pass
      - kind: other
        ref: "uv tree --package khetsetu-frontend lists khetsetu-contracts and not khetsetu-backend"
        status: pass
    human_judgment: false
  - id: D5
    description: "Each package imports, exposes __version__ 0.1.0 and ships a py.typed marker"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "contracts/tests/test_contracts_package.py, backend/tests/test_backend_package.py, frontend/tests/test_frontend_package.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "ruff check, ruff format --check, strict mypy and pytest each pass with one command from the repo root"
    verification:
      - kind: other
        ref: "uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest -q"
        status: pass
    human_judgment: false
  - id: D7
    description: "Space install-order resolution check answered: gradio[oauth,mcp]==6.30.0 plus exported runtime requirements resolves under the pydantic <=2.12.5 constraint"
    verification:
      - kind: other
        ref: "uv pip install --dry-run 'gradio[oauth,mcp]==6.30.0' -r build/resolve-check.txt (exit 0)"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-23
status: complete
---

# Phase 1 Plan 01: Repository hygiene and uv workspace skeleton Summary

**Root-anchored `.gitignore` plus a three-member uv workspace (contracts, backend, frontend) locked once, with ruff, strict mypy and pytest green and a pydantic <=2.12.5 constraint forced by Gradio's `mcp` extra**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-23T19:03:32Z
- **Completed:** 2026-10-23T19:07:00Z
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 TDD, Task 3 auto)
- **Files created:** 18 (plus 0 modified tracked files)
- **Commits:** 0 (user instruction: "do not commit changes, i will commit myself")

## Accomplishments

- OPS-03: the 823 MB `data/` directory, `.env` files, weights, parquet files and caches cannot be staged by accident. `tests/test_repo_hygiene.py` proves it with `git check-ignore --no-index` (10 must-ignore, 9 must-not-ignore) and asserts that history, index and working tree never contain `data/`, `.env` or weight files. Anchoring (`/data/`) keeps `backend/src/khetsetu_backend/data/` trackable.
- FND-06 (part 1): one `uv sync --locked --all-packages` builds a single environment from a workspace of exactly three members plus the unpackaged root project. A seven-test invariant file pins the dependency direction, so the frontend can never declare a dependency on the backend.
- Space install-order question answered before any app code exists: `uv pip install --dry-run "gradio[oauth,mcp]==6.30.0" -r <exported runtime>` first failed (mcp extra requires `pydantic<=2.12.5`, lock had 2.14.1). The constraint `pydantic>=2.11.10,<=2.12.5` was added with an explanatory comment; the lock now records pydantic 2.12.5 and the dry run exits 0.
- Lockfile created once for the whole phase (103 packages, gradio 6.30.0, pillow 12.3.0, pydantic 2.12.5).

## Task Commits

No commits were made. The user instructed "do not commit changes, i will commit myself", which overrides the plan's per-task commit protocol. All work is in the working tree, in plan order (`.gitignore` already present before anything else was created).

1. **Task 1: Hygiene first, one-package workspace** - uncommitted (22 hygiene tests, version prints 0.1.0)
2. **Task 2: contracts and frontend members, dependency direction** - uncommitted (7 workspace tests, red first with 6 failing, then green)
3. **Task 3: tool configuration, dev group, Space-compat check** - uncommitted (35 tests total)

**Plan metadata:** not committed (STATE.md and ROADMAP.md progress written to disk only)

Suggested commit order for the user, so `.gitignore` is the earliest file: first `.gitignore`, then the remaining 17 files, staging explicit paths only (never `git add -A`: unrelated user changes and `data/` must stay out).

## Files Created/Modified

- `.gitignore` - root-anchored ignore rules (pre-existing untracked file, kept unchanged)
- `.python-version` - `3.12`
- `pyproject.toml` - workspace root and unpackaged app project `khetsetu`; dev group; ruff, mypy, pytest, coverage config; pydantic constraint
- `uv.lock` - hash-pinned lock for the whole phase
- `backend/pyproject.toml`, `backend/src/khetsetu_backend/{__init__.py,py.typed}` - backend distribution (pydantic, pydantic-settings, pillow, typer, contracts; extra `data`)
- `contracts/pyproject.toml`, `contracts/src/khetsetu_contracts/{__init__.py,py.typed}` - pure pydantic leaf package
- `frontend/pyproject.toml`, `frontend/src/khetsetu_frontend/{__init__.py,py.typed}` - gradio==6.30.0 plus contracts only
- `tests/test_repo_hygiene.py` - OPS-03 guard (22 cases)
- `tests/test_workspace.py` - FND-06 guard (7 tests)
- `contracts/tests/test_contracts_package.py`, `backend/tests/test_backend_package.py`, `frontend/tests/test_frontend_package.py` - per-package smoke tests (2 each)

## Decisions Made

- Pydantic upper bound `<=2.12.5` via `[tool.uv] constraint-dependencies`, with a comment recording the reason. STACK.md's pydantic 2.14.1 is not installable on a Gradio Space; plans 01-04, 01-06 and 01-07 should treat 2.12.5 as the pinned version and revisit when the Gradio pin moves.
- `extend-exclude = [".claude", ".planning"]` for ruff: the installed third-party skill scripts under `.claude/skills` produced 559 findings that are not project source. No rule was weakened.
- Existing root `.gitignore` kept byte-for-byte: it already contained every rule the plan lists.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy override pattern `test_*` rejected**
- **Found during:** Task 3 (mypy configuration)
- **Issue:** `module = ["test_*", "conftest"]` fails with "Patterns must be fully-qualified module names"; under `explicit_package_bases` test modules are rooted at the repo (`contracts.tests.test_x`, `tests.test_x`).
- **Fix:** override module list is `["*.tests.*", "tests.*", "conftest"]` (still relaxes only `disallow_untyped_defs` and `disallow_untyped_decorators`).
- **Files modified:** pyproject.toml
- **Verification:** `uv run mypy` prints "Success: no issues found in 8 source files" with no config warning.

**2. [Rule 3 - Blocking] ruff scanned third-party skill scripts**
- **Found during:** Task 3 (first `ruff check .`)
- **Issue:** 559 findings, all in `.claude/skills/**` (installed agent skills), failing `ruff check .` and `ruff format --check .`.
- **Fix:** `extend-exclude = [".claude", ".planning"]` under `[tool.ruff]`.
- **Files modified:** pyproject.toml
- **Verification:** `ruff check .` and `ruff format --check .` exit 0.

**3. [Rule 1 - Lint] S603 on the git subprocess helper**
- **Found during:** Task 1/3 authoring
- **Fix:** resolved git with `shutil.which` (avoids S607) and used a single justified `# noqa: S603` on the fixed-executable call; the rule remains on globally.
- **Files modified:** tests/test_repo_hygiene.py

### Plan-adherence deviations caused by the no-commit instruction

**4. Commit-history acceptance criteria verified by working-tree equivalents**
- Task 1 criteria "`uv.lock` ... is tracked", "`git log --diff-filter=A -- .gitignore` returns a commit" and "no commit adds any other file before `.gitignore`" cannot be satisfied without a commit. Equivalents verified instead: `.gitignore` exists and `git check-ignore` behaves as specified; `uv.lock` exists, is not ignored (`git check-ignore -v uv.lock` exits 1) and `uv sync --locked` exits 0; `git status --porcelain --untracked-files=all` shows no `data/` line; `git log` is unchanged at `df765d6`. The ordering requirement (ignore rules before any other file) was honoured in the working tree (the `.gitignore` already existed) and should be honoured when the user stages: commit `.gitignore` first.
- Per-task atomic commits and the final docs commit were not made; `commits: 0` is the measured value and `plan_head_before == plan_head_after`.

---

**Total deviations:** 3 auto-fixed (2 Rule 1, 1 Rule 3) plus 1 commit-related adjustment
**Impact on plan:** All fixes were configuration correctness; no scope creep.

## Issues Encountered

- First resolution dry run failed as the plan anticipated; resolved by the constraint above (one iteration).
- `uv` selected CPython 3.12.13 (managed) rather than the system 3.12.3; both satisfy `>=3.12,<3.13`.
- Planned test counts: hygiene 22 collected cases (10 + 9 + 3), workspace 7, smoke 6, total 35 collected and passing.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The three packages contain only a docstring and `__version__` by design; DTOs and services arrive in later plans.

## Threat Flags

None. No new network endpoints, auth paths or file access beyond the plan's threat model. T-01-01, T-01-02 mitigated by the hygiene tests; T-01-SC mitigated by the exact gradio pin and the hash-pinned lockfile (`pip-audit` gate arrives in plan 01-03).

## Next Phase Readiness

- Plans 01-02 and 01-03 (wave 2) can build on a locked, green skeleton: add the `khetsetu` script entry and settings (01-02), Makefile, CI, import-linter contracts and the coverage floor (01-03).
- Plan 01-04 must add `app.py` to the mypy `files` list; plan 01-06 adds `scripts`.
- Open item for the user: the files above are uncommitted. Commit `.gitignore` first, then the rest, staging explicit paths only.

## Self-Check: PASSED

- All 18 created files exist on disk (checked via `git status --porcelain --untracked-files=all`).
- Zero commits made: `git log --oneline | head -1` is still `df765d6`, `git rev-list --count df765d6..HEAD` is 0.
- Final gate run: `uv sync --locked --all-packages`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest -q` all exit 0 (35 passed).

---
*Phase: 01-walking-skeleton-hosting-verification*
*Completed: 2026-10-23*
