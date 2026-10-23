---
phase: 01-walking-skeleton-hosting-verification
plan: 03
subsystem: infra
tags: [ci, github-actions, makefile, import-linter, gitleaks, pre-commit, pip-audit, canary-tests]

requires:
  - phase: 01-walking-skeleton-hosting-verification
    provides: "plan 01-01 uv workspace, ruff/mypy-strict/pytest config, three packages"
provides:
  - "make check: ruff, ruff format check, strict mypy, import-linter, pytest with an 80 percent coverage floor"
  - "CI workflow with required checks quality, audit, secrets (SHA-pinned actions, contents:read, no secrets)"
  - "Three import-linter forbidden contracts enforcing the frontend/backend/contracts boundary"
  - "Checksum-verified pinned gitleaks installer and a history/staged scan wrapper"
  - "Pre-commit config: ruff, mypy, lint-imports, gitleaks, 500 KB large-file limit, private-key guard"
  - "Canary tests proving each gate fails on a planted violation, and workflow-structure tests"
  - "docs/ci.md runbook including the one manual GitHub branch-protection step"
affects: [01-04, 01-05, 01-06, 01-07]

# Uncommitted at user request, so commits is a measured 0
commits: 0
plan_head_before: df765d608436fe10f308cc2c062ed55d29b83279
plan_head_after: df765d608436fe10f308cc2c062ed55d29b83279

actuals:
  tokens: 9200   # chars/4 over the 9 new files plus the pyproject.toml additions
  tasks: 3
  commits: 0

tech-stack:
  added: [GitHub Actions workflow, GNU Make, gitleaks 8.30.1, pre-commit-hooks v6.0.0, ruff-pre-commit v0.17.2]
  patterns:
    - "Makefile is the single source of truth; the workflow only calls make targets"
    - "Every gate has a canary: bad input exits non-zero, clean counterpart exits 0"
    - "Fake secrets assembled at runtime from fragments, never a literal token in the repo"
    - "Third-party tooling pinned and verified: action SHAs, gitleaks tarball checksum, pre-commit version tags"

key-files:
  created:
    - Makefile
    - .github/workflows/ci.yml
    - .gitleaks.toml
    - .pre-commit-config.yaml
    - scripts/install_gitleaks.sh
    - scripts/gitleaks.sh
    - tests/test_gates_canary.py
    - tests/test_ci_workflow.py
    - docs/ci.md
  modified:
    - pyproject.toml

key-decisions:
  - "Action pins: actions/checkout v7.0.1 (3d3c42e5aac5ba805825da76410c181273ba90b1), astral-sh/setup-uv v10.3.2 (07a047e608db84b3d8c06cd9a7c7dcc9c355c18e), both confirmed as the latest non-prerelease via the GitHub releases API"
  - "gitleaks pinned to 8.30.1 (latest stable, published 2026-03-21); installer verifies the release checksum file before extracting"
  - "No gitleaks allowlist entries: the full-history scan and a scan of every non-ignored working-tree file found zero false positives"
  - "The `pip-audit` finding on Pillow 12.3.0 is NOT ignored; it is documented in docs/ci.md and escalated for a maintainer decision"

patterns-established:
  - "Pattern 1: new gates are added as a Makefile target first, then a workflow step, then a canary and a structure assertion"
  - "Pattern 2: tests that need an external binary skip with an explicit reason locally and fail when CI is set"

requirements-completed: [FND-04, FND-06, OPS-03]
requirements-partial: [FND-02]

