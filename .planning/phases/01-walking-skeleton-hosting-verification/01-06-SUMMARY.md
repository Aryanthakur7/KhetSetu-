---
phase: 01-walking-skeleton-hosting-verification
plan: 06
subsystem: infra
tags: [huggingface-spaces, gradio, packaging, uv, rehearsal, probe, docs]

requires:
  - phase: 01-walking-skeleton-hosting-verification
    provides: "01-04 composition root app.py with the sys.path shim and the /diagnose and /readiness endpoints; 01-05 dataset downloader that does nothing on a Space; 01-01 uv workspace and locked gradio 6.30.0"
provides:
  - "scripts/space_bundle.py: build_bundle stages app.py + the three src trees + generated Space README + pinned requirements.txt; assert_bundle_clean refuses .env, datasets, weights, planning and tool folders"
  - "scripts/space_rehearsal.py: installs the bundle into a fresh Python 3.12 venv in the Hugging Face order, boots `python app.py` under KHETSETU_APP_ENV=space, calls it through the Gradio client"
  - "scripts/space_probe.py: whoami, create-space, deploy, wait, smoke, llm-probe against a live account; classifies 401/402/403/404/429; private by default; token never printed or stored"
  - "docs/hosting.md runbook and fallback ladder, docs/architecture.md, contracts/README.md, frontend/README.md, finished README.md"
  - "Observed local rehearsal results for both packaging options and a one-off pip-audit of the Space dependency set"
affects: [01-07, phase-4-diagnosis]

# Nothing committed by this run (user instruction: "do not commit changes, i will commit myself").
commits: 0
plan_head_before: 1b0c9930032978d366f6ca6e37591a5005383b06
plan_head_after: 1b0c9930032978d366f6ca6e37591a5005383b06

actuals:
  tokens: 19200   # chars/4 over the 12 files created or rewritten (about 76,700 characters)
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "Allow-list staging: the Space folder is built by copying named things in, never by filtering a copy of the repo"
    - "Hub, Gradio and LLM clients are passed into every probe command, so tests use small fakes and the real clients exist only in main()"
    - "Space README is generated from uv.lock so sdk_version can never disagree with the locked Gradio"

key-files:
  created:
    - scripts/__init__.py
    - scripts/space_bundle.py
    - scripts/space_rehearsal.py
    - scripts/space_probe.py
    - tests/test_space_bundle.py
    - tests/test_space_rehearsal.py
    - tests/test_space_probe.py
    - docs/architecture.md
    - docs/hosting.md
    - contracts/README.md
    - frontend/README.md
  modified:
    - README.md
    - pyproject.toml

key-decisions:
  - "The rehearsal and the smoke probe check /diagnose AND /readiness: the 'Demo mode' text is the page banner served by /readiness, while /diagnose returns the fake diagnosis"
  - "Installs in the rehearsal use `uv pip` (fast) rather than plain pip; the resulting package set is what matters"
  - "docs/hosting.md points at docs/decisions/ADR 0001, which plan 01-07 creates; this is the only forward reference"

patterns-established:
  - "Pattern 1: a new Space tool is a module under scripts/ with a main(argv) -> int, JSON on stdout, diagnostics on stderr"
  - "Pattern 2: a slow, network-installing test carries the opt-in `rehearsal` marker"

requirements-completed: []  # FND-05 deliberately stays PENDING until plan 01-07 records the real-account decision

