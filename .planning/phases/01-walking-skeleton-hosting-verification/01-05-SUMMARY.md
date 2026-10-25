---
phase: 01-walking-skeleton-hosting-verification
plan: 05
subsystem: data
tags: [dataset, huggingface-hub, manifest, sha256, cli, typer, cache]

requires:
  - phase: 01-walking-skeleton-hosting-verification
    provides: "01-02 Settings (data_dir, dataset_repo_id, dataset_revision, effective_dataset_mode) and the khetsetu CLI; 01-04 app.py composition root with the dataset-prefetch extension point"
provides:
  - "khetsetu_backend.data: DatasetManifest (pinned revision, sizes, sha256), ensure_dataset (cache_hit or downloaded, no network on a hit), DatasetError family, requires_dataset decorator + active_dataset()"
  - "khetsetu_backend.data.summary: row, class and shard counts read from the real parquet shards and dataset card (needs the optional data extra)"
  - "khetsetu_backend.bootstrap.prepare_runtime(settings): fetches the dataset locally, does nothing on Space or CI"
  - "khetsetu data download [--verify] and khetsetu data inspect; exit codes 0, 2, 3"
  - "app.py calls prepare_runtime before building the demo (exit 3 on a dataset error)"
  - "docs/dataset.md"
affects: [phase-2-data-pipeline, phase-3-training, 01-06, 01-07]

# Nothing committed by this run (user instruction: "do not commit changes, i will commit myself").
commits: 0
plan_head_before: 1b0c9930032978d366f6ca6e37591a5005383b06
plan_head_after: 1b0c9930032978d366f6ca6e37591a5005383b06

actuals:
  tokens: 12300   # chars/4 over the 14 created and 4 edited files (about 49,000 characters of code, tests and docs)
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "Idempotent ensure_dataset: compare on-disk sizes to a packaged manifest; only on a mismatch call an injectable downloader, then verify size and sha256"
    - "The Hub client, pyarrow and yaml are imported lazily or in one module (summary.py) so the Space process never needs them"
    - "Errors carry repo id, revision, file name or exception class name only, never request text or tokens"
    - "Every dataset-consuming command is decorated with @requires_dataset and reads the files through active_dataset()"

key-files:
  created:
    - backend/src/khetsetu_backend/data/__init__.py
    - backend/src/khetsetu_backend/data/manifest.py
    - backend/src/khetsetu_backend/data/dataset_manifest.json
    - backend/src/khetsetu_backend/data/ensure.py
    - backend/src/khetsetu_backend/data/summary.py
    - backend/src/khetsetu_backend/data/guard.py
    - backend/src/khetsetu_backend/bootstrap.py
    - backend/tests/test_backend_data_ensure.py
    - backend/tests/test_backend_data_summary.py
    - backend/tests/test_backend_data_guard.py
    - backend/tests/test_backend_bootstrap.py
    - backend/tests/test_backend_data_network.py
    - tests/test_app_dataset_first.py
    - docs/dataset.md
  modified:
    - backend/src/khetsetu_backend/cli.py
    - app.py
    - pyproject.toml
    - backend/README.md

key-decisions:
  - "ensure_dataset takes the downloader as an optional argument and looks up the real Hub downloader lazily, so unit tests never touch the network and the Space does not import huggingface_hub from this module"
  - "The packaged manifest also records a sha256 for README.md (computed locally; the Hub shows only its git blob id, which was matched too), so the dataset card is verified after a download like the shards"
  - "Policy machinery for future entrypoints was skipped on purpose (user override: no extra tooling); the decorator and docs/dataset.md carry the convention"

patterns-established:
  - "Pattern 1: a new dataset command = @data_app.command(...) then @requires_dataset, body calls active_dataset()"
  - "Pattern 2: a test that must prove 'no download' replaces khetsetu_backend.data.ensure._hub_download (or passes an exploding downloader) and runs the real code above it"