coverage:
  - id: D1
    description: "make check runs ruff, ruff format check, strict mypy, import-linter and pytest with coverage and exits 0"
    requirement: FND-04
    verification:
      - kind: integration
        ref: "make check (96 passed, coverage 98.40 percent, floor 80)"
        status: pass
    human_judgment: false
  - id: D2
    description: "import-linter enforces three forbidden contracts; each violation and the clean tree are exercised"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "tests/test_gates_canary.py#test_import_linter_fails_on_a_boundary_violation (6 cases) and #test_import_linter_accepts_the_legitimate_dependency_edges"
        status: pass
    human_judgment: false
  - id: D3
    description: "ruff, ruff format, strict mypy and pytest each fail on a planted violation and pass on a clean file"
    requirement: FND-04
    verification:
      - kind: unit
        ref: "tests/test_gates_canary.py (ruff check, ruff format, mypy, pytest canaries)"
        status: pass
    human_judgment: false
  - id: D4
    description: "gitleaks history scan fails on a runtime-built Hugging Face token (redacted in output) and passes on a clean repo; full real history scans clean"
    requirement: FND-02
    verification:
      - kind: unit
        ref: "tests/test_gates_canary.py#test_gitleaks_history_scan_fails_on_a_planted_token (ran, not skipped, also with CI=true)"
        status: pass
      - kind: integration
        ref: "make secrets (8 commits scanned, no leaks found)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Workflow structure: read-only permissions, no pull_request_target, SHA-pinned actions, exactly quality/audit/secrets jobs calling make, no secret references, fetch-depth 0 on the secrets job"
    requirement: FND-04
    verification:
      - kind: unit
        ref: "tests/test_ci_workflow.py (8 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "A staged file over 500 KB, and a staged token-shaped string, are blocked by pre-commit; all hooks pass twice on the project files"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "scratch-repo simulation of `pre-commit run --all-files` x2 plus planted 792 KB file and planted token (see Deviations)"
        status: pass
    human_judgment: false
  - id: D7
    description: "GitHub Actions run shows quality, audit, secrets green, and branch protection requires them"
    requirement: FND-04
    verification:
      - kind: other
        ref: "docs/ci.md#branch-protection-required-one-time-manual"
        status: not_run
    human_judgment: true
  - id: D8
    description: "make audit (pip-audit) passes on the runtime dependency set"
    requirement: FND-04
    verification:
      - kind: integration
        ref: "make audit"
        status: fail
    human_judgment: true

duration: 18min
completed: 2026-10-24
status: complete
---

# Phase 1 Plan 03: Quality gates, CI and secret scanning Summary

**One `make check` command (ruff, format, strict mypy, import-linter, pytest at an 80 percent floor), a three-job CI workflow that only calls the same make targets, full-history gitleaks, and canary tests that prove every gate bites. The `audit` gate works and is currently red: Pillow 12.3.0 has 35 known vulnerabilities fixed only in 13.0.0, which Gradio 6.30.0 forbids.**

## Performance

- **Duration:** 18 min (about 3 of them waiting on a slow GitHub release download)
- **Started:** 2026-10-23T19:08:00Z
- **Completed:** 2026-10-23T19:26:00Z
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 auto, Task 3 TDD)
- **Files created:** 9, modified: 1 (`pyproject.toml`)
- **Commits:** 0 (user instruction: "do not commit changes, i will commit myself")

## Accomplishments

- FND-04: `make check` exits 0 (96 tests, 98.40 percent coverage against a floor of 80). The workflow has jobs `quality` (separate steps `make lint`, `make type`, `make imports`, `make test`), `audit` and `secrets`; it holds no command list of its own.
- FND-06: `[tool.importlinter]` has three forbidden contracts (Frontend depends on contracts only; Backend has no UI; Contracts is a leaf), `lint-imports` reports 3 kept, 0 broken. Six violation cases (including external packages `gradio` and `huggingface_hub`) are proven to print BROKEN and exit non-zero, and the legitimate edges (frontend imports gradio and contracts) pass.
- FND-02 (scan half): gitleaks 8.30.1 is installed by a checksum-verified script; `make secrets` scans all history and finds nothing; the staged-mode hook blocks a planted token. `--redact` is on in every mode, and a test asserts the planted token never appears in output.
- OPS-03: pre-commit `check-added-large-files --maxkb=500` (excluding only `^uv\.lock$`) blocked a planted 792 KB file; `detect-private-key` is enabled.
- Canary and structure tests: 12 canary tests (ruff check, ruff format, mypy, 6+1 import-linter cases, pytest, gitleaks) and 8 structure tests, all passing. The gitleaks canary ran (not skipped) and still passes with `CI=true`.
- Pinned third-party inputs: two action SHAs (latest non-prerelease per the releases API), gitleaks tarball checksum, pre-commit-hooks v6.0.0 and ruff-pre-commit v0.17.2 (matches locked ruff 0.17.2).