coverage:
  - id: D1
    description: "One command builds the Space folder; the self-check refuses .env, parquet/safetensors, a top-level data folder, .planning, .claude, .git, .tools and build"
    requirement: FND-05
    verification:
      - kind: unit
        ref: "tests/test_space_bundle.py (allow-list, 11 planted-violation cases, nested data package allowed, deterministic bytes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Space card has sdk gradio, sdk_version equal to the locked gradio (6.30.0) and the quoted string python_version '3.12'; requirements are pinned with pillow 12.x and no workspace lines"
    requirement: FND-05
    verification:
      - kind: unit
        ref: "tests/test_space_bundle.py#test_readme_header_matches_the_locked_gradio and #test_requirements_are_pinned_without_workspace_packages"
        status: pass
    human_judgment: false
  - id: D3
    description: "The bundle installs into a fresh venv in the HF order, no khetsetu_* package is installed, `python app.py` under KHETSETU_APP_ENV=space answers an upload via the Gradio client, shows Demo mode, and creates no data folder"
    requirement: FND-05
    verification:
      - kind: integration
        ref: "uv run pytest -m rehearsal tests/test_space_rehearsal.py (1 passed) and build/rehearsal-syspath.json (ok: true, 11 steps)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Probe tool: classifies 401/402/403/404/429, redacts secrets, creates private Gradio Spaces, deploys with one non-secret variable, waits with a redacted log tail, smoke-tests, makes exactly one LLM request, never writes the token"
    requirement: FND-05
    verification:
      - kind: unit
        ref: "tests/test_space_probe.py (28 tests over a fake Hub, Gradio client and LLM)"
        status: pass
      - kind: other
        ref: "`python -m scripts.space_probe --help` lists all six commands; `whoami` with no HF_TOKEN exits 2 naming HF_TOKEN (run from an empty directory so the real .env was not read)"
        status: pass
    human_judgment: false
  - id: D5
    description: "README, architecture and hosting docs describe only files and commands that exist"
    requirement: FND-05
    verification:
      - kind: other
        ref: "one-off script checked every backticked repository path and relative link in README.md, docs/*.md and the package READMEs; only docs/decisions/ (created by plan 01-07) is missing; backend/tests/test_backend_docs.py also checks the README commands"
        status: pass
    human_judgment: false
  - id: D6
    description: "A newcomer can follow README top to bottom (quickstart, run the app, dataset, quality gates, deploy)"
    verification: []
    human_judgment: true
    rationale: "Reading order and clarity of the README cannot be judged by a script"

duration: 45min
completed: 2026-10-25
status: complete
---

# Phase 1 Plan 06: Space tooling, local rehearsal and docs Summary

**The monorepo is proven to run the way a Gradio Space runs it, with no Hugging Face account: a generated Space folder installs into a fresh Python 3.12 environment in Hugging Face's order, boots under `KHETSETU_APP_ENV=space` through the `sys.path` fallback, and answers an image upload; a probe CLI with six commands is ready for the real account in plan 01-07.**

## Performance

- **Duration:** about 45 min
- **Completed:** 2026-10-25
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 TDD, Task 3 docs)
- **Quality gates:** `make check` exits 0: ruff, ruff format, strict mypy (now including `scripts`), import-linter (3 kept), 275 tests, coverage 97.97 percent. The opt-in rehearsal test also passes.

## Accomplishments

- **Bundle builder** (`scripts/space_bundle.py`): copies a fixed allow-list into `build/space/` (28 files for the default packaging), generates the Space `README.md` header with `sdk_version` read from `uv.lock` (6.30.0) and `python_version: '3.12'` quoted, and `requirements.txt` from `uv export` (pillow 12.3.0, no workspace lines, no hashes). Same inputs give identical bytes.
- **Rehearsal** (`scripts/space_rehearsal.py`): the tracer slice. Eleven reported steps from "build bundle" to "no data directory", stopping at the first failure and always stopping the child process. Full run takes about 13 seconds when uv's cache is warm.
- **Probe** (`scripts/space_probe.py`): `whoami`, `create-space`, `deploy`, `wait`, `smoke`, `llm-probe`. Reports go to `build/space-probe/<command>[-variant].json`. The fallback ladder is described once in the module docstring and in `docs/hosting.md`.
- **Docs**: finished `README.md` (run the app, dataset, quality gates, deploy, extended layout table), `docs/architecture.md` (diagram, the three import rules by name, composition root, diagnose flow, Phase 4 swap point, two-Space split), `docs/hosting.md` (runbook), `contracts/README.md`, `frontend/README.md`.

## Observed behaviour (feeds plan 01-07)

| Packaging | Result in the local rehearsal |
| --- | --- |
| `syspath` | Passed all 11 steps. `uv pip check`: all packages compatible (the pydantic <=2.12.5 constraint from plan 01-01 holds). No `khetsetu_*` package installed. `/diagnose` returned the fake "Tomato - Late blight"; `/readiness` returned the Demo mode banner. Page up about 11 s after launch. |
| `editable` | Failed at "install requirements": `Distribution not found at: file:///.../contracts`, because `./contracts` does not resolve when `requirements.txt` is installed from a copy outside the bundle. Expected; recorded in `build/rehearsal-editable.json`. |

One-off `pip-audit` over the rehearsal's frozen set (71 packages, including the `oauth` and `mcp` extras): 37 advisories, all in **pillow 12.3.0**, all fixed in 13.0.0, which Gradio 6.30.0 forbids (`pillow<13`). Same root cause as the already-known red `make audit`; not fixed here. Nothing else was reported.

## Task Commits

None. The user asked to commit everything themselves; all files are in the working tree. `commits: 0` is measured (`git rev-list --count 1b0c993..HEAD` is 0) and is correct for a plan that changed code, because the changes are deliberately uncommitted.

