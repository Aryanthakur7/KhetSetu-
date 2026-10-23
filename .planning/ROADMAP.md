# Roadmap: KhetSetu

## Overview

KhetSetu goes from an empty repo to a farmer-facing Hugging Face Space in seven vertical slices. Phase 1 is a walking skeleton: a CI-gated, deployed hello-world Space that settles the open hosting, packaging and LLM-funding questions before any real feature is built. Phases 2-4 deliver the core value: a frozen leak-free split and a field probe set (Phase 2), a calibrated classifier with a refusal gate (Phase 3), and the farmer-facing diagnosis screen that says "send a clearer photo" instead of guessing (Phase 4). Phase 5 builds the citable, versioned knowledge snapshot and can run in parallel with Phases 2-4. Phase 6 joins the diagnosis and the knowledge store into cited, safety-checked Hindi/English chat. Phase 7 adds the live-search fallback, failure handling for LLM quota problems, and the onboarding docs.

**Execution notes:**
- Hard orderings: Phase 1 first; Phase 2 before Phase 3 (frozen grouped split before any model selection); Phase 5 before Phase 6 (knowledge store before chat).
- Parallelism: after Phase 1, the diagnosis track (2 -> 3 -> 4) and the ingest side of the knowledge track (plans 05-01 to 05-04) are independent and can run side by side.
- Plan lists below are sketches. `/gsd-plan-phase` produces the real plans, and plan counts are refined then.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Walking Skeleton & Hosting Verification** - CI-gated, typed, deployed hello-world Space that proves hosting, packaging and LLM funding
- [ ] **Phase 2: Trustworthy Data & Field Probe** - Frozen leak-free split, field/non-leaf probe set, label metadata and the supported-crops list
- [ ] **Phase 3: Gated Classifier** - Reproducible training, 3-backbone benchmark, field augmentation, calibrated refusal gate, Hub artifacts
- [ ] **Phase 4: Farmer Diagnosis** - Photo in, honest diagnosis or retake request out, with summary card and warming-up page
- [ ] **Phase 5: Knowledge Snapshot** - Source registry, polite scraper, dosage records, embedder bake-off, versioned snapshot the Space pulls
- [ ] **Phase 6: Cited Safe Chat** - Diagnosis-aware Hindi/English chat with citations, dosage guard and deterministic safety footer
- [ ] **Phase 7: Resilient Chat & Release Readiness** - Allowlisted live-search fallback, LLM-quota degraded mode, onboarding docs

## Phase Details

### Phase 1: Walking Skeleton & Hosting Verification

**Goal:** As a developer, I want to push a change and watch it pass CI and run on a deployed hello-world Space, so that hosting, packaging and LLM funding are proven before real features are built.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05, FND-06, OPS-03
**Success Criteria** (what must be TRUE):
  1. A hello-world Gradio app is live on the team's real Hugging Face account with `backend/` and `frontend/` installed from the monorepo, and a recorded decision states whether a free account can host it, how the packages install on the Space, and how LLM calls will be funded (with a named fallback if blocked).
  2. On that deployed Space, a user uploads an image and sees a result rendered by the frontend from a fake diagnosis service, reached only through the typed `contracts/` layer and a single composition root.
  3. Starting the app with a missing or invalid required setting fails at once with a message naming the setting, and a new developer can configure everything from the committed `.env.example` alone.
  4. Running any training, evaluation or dev entrypoint first downloads `Project-AgML/plant_village_classification`; a second run reuses the cache and downloads nothing.
  5. A change that breaks ruff, strict mypy, pytest, import-linter or the secret scan is blocked in CI, and `data/`, model weights and secrets cannot be committed by accident.

**Plans**: 7 plans

