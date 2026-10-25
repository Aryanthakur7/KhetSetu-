---
gsd_state_version: "1.0"
current_phase: 2
current_phase_name: Trustworthy Data & Field Probe
status: planning
stopped_at: Phase 1 complete, ready to plan Phase 2
last_updated: "2026-10-25T10:19:49.355Z"
last_activity: 2026-10-25
last_activity_desc: Phase 1 complete, transitioned to Phase 2
state_head: 1b0c9930032978d366f6ca6e37591a5005383b06
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 7
  completed_plans: 7
  percent: 14
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-23)

**Core value:** A farmer gets a correct, trustworthy disease diagnosis from a leaf photo, and an honest "I'm not sure, send a clearer photo" instead of a confident wrong answer.
**Current focus:** Phase 1 — Walking Skeleton & Hosting Verification

## Current Position

Phase: 2 — Trustworthy Data & Field Probe
Plan: Not started
Status: Ready to plan
Last activity: 2026-10-25 — Phase 1 complete, transitioned to Phase 2

Progress: [█░░░░░░░░░] 14%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 7 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 1 P01-01 | 4min | 3 tasks | 18 files |
| Phase 1 P01-02 | 15min | 3 tasks | 14 files |
| Phase 1 P01-04 | 55min | 3 tasks | 17 files |
| Phase 1 P05 | 30min | 3 tasks | 18 files |
| Phase 01 P06 | 45min | 3 tasks | 13 files |
| Phase 1 P07 | 25min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 7 vertical-slice phases, all in MVP mode. Phase 1 is the walking skeleton; Phases 4, 6 and 7 are farmer-facing; Phases 2, 3 and 5 are researcher/developer slices.
- [Roadmap]: Hard orderings kept from research: hosting verification first (Phase 1), frozen grouped split before model selection (2 before 3), knowledge store before chat (5 before 6).
- [Roadmap]: Diagnosis track (2-3-4) and ingest side of the knowledge track (05-01 to 05-04) can run in parallel after Phase 1.
- [Roadmap]: Research's separate "Hardening" phase folded away; only OPS-02 (docs) remained as a v1 requirement, so it joins Phase 7 with the chat resilience work.
- [Roadmap]: DATA-04 (supported-crops list) lands in Phase 2 and OPS-01 (warming-up page) in Phase 4, where each first becomes user-visible.
- [Phase 1]: [01-01] Constrain pydantic<=2.12.5 (uv constraint-dependencies): gradio[oauth,mcp]==6.30.0, which the Space installs first, is unsatisfiable with pydantic 2.14.1
- [Phase 1]: [01-02] Env var contract: KHETSETU_ prefix; HF_TOKEN and HF_SPACE_ID (alias SPACE_ID) unprefixed; SettingsError names env vars and never echoes inputs or secrets
- [Phase 1]: [01-02] Deployed Space rejects KHETSETU_DATASET_MODE=blocking; effective mode is blocking on local, off on ci and space
- [Phase 1]: Upload box is gr.File(file_types=image), not gr.Image, because gr.Image decodes uploads before our handler and shows Gradio's generic error for non-images
- [Phase 1]: Refusal honesty is enforced in the DiagnosisResult validator: only DIAGNOSED may carry a disease name, crop or alternatives
- [Phase 1]: ensure_dataset: size check on every call, sha256 after download/--verify; downloader injectable and lazily imported so the Space never needs huggingface_hub/pyarrow/yaml from the data package
- [Phase 1]: No policy test for future entrypoints (user: keep tooling light); @requires_dataset and docs/dataset.md carry the convention
- [Phase 01]: Space bundle is an allow-list copy (app.py + three src trees); the sys.path packaging passes the local rehearsal, the editable ./pkg packaging fails when requirements.txt is installed from outside the bundle
- [Phase 1]: ADR 0001: private ZeroGPU Gradio Space as interim hosting (free cpu-basic Gradio needs PRO, HTTP 402); sys.path packaging; LLM funding UNRESOLVED (HTTP 402); fallback Static Space + external backend

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1, VERIFIED 2026-10-25] Free Hugging Face account: cpu-basic Gradio Space creation is BLOCKED (HTTP 402, needs PRO); a private ZeroGPU Space works as interim hosting; LLM calls return HTTP 402 (no credits). See docs/decisions/0001-hosting-packaging-and-llm-funding.md. RESOLVED 2026-10-25 by the team: keep the private ZeroGPU Space for hosting; LLM = Google Gemini API with the team API key (planned env var GEMINI_API_KEY, added in Phase 6; Space secret, never a Variable). Still open: pick/test the Gemini model id and Hindi quality at the start of Phase 6.
- [Phase 1, accepted by user with caveats] OPEN human items: (a) CI has never run on GitHub; push, check the run, enable branch protection with checks `quality`, `audit`, `secrets` (docs/ci.md); FND-04 stays unticked until then. (b) `make audit` is red: 35+ Pillow advisories, Gradio 6.30.0 caps pillow<13; decide override / dated ignore / wait. (c) Rotate the Hugging Face token used for probes. (d) Test Space `HimanshuGoyal2004/khetsetu-skeleton` (private, RUNNING) left in place; delete or keep.
- [Phase 4] Remove `mark_zerogpu_ready()` workaround in app.py when a real GPU function exists; HF build image pins torch<=2.13.0 vs lock 2.14.1; upload box is gr.File (no webcam/preview).
- [Phase 1] `data/` (823 MB) is currently untracked; the `.gitignore` plan (01-01) must land before any `git add` of the working tree.
- [Phase 2] Field probe set needs manual collection of about 100-200 field leaf photos plus about 50 non-leaf images; licences of public field datasets and of the AgML mirror are unconfirmed.
- [Phase 3] Training compute (local GPU vs HF Jobs on a free account) is not yet confirmed.
- [Phase 5] Authoritative Hindi source coverage is thin and often legacy-font PDFs; scraping licences are per source; keep derived corpora private by default.
- [Phase 6] Hindi quality of candidate LLMs is unverified; product decision pending on chat without a diagnosis (`DiagnosisContext | None`).

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-25T10:13:27.445Z
Stopped at: Phase 1 complete, ready to plan Phase 2
Resume file: None