## Deviations from Plan

### User-directed simplifications (override: no heavy CI/quality tooling, no commits)

**1. No commits.** Task commits, the final metadata commit and the post-commit deletion check were not run. Criteria that depend on commit history were checked in the working tree instead.

**2. `tests/test_docs_accuracy.py` not created.** The plan wants a test that checks every repository path named in the docs. The user asked for no new meta tests, so I ran an equivalent one-off script instead (result in coverage D5). The existing `backend/tests/test_backend_docs.py` still checks the README's `khetsetu ...` commands. Docs can therefore drift without a test noticing.

**3. Simpler fakes and rehearsal layers.** The probe's Hub, Gradio and LLM clients are typed as `Any` aliases (`HubApi`, `GradioClient`, `LlmClient`) and the tests pass small hand-written fakes, instead of a typed Protocol hierarchy. The rehearsal installs with `uv pip` rather than plain `pip`, so resolver differences from the real Space build are possible; plan 01-07 compares against the real build log.

### Auto-fixed issues

**4. [Rule 1 - Plan/code mismatch] "Demo mode" is not in the `/diagnose` response.**
- **Found during:** Task 1 (reading `ui.py` and the existing e2e test)
- **Issue:** The plan says the `/diagnose` response contains "Demo mode". In the code, `/diagnose` returns the fake diagnosis text and the Demo mode banner comes from `/readiness`.
- **Fix:** The rehearsal `client_call` step and `cmd_smoke` call both endpoints and require a non-empty diagnosis plus the banner text; the step detail contains "Demo mode".
- **Files modified:** `scripts/space_rehearsal.py`, `scripts/space_probe.py`
- **Commit:** none (uncommitted)

**5. [Rule 1 - Bug] Relative `--work-dir` broke the rehearsal.** The first run failed with `FileNotFoundError` for `venv/bin/python` because the steps run in other directories. `rehearse()` now resolves the work directory to an absolute path.

**6. [Rule 1 - Bug] `uv pip freeze` output included uv's stderr line, which made pip-audit reject the file.** Fixed with `--quiet`.

**7. [Rule 3 - Blocking] Lint rules.** `S607` (partial executable path) was handled by resolving `uv` with `shutil.which`; `PLR0913` on `cmd_wait` has a justified `noqa` (injectable clock and sleep keep tests instant); the `deploy` command no longer takes a `repo_root` argument.

### Other differences

- `space_probe` places `--space-id` and `--out` both before and after the subcommand (argparse parent parser with suppressed defaults), so either style works.
- `deploy` sets the `KHETSETU_APP_ENV` Variable **before** uploading, so the first Space build already has it and does not restart.
- The hosting runbook contains one forward reference, `docs/decisions/` (ADR 0001), exactly as the plan requires; the folder does not exist until plan 01-07.

## Authentication gates

None. By design this plan never contacts Hugging Face with the user's token. The `.env` file was not read. The only network use was PyPI (package install and `pip-audit`).

## Known Stubs

None added. The diagnosis service remains the deliberate fake from plan 01-04, replaced in Phase 4.

## Threat Flags

None beyond the plan's threat model. Mitigations in place: allow-list staging plus `assert_bundle_clean` (T-01-18), `redact` on all report content and token read only in `main` (T-01-19), private Space by default with `--public` required for public (T-01-20), pinned gradio and a recorded `pip-audit` of the rehearsal set (T-01-SC).

## Issues Encountered

- `make audit` remains red because of pillow (see above); out of scope here.
- The plan's acceptance check "`whoami` with no `HF_TOKEN` exits 2" cannot be run from the repository root on this machine without loading the real `.env`. It was run from an empty temporary directory instead and is also covered by `tests/test_space_probe.py` using an isolated working directory.

## Next Phase Readiness

Plan 01-07 can run: `create-space --hardware cpu-basic` (then `zero-a10g` if blocked), `deploy --packaging syspath`, `wait`, `smoke`, `llm-probe`, and compare the real build log with the rehearsal. The human must provide `HF_TOKEN` and `HF_SPACE_ID` in `.env`. FND-05 stays pending until then.

## Self-Check: PASSED

All created files exist (`scripts/*.py`, three new test files, `docs/architecture.md`, `docs/hosting.md`, `contracts/README.md`, `frontend/README.md`, `build/space/`, `build/rehearsal-syspath.json`, `build/rehearsal-editable.json`). No commit hashes to verify (none made). `make check` exits 0.
