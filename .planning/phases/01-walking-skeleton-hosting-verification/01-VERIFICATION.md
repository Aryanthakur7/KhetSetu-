---
phase: 01-walking-skeleton-hosting-verification
verified: 2026-10-25T00:00:00Z
status: passed
score: 4/5 must-haves verified (SC5 structurally verified, remote CI unproven)
covered_files: [".github/workflows/ci.yml", "Makefile", "app.py", "docs/decisions/0001-hosting-packaging-and-llm-funding.md"]
covered_digest: "v3:sha256:870be5d4e8b04b169551b0a31b9b0dfd376ed73971987d0e4156806c379a0460"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - item: "SC5 remote CI enforcement, LLM funding decision, hosting target (PRO vs Static Space), live-Space visual check"
    accepted_by: "user (HimanshuGoyal2004), 2026-10-25"
    reason: "User chose 'Accept with caveats' when asked how to close Phase 1. These four human items stay OPEN and are tracked in STATE.md; they are not verified."
human_verification:
  - test: "Push to GitHub and open a PR; watch the CI workflow (quality, audit, secrets jobs)"
    expected: "quality and secrets jobs green; a deliberately broken change (ruff/mypy/test/import/secret) turns the run red"
    why_human: "Nothing has been pushed; the workflow has never run on GitHub"
  - test: "Enable branch protection on main with the CI jobs as required checks (docs/ci.md section 'Branch protection')"
    expected: "A red CI run blocks merge"
    why_human: "Repo-admin step in GitHub settings; cannot be verified from the working tree"
  - test: "Decide the LLM funding option from ADR 0001 (PRO, buy credits, BYO key, local model) and the hosting target (PRO vs Static Space split)"
    expected: "ADR status moves from Blocked to Accepted"
    why_human: "Product/money decision owned by the team"
  - test: "Open the private Space https://huggingface.co/spaces/HimanshuGoyal2004/khetsetu-skeleton while logged in and upload a leaf image"
    expected: "Demo-mode banner and fake Tomato - Late blight diagnosis"
    why_human: "Live-Space evidence rests on redacted build/space-probe/*.json reports (smoke-syspath-ok.json: outcome ok, 8.58 s; wait-attempt2-syspath-ok.json: RUNNING); not re-probed by the verifier (no token use)"
---

# Phase 1: Walking Skeleton & Hosting Verification - Verification Report

**Phase goal:** push a change, watch it pass CI and run on a deployed hello-world Space, so hosting, packaging and LLM funding are proven before real features.
**Status:** passed by user acceptance (originally human_needed; see `overrides` in the frontmatter, the four human items remain open and unverified). The working tree meets the goal on every locally checkable point; the remaining items need GitHub/HF-account actions or a team decision.
**Re-verification:** No, initial verification.

## Success criteria

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Hello-world live on real HF account, monorepo packages installed, recorded decision on hosting / packaging / LLM funding with named fallback | VERIFIED (with caveats) | ADR 0001 records: cpu-basic Gradio creation blocked (HTTP 402), zero-a10g allowed; Space `HimanshuGoyal2004/khetsetu-skeleton` private, RUNNING after 2 deploys; packaging decision = sys.path (editable `./contracts` BUILD_ERROR on real HF build). Probe reports `build/space-probe/` agree: `wait-attempt2-syspath-ok.json` stage RUNNING, `smoke-syspath-ok.json` ok, `deploy-editable`/`wait-editable` show the failing variant. LLM probe HTTP 402 -> funding UNRESOLVED, with 4 ranked options and a named hosting fallback (Static Space + external backend). Criterion asks for a recorded decision with a fallback, which exists; the funding itself is not resolved (ADR Status: Blocked). Reports contain no `hf_...` token strings (grep). |
| 2 | Upload on the Space returns a result rendered by frontend from a fake diagnosis service via typed contracts and one composition root | VERIFIED | `app.py` is the only module importing backend and frontend; `uv run lint-imports`: 3 contracts kept, 0 broken (frontend->contracts only, backend has no UI, contracts leaf). `tests/test_app_e2e.py` drives the real app over HTTP (upload -> fake diagnosis, 4 colours -> 4 renderings, invalid image, too-large) and passes. Space smoke: "This looks like: Tomato - Late blight", demo_mode true. Caveat: uses `gr.File` not `gr.Image` (deliberate, documented in ui.py); no preview/webcam. |
| 3 | Missing/invalid setting fails at startup naming the setting; new dev can configure from .env.example alone | VERIFIED | From an empty temp dir with `env -i`: `khetsetu config check` -> "Invalid configuration (1 problem(s)): - KHETSETU_APP_ENV: required, not set. See .env.example and docs/configuration.md". With `KHETSETU_MAX_UPLOAD_BYTES=abc` -> names that setting. `.env.example` documents every setting with defaults/ranges; `test_app_exits_2_at_once_when_app_env_is_missing` passes. (`.env` itself was not read.) |
| 4 | Entrypoints first download the dataset; second run reuses cache with no download | VERIFIED | `khetsetu data inspect` and `data download` -> `outcome: cache_hit`, pinned revision cb08789a..., 55448 rows, 39 classes, 2 shards (HF_HUB_OFFLINE=1, proving no network needed). Unit tests: `test_complete_dataset_is_a_cache_hit_and_never_downloads`, `test_missing_files_are_downloaded_once_then_reused`, size/hash/symlink guards. `app.py` calls `prepare_runtime` (blocking locally, off on ci/space). The live-network test is opt-in (`-m network`, deselected here); no training/eval entrypoints exist yet beyond `data` CLI plus a guard module, so "any entrypoint" is satisfied by the shared `ensure_dataset` function. |
| 5 | Breaking ruff / strict mypy / pytest / import-linter / secret scan is blocked in CI; data/, weights, secrets cannot be committed by accident | PARTIAL (structural only) | Local gates all green: ruff check + format (65 files), mypy strict (53 files, no issues), lint-imports (3 kept), pytest 276 passed (2 deselected), coverage 97.97% vs floor 80. `make secrets` (gitleaks, full history, 9 commits) no leaks. `.github/workflows/ci.yml` has quality (lint, type, imports, test), audit and secrets (fetch-depth 0) jobs, SHA-pinned actions, calling Makefile targets; `tests/test_ci_workflow.py`, `tests/test_gates_canary.py`, `tests/test_repo_hygiene.py` pass. pre-commit config has large-file (500 KB), private-key, gitleaks, ruff, mypy, lint-imports hooks. `git check-ignore -v`: `data/x` -> `/data/`, `.env` -> `.env`, `model.safetensors` -> `*.safetensors`; `git status --untracked-files=all` shows no data/, .env or build/ entries (`.env.example` is the only tracked env file). NOT proven: the workflow has never run on GitHub and branch protection (required checks) is a manual admin step, so "blocked in CI" is unproven end to end. Also, the audit job will be red (see open items). |

