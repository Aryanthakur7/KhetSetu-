---
phase: 01-walking-skeleton-hosting-verification
plan: 04
subsystem: architecture
tags: [contracts, pydantic, gradio, composition-root, fake-services, e2e]

requires:
  - phase: 01-walking-skeleton-hosting-verification
    provides: "plan 01-01 workspace and packages, 01-02 Settings/load_settings/configure_logging, 01-03 make check and import-linter contracts"
provides:
  - "khetsetu_contracts: DiagnosisRequest, DiagnosisResult (refusals cannot carry a disease name), ScoredLabel, MessageKey, Readiness, ContractError subclasses, DiagnosisService/HealthService Protocols, Services container"
  - "khetsetu_backend.services: FakeDiagnosisService (colour-driven, safe image checks), FakeHealthService, build_services(settings)"
  - "khetsetu_frontend: build_ui(services), diagnose_upload, load_banner, presenters, English message table"
  - "app.py composition root: _ensure_workspace_importable, build_demo, launch_options, main (exits 2 on bad config)"
  - "End-to-end tests over real HTTP and a test proving app.py is the only module importing both backend and frontend"
affects: [01-05, 01-06, 01-07, phase-4-diagnosis]

# Nothing committed by this run (user instruction). The draft of Task 1 was already in the
# user's own commit 1b0c993, which is HEAD both before and after this plan.
commits: 0
plan_head_before: 1b0c9930032978d366f6ca6e37591a5005383b06
plan_head_after: 1b0c9930032978d366f6ca6e37591a5005383b06

actuals:
  tokens: 14100   # chars/4 over the 17 files created or changed (56,382 characters)
  tasks: 3
  commits: 0

tech-stack:
  added: []
  patterns:
    - "Frontend sees only contract DTOs and Protocols; app.py is the one place that builds real objects and hands them over"
    - "Refusal honesty is encoded in the DTO validator, not in UI code"
    - "Errors cross the seam as typed ContractError subclasses carrying a MessageKey; the UI never shows exception text"
    - "Image safety order: byte length, then header pixel count, then decode, with Pillow bomb warnings turned into errors"

key-files:
  created:
    - contracts/src/khetsetu_contracts/errors.py
    - frontend/src/khetsetu_frontend/messages.py
    - frontend/src/khetsetu_frontend/presenters.py
    - contracts/tests/test_contracts_models.py
    - backend/tests/test_backend_fakes.py
    - frontend/tests/test_frontend_presenters.py
    - frontend/tests/test_frontend_ui.py
    - tests/test_composition_root.py
  modified:
    - contracts/src/khetsetu_contracts/__init__.py
    - contracts/src/khetsetu_contracts/models.py
    - contracts/src/khetsetu_contracts/protocols.py
    - backend/src/khetsetu_backend/services/fakes.py
    - backend/src/khetsetu_backend/services/container.py
    - frontend/src/khetsetu_frontend/ui.py
    - app.py
    - tests/test_app_e2e.py
    - pyproject.toml

key-decisions:
  - "The upload box is gr.File(file_types=['image']), not gr.Image: gr.Image opens every upload with Pillow before our handler runs, so a text file renamed .png ended in Gradio's generic error instead of our friendly message"
  - "Subclassing gr.Image to skip that decode was tried and rejected: Gradio writes a generated ui.pyi stub into the source tree for every Component subclass"
  - "Demo colour rule (green -> diagnosed, red -> not a leaf, blue -> unsupported crop, dark -> low confidence) is documented as a demo rule that Phase 4 replaces"

patterns-established:
  - "Pattern 1: new service = Protocol in contracts, fake in backend/services/fakes.py, wired only in container.py, rendered through a presenter"
  - "Pattern 2: a test that launches Gradio uses a free port from a bound socket and closes both client and demo"

requirements-completed: [FND-06]