requirements-completed: [FND-03]

coverage:
  - id: D1
    description: "khetsetu data inspect ensures the dataset, then prints outcome, revision, path, rows 55448, classes 39, shards 2 read from the real files, with the Hub forced offline"
    requirement: FND-03
    verification:
      - kind: e2e
        ref: "KHETSETU_APP_ENV=local HF_HUB_OFFLINE=1 uv run khetsetu data inspect (exit 0; outcome: cache_hit, rows: 55448, classes: 39, shards: 2)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_backend_data_summary.py#test_real_dataset_has_the_documented_shape (marker dataset, ran against data/plant_village_classification)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A complete local copy is a CACHE_HIT and the downloader is never called; the user's existing 823 MB copy was reused and not modified"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_data_ensure.py#test_complete_dataset_is_a_cache_hit_and_never_downloads"
        status: pass
      - kind: other
        ref: "file list, sizes and mtimes under data/ identical before and after data download --verify and data inspect"
        status: pass
    human_judgment: false
  - id: D3
    description: "Missing or wrong-size files download exactly the manifest files at the pinned revision, verify size and sha256, return DOWNLOADED; the immediate second call is a CACHE_HIT with no download"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_data_ensure.py#test_missing_files_are_downloaded_once_then_reused and #test_a_wrong_size_file_triggers_a_download"
        status: pass
      - kind: integration
        ref: "uv run pytest -m network backend/tests/test_backend_data_network.py (real Hub download of the 4 KB card, then cache hit); 1 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "Integrity and safety failures are loud and name the repo, revision or file, never a token: wrong size, wrong hash, failing downloader, settings that disagree with the manifest, path traversal and symlink escape"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_data_ensure.py (size, hash, token-not-leaked in message and logs, KHETSETU_DATASET_REVISION / KHETSETU_DATASET_REPO_ID, unsafe paths, symlink escape)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A command decorated with requires_dataset downloads first (exit 2 on bad settings, exit 3 on a dataset problem, body never runs); khetsetu data inspect and download use it / the same function"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_data_guard.py (9 tests including the CLI commands)"
        status: pass
    human_judgment: false
  - id: D6
    description: "app.py locally prepares the dataset after logging and before building the demo; on a Space or in CI the downloader is never reached; a DatasetError exits 3 with no demo built"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "tests/test_app_dataset_first.py (4 tests) and backend/tests/test_backend_bootstrap.py (5 cases)"
        status: pass
    human_judgment: false
  - id: D7
    description: "Any command under train, eval or dev (and any non-allowlisted command) must be wrapped by requires_dataset, enforced by a failing-by-default policy test"
    requirement: FND-03
    verification:
      - kind: other
        ref: "NOT IMPLEMENTED on purpose (user override: no process-only tooling); see Deviations"
        status: not_run
    human_judgment: false

duration: 30min
completed: 2026-10-25
status: complete
---

# Phase 1 Plan 05: Dataset first, idempotently Summary

**`ensure_dataset` makes every dataset-consuming command start from a verified, pinned copy of `Project-AgML/plant_village_classification`: the existing 823 MB local copy is recognised and reused with zero network, a missing or damaged copy is downloaded once and checked by size and sha256, and the Space and CI never download it.**

## Performance

- **Duration:** about 30 min
- **Completed:** 2026-10-25
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 TDD, Task 3)
- **Files created:** 14, modified: 4
- **Commits:** 0 (user instruction: "do not commit changes, i will commit myself")

## Accomplishments

