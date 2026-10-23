# Requirements: KhetSetu

**Defined:** 2026-10-23
**Core Value:** A farmer gets a correct, trustworthy disease diagnosis from a leaf photo, and an honest "I'm not sure, send a clearer photo" instead of a confident wrong answer.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [ ] **FND-01**: Developer can configure the whole app through typed, validated settings loaded from `.env`, and the app fails fast at startup with a clear message when a required setting is missing or invalid
- [ ] **FND-02**: Developer can onboard from a committed `.env.example` that documents every setting, and no secret or token is ever committed (enforced by a secret scan)
- [ ] **FND-03**: Developer can run any training, evaluation or dev entrypoint and have the dataset `Project-AgML/plant_village_classification` downloaded first, idempotently and from cache when already present
- [ ] **FND-04**: Contributor's change is blocked in CI unless ruff, mypy (strict), pytest, import-linter and the secret scan all pass
- [ ] **FND-05**: Developer can verify with a hello-world Space deploy whether a free Hugging Face account can host the Gradio app, how the `backend/` and `frontend/` packages install on the Space, and how LLM calls are funded, before dependent work is built
- [ ] **FND-06**: Repo keeps `backend/` and `frontend/` as separate packages, with the frontend depending only on a typed `contracts/` layer and a single composition root wiring them together

### Data & Evaluation

- [ ] **DATA-01**: Researcher can use a frozen, versioned train/validation/test split in which near-duplicate leaf images are grouped so they never straddle splits
- [ ] **DATA-02**: Researcher can evaluate any model on a field/out-of-distribution probe set (about 100-200 real field leaf photos plus about 50 non-leaf images) that is kept out of training
- [ ] **DATA-03**: Developer can look up each of the 39 classes in `diseases.yaml` with crop, pathogen type, English name and Hindi name
- [ ] **DATA-04**: Farmer and developer can see the explicit list of supported crops, derived from the dataset, and the app states that other crops are not covered

### Model & Gate

- [ ] **MODEL-01**: Researcher can reproduce a benchmark of three backbones (ConvNeXt V2 Tiny, Swin Tiny, ViT) and the chosen model is selected on field-set macro-F1, calibration error and CPU latency, not on in-domain accuracy
- [ ] **MODEL-02**: Training uses field-style augmentation (background swap, lighting, blur) aimed at narrowing the lab-to-field gap
- [ ] **MODEL-03**: Model output passes through a calibrated confidence gate (temperature scaling, top-1/top-2 margin, not-a-leaf class) whose threshold is chosen from a risk-coverage curve on field data and stored with its provenance
- [ ] **MODEL-04**: Developer can fetch the trained model, model card and `gate.json` as versioned artifacts from the Hugging Face Hub
- [ ] **MODEL-05**: Researcher can run training from a single reproducible CLI command with tracked metrics

### Diagnosis

- [ ] **DIAG-01**: Farmer can upload or capture a leaf photo and receive the disease name, a plain-language confidence level (High / Medium / Low) and the top three alternatives
- [ ] **DIAG-02**: Farmer receives an explicit low-confidence, not-a-leaf or unsupported-crop outcome, with tips for retaking the photo, instead of a guessed diagnosis
- [ ] **DIAG-03**: Farmer sees a short curated summary card for the diagnosed disease (including a clear "healthy" outcome)

### Knowledge

- [ ] **KNOW-01**: Developer can manage a source registry (`sources.yaml`) recording URL, licence, robots.txt stance and trust tier for every scraped source
- [ ] **KNOW-02**: Scraper respects robots.txt, rate-limits itself and stores source URL, title, trust tier and fetch date with every chunk
- [ ] **KNOW-03**: Ingest extracts dosage facts into typed records so answers can quote retrieved doses rather than generate them
- [ ] **KNOW-04**: Developer can run a Hindi/English retrieval evaluation comparing candidate embedding models before one is locked in
- [ ] **KNOW-05**: Developer can run one command that scrapes, chunks, embeds and publishes a versioned knowledge snapshot that the Space pulls at startup

### Chat & Safety