coverage:
  - id: D1
    description: "A user uploads an image over HTTP and sees a result rendered by the frontend from a fake service, through contracts only"
    requirement: FND-06
    verification:
      - kind: e2e
        ref: "tests/test_app_e2e.py#test_upload_returns_a_fake_diagnosis_over_http"
        status: pass
    human_judgment: false
  - id: D2
    description: "app.py is the only module importing both backend and frontend; frontend imports nothing from backend"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "tests/test_composition_root.py#test_only_app_py_imports_both_backend_and_frontend"
        status: pass
      - kind: integration
        ref: "uv run lint-imports (3 kept, 0 broken)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A non-DIAGNOSED result can never carry a disease name, crop or alternatives"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "contracts/tests/test_contracts_models.py#test_a_refusal_can_never_carry_a_name_crop_or_alternatives (12 cases)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Garbage bytes, too many bytes and too many pixels give friendly messages, never a stack trace"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "backend/tests/test_backend_fakes.py (garbage, byte cap before decode, pixel cap, Pillow bomb warning and error)"
        status: pass
      - kind: e2e
        ref: "tests/test_app_e2e.py#test_a_text_file_renamed_to_png_gives_the_invalid_image_message and #test_an_upload_above_the_byte_limit_gives_the_too_large_message"
        status: pass
    human_judgment: false
  - id: D5
    description: "Page banner says Demo mode on load; four colours give four different outcome renderings"
    requirement: FND-06
    verification:
      - kind: e2e
        ref: "tests/test_app_e2e.py#test_the_page_banner_says_demo_mode and #test_the_four_demo_colours_give_four_different_renderings"
        status: pass
    human_judgment: false
  - id: D6
    description: "python app.py exits 2 at once with KHETSETU_APP_ENV missing (and with a blocking dataset mode on a Space), naming the variable"
    requirement: FND-06
    verification:
      - kind: e2e
        ref: "tests/test_app_e2e.py#test_app_exits_2_at_once_when_app_env_is_missing and #test_app_exits_2_when_the_space_asks_for_a_blocking_dataset_download"
        status: pass
    human_judgment: false
  - id: D7
    description: "app.py works with the packages installed AND with only third-party dependencies (sys.path fallback)"
    requirement: FND-06
    verification:
      - kind: unit
        ref: "tests/test_app_e2e.py#test_app_adds_missing_workspace_sources_to_sys_path (simulated by hiding the packages from find_spec; a real Space bundle was not built)"
        status: pass
    human_judgment: false
  - id: D8
    description: "Manual check in a desktop browser and at phone width: banner visible, upload shows a result, no stack trace"
    requirement: FND-06
    verification:
      - kind: other
        ref: "Task 3 human-check; only a curl smoke test was done (HTTP 200, /config lists api names diagnose and readiness)"
        status: not_run
    human_judgment: true

duration: 55min
completed: 2026-10-25
status: complete
---

# Phase 1 Plan 04: Walking-skeleton tracer Summary

**An image uploaded to the running Gradio app reaches a fake diagnosis service only through typed `contracts/` Protocols; `app.py` is the single composition root, and the contract itself refuses to let a "not sure" answer carry a disease name.**

## Performance

- **Duration:** about 55 min (a good part spent on Gradio and pytest warning-handling surprises, see Deviations)
- **Completed:** 2026-10-25
- **Tasks:** 3 of 3 (Task 1 tracer, Task 2 TDD, Task 3 TDD)
- **Files created:** 8, modified: 9
- **Commits:** 0 (user instruction: "do not commit changes, i will commit myself")

## Accomplishments

- FND-06 delivered: three packages with a typed seam, the frontend depending only on contracts, and one composition root wiring them. Proven by `uv run lint-imports` (3 kept, 0 broken) and `tests/test_composition_root.py`.
- Contracts: `DiagnosisResult` validates that a refusal (low confidence, not a leaf, unsupported crop) has no `disease_id`, `display_name`, `crop` or `top_k`, that `message_key` matches the status, that `top_k` has at most 3 entries and that scores are in [0, 1]. It can already carry every Phase 4 outcome, so Phase 4 changes no contract.
- Backend fake: deterministic colour rule; checks bytes first, then header pixel count, then decodes; turns Pillow decompression-bomb warnings and errors into `ImageTooLargeError`; garbage becomes `InvalidImageError`.
- Frontend: English message table with one string per `MessageKey` (test fails if a key is added without a string), pure presenters, a handler that maps `ContractError` to its message and hides unexpected exceptions (logged server-side only), and a "Demo mode" banner loaded on every page load (`/readiness`).
- `app.py`: `launch_options` (max_file_size from settings, `ssr_mode=False`, `show_error=False`), request queue (max 20, 2 at once), and exit code 2 with the variable named on bad configuration. A comment marks where plan 01-05's dataset prefetch goes.
- `make check` exits 0: 185 tests passed, coverage 99.12 percent (floor 80). `KHETSETU_APP_ENV=local uv run python app.py` serves HTTP 200 and exposes the `diagnose` and `readiness` endpoints.

## Task Commits