Plans:
**Wave 1**
- [ ] 01-01-PLAN.md — `.gitignore` first (`data/`, weights, secrets), uv workspace with `backend/`, `frontend/`, `contracts/`, tool configuration and one lockfile

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 01-02-PLAN.md — typed Settings with fail-fast validation, committed `.env.example`, `khetsetu config check`, onboarding docs
- [ ] 01-03-PLAN.md — CI gates: ruff, mypy strict, pytest, import-linter (frontend depends on contracts only), gitleaks secret scan, pre-commit, with canary tests proving each gate bites

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 01-04-PLAN.md — Tracer slice: fake services behind `contracts/`, single composition root, hello-world Gradio upload-to-result app running locally

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 01-05-PLAN.md — Idempotent, cached `ensure_dataset()` wired into every training, evaluation and dev entrypoint (decorator plus policy test); Space and CI never download

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 01-06-PLAN.md — Space bundle builder, Space-faithful local rehearsal (packaging: editable install vs `sys.path`), probe tooling, architecture and hosting docs

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 01-07-PLAN.md — Human gate (HF token), live Space deploy on the real account, packaging comparison on the real build, LLM-funding probe, recorded hosting, packaging and funding decision with fallback (ADR 0001)

### Phase 2: Trustworthy Data & Field Probe

**Goal:** As a researcher, I want to evaluate any model on a frozen leak-free split and a held-out field probe set, so that model choices rest on honest field evidence rather than inflated PlantVillage accuracy.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. A researcher can rebuild the train/validation/test split from one command and get the identical frozen, versioned split (recorded hash), with near-duplicate leaf images grouped so no group appears in more than one split, confirmed by an automated leakage check.
  2. A researcher can run any model, even a trivial baseline, through one evaluation command against the held-out field/OOD probe set (about 100-200 real field leaf photos plus about 50 non-leaf images, never used in training) and see macro-F1 and the in-domain versus field gap side by side.
  3. A developer can look up each of the 39 classes in `diseases.yaml` and get crop, pathogen type, English name and Hindi name, and a check fails if any class has no entry.
  4. A farmer opening the deployed Space sees the explicit list of supported crops, derived from the dataset, together with a statement that other crops are not covered.

**Plans**: 4 plans
**Research flag**: yes - public field datasets overlapping the 14 crops (PlantDoc and similar), near-duplicate detection method, and licensing of field data.

Plans:
- [ ] 02-01: Near-duplicate grouping and frozen, hashed, versioned train/val/test split with an automated leakage check (including a border-only background probe)
- [ ] 02-02: Source and curate the field/OOD probe set (field photos plus non-leaf negatives) with licences recorded, kept out of training
- [ ] 02-03: One-command evaluation harness (macro-F1, per-class, in-domain vs field gap), proven end to end on a trivial baseline
- [ ] 02-04: `diseases.yaml` for all 39 classes (EN/HI) with a completeness check; supported-crops list derived from the dataset and shown in the Space

### Phase 3: Gated Classifier

**Goal:** As a researcher, I want to run one command that trains, calibrates and publishes a gated classifier, so that the app can refuse low-confidence photos instead of guessing.
**Mode:** mvp
**Depends on**: Phase 2 (frozen grouped split and field probe set must exist before any model selection)
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05
**Success Criteria** (what must be TRUE):
  1. A researcher can reproduce a training run from a single CLI command, with config, seed and split hash recorded and metrics tracked.
  2. A benchmark report compares ConvNeXt V2 Tiny, Swin Tiny and ViT on field-set macro-F1, calibration error and CPU latency, and the chosen model is selected from that report rather than from in-domain accuracy.
  3. Training applies field-style augmentation (background swap, lighting, blur), and the benchmark reports the field-set score with and without it.
  4. Given a leaf photo, a gated predict command returns accept, low-confidence or not-a-leaf using temperature scaling, the top-1/top-2 margin and a not-a-leaf class, with the threshold chosen from a risk-coverage curve on field data and its provenance stored in `gate.json`.
  5. A developer can fetch the trained model, model card and `gate.json` as versioned artifacts from the Hugging Face Hub.

**Plans**: 5 plans
**Research flag**: yes - OOD/non-leaf scoring method, background-swap augmentation, CPU latency and quantization, and calibration approach. Training compute (local GPU vs HF Jobs) is confirmed during planning.