- [ ] **CHAT-01**: Farmer can chat in Hindi or English about the diagnosed disease and receive answers that cite their sources
- [ ] **CHAT-02**: Farmer receives a clear "no reliable source found" reply when retrieval cannot support an answer
- [ ] **CHAT-03**: Any dosage or numeric figure in an answer is checked against the retrieved sources and removed or blocked if not present
- [ ] **CHAT-04**: When curated data is insufficient, chat falls back to allowlisted live web search (`.gov.in`, `.ac.in`, FAO, ICAR), tags results as lower trust, and never takes dosages from them
- [ ] **CHAT-05**: Every remedy answer ends with a deterministic bilingual pesticide-safety footer added by code, not by the model
- [ ] **CHAT-06**: Chat stays usable when the LLM quota is exhausted or the API errors: per-session rate limits, a budget guard and a clear degraded-mode message

### Operations & Quality

- [ ] **OPS-01**: Farmer sees a "warming up" page immediately on Space start while the model and knowledge snapshot load in the background
- [ ] **OPS-02**: Team can onboard from README, architecture docs and `CLAUDE.md`/`AGENTS.md` that match the real code
- [ ] **OPS-03**: Repo ignores `data/`, model weights and secrets so large or sensitive files cannot be committed by accident

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Diagnosis

- **DIAG-V2-01**: Farmer can use the diagnosis screen itself in Hindi (v1 diagnosis UI is English; chat is already bilingual)
- **DIAG-V2-02**: Follow-up question chips after a diagnosis

### Knowledge & Ops

- **KNOW-V2-01**: Knowledge ingest runs on a schedule (GitHub Actions cron or HF Job) without manual trigger
- **OPS-V2-01**: Space polls for a new knowledge snapshot and hot-swaps it without restart
- **OPS-V2-02**: Full red-team CI suite for dosage and prompt-injection attacks, plus a Hindi LLM golden set (v1 keeps unit tests on the dosage guard and safety footer)
- **MODEL-V2-01**: Coverage for staple Indian crops (rice, wheat, cotton, sugarcane, mustard) once suitable data is collected

### Platform

- **PLAT-V2-01**: Voice input/output
- **PLAT-V2-02**: Additional Indian languages
- **PLAT-V2-03**: Two-Space split (separate backend API and frontend)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| DETR / object detection | Dataset has image-level labels only, no bounding boxes |
| Severity estimation, multi-leaf detection | Needs annotated data and does not serve the core value in v1 |
| LLM-generated dosages or brand recommendations | Hallucination risk on pesticide advice; doses may only be quoted from retrieved sources |
| Always returning a diagnosis | Violates the core value; the gate must be allowed to refuse |
| User accounts, forum, marketplace | Not core; adds privacy and moderation burden |
| Weather, mandi-price, government-scheme features | Different product (Kisan Suvidha / e-Mitra territory) |
| Self-hosted LLM | HF Inference API chosen to avoid GPU hosting |
| Retraining on farmer-uploaded photos | Needs a consent and data-collection pipeline; v2+ |
| Native or offline mobile app | Web (Gradio) first |
| LangChain / LlamaIndex | Hand-rolled retrieve-cite-answer flow is small and easier to test and audit |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | TBD | Pending |
| FND-02 | TBD | Pending |
| FND-03 | TBD | Pending |
| FND-04 | TBD | Pending |
| FND-05 | TBD | Pending |
| FND-06 | TBD | Pending |
| DATA-01 | TBD | Pending |
| DATA-02 | TBD | Pending |
| DATA-03 | TBD | Pending |
| DATA-04 | TBD | Pending |
| MODEL-01 | TBD | Pending |
| MODEL-02 | TBD | Pending |
| MODEL-03 | TBD | Pending |
| MODEL-04 | TBD | Pending |
| MODEL-05 | TBD | Pending |
| DIAG-01 | TBD | Pending |
| DIAG-02 | TBD | Pending |
| DIAG-03 | TBD | Pending |
| KNOW-01 | TBD | Pending |
| KNOW-02 | TBD | Pending |
| KNOW-03 | TBD | Pending |
| KNOW-04 | TBD | Pending |
| KNOW-05 | TBD | Pending |
| CHAT-01 | TBD | Pending |
| CHAT-02 | TBD | Pending |
| CHAT-03 | TBD | Pending |
| CHAT-04 | TBD | Pending |
| CHAT-05 | TBD | Pending |
| CHAT-06 | TBD | Pending |
| OPS-01 | TBD | Pending |
| OPS-02 | TBD | Pending |
| OPS-03 | TBD | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 32 ⚠️

---
*Requirements defined: 2026-10-23*
*Last updated: 2026-10-23 after initial definition*