- FND-03 delivered. `KHETSETU_APP_ENV=local HF_HUB_OFFLINE=1 uv run khetsetu data inspect` exits 0 and prints `outcome: cache_hit`, `revision: cb08789a...`, `path: data/plant_village_classification`, `rows: 55448`, `classes: 39`, `shards: 2` (read from the real parquet metadata and dataset card; class 0 is `Apple___Apple_scab`, class 4 `Background_without_leaves`).
- The pinned manifest was verified against everything it claims: sha256 of both local shards recomputed (both match the plan values), and `HfApi().dataset_info(..., revision=cb08789a..., files_metadata=True)` on the public repo reports the same sizes, the same LFS sha256 values and the same git blob id for `README.md` as `git hash-object` on the local file. Nothing was downloaded (read-only metadata call).
- `khetsetu data download --verify` re-hashed the whole local copy (about 2 s) and exited 0 with `cache_hit`; before and after, the file list, sizes and mtimes under `data/` were byte-for-byte the same.
- Real Hub path proven cheaply: the opt-in network test downloads only the 4 KB dataset card at the pinned revision (outcome `downloaded`, size 4193), then a second call is a cache hit with a downloader that fails the test if called. `uv run pytest -m network ...` gives 1 passed; the default run deselects it.
- `@requires_dataset` plus `active_dataset()` make "dataset first" a one-line habit for future commands; `prepare_runtime` plus the `app.py` call make a local `python app.py` prefetch it. Tests prove that with `KHETSETU_APP_ENV` `space` or `ci` the Hub download function is never reached by the real `app.main()` code path.
- Space-safety checked: importing `khetsetu_backend.data` and `khetsetu_backend.bootstrap` pulls in none of `pyarrow`, `yaml` or `huggingface_hub`.
- Whole existing gate set green: `ruff check`, `ruff format --check`, `mypy` (46 files), `lint-imports` (3 kept, 0 broken), `pytest --cov` (228 passed, 1 deselected network test, coverage 97.97 percent, floor 80).

## Task Commits

None. All work is in the working tree for the user to commit. `plan_head_before` and `plan_head_after` are both `1b0c993`, so `commits: 0` is measured, and the changes are intentionally uncommitted.

## Files Created/Modified

- `backend/src/khetsetu_backend/data/manifest.py`, `dataset_manifest.json` - pinned repo, revision, three files with size and sha256; path validators reject `..`, leading slash, backslash and empty segments
- `backend/src/khetsetu_backend/data/ensure.py` - `ensure_dataset`, `DatasetHandle`, `DownloadOutcome`, `DatasetError` / `DatasetDownloadError` / `DatasetIntegrityError`, `dataset_dir`
- `backend/src/khetsetu_backend/data/summary.py` - the only module importing pyarrow and yaml
- `backend/src/khetsetu_backend/data/guard.py`, `data/__init__.py` - decorator and exports
- `backend/src/khetsetu_backend/bootstrap.py` - `prepare_runtime`
- `backend/src/khetsetu_backend/cli.py` - `data download [--verify]`, `data inspect`, shared settings-or-exit helper
- `app.py` - `prepare_runtime` call, `EXIT_DATASET_PROBLEM = 3`
- `pyproject.toml` - one mypy override: `ignore_missing_imports` for `pyarrow.*` only
- `docs/dataset.md`, `backend/README.md` - how the dataset is fetched, pinned, verified, bumped; commands and exit codes
- Tests: `backend/tests/test_backend_data_{ensure,summary,guard,network}.py`, `backend/tests/test_backend_bootstrap.py`, `tests/test_app_dataset_first.py`

## Decisions Made