Plans:
- [ ] 03-01: Tracer: reproducible `train` CLI with tracked metrics, one backbone trained and scored through the Phase 2 harness
- [ ] 03-02: Field-style augmentation pipeline (background swap, lighting, blur) with an on/off comparison
- [ ] 03-03: Three-backbone benchmark and selection report (field macro-F1, ECE, CPU latency)
- [ ] 03-04: Temperature scaling, margin and not-a-leaf gate, risk-coverage threshold selection, `gate.json` with provenance, gated predict CLI
- [ ] 03-05: Publish model, model card and `gate.json` as versioned Hub artifacts with a one-call fetch helper

### Phase 4: Farmer Diagnosis

**Goal:** As a farmer, I want to upload a leaf photo and get a clear diagnosis or an honest request for a clearer photo, so that I never act on a confident wrong answer.
**Mode:** mvp
**Depends on**: Phase 3 (published model and gate), Phase 2 (`diseases.yaml`), Phase 1 (Space, contracts)
**Requirements**: DIAG-01, DIAG-02, DIAG-03, OPS-01
**Success Criteria** (what must be TRUE):
  1. A farmer on a phone can upload or capture a leaf photo and see the disease name, a plain-language confidence level (High / Medium / Low) and the top three alternatives.
  2. A farmer who uploads a blurry, non-leaf or unsupported-crop photo gets an explicit low-confidence, not-a-leaf or unsupported-crop message with retake tips, and never a guessed disease name.
  3. A farmer sees a short curated summary card for the diagnosed disease, including a clear "healthy" outcome for healthy leaves.
  4. On a cold Space start, the farmer sees a "warming up" page immediately, and the upload form becomes usable once the model finishes loading in the background, with no timeout or blank screen.

**Plans**: 4 plans
**UI hint**: yes

Plans:
- [ ] 04-01: Tracer: real `DiagnosisService` (model and `gate.json` from the Hub, shared preprocessing with EXIF handling and size caps) swapped in for the fake at the composition root
- [ ] 04-02: Three-state result rendering: plain-language confidence, top-3 alternatives, retake tips, crop confirmation, tested on a real phone
- [ ] 04-03: Curated summary cards for all 39 classes including the healthy outcome
- [ ] 04-04: Staged bootstrap with readiness banner and "warming up" page; `preload_from_hub`; cold-start check on the deployed Space

### Phase 5: Knowledge Snapshot

**Goal:** As a developer, I want to run one command that scrapes trusted sources into a versioned, citable knowledge snapshot, so that chat answers can be grounded in sources I can audit.
**Mode:** mvp
**Depends on**: Phase 1 (plans 05-01 to 05-04 are independent of the ML track and can run in parallel with Phases 2-4); Phase 2 and Phase 4 for plan 05-05 (`diseases.yaml` for the 39-class coverage report, and the bootstrap manager that hosts the startup pull)
**Requirements**: KNOW-01, KNOW-02, KNOW-03, KNOW-04, KNOW-05
**Success Criteria** (what must be TRUE):
  1. A developer can open `sources.yaml` and see URL, licence, robots.txt stance and trust tier for every scraped source, and the scraper refuses a source that is missing any of them.
  2. Running the scraper respects robots.txt and rate limits, and every stored chunk carries its source URL, title, trust tier and fetch date.
  3. A developer can run the Hindi/English retrieval evaluation that compares candidate embedding models, and the embedding model in use is the one that evaluation selected.
  4. Ingest produces typed dosage records separate from prose, so answers can quote a retrieved dose instead of generating one.
  5. One command scrapes, chunks, embeds and publishes a versioned snapshot, and a fresh Space process pulls it at startup and answers a Hindi and an English query with cited chunks; a report shows which of the 39 classes have sources.

**Plans**: 5 plans
**Research flag**: yes - concrete Indian sources with robots.txt and terms, legacy-font Devanagari PDFs and OCR fallback, CIB&RC banned/restricted pesticide lists, and the embedder bake-off (bge-m3, multilingual-e5, Qwen3-Embedding).