None. All work is in the working tree (the Task 1 draft files were already part of the user's commit 1b0c993, so `git status` shows them as modified rather than new).

## Files Created/Modified

- `contracts/src/khetsetu_contracts/{models,errors,protocols,__init__}.py` - DTOs, honesty validator, errors with message keys, Protocols, `Services(diagnosis, health)`
- `backend/src/khetsetu_backend/services/{fakes,container}.py` - fakes and `build_services(settings)`
- `frontend/src/khetsetu_frontend/{messages,presenters,ui}.py` - text, rendering, Gradio page
- `app.py` - composition root
- `pyproject.toml` - narrow warning filters and one mypy override (see Deviations)
- Tests: `contracts/tests/test_contracts_models.py`, `backend/tests/test_backend_fakes.py`, `frontend/tests/test_frontend_presenters.py`, `frontend/tests/test_frontend_ui.py`, `tests/test_app_e2e.py`, `tests/test_composition_root.py`

## Decisions Made

- `gr.File(file_types=["image"])` for the upload (reason above). Consequence: no in-page webcam capture and no image preview in this skeleton. On phones the file picker still offers the camera.
- A fake `top_k` for the diagnosed case lists Late blight 0.62, Early blight 0.21, Septoria leaf spot 0.08.
- `Readiness` precedence in the banner: a loading or failed state is shown first, and the Demo mode line is always added when the mode is FAKE.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Warnings-as-errors broke any test that launches Gradio**
- **Found during:** Task 1 (the killed run's draft e2e test errored)
- **Issue:** `filterwarnings = ["error"]` turns Gradio's unclosed event loops and sockets (created when a `Blocks` is built or launched) and a pandas 4 deprecation inside Gradio's request-timing summary into failures.
- **Fix:** three narrow `ignore` lines appended in `[tool.pytest.ini_options] filterwarnings`: unclosed event loop, unclosed socket, `pandas.errors.Pandas4Warning`. The e2e module additionally ignores `unclosed file` (gradio_client leaves the uploaded file open). Every other warning is still an error.
- **Files modified:** pyproject.toml, tests/test_app_e2e.py

**2. [Rule 1 - Bug] gr.Image rejects non-image files before our code runs**
- **Found during:** Task 3 (text file renamed .png test)
- **Issue:** with `gr.Image(type="filepath")` Gradio opens the upload with Pillow in its own preprocessing, raising a Gradio error instead of letting the service return the friendly invalid-image message.
- **Fix:** switched to `gr.File` as described under Decisions. Subclassing `gr.Image` to skip the decode worked but made Gradio generate a `ui.pyi` stub inside the source tree, so it was removed.
- **Files modified:** frontend/src/khetsetu_frontend/ui.py

**3. [Rule 3 - Blocking] mypy strictness for Gradio tests**
- **Issue:** `gradio_client` ships no type information.
- **Fix:** the one permitted mypy override (`ignore_missing_imports` for `gradio_client`). The draft's `# type: ignore` on `Settings(...)` was replaced by passing `AppEnv.CI`.
- **Files modified:** pyproject.toml, tests/test_app_e2e.py

### Plan deviations caused by user instructions

**4. No new tooling, no commits.** Nothing was added beyond the one mypy override and the warning filters above. Commit-based criteria (per-task commits, final docs commit) were not performed; `commits: 0` is the measured value. The success criterion "`git log --oneline | head -1` is still df765d6" no longer applies literally: HEAD is the user's own commit 1b0c993 and it did not move during this run.

**5. Webcam source dropped.** Plan Task 1 asked for `sources=["upload", "webcam"]` on `gr.Image`. Not possible with `gr.File` (deviation 2).

**6. A non-image extension is rejected by Gradio, not by our service.** With `file_types=["image"]` a `.txt` upload gets Gradio's own short "invalid file type" notice rather than our message. A renamed text file (`.png`) does reach our service and gets the friendly message (tested). No stack trace is shown in either case.

**7. The 'sys.path fallback' is verified by simulation.** The unit test hides the packages from `importlib.util.find_spec`; a bundle with only third-party dependencies installed was not built here (plan 01-05/06 own the Space bundle).

**Total deviations:** 3 auto-fixed, 4 plan-adherence notes.

## Issues Encountered

- **Gradio phones home by default.** On launch the log shows requests to `huggingface.co/api/telemetry/...gradio-initiated-analytics` and `api.gradio.app/pkg-version`. For a farmer-facing app this is worth a decision (set `GRADIO_ANALYTICS_ENABLED=False`); not changed here as it is a policy choice (see Threat Flags).
- Hanging or killed earlier launches left no stray processes; `ps` is clean.
- Manual browser check (desktop and phone width) was not done; only an HTTP smoke test.

## User Setup Required

None.

## Known Stubs

The fake services are intentional and visible to users (Demo mode banner): `FakeDiagnosisService` and `FakeHealthService` in `backend/src/khetsetu_backend/services/fakes.py`. Phase 4 replaces the diagnosis fake at the composition root (`container.py`); the frontend and contracts do not change. Not recorded in `.planning/WINDOWS.md` because this is the planned tracer behaviour, not a defect.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: outbound-telemetry | app.py | Gradio sends anonymous usage/version pings to huggingface.co and api.gradio.app at launch; consider disabling before real farmer traffic |

Plan threat model status: T-01-10 (size, pixel cap and bomb handling tested at the service; `max_file_size` set from settings and tested to reject at Gradio), T-01-11 (only enum-keyed strings and server display names are rendered; file name asserted absent), T-01-12 (handler catches everything, `show_error=False`, exception text asserted absent from output), T-01-13 (Demo mode banner), T-01-SC (no new dependencies).

## Next Phase Readiness

- Plan 01-05 can add the dataset prefetch at the marked line in `app.py:main()`; the Space bundle must run `app.py` with only third-party packages installed (the path fallback is in place).
- `make check` is green and `app.py` is already in the mypy `files` list.
- Open from earlier plans: Pillow audit finding (01-03) is unchanged.

## Self-Check: PASSED

- All 17 files listed above exist (checked with `git status --short`); no stray `ui.pyi`.
- Zero commits made: HEAD is 1b0c993 before and after.
- `make check` exit 0 (185 passed, coverage 99.12 percent); `uv run lint-imports`: 3 kept, 0 broken; `uv run pytest -m e2e`: part of the 185.

---
*Phase: 01-walking-skeleton-hosting-verification*
*Completed: 2026-10-25*
