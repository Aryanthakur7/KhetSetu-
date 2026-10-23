# Project Research Summary

**Project:** KhetSetu
**Domain:** Plant-disease image diagnosis (HF transformer, confidence-gated) + Hindi/English cited RAG advisory chat for farmers, on a single Hugging Face Space (Gradio)
**Researched:** 2026-10-23
**Confidence:** MEDIUM-HIGH

## Executive Summary

KhetSetu sits at the join of two product categories that are usually separate: photo-diagnosis apps (Plantix, Nuru) and grounded conversational advisors (Farmer.CHAT, Kisan e-Mitra). The recommended build is one Gradio Space that is a read-only consumer of versioned Hub artifacts. The fine-tuned classifier goes in a model repo. The knowledge snapshot goes in a dataset repo. The two offline producers are training (local RTX 3050 or HF Jobs) and a scheduled ingest job (GitHub Actions cron or HF Jobs). The Space has `app.py` as composition root, a `frontend/` that depends only on typed `contracts/`, and a `backend/` service layer. RAG is hand-rolled (retrieve, cite, one LLM call) with no LangChain. The core value is the calibrated confidence gate plus honest refusal, so that is where engineering effort should go.

Four findings change the PROJECT.md assumptions and must be resolved in the first phase.
- **Hosting cost.** Creating a Gradio Space needs a paid HF plan (PRO or org). CPU Basic hardware is free, but Inference Providers gives only $2/month credit on PRO and nothing on free accounts.
- **Disk and scheduling.** The Space disk is ephemeral and free Spaces sleep. So scraping, scheduling and index building cannot live in the Space.
- **Dataset download.** The 823 MB dataset must not be downloaded at Space boot. The idempotent downloader belongs to the train/eval entrypoints.
- **Crop coverage.** The dataset has one `train` split and 14 crops, mostly temperate. Wheat, rice, cotton and mustard are absent, so "unsupported crop" must be a first-class outcome and the UI must state supported crops honestly.

The main risks are, in order:
1. Inflated metrics from near-duplicate leaves and background bias. Mitigate with a frozen, hash-grouped split built before any model selection.
2. The lab-to-field gap (about 99% in-domain versus roughly 55-67% on field images in cited studies). Mitigate with a hand-collected field/OOD probe set that drives model selection and gate tuning.
3. Dosage and pesticide hallucination. Mitigate with retrieval-only dosages, a numeric post-validator and a templated safety footer.
4. Unverified Hindi quality for the LLM, the embedder and PDF text extraction. Mitigate with small evals before locking choices.

Stack versions are current and verified, but most online tutorials show v4-era APIs. See STACK.md for pins.

## Key Findings

### Recommended Stack

Python 3.12 with uv workspace (`backend`, `frontend`), torch 2.14.1 CPU wheels on the Space, transformers 5.20.2, datasets 5.1.0, huggingface_hub 2.3.0 and Gradio 6.30.0 with `pillow<13`. Use `Trainer` with `processing_class=`, torchvision v2 augmentations, scikit-learn and torchmetrics for metrics, and trackio for tracking. Split `backend` into extras (`train`, `ingest`) so the Space installs only serving dependencies. Full pins and install commands are in `STACK.md`.

**Core technologies:**
- **ConvNeXt V2 Tiny (`facebook/convnextv2-tiny-22k-224`):** default classifier. Benchmark it against Swin-Tiny and ViT-S/B, and choose on field-set macro-F1, ECE and CPU latency (under 1.5 s p95), not PlantVillage accuracy.
- **Gate:** temperature scaling, top-1/top-2 margin and the `Background_without_leaves` class. Thresholds are shipped in `gate.json` with the model.
- **LLM via `InferenceClient`:** default `google/gemma-4-26B-A4B-it` (about $0.13/M in, $0.40/M out). The model id is a setting with fallbacks. Hindi quality is unverified.
- **Embeddings and store:** `BAAI/bge-m3` (no prefixes, cross-lingual) and ChromaDB 1.5.9 behind a `VectorStore` Protocol. The index is built offline and pulled at boot.
- **Scraping and search:** httpx, trafilatura, pypdf, robotparser, and Tavily with `include_domains` (`.gov.in`, `.ac.in`, fao.org, icar.org.in) as the live fallback.
- **Quality tooling:** ruff, mypy strict, pytest with hypothesis for gate properties, import-linter to enforce frontend-to-contracts-only, gitleaks pre-commit, pip-audit and deptry.

Avoid: LangChain/LlamaIndex, Albumentations, `evaluate`, APScheduler in the Space, unpinned pillow, `langdetect`, and gated models (DINOv3, embeddinggemma).

### Expected Features

