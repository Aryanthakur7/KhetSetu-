# Walking Skeleton — KhetSetu

**Phase:** 1
**Generated:** 2026-10-24

## Capability Proven End-to-End

A user uploads a leaf photo in a Gradio app (locally, and on a Hugging Face Space if the team's account allows it) and sees a result rendered by the frontend from a fake diagnosis service, reached only through the typed `contracts/` layer and one composition root, while every change to the repository is gated by ruff, strict mypy, pytest, import-linter and a secret scan.

Status of the "on a Space" half is deliberately **unverified at planning time**: plan 01-07 measures it against the team's real account and records the result (including a blocked outcome and the fallback) in ADR 0001. Nothing in this document or in plans 01-01 to 01-06 assumes it succeeds.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language and runtime | Python 3.12 (`requires-python >=3.12,<3.13`, `.python-version` 3.12) | Matches STACK.md: pydantic-settings 2.16 and Pillow need 3.11+, wheels for the later ML stack lag on 3.13/3.14, and Spaces default to 3.10 so `python_version: "3.12"` is set explicitly |
| Repo and packaging | uv workspace: root app project (`khetsetu`, not packaged) plus members `contracts/`, `backend/`, `frontend/` (src layout, hatchling, PEP 561 `py.typed`); one hash-pinned `uv.lock` | One lockfile, one environment, separate import packages `khetsetu_contracts`, `khetsetu_backend`, `khetsetu_frontend` keep a later two-Space split cheap (brief B-01) |
| Frontend | Gradio 6.30.0 (exact pin), `pillow>=12,<13` | Gradio 6 declares `pillow<13`; theme/css/js live on `launch()`; Space `sdk_version` is derived from the lock so the two cannot drift |
| Contracts seam | `khetsetu_contracts`: pydantic DTOs (`DiagnosisRequest`, `DiagnosisResult`, `Readiness`, ...) plus `Protocol`s (`DiagnosisService`, `HealthService`) and a `Services` container; images cross as encoded bytes | Pure pydantic keeps the seam importable anywhere and HTTP-ready; the contract itself forbids a refusal carrying a disease name (core value) |
| Composition root | Repo-root `app.py` is the only module importing both backend and frontend; it also holds a `sys.path` fallback that makes the same file run on a Space where only third-party dependencies are pip-installed | Satisfies "single composition root"; the fallback is the packaging answer to the Gradio-SDK install order, to be confirmed by ADR 0001 |
| Boundary enforcement | import-linter forbidden contracts in `pyproject.toml` (frontend to contracts only; backend has no UI; contracts is a leaf) run in `make check`, pre-commit and CI | Boundaries are checked by machine, not convention (FND-06) |
| Configuration | pydantic-settings `Settings` with `KHETSETU_` prefix (HF standard names `HF_TOKEN`, `HF_SPACE_ID` unprefixed), `.env` + committed `.env.example`, `SecretStr`, fail-fast `SettingsError` naming the env var; one required setting `KHETSETU_APP_ENV` (local, ci, space) | FND-01/FND-02; app environment also decides dataset behaviour so the Space cannot be set to download data |
| Quality gates | ruff (lint+format), mypy strict (pydantic plugin), pytest + coverage floor 80, import-linter, gitleaks (history in CI, staged in pre-commit), pip-audit, 500 KB large-file hook; single `Makefile` is the source of truth that CI calls | FND-04 plus proof by canary tests that each gate fails on a planted violation |
| Data hygiene | root-anchored `.gitignore` (`/data/`, weights, `.env`, caches) committed first; test asserts ignore rules and that history never tracked `data/` | OPS-03; anchoring keeps the `khetsetu_backend.data` code package trackable |
| Dataset access | `ensure_dataset(settings)` with a packaged manifest (pinned revision `cb08789a92460034ced0449eac1dba72bb4883da`, per-file size and sha256), size check on cache hit with zero network, sha256 after download; `requires_dataset` decorator + policy test; local runs prefetch, Space and CI never do | FND-03; existing 823 MB local copy is reused |
| Data layer | None in Phase 1 (no database, no persisted user data). The only persistent read is the Hub dataset cache under `data/`, exercised by `khetsetu data inspect` | The product's state is artifacts on the Hub (STACK.md); photos are processed in memory and not stored |
| Auth | None for end users. The HF token is a developer secret in the untracked `.env`; never a Space Variable and never on the Space in Phase 1 | Keeps the skeleton free of accounts (Out of Scope) and the token off the deployed app |
| Deployment target | Hugging Face Space, `sdk: gradio`, CPU Basic, private during the spike; ladder: cpu-basic Space, then zero-a10g Space, then named alternatives (Static Space + external backend, other hosting) | Decided by plan 01-07 from observed outcomes and recorded in `docs/decisions/0001-hosting-packaging-and-llm-funding.md` |
| Packaging on the Space | Bundle built by `scripts/space_bundle.py` (allowlist: `app.py`, three `src` trees, generated Space `README.md`, pinned `requirements.txt` from `uv export`); `sys.path` fallback versus editable `./backend` requirements compared locally (01-06) and on the real build (01-07) | HF installs requirements from a copy outside the repo, so relative local paths are expected to fail; to be confirmed |
| LLM access | Model id is a setting (`KHETSETU_LLM_MODEL`); funding probed with one minimal `InferenceClient` call in plan 01-07; no LLM client in Phase 1 | Provider interface and fallbacks arrive in Phase 6; Phase 1 only decides how calls will be paid for |
| Test strategy | Per-package tests plus root `tests/`; fake services behind contracts; end-to-end test over HTTP via `gradio_client`; opt-in markers `network`, `rehearsal`; hermetic env fixture | Fast, offline-by-default CI; the 823 MB dataset and any token are never needed by the default suite |
| Directory layout | `contracts/`, `backend/`, `frontend/` (each with `src/`, `tests/`, `README.md`), `app.py`, `scripts/`, `tests/`, `docs/` (with `decisions/`), `.github/workflows/`, `Makefile`, `.env.example` | Mirrors the team's reference projects (per-package README, docs, tests, scripts, `.env.example`, CI) |

## Stack Touched in Phase 1

- [x] Project scaffold (uv workspace, build, lint, type check, test runner, CI) — plans 01-01, 01-03
- [x] Routing — one real Gradio endpoint `/diagnose` (plus `/readiness`) — plan 01-04
- [ ] Database — not applicable in Phase 1; the equivalent real read is the Hub dataset cache read by `khetsetu data inspect` (plan 01-05). There is no real write of user data by design
- [x] UI — an upload control and result panel wired to the service through the Protocol — plan 01-04
- [x] Deployment — documented local full-stack run (`uv run python app.py`) AND a Space deploy attempt on the real account with a recorded outcome — plans 01-06, 01-07

## Out of Scope (Deferred to Later Slices)

- Any real model, calibration or confidence gate (Phase 3); the fake service uses a documented image-colour rule that Phase 4 replaces
- Retrieval, scraping, embeddings, knowledge snapshot (Phase 5) and any chat, LLM client, `ChatService` contract, citations or safety footer (Phases 6-7)
- Field/OOD probe set, grouped split, `diseases.yaml`, supported-crops list (Phase 2)
- Hindi UI strings (v2 for the diagnosis screen; chat is bilingual from Phase 6)
- Upload privacy policy: EXIF stripping, retention of Gradio's temporary upload cache, user-facing privacy notice (Phase 4); Phase 1 never persists or logs uploaded bytes itself
- Warming-up page and staged bootstrap manager (Phase 4); the readiness contract exists but only reports a fake READY state
- Scheduled ingest, budget guard, rate limits, degraded mode (Phase 7)
- A GitHub Actions deploy-to-Space workflow and any CI secret; deployment stays a manual, token-holder action
- Full `CLAUDE.md`/`AGENTS.md` alignment and final docs pass (Phase 7); Phase 1 ships package READMEs, `docs/architecture.md`, `docs/configuration.md`, `docs/ci.md`, `docs/dataset.md`, `docs/hosting.md`, ADR 0001

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions (swapping a fake for a real service at `build_services` is the intended change, not a decision change):

- Phase 2: A researcher evaluates any model on a frozen leak-free split and a held-out field probe set; `diseases.yaml` and the supported-crops list exist
- Phase 3: A researcher runs one command that trains, calibrates and publishes a gated classifier with `gate.json`
- Phase 4: A farmer uploads a photo and gets a diagnosis or an honest retake request; the real `DiagnosisService` replaces the fake at the composition root; warming-up page
- Phase 5: A developer runs one command that scrapes trusted sources into a versioned, citable knowledge snapshot the Space pulls
- Phase 6: A farmer chats in Hindi or English about the diagnosed disease with cited, safety-checked answers
- Phase 7: Chat degrades gracefully (live-search fallback, quota handling) and docs match the code

## Plan Map (Phase 1)

| Plan | Wave | Slice |
|---|---|---|
| 01-01 | 1 | Hygiene first (`.gitignore`), uv workspace skeleton, tool configuration, dependency lock |
| 01-02 | 2 | Typed settings, `.env.example`, fail-fast `khetsetu config check`, onboarding docs |
| 01-03 | 2 | CI and local gates: Makefile, workflow, import-linter, gitleaks, pre-commit, canary tests |
| 01-04 | 3 | Tracer: upload to fake diagnosis through contracts and the composition root |
| 01-05 | 4 | `ensure_dataset`, `requires_dataset` policy, mode-aware bootstrap, `khetsetu data` commands |
| 01-06 | 5 | Space bundle, Space-faithful local rehearsal, probe tooling, architecture and hosting docs |
| 01-07 | 6 | Human gate (HF token), live Space attempt, packaging comparison, LLM funding probe, ADR 0001 (the only plan with a checkpoint) |