## Task Commits

No commits were made (user override). Work is in the working tree in plan order: Task 1 (pyproject, Makefile, ci.yml), Task 2 (scripts, gitleaks config, pre-commit, `secrets` target and job), Task 3 (tests, runbook).

## Files Created/Modified

- `Makefile` - targets help, sync, lint, type, imports, test, secrets, audit, check, hooks; no recipe hides a failure
- `.github/workflows/ci.yml` - jobs quality, audit, secrets; `permissions: contents: read`; concurrency; job-level `KHETSETU_APP_ENV: ci`, `KHETSETU_DATASET_MODE: "off"` on quality and audit
- `pyproject.toml` - `[tool.importlinter]` plus three contracts; `fail_under = 80` (edited only those tables)
- `scripts/install_gitleaks.sh` (executable) - `GITLEAKS_VERSION="8.30.1"`, linux x64 and darwin arm64/x64, checksum verified, curl timeouts and retries
- `scripts/gitleaks.sh` (executable) - modes `history` (`gitleaks git`) and `staged` (`gitleaks git --pre-commit --staged`), exit 3 with an install hint when the binary is missing
- `.gitleaks.toml` - `useDefault = true`, no allowlist entries
- `.pre-commit-config.yaml` - hygiene hooks, ruff-check/ruff-format, local mypy / lint-imports / gitleaks
- `tests/test_gates_canary.py`, `tests/test_ci_workflow.py` - see above
- `docs/ci.md` - gate table, local commands, workflow design, branch-protection steps, bump procedures, allowlist policy, leak response, pip-audit handling and the open Pillow finding

## Decisions Made