**Must have (table stakes):**
- Photo upload (camera and gallery) returning a disease name, with plain-language confidence (High/Medium/Low) and top-3 alternatives.
- Explicit "healthy" handling and a visible supported-crops list.
- Confidence gate with retake guidance, and non-leaf rejection.
- Per-class disease summary from 39 curated knowledge cards.
- Diagnosis-aware Hindi/English chat, cited remedy answers and "I don't know" handling.
- Pesticide safety framing and a "no source, no dosage" guard.
- Graceful degradation when the LLM, quota or Space is unavailable.
- Mobile-friendly, low-bandwidth UI.

**Should have (competitive):**
- Calibrated uncertainty UX with selective-accuracy reporting.
- The joined niche: diagnosis-grounded, cited Hindi chat.
- Curated scheduled scrape plus lower-trust live-search fallback, with source-tier labels.
- Field-style augmentation and a field eval set.
- A 3-backbone benchmark with documented rationale.
- A curated bilingual glossary and `diseases.yaml`.
- Follow-up chips (cheap, v1.x).

**Defer (v2+):**
- Voice I/O, extra Indian languages, rice/wheat/cotton models (needs new data; the largest real-world usefulness gap), severity estimation, multi-leaf detection, and retraining on farmer photos.
- Offline or mobile app, two-Space split.
- Never build: accounts, community forum, marketplace, weather/mandi/scheme features, LLM-generated dosages.

### Architecture Approach

One runtime process (the Space) and two offline producers that publish versioned Hub artifacts. `app.py` is the only place both packages meet, and it injects `Services` into the UI. Startup is staged and non-blocking: the port binds immediately, a `BootstrapManager` thread loads the classifier first, then the knowledge snapshot, then warm-up. A readiness banner is shown meanwhile. Chat uses two-tier retrieval: curated first, a sufficiency check, then live search tagged `origin="live"`. Safety text is deterministic and never LLM-generated. The index manifest records the embedding model id, and the runtime refuses to load a mismatch.

**Major components:**
1. `contracts/`: pydantic DTOs and Protocols (`DiagnosisService`, `ChatService`, `HealthService`). This is the stable seam, and a later two-Space split becomes a `RemoteServices` swap.
2. `vision/`: preprocessing with the saved `AutoImageProcessor`, calibrated inference, gate and `NotReady` handling; thresholds come from the model repo's `gate.json`.
3. `knowledge/` + `ingest/`: snapshot loader and retriever on the serving side; the source-registry-driven scraper, chunker and embedder on the offline side (CLI only).
4. `chat/` + `llm/` + `search/`: RAG orchestrator, citation validation, dosage validator, safety footer, budget and retry wrapper, and the search fallback behind a Protocol.
5. `bootstrap/` + `domain/diseases.yaml`: staged startup and the curated label metadata (EN/HI names, crop, pathogen type, search terms).

### Critical Pitfalls

1. **Leaky split and background bias inflate metrics.** Freeze a hash-grouped split (imagehash plus `StratifiedGroupKFold`), run a border-only probe, and never use in-domain accuracy as the headline number.
2. **Lab-to-field gap and a non-Indian crop catalogue.** Build a 100-300 image field/OOD probe set early and track it every run. Use background-swap augmentation, add a crop-confirmation step, and show the supported-crops list.
3. **Uncalibrated or magic-number gate.** Use temperature scaling and several signals (margin, background class, quality heuristics). Pick the threshold from a risk-coverage curve on field data, and ship it with its provenance.
4. **Dosage and pesticide hallucination.** Extract dose facts at ingest into typed records and let the LLM only quote retrieved records. Add a numeric post-validator, block dosages from the web fallback, keep a banned-pesticide list and a red-team CI suite. Make viral and HLB answers non-chemical.
5. **Treating the Space as a durable server or free tier.** Confirm PRO or org eligibility and the credit plan in Phase 1. Keep scrape and index build offline, never download the dataset at Space boot, and handle 402/429 with degraded mode and rate limits.

Runners-up with phase impact:
- Hindi retrieval and legacy-font PDFs need an eval and an extraction QA gate.
- Scrape licensing needs a source registry.
- Fallback prompt injection needs allowlists and untrusted-content delimiters.
- Secrets and the untracked `data/` need `.gitignore` and gitleaks before the next commit.

## Implications for Roadmap

Suggested structure is 7 phases. The ML track (2-3) and the knowledge track (5) are independent and can run in parallel after Phase 1. The data and eval harness precedes training because a late-discovered leaky split is the costliest recovery.

### Phase 1: Foundation, Hosting Verification and Contracts
**Rationale:** It surfaces the paid-plan, import-path and cold-start unknowns cheaply, before any ML work. It also fixes `.gitignore` and secrets hygiene before the next commit.
**Delivers:** uv workspace skeleton; typed Settings and `.env.example`; `contracts/` and fake services; CI (ruff, mypy, pytest, import-linter, gitleaks); a hello-world Gradio Space deployed on the target account; packaging spike (editable install versus `sys.path`); idempotent `ensure_dataset()` as a dev/train entrypoint; PROJECT.md decisions recorded (account tier, `DatasetMode` resolution, funding model).
**Addresses:** typed config, tests/lint/docs, single-Space deploy.
**Avoids:** pitfalls 5, 6, 13, 14 and 20.