- The downloader is an optional argument (`Downloader` Protocol); the default calls `huggingface_hub.snapshot_download` through a function that imports it lazily.
- A failed download is reported as `Could not download <repo> at revision <sha> (<ExceptionClass>)`, with the original exception dropped (`from None`) because its text could echo request details; a test feeds a fake error containing a token and checks the token is absent from the message and from captured logs.
- `README.md` in the manifest carries a sha256 (see Deviations) so every file in the manifest is hash-checked after a download.
- A size mismatch is repaired by downloading; if the file is still wrong afterwards the error tells the user to delete that file and run `khetsetu data download` again. The downloader never deletes files itself (the user's data stays untouched).

## Deviations from Plan

### Intentional omissions (user overrides)

**1. [User override 2 - no extra tooling] Policy checker for future entrypoints not built**
- **Plan asked for:** `find_unguarded_commands`, `GUARD_REQUIRED_GROUPS`, `NO_DATASET_ALLOWLIST`, `REQUIRES_DATASET_ATTR`, `backend/tests/test_backend_cli_policy.py`, and an ast test that `data/__init__.py` and `ensure.py` do not import pyarrow or yaml.
- **Why:** these only scan for commands that do not exist yet; the user asked for no new checker or meta test. The product behaviour (decorator, bootstrap, CLI) and all behaviour tests were built.
- **Effect:** must-have truth 4 ("a test fails if a future command forgets it") is not enforced; `docs/dataset.md` states this under Open items and shows the pattern. Phase 1 has no other dataset-consuming commands, so FND-03's text ("run any training, evaluation or dev entrypoint and have the dataset downloaded first") holds for everything that exists. The Space-safety fact is instead checked once by hand (no pyarrow, yaml or huggingface_hub in `sys.modules` after importing the data package and bootstrap) and by the lazy imports.

**2. [User override 1 - no commits] Commit-based criteria**
- The plan's "record the verification outcome in the task commit message" is replaced by the verification record above. No git commands that modify anything were run.

### Auto-fixed / small differences

**3. [Rule 2 - Missing critical functionality] README sha256 recorded**
- The plan listed no sha256 for `README.md`. I computed it locally (`335db68c...`) after confirming that the local file's git blob id equals the Hub's blob id for that revision, so the hash describes the authentic file. Benefit: a tampered card is detected after download. Files: `dataset_manifest.json`.

**4. [Rule 3 - Blocking] Lint rules needed local handling**
- Ruff `PLR0913` (six keyword-only arguments mirroring `snapshot_download`) is silenced with two targeted `# noqa` comments; `requires_dataset` uses the Python 3.12 `def f[**P, R]` syntax (ruff `UP047`) instead of `ParamSpec`/`TypeVar`. One mypy override for `pyarrow.*` (anticipated by the plan).

**5. [Plan wording] Network test uses the default downloader through `ensure_dataset(settings, manifest=...)`**
- Same behaviour as asked ("REAL default downloader"); done by omitting the `downloader` argument.

## Authentication Gates

None. The public dataset needs no token; the local `.env` was never read or printed by me (the CLI loads it itself, as for every command).

## Known Stubs

None.

## Threat Flags

None. All surface added (file writes into `data/`, Hub download) is in the plan's threat model (T-01-14 to T-01-17); mitigations are implemented and tested: pinned commit plus size/sha256 (T-01-14), mode OFF outside local and tests for space and ci (T-01-15), token-free error text and logs (T-01-16), manifest path validation plus `is_relative_to` check including a symlink escape test (T-01-17).

## Issues Encountered

- A first draft of one bootstrap test patched the keyword default of `prepare_runtime`; replaced with a patch of the Hub download function so the real `prepare_runtime` and `ensure_dataset` code runs.
- Not verified: a first-time full 823 MB download (not allowed; the real path was proven with the 4 KB card), and behaviour when `snapshot_download` meets a same-name but corrupted file whose cache metadata claims it is current (the error message tells the user to delete that file).

## Next Phase Readiness

- Plan 01-06 and 01-07 are unaffected. Phase 2 can call `ensure_dataset` / `@requires_dataset` and read shards through `handle.parquet_files`.
- Open item for Phase 3: the AgML mirror's licence and attribution are unconfirmed (recorded in `docs/dataset.md`).

## Self-Check: PASSED

- All 14 created files exist (checked with `git status` and the test run importing them).
- `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `pytest --cov` (228 passed) and `pytest -m network` (1 passed) all exit 0 on the final tree.
- No commits were made, as instructed; `HEAD` is still `1b0c993`.