- Used the exact subcommand spellings of the installed gitleaks (`git`, `--pre-commit --staged`, `dir`) after reading `gitleaks git --help`, as the plan required.
- Dropped an interim `tree` mode from `scripts/gitleaks.sh`: `gitleaks dir` does not honour `.gitignore`, so it scanned the 823 MB git-ignored `data/` and the local `.env`. The plan only specifies `history` and `staged`.
- Left the Pillow audit failure visible rather than adding 35 `--ignore-vuln` entries for the library that decodes farmer uploads (see below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Slow GitHub release downloads stalled the installer**
- **Found during:** Task 2
- **Issue:** The first `scripts/install_gitleaks.sh` run hung for about 3 minutes on connection setup before the transfer completed.
- **Fix:** Added `fetch()` helper with `--retry 3 --retry-delay 5 --connect-timeout 30 --max-time 600`.
- **Files modified:** scripts/install_gitleaks.sh

**2. [Rule 1 - Bug] Interim `tree` scan mode scanned git-ignored files**
- **Found during:** Task 2 (my own addition, removed before completion)
- **Fix:** removed the mode; the equivalent working-tree check was done on a scratch copy of non-ignored files instead.

### Plan-adherence deviations caused by the no-commit instruction

**3. Pre-commit verification run in a scratch repository, not the real one**
- `uv run pre-commit run --all-files` only inspects tracked files, and almost nothing in the real repo is tracked, so it would pass vacuously; running `make hooks` (`pre-commit install`) writes into `.git/`, which the override forbids.
- Equivalent verification: copied every non-ignored file (excluding `.claude/`, `.planning/`) to a scratch directory, `git init` there, staged it, and ran `pre-commit run --all-files` twice. Both runs passed all 12 hooks with no file modifications. In the same scratch repo a staged 792 KB file failed `check-added-large-files` and a staged runtime-built token failed the `gitleaks` hook; the clean state passed. The script is at `/tmp/claude-1000/-home-himanshu-Desktop-Aryan-Project-KhetSetu-/18f7f828-03f1-43bb-af7a-a5456279f542/scratchpad/precommit_sim.sh`. Hooks ran with `UV_NO_SYNC=1` against the real `.venv` so the real environment was not modified.
- `make hooks` was not run. **One-time developer step: run `make hooks` after your first commit setup.**

**4. Secret-scan equivalents**
- `make secrets` scans committed history only (8 commits, clean). Files that are not yet committed were checked with `gitleaks dir` on a scratch copy of all tracked-or-untracked-but-not-ignored files: no leaks. The criterion "no file under `tests/` contains a token-shaped literal: `make secrets` still exits 0 after the tests are committed" is satisfied by the working-tree scan and must be re-confirmed by CI after your commit.
- Commit-based criteria (per-task commits, final docs commit) were not performed; `commits: 0` is the measured value.

**Total deviations:** 2 auto-fixed, 2 commit-related adjustments.

## Issues Encountered

- **OPEN, needs a maintainer decision: `make audit` fails.** pip-audit reports 35 vulnerabilities, all in `pillow 12.3.0`, all with fix version 13.0.0. Gradio 6.30.0 requires `pillow<13` (STACK.md), so the fix cannot be installed under the current pin. I did not add ignores (the CI `audit` job will be red until resolved). Options recorded in `docs/ci.md`: override Gradio's cap with `override-dependencies` and smoke-test uploads; dated `--ignore-vuln` with rationale; wait for a Gradio release. This also contradicts the plan 01-01 assumption that `pillow >=12,<13` is safe. This is a dependency-policy decision (pillow processes untrusted farmer uploads), so it was not decided here.
- **A real-looking Hugging Face token exists in the local, git-ignored `.env`** (found when an early directory scan accidentally covered the working directory). It is untracked, ignored (`.gitignore:17`), absent from history (`make secrets` clean), and was printed only redacted. This is the intended place for it, so it was not treated as a leak and nothing was allowlisted. Be careful never to stage it; rotate it if it was ever shared.
- The gitleaks hook on staged changes cannot run in CI usefully, as documented: CI uses the history scan.
- The first real GitHub Actions run has not happened (no push). Workflow validity is established structurally and by running each make target locally; the first run could still surface a runner-specific problem (for example `uv` version or cache behaviour).

## User Setup Required

External service configuration is required (GitHub admin setting, cannot be done by Claude):

1. Push a branch and open a pull request so the three checks appear.
2. Repository Settings -> Branches (or Rules -> Rulesets): protect `main`, require status checks `quality`, `audit` and `secrets`, and require the branch to be up to date. Details in `docs/ci.md`.
3. After cloning, run `make hooks` once to install the local pre-commit hooks.
4. Decide the Pillow audit finding (above) before expecting a green `audit` check.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-06 (secret scan, hook, canary), T-01-07 (SHA pins, read-only token, no `pull_request_target`, enforced by tests), T-01-08 (no secrets in CI, `--redact`), T-01-09 (structure tests, canaries, documented branch protection) and T-01-SC (checksum-verified gitleaks, tag-pinned hooks, audit job) are implemented. The audit job doing its job surfaced the Pillow exposure noted above.

## Next Phase Readiness

- `make check` is the gate for plans 01-04 to 01-07; they should add new paths to the mypy `files` list (`app.py`, `scripts`) and keep `make check` green.
- The `quality` job in CI sets `KHETSETU_APP_ENV=ci` and `KHETSETU_DATASET_MODE=off`; plan 01-02's `Settings` already accepts `ci` as an environment value, but the full suite has only been run locally without those two variables set, so the first CI run is the first time it executes with them.
- Open items for the user: commit the uncommitted files (explicit paths only, `.gitignore` first; never `data/` or `.env`), configure branch protection, decide the Pillow finding.

## Self-Check: PASSED

- All 10 files in the list exist (checked with `git status`): Makefile, ci.yml, .gitleaks.toml, .pre-commit-config.yaml, both scripts, both tests, docs/ci.md, modified pyproject.toml.
- Zero commits: `git log --oneline | head -1` is `df765d6`; HEAD equals `plan_head_before`.
- Final gate run: `make check` exit 0 (96 passed, 98.40 percent coverage), `make secrets` exit 0, canary plus structure tests 20 passed (12 with `-m gates` under `CI=true`), gitleaks missing-binary path exits 3.
- STATE.md, ROADMAP.md and REQUIREMENTS.md were not touched by this plan.

---
*Phase: 01-walking-skeleton-hosting-verification*
*Completed: 2026-10-24*