### Phase 2: Data and Evaluation Harness
**Rationale:** Every model decision depends on a trustworthy split and a field/OOD set. This is the largest lever on the core value.
**Delivers:** frozen grouped split artifact (dedup, split hash); label metadata table (`diseases.yaml`: crop, type, EN/HI names); field-photo probe set and non-leaf/OOD negatives (100-200 plus about 50); border-only background probe; supported-crops list.
**Addresses:** own split, supported-crops list, label semantics.
**Avoids:** pitfalls 1, 2, 11 and 23.

### Phase 3: Model Training, Calibration and Gate
**Rationale:** This is the long pole. It starts as soon as Phase 2 lands, runs in parallel with Phase 5, and the other tracks can use a stub classifier meanwhile.
**Delivers:** 3-backbone benchmark selected on field-set macro-F1, ECE and CPU latency; field-style augmentation; temperature scaling and risk-coverage tuned gate; `gate.json` and model card published to the Hub model repo; reproducible `train` CLI.
**Uses:** transformers 5 `Trainer`, torchvision v2, scikit-learn, torchmetrics, trackio.
**Implements:** `training/`, `vision/gate`.
**Avoids:** pitfalls 3, 10, 11 and 24.

### Phase 4: Vision Service and Diagnosis UI (first vertical slice)
**Rationale:** First user-visible delivery of the core value. It validates the real model on the Space (CPU latency, cold start).
**Delivers:** `DiagnosisService` with shared preprocessing (EXIF, size caps); three-state gate rendering; bilingual Diagnose tab with plain-language confidence, top-3, healthy handling, retake tips, crop confirmation and the supported-crops list; staged bootstrap with readiness banner; `preload_from_hub`.
**Addresses:** table-stakes diagnosis features, knowledge cards, mobile UX.
**Avoids:** pitfalls 10, 12 (`DiagnosisContext`), 15, 16, 17 and 22.

### Phase 5: Knowledge Ingestion and Retrieval
**Rationale:** It is independent of model training and benefits from early content curation. It can start right after Phase 1.
**Delivers:** `sources.yaml` registry (licence, robots, tier); polite scraper with encoding/mojibake QA and OCR fallback; structure-aware chunking with full citation metadata; typed dosage records; class-by-source coverage matrix (39 classes); embedder bake-off (bge-m3 versus multilingual-e5 versus Qwen3-Embedding) on a Hindi/English/Hinglish retrieval eval; snapshot with manifest published privately; offline cron (GitHub Actions or HF Jobs).
**Uses:** httpx, trafilatura, pypdf, sentence-transformers, ChromaDB.
**Implements:** `ingest/`, `knowledge/`.
**Avoids:** pitfalls 4 (extraction half), 6, 7, 8, 18 and 19.

### Phase 6: RAG Chat, Hindi and Safety
**Rationale:** It needs the knowledge store (Phase 5) and the `DiagnosisContext` shape (Phase 4). It is the highest-risk phase for user harm, so its completion is gated on the red-team suite.
**Delivers:** LLM client with fallbacks, budget and 402/429 degraded mode; Hindi/English prompts; citation validation; dosage and numeric validator; deterministic bilingual safety footer; sufficiency-gated live fallback (allowlisted, injection-hardened, no dosages); streaming Chat tab; per-session rate limits and answer cache; Hindi LLM golden eval; follow-up chips.
**Implements:** `chat/`, `llm/`, `search/`.
**Avoids:** pitfalls 4, 5, 7, 9, 12, 21 and 26.

### Phase 7: Hardening, Quality Pass and Release
**Rationale:** Only real artifacts make cold start, concurrency and rejection rates measurable. This phase delivers the "senior-level" bar.
**Delivers:** KnowledgeRefresher with atomic swap; cold-start and 5-concurrent-user P95 tests on CPU Basic; production rejection-rate and fallback-rate logging; secret and Variable audit on the deployed Space; Hindi UX review with a native speaker; docs, README/Space card and `CLAUDE.md`/`AGENTS.md`.
**Avoids:** pitfalls 15, 22 and 25.

### Phase Ordering Rationale