Plans:
- [ ] 05-01: Tracer: `sources.yaml` registry plus polite scraper (robots.txt, rate limit, citation metadata) on one or two sources, with encoding and OCR quality checks
- [ ] 05-02: Structure-aware chunking and Hindi/English/Hinglish retrieval evaluation to pick the embedder
- [ ] 05-03: Typed dosage-record extraction at ingest
- [ ] 05-04: One-command build and publish of a versioned snapshot with a manifest recording the embedding model id
- [ ] 05-05: Snapshot loader and retriever pulled in the Space bootstrap (refuses an embedder mismatch); 39-class source coverage report

### Phase 6: Cited Safe Chat

**Goal:** As a farmer, I want to ask about my diagnosed disease in Hindi or English and get remedy answers that cite their sources, so that I can trust the advice or be told plainly when none exists.
**Mode:** mvp
**Depends on**: Phase 4 (diagnosis result and UI), Phase 5 (knowledge store)
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-05
**Success Criteria** (what must be TRUE):
  1. After a diagnosis, a farmer can chat about that disease in Hindi or English, and every answer shows the sources it came from.
  2. When retrieval cannot support an answer, the farmer sees a clear "no reliable source found" reply in their language instead of a guess.
  3. A dosage or numeric figure appears in an answer only if it exists in the retrieved sources; an answer containing an unsupported figure has it removed or blocked, confirmed by adversarial tests that must pass before the phase is complete.
  4. Every remedy answer ends with the bilingual pesticide-safety footer added by code, whatever the model wrote.

**Plans**: 4 plans
**UI hint**: yes
**Research flag**: yes - Hindi quality of the candidate LLMs (30-question eval), and guardrail and validator design against a small red-team set.

Plans:
- [ ] 06-01: Tracer: LLM client behind a provider interface (model id as a setting, fallbacks) plus retrieve-cite-answer flow for English chat on a diagnosed disease
- [ ] 06-02: Hindi and English prompts, citation validation, "no reliable source found" path
- [ ] 06-03: Safety layer: numeric/dosage validator against retrieved records, banned-pesticide list, deterministic bilingual safety footer, with unit and adversarial tests
- [ ] 06-04: Streaming Chat tab wired to the diagnosis result; Hindi golden-question evaluation

### Phase 7: Resilient Chat & Release Readiness

**Goal:** As a farmer, I want chat to keep helping, or tell me plainly why it cannot, when curated sources run thin or the AI service is down, so that I am never left with an error or an unsourced guess.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: CHAT-04, CHAT-06, OPS-02
**Success Criteria** (what must be TRUE):
  1. When curated data cannot answer, chat falls back to allowlisted live web search (`.gov.in`, `.ac.in`, FAO, ICAR), labels those results as lower trust, and never takes a dosage from them, even when a fetched page tries to inject instructions.
  2. When the LLM quota is exhausted or the API errors, the farmer sees a clear degraded-mode message instead of an error or a hang, diagnosis keeps working, and per-session rate limits and a budget guard cap spend.
  3. A new contributor can follow the README to run the app locally and on a Space, and the architecture docs and `CLAUDE.md`/`AGENTS.md` describe modules that actually exist in the repo.

**Plans**: 3 plans

Plans:
- [ ] 07-01: Search provider behind a Protocol; sufficiency check; allowlisted, injection-hardened live fallback tagged lower trust with dosages blocked
- [ ] 07-02: LLM budget guard, 402/429 and error handling, per-session rate limits, degraded-mode message
- [ ] 07-03: README, architecture docs and `CLAUDE.md`/`AGENTS.md` checked against the real code; final end-to-end walkthrough on the deployed Space

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 (Phase 5 ingest plans may run in parallel with Phases 2-4)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Walking Skeleton & Hosting Verification | 0/7 | Planned | - |
| 2. Trustworthy Data & Field Probe | 0/4 | Not started | - |
| 3. Gated Classifier | 0/5 | Not started | - |
| 4. Farmer Diagnosis | 0/4 | Not started | - |
| 5. Knowledge Snapshot | 0/5 | Not started | - |
| 6. Cited Safe Chat | 0/4 | Not started | - |
| 7. Resilient Chat & Release Readiness | 0/3 | Not started | - |
