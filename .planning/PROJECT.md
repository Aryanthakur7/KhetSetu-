# KhetSetu

## What This Is

KhetSetu is a plant-disease assistant for farmers. A farmer uploads a photo of a diseased leaf, a fine-tuned Hugging Face image-classification transformer identifies the disease, and the farmer can then chat (in Hindi or English) about that disease and get remedies grounded in a RAG knowledge base built from scraped agricultural sources plus live web search. It deploys as a single Hugging Face Space with a Gradio frontend.

## Core Value

A farmer gets a correct, trustworthy disease diagnosis from a leaf photo, and an honest "I'm not sure, send a clearer photo" instead of a confident wrong answer.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Dataset `Project-AgML/plant_village_classification` is downloaded automatically by every training/eval/dev entrypoint (idempotent, cached) before anything else runs; the deployed Space downloads only the model and knowledge snapshot
- [ ] Fine-tune a Hugging Face image-classification transformer (ViT / Swin / ConvNeXt family; benchmark 2-3 candidates) on the dataset, with augmentation aimed at real field photos
- [ ] Confidence gate: below a threshold (or for non-leaf images) the app declines to diagnose and asks for a clearer photo
- [ ] Farmer uploads an image and receives disease label, confidence, and a short summary
- [ ] Chat about the diagnosed disease in Hindi and English, powered by the Google Gemini API (team API key, behind a provider interface)
- [ ] RAG over a curated, scheduled-scrape store of agricultural sources (e.g. ICAR, state agriculture universities, FAO) with a live web-search fallback when curated data has no answer
- [ ] Remedy answers cite their sources and include safety framing for any chemical/pesticide advice
- [ ] Backend (`backend/`) and frontend (`frontend/`) are separate packages in one repo; Gradio frontend consumes the backend service layer
- [ ] Single Hugging Face Space deployment
- [ ] Proper configuration: typed settings loaded from `.env`, committed `.env.example`, no secrets in git
- [ ] Senior-level code quality: typed, linted, tested, documented, clear module boundaries

### Out of Scope

- Object detection / DETR — the dataset has image-level labels only, no bounding boxes; revisit only if multi-leaf localisation is wanted later
- Indian languages beyond Hindi and English — larger scope, later phase
- Two-Space (separate BE API / FE) deployment — layout allows it later, v1 ships one Space
- Self-hosted LLM — Gemini API chosen to avoid GPU hosting and HF Inference credits (team decision 2026-10-25)
- Retraining on collected farmer photos — v2, needs a data collection pipeline
- Native mobile app — web (Gradio) first

## Context

- Dataset: `Project-AgML/plant_village_classification` on Hugging Face, two parquet shards (~823 MB), already downloaded to `data/plant_village_classification/` for local exploration. Not yet inspected (classes, split, image sizes unknown).
- PlantVillage images are lab-style single-leaf photos; models trained on them typically generalise poorly to messy field photos. This is why augmentation and the confidence gate are core, not optional.
- Reference project layout the team already uses: `MTT-VoiceAgent-BE` / `MTT-VoiceAgent-FE` as separate folders, each with `.env.example`, `docs/`, `tests/`, `scripts/`, Dockerfile, CI, `CLAUDE.md`/`AGENTS.md`. KhetSetu follows the same conventions.
- Hugging Face skills installed in `.claude/skills/`: `huggingface-llm-trainer`, `fine-tuning-expert`.
- Users are farmers: low-bandwidth, mobile-first usage, Hindi and English, non-technical.

## Constraints

- **Platform**: Hugging Face (datasets, model hub, Spaces) — team decision; LLM chat uses the Google Gemini API instead of HF Inference (2026-10-25)
- **Frontend**: Gradio — fast to build, native to Spaces
- **Deployment**: Single HF Space — simplest to operate; free/low tier limits compute, so inference must be lightweight
- **Account**: Team is on a FREE Hugging Face account. Research (HF docs, 2026-10-23) reports Gradio/Docker Space creation needs a paid plan and Inference Providers gives free users no credits. Unverified for this account — Phase 1 verifies with a hello-world deploy and, if blocked, picks a fallback (ZeroGPU Space, Static Space + external backend, or other hosting) before architecture hardens. LLM access sits behind a provider interface so the backend can change without touching chat logic.
- **Repo layout**: `backend/` and `frontend/` fully separated — keeps a later two-Space split cheap
- **Config**: all secrets and tunables via `.env` / `.env.example` — team onboarding
- **Safety**: remedy advice touches pesticides and crop loss — must cite sources and avoid unsourced dosage claims
- **Quality**: senior-level code (types, tests, lint, docs) — explicit user requirement

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Image-classification transformer (ViT/Swin/ConvNeXt), not DETR | Dataset has image-level labels only; DETR needs boxes | — Pending |
| LLM via Google Gemini API (own API key), replacing HF Inference API | HF Inference gave no free credits (HTTP 402); Gemini key is simple and handles Hindi; provider stays behind an interface | ✓ Decided 2026-10-25 (model id + Hindi quality tested in Phase 6) |
| Hindi + English | Target farmers; needs multilingual LLM and Hindi sources | — Pending |
| One HF Space, separate `backend/` and `frontend/` folders | Simple deploy now, cheap split later | — Pending |
| Augmentation + confidence gate for field photos | PlantVillage is lab imagery; avoid confident wrong diagnoses | — Pending |
| RAG: curated scheduled scrape + live search fallback | Trustworthy default, coverage fallback | — Pending |
| Dataset auto-download in training/eval/dev entrypoints, not at Space boot | 823 MB is only needed for training; Space disk is ephemeral and boot would risk cold-start timeouts | — Pending |
| Free HF account; hosting/LLM funding verified in Phase 1 | Research says Space creation and Inference credits need a paid plan; unverified | Verified 2026-10-25: free CPU Basic Gradio Space refused (HTTP 402); private ZeroGPU Gradio Space works as interim hosting with sys.path packaging; LLM calls get HTTP 402 (no credits), funding UNRESOLVED (options: PRO, buy credits, other provider key); fallback: Static Space + external backend (ADR 0001). 2026-10-25 team decision: keep the private ZeroGPU Space; LLM via Gemini API key instead of HF credits |
| Evidence-driven model choice: field-set macro-F1, calibration, CPU latency (not PlantVillage accuracy) | PlantVillage accuracy is inflated by leakage and lab backgrounds | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-23 after research (free-account and dataset-download decisions)*