- Foundation first, because plan eligibility and packaging unknowns can invalidate downstream assumptions.
- Data and eval before training, because rework from a leaky split is the most expensive recovery.
- The ML track (2-3-4) and knowledge track (5) are parallelizable. They converge at chat (6), which needs both the diagnosis context and the store.
- Chat last among features because it carries the most safety risk and depends on everything else.
- The `contracts/` plus fakes strategy in Phase 1 lets UI, ingest and training proceed independently.
- Safety and honesty requirements (grouped split, field set, dosage validator) are built into the phases that create the artifacts, not bolted on at the end.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-plan-phase --research-phase <N>`):
- **Phase 2:** public field datasets that overlap the 14 crops (PlantDoc and similar), the dedup method, and licensing of field data.
- **Phase 3:** OOD and non-leaf scoring method, background-swap augmentation, CPU latency and quantization, and calibration approach.
- **Phase 5:** concrete Indian sources, their robots.txt and terms, legacy-Devanagari PDFs, and CIB&RC banned/restricted lists. Plus the embedder bake-off.
- **Phase 6:** Hindi quality of providers' LLMs, and guardrail/validator design with the red-team set.

Phases with standard patterns (skip research-phase):
- **Phase 1:** well-documented, except a short verification spike for plan eligibility and monorepo packaging.
- **Phase 4:** well-documented Gradio patterns. Test on a real phone.
- **Phase 7:** standard once Phase 1 verification is done.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Versions and HF platform facts were verified live on 2026-10-23. Hindi LLM and embedding quality, and monorepo packaging on a Gradio Space, are unverified and need spikes. |
| Features | MEDIUM | Competitor sets come from web sources and not hands-on testing. Dataset constraints are HIGH (read locally). |
| Architecture | MEDIUM-HIGH | HF platform behaviour comes from official docs. Cold-start timing, editable-install behaviour and some patterns are author synthesis and untested. |
| Pitfalls | MEDIUM-HIGH | Platform and dataset facts are HIGH. Field-accuracy figures, Hindi embedder comparisons and Indian scraping law are secondary sources (MEDIUM/LOW). Legal points are not legal advice. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **HF plan and funding (blocking):** confirm PRO or org availability and the credit budget in Phase 1. If unavailable, the single Gradio Space premise needs a fallback hosting plan (ZeroGPU, Static Space plus external backend).
- **Monorepo packaging on a Gradio-SDK Space:** settle in the Phase 1 hello-world deploy. Fall back to `sys.path` in `app.py` or a Docker SDK Space.
- **Dataset-on-startup wording:** record the decision that the downloader runs in training/dev entrypoints, and only optionally in the background on the Space.
- **Field-photo probe set:** no existing PlantVillage calibration or OOD benchmark was found, so thresholds must be empirical. Budget time to collect 100-200 field photos plus about 50 negatives.
- **Hindi LLM and embedder quality:** run the 30-question LLM eval and the 50-pair retrieval eval before locking defaults.
- **Hindi source coverage:** authoritative content is mostly English, with legacy-font PDFs. Plan OCR, glossary expansion and the coverage matrix.
- **Scrape licensing and robots per source:** record in `sources.yaml`. Keep derived corpora private by default.
- **Chat without a diagnosis:** product decision pending. Architecture supports `DiagnosisContext | None`, and the pitfalls research advises a manual crop/problem path.
- **Dataset licence/attribution:** unconfirmed for the AgML mirror. Check before publishing a model.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (2026-10-23): all pinned versions and `requires_dist` constraints.
- HF docs (spaces-overview, spaces-config-reference, spaces-storage, storage-buckets, jobs-overview, inference-providers pricing): Gradio Space paid-plan rule, ephemeral disk, `preload_from_hub`, PRO $2 credits, cron Jobs.
- transformers v5 image-classification guide and migration guide; Gradio 6 migration guide.
- HF router `/v1/models` catalogue (volatile): default LLM and pricing.
- Local `data/plant_village_classification/README.md`: 55,448 images, 39 classes, single `train` split, `Background_without_leaves`.

### Secondary (MEDIUM confidence)
- Competitor sources (Plantix, Nuru/IITA, Wadhwani Kisan e-Mitra, Farmer.CHAT) for the feature landscape.
- Lab-to-field generalisation studies (arXiv 2511.18989, 2206.04374, IEEE Access 2023): the 94% to 55-67% drop and background bias.
- Hindi-BEIR / NLLB-E5 papers: BGE-M3 versus mE5 comparisons.
- Agricultural LLM hallucination literature and Indian pesticide label-claim context.
- Tavily docs (free plan quota) and HF forum cold-start threads.

### Tertiary (LOW confidence)
- Indian scraping-law commentary (law.asia, Mondaq); not legal advice.
- Wrong-crop herbicide incident report (secondary, unverified).
- Kisan Suvidha feature set (training knowledge only).
- Experience-based items to verify in-phase: legacy-font Devanagari PDFs, FAO licence terms, Kisan Call Centre number.

Detailed sources are in `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md` and `PITFALLS.md` in this directory.

---
*Research completed: 2026-10-23*
*Ready for roadmap: yes*