## Requirements coverage

| Req | Status | Note |
|-----|--------|------|
| FND-01 | SATISFIED | typed settings, fail-fast naming the setting (SC3) |
| FND-02 | SATISFIED | .env.example + gitleaks history scan clean + hooks |
| FND-03 | SATISFIED | cache_hit / unit-tested download path (SC4) |
| FND-04 | PARTIAL | all gates exist and pass locally; remote enforcement unproven (branch protection manual) |
| FND-05 | SATISFIED | hello-world probed on real account; decisions recorded; funding open but documented with fallbacks |
| FND-06 | SATISFIED | lint-imports contracts + single composition root |
| OPS-03 | SATISFIED | check-ignore and clean status confirmed |

All seven are ticked in REQUIREMENTS.md; FND-04 should arguably stay unticked until the first CI run is green and branch protection is on. No orphaned requirements found.

## Anti-patterns / open items (reported, not hidden)

- `make audit` is RED: pip-audit reports 35+ Pillow advisories; Gradio 6.30.0 caps `pillow<13`, so the fix is blocked upstream. The CI `audit` job will fail on first push; decide whether it is allowed-to-fail/ignore-listed (docs/ci.md section "Handling a pip-audit finding" documents the open finding) or a required check. Treat as WARNING for FND-04.
- LLM funding UNRESOLVED (HTTP 402 on llm-probe). ADR Status: Blocked. Blocks Phase 6, not Phase 2-5.
- Free account cannot create cpu-basic Gradio Space (HTTP 402); interim private ZeroGPU Space is RUNNING and was intentionally left up.
- `mark_zerogpu_ready()` in app.py is a platform workaround (empty `@spaces.GPU` function) to be replaced in Phase 4; it is unit-tested and a no-op off-HF.
- UI uses a Gradio file picker (`gr.File`) instead of `gr.Image`: no webcam/preview; revisit in Phase 5.
- torch pin: HF build image imposes `torch<=2.13.0`, lock has 2.14.1; harmless now (hello-world has no torch) but a Phase 4 blocker to resolve.
- Remind owner to revoke the HF token used for probes (ADR consequence).
- Commit state: most work is uncommitted by user instruction; the verification judges the working tree. Redacted probe JSONs live under git-ignored `build/` and will not be in the repo; the ADR carries the copied findings.
- No TBD/FIXME/XXX blockers checked in changed Python files beyond what lint passes (ruff has no T-rule failures); no stub components found in the request path (the "fake" diagnosis service is the intended Phase 1 deliverable).

## Recommendation

Phase 1 goal is substantively achieved. Before treating the phase as closed: (1) commit and push, confirm the CI run (decide on the red `audit` job), turn on branch protection; (2) team picks the LLM funding option and the hosting target (PRO vs Static split) and the ADR moves from Blocked to Accepted. Neither blocks starting Phase 2 (data/training work), but the funding decision gates Phase 6.

---

_Verified: 2026-10-25_
_Verifier: Claude (gsd-verifier)_
