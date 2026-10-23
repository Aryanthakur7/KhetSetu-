<!-- GSD:project-start source:PROJECT.md -->

## Project

**KhetSetu**

KhetSetu is a plant-disease assistant for farmers. A farmer uploads a photo of a diseased leaf, a fine-tuned Hugging Face image-classification transformer identifies the disease, and the farmer can then chat (in Hindi or English) about that disease and get remedies grounded in a RAG knowledge base built from scraped agricultural sources plus live web search. It deploys as a single Hugging Face Space with a Gradio frontend.

**Core Value:** A farmer gets a correct, trustworthy disease diagnosis from a leaf photo, and an honest "I'm not sure, send a clearer photo" instead of a confident wrong answer.

### Constraints

- **Platform**: Hugging Face (datasets, model hub, Inference API, Spaces) — team decision
- **Frontend**: Gradio — fast to build, native to Spaces
- **Deployment**: Single HF Space — simplest to operate; free/low tier limits compute, so inference must be lightweight
- **Account**: Team is on a FREE Hugging Face account. Research (HF docs, 2026-10-23) reports Gradio/Docker Space creation needs a paid plan and Inference Providers gives free users no credits. Unverified for this account — Phase 1 verifies with a hello-world deploy and, if blocked, picks a fallback (ZeroGPU Space, Static Space + external backend, or other hosting) before architecture hardens. LLM access sits behind a provider interface so the backend can change without touching chat logic.
- **Repo layout**: `backend/` and `frontend/` fully separated — keeps a later two-Space split cheap
- **Config**: all secrets and tunables via `.env` / `.env.example` — team onboarding
- **Safety**: remedy advice touches pesticides and crop loss — must cite sources and avoid unsourced dosage claims
- **Quality**: senior-level code (types, tests, lint, docs) — explicit user requirement

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Critical Findings That Change PROJECT.md Assumptions

| # | Finding | Impact | Confidence |
|---|---------|--------|------------|
| 1 | **Creating a Gradio/Docker Space requires a paid plan (PRO for personal accounts, Team/Enterprise for orgs).** Free accounts only get ZeroGPU Gradio Spaces (max 2). CPU Basic hardware itself is free (2 vCPU, 16 GB RAM, 50 GB ephemeral disk). | "Free/low tier" constraint is really "PRO ($9/mo) + free CPU Basic". Decide account/org before Phase 1. | HIGH (HF docs: spaces-overview) |
| 2 | **Space disk is ephemeral and "persistent storage" is removed.** Persistence = Storage Buckets mounted as volumes (or Hub repos pulled at startup). | Chroma/any local index written on the Space is lost on restart. The index must be built *outside* the Space and pulled in, or rebuilt on boot. | HIGH (HF docs: spaces-storage, spaces-config-reference) |
| 3 | **Inference Providers has no free credits for free users; PRO gets $2/month** of compute credits (shared with Spaces hardware, Jobs). Pay-as-you-go beyond. | LLM usage must be cheap and rate-limited; budget guard needed. Chosen model costs ~$0.13/M in, $0.40/M out (see below). | HIGH (HF docs: inference-providers/pricing) |
| 4 | **The dataset has ONE split (`train`, 55,448 images, 39 classes) and class 4 is `Background_without_leaves` (1,143 images).** No val/test. | You must create your own splits (group-aware, see Pitfalls). The Background class is a free built-in "not a leaf" reject class for the confidence gate. | HIGH (dataset README, read locally) |
| 5 | **"Dataset downloaded on startup" should be scoped to the training/eval CLI, not Space boot.** The Space needs only the model (~110 MB) and the index, not 823 MB of training images. | Downloading 823 MB on every cold boot of an ephemeral-disk Space wastes startup time; the Space should `preload_from_hub` the model. Keep the idempotent downloader in `backend.data` and call it from `train`/`evaluate` entrypoints. | HIGH (reasoning from HF docs: preload_from_hub, ephemeral disk) |
| 6 | **A scheduled scraper cannot live inside a free-tier Space** (it sleeps when idle, disk is ephemeral). | Schedule scrape + index build on HF Jobs (cron-scheduled) or GitHub Actions; publish the index artifact; Space pulls it. | HIGH (HF docs: jobs-overview supports cron schedules) |
| 7 | Local dev box has an **RTX 3050 6 GB laptop GPU**, Python 3.12.3, uv 0.11.20. | Fine-tuning *tiny/small* backbones (~22-29M params) locally is realistic with bf16 + batch 32; ViT-Base needs smaller batch/grad-accum or an HF Job. | HIGH (nvidia-smi, local) |

## Recommended Stack

### Core Technologies

| Technology | Version (verified 2026-10-23) | Purpose | Why Recommended | Confidence |
|------------|-------------------------------|---------|-----------------|------------|
| Python | **3.12** (set `python_version: "3.12"` in Space README; HF default is 3.10!) | Runtime | pydantic-settings 2.16, Pillow 13, onnxruntime 1.31, scikit-learn 1.9 all need >=3.11. 3.12 matches local dev (3.12.3) and has wheels for everything. Avoid 3.13/3.14 (torch/pillow-heif/other wheels lag; `torchvision` excludes 3.14.1). | HIGH |
| PyTorch + torchvision | **torch 2.14.1 / torchvision 0.29.1** | Training + CPU inference | Only supported backend for transformers 5 (TF/Flax removed). `torchvision.transforms.v2` is the augmentation library (see "What NOT to Use" for Albumentations). On the Space install the **CPU wheels** (`+cpu` exists for cp312 at 2.14.1) to avoid multi-GB CUDA wheel download. | HIGH |
| transformers | **5.20.2** | Model loading, `Trainer`, `AutoModelForImageClassification` | v5 is current and torch-only. Official image-classification guide (v5.20.2) uses `Trainer`, `eval_strategy`, `processing_class=image_processor`, `report_to="trackio"`. Requires `huggingface-hub>=1.31`, `torch>=2.6`, `accelerate>=1.1`. | HIGH |
| datasets | **5.1.0** | Load Project-AgML/plant_village_classification, splits, `with_transform` | Native parquet/Image feature, on-the-fly transforms, stratified `train_test_split(stratify_by_column="label")`. Requires `pyarrow>=24`. | HIGH |
| huggingface_hub | **2.3.0** (gradio, transformers, datasets all allow `<3`) | Dataset/model download (`snapshot_download`), `InferenceClient` chat, Hub uploads, Jobs, Buckets | v2 is current (2.0.0 released 2026-09-24); HTTP layer moved to `httpx2`. Provides `hf` CLI, `hf jobs`, `hf buckets`. | HIGH |
| accelerate | **1.15.0** | Trainer backend (mixed precision, grad accumulation) | Required by Trainer; v5 needs >=1.1. | HIGH |
| scikit-learn | **1.9.1** | Metrics (macro-F1, confusion matrix), `StratifiedGroupKFold` for leak-free splits | Replaces `evaluate` (stagnant, see What NOT to Use). | HIGH |
| torchmetrics | **1.9.0** | `MulticlassCalibrationError` (ECE), per-class metrics | Clean calibration metric for the confidence gate evaluation. | MEDIUM |
| Gradio | **6.30.0** (`sdk: gradio`, `sdk_version: 6.30.0` in Space README) | Frontend (image upload, chat, Hindi/English UI) | Native to Spaces. **Gradio 6 breaking changes**: `theme`/`css`/`js`/`head` moved from `gr.Blocks()` to `demo.launch()`; `gr.Chatbot` is messages-format only (`{"role","content"}`), `allow_tags` defaults True (set False for LLM output), `show_*_button` -> `buttons=[...]`; `gr.Image` webcam args -> `webcam_options=gr.WebcamOptions(...)`. Requires `pillow<13` and `huggingface-hub>=1.16,<3`. | HIGH |
| Pillow | **>=12,<13** (pin below 13.0.0 because Gradio 6.30.0 declares `pillow<13.0`; PyPI latest is 13.0.0) | Image IO | Version conflict trap: unpinned `pillow` resolves to 13 and breaks Gradio resolution. | HIGH |
| pydantic + pydantic-settings | **2.14.1 / 2.16.1** | Typed config from `.env`, API/DTO models | `BaseSettings` + `SettingsConfigDict(env_file=".env", env_prefix=..., extra="ignore")`, `SecretStr` for tokens, `.env.example` committed. pydantic-settings 2.16 needs Python >=3.11. | HIGH |
| uv | **>=0.11** (0.13.5 on PyPI; local 0.11.20) | Env + lock + workspace | uv workspace with two members (`backend`, `frontend`); `uv.lock` committed; `uv export --no-dev --no-hashes` generates the Space `requirements.txt`. | HIGH |

### Image classification model candidates (benchmark 3, decide on data)

| Candidate | Checkpoint ID (verified exists) | Params | Why include | Expected role |
|-----------|---------------------------------|--------|-------------|---------------|
| ConvNeXt V2 Tiny (22k pretrain -> 1k) | `facebook/convnextv2-tiny-22k-224` (Apache-2.0) | ~29M | Conv nets are texture-biased, which suits leaf-lesion patterns; 22k pretraining helps transfer; fast on CPU. | **Primary expected winner / default** |
| Swin Transformer Tiny | `microsoft/swin-tiny-patch4-window7-224` (or SwinV2 `microsoft/swinv2-tiny-patch4-window8-256`) | ~28M | Hierarchical transformer; the "Swin" arm of the user's ViT/Swin/ConvNeXt brief. | Benchmark arm |
| ViT | `google/vit-base-patch16-224-in21k` (86M, safe default in official HF guide) **or** smaller `timm/vit_small_patch16_224.augreg_in21k_ft_in1k` (22M) | 22-86M | The "ViT" arm. ViT-B is ~4x the FLOPs of the others; use ViT-S if CPU latency matters. | Benchmark arm |

### LLM (Hindi + English) via HF Inference Providers

| Item | Recommendation | Why | Confidence |
|------|----------------|-----|------------|
| Client | `huggingface_hub.InferenceClient` (`client.chat.completions.create(model=..., messages=..., stream=True)`) with default `provider="auto"`; or `base_url="https://router.huggingface.co/v1"` through the OpenAI SDK. Pick `InferenceClient` (no extra dependency). | Official; supports `:fastest` / `:cheapest` / `:provider` model suffixes; billing flows through the HF account with no markup. | HIGH |
| Default model | **`google/gemma-4-26B-A4B-it`** (MoE, 25B total / 3.8B active, Apache-2.0, 256K ctx, "35+ languages out of the box, pretrained on 140+"). Live router listing: novita, $0.13/M input, $0.40/M output. | Cheap enough for a $2/month PRO credit, strong multilingual family. Hindi quality is not explicitly documented on the model page, so verify. | MEDIUM |
| Fallbacks (configurable via `.env`) | `Qwen/Qwen3.5-35B-A3B` (novita $0.25/$2.00, 262K ctx), `google/gemma-4-31B-it` ($0.14/$0.40), `openai/gpt-oss-120b` (many providers, cheapest, weaker Hindi expected) | Model id must be a `Settings` field (`LLM_MODEL`, `LLM_FALLBACK_MODELS`), not a constant, because this router catalogue churns monthly. | MEDIUM |
| Avoid | `CohereLabs/aya-expanse-32b` (explicit Hindi support but CC-BY-NC = non-commercial; Cohere-only provider) | License. | HIGH |
| Gate | Run a ~30-question Hindi + English remedy eval (faithfulness to retrieved context, Devanagari output, no invented dosages) before locking the default. | Hindi quality is the biggest unverified claim in this stack. | -- |

### RAG: embeddings, vector store, scraping, search

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| sentence-transformers | **6.2.0** | Local embedding inference + index build | Loads `BAAI/bge-m3` directly; requires `transformers>=5`, consistent with the rest of the stack. | HIGH |
| `BAAI/bge-m3` (embedding model) | n/a (MIT, ~568M, 29.6M downloads) | Multilingual dense embeddings incl. Hindi + cross-lingual (Hindi query to English doc) | Best-known multilingual retriever for Hindi/English cross-lingual retrieval; **no query/passage prefixes needed** (unlike `multilingual-e5-*`, which silently degrade if you forget `query: ` / `passage: `). ~2.2 GB fp32 RAM is fine on 16 GB CPU Basic; query-time embedding is one short string. Index is built offline, so build-time CPU cost does not hit the Space. Fallback: `intfloat/multilingual-e5-base` (278M, tagged `hi`) if cold-start/latency is too high. Avoid `google/embeddinggemma-300m` (gated: manual). | MEDIUM |
| ChromaDB | **1.5.9** | Vector store with metadata filtering | Mature 1.x API, simple `PersistentClient`, metadata `where` filters (language, source, crop). Index is a directory; build offline, publish to a Hub repo / Storage Bucket, `snapshot_download` at Space start into a writable path. Hide behind a `VectorStore` Protocol so LanceDB (0.40.0, lighter deps, pre-1.0) can replace it. Heavy transitive deps (grpc, kubernetes, onnxruntime, opentelemetry); set `anonymized_telemetry=False`. | MEDIUM |
| httpx | **0.28.1** | Scraper HTTP client | Stable, sync+async, `respx` can mock it. (`huggingface_hub` 2 now uses `httpx2`; do not expect `respx` to intercept HF client calls: fake the `LLMClient` port in tests instead.) | HIGH |
| trafilatura | **2.3.1** | Boilerplate-free main-text extraction from agri-extension HTML (+ metadata, language) | Purpose-built for article extraction; outperforms hand-written BeautifulSoup selectors across heterogeneous ICAR / SAU / FAO sites. | HIGH |
| beautifulsoup4 | **4.15.0** | Site-specific fallback parsing, link discovery | Use only where trafilatura fails. | HIGH |
| pypdf | **6.21.2** | PDF text extraction (many ICAR/SAU advisories are PDFs) | Pure-Python, light. Upgrade to `docling` (2.142.1) only if tables/scanned PDFs matter. | MEDIUM |
| `urllib.robotparser` (stdlib) | stdlib | Honour robots.txt, per-host rate limit | Required for a trustworthy scraper; zero dependency. | HIGH |
| tenacity | **9.2.1** | Retries/backoff for LLM + search + scrape | Cleaner than ad-hoc loops. | HIGH |
| Tavily (`tavily-python`) | **0.8.5** | Live web-search fallback | `include_domains` lets you restrict to `.gov.in`, `.ac.in`, `fao.org`, `icar.org.in`: fits the "trustworthy" requirement. Free plan: 1,000 credits/month, no card (docs.tavily.com; basic search = 1 credit per third-party sources, MEDIUM). Make the provider a `WebSearch` Protocol. | MEDIUM |
| `ddgs` | **9.16.0** | Keyless emergency search fallback only | Scrapes search engines; breaks and rate-limits unpredictably. Not for primary. | LOW |
| tiktoken-free chunking | custom, ~800 chars Hindi / ~1,200 chars English with overlap, split on sentence boundaries including the Devanagari danda `।` | Chunking | Do not use token-count chunkers tuned for English; Devanagari tokenizes poorly in generic tokenizers. | MEDIUM |

### Infrastructure

| Technology | Version / setting | Purpose | Why | Confidence |
|------------|-------------------|---------|-----|------------|
| HF Space (Gradio SDK) | `sdk: gradio`, `sdk_version: 6.30.0`, `python_version: "3.12"`, `app_file: app.py`, `startup_duration_timeout: 30m` default OK; hardware **CPU Basic** (2 vCPU/16 GB/50 GB ephemeral) | Single deployment | Matches constraint. Root `app.py` imports `frontend` and calls `demo.launch()`; `frontend` imports `backend` in-process (no HTTP hop). Account must be PRO/org (finding #1). | HIGH (config), MEDIUM (monorepo packaging, see below) |
| `preload_from_hub` (README YAML) | e.g. `- <org>/khetsetu-vit-<name>` | Bake the fine-tuned classifier into the image at build time | Cuts cold-start; files go in default `~/.cache/huggingface/hub`, so do NOT override `HF_HOME` at runtime. Public repos only. | HIGH |
| HF Model repo | `<org>/khetsetu-<backbone>` | Publish fine-tuned weights + `id2label` + model card + calibration temperature + gate thresholds (`gate.json`) | Single source of truth for Space and training. | HIGH |
| HF Dataset repo or Storage Bucket | `<org>/khetsetu-kb` | Publish scraped corpus (jsonl) + built Chroma index | Space pulls at start (`snapshot_download`) or mounts a Bucket volume (read-only). Dataset repo gives versioning/rollback; Bucket gives cheap mutable overwrite. Prefer **Dataset repo** for v1 (rollback matters for safety content). | MEDIUM |
| HF Jobs | `hf jobs uv run --flavor <gpu> train.py` ; scheduled via cron (`@daily`/`@weekly`) | (a) optional GPU fine-tune of larger backbones; (b) scheduled scrape + embed + index publish | PEP 723 script headers, no Docker needed; costs come from the same PRO credits. The installed `huggingface-llm-trainer` skill covers Jobs mechanics. | MEDIUM |
| GitHub Actions | CI (lint/type/test) and fallback scheduler for scrape if Jobs is unavailable | CI | Team convention (reference repos have CI + Dockerfile). | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| trackio | 0.43.0 | Experiment tracking (`report_to="trackio"` is what the official v5.20 guide now uses) | Training runs; free, HF-native, local-first. Use instead of wandb. |
| tensorboard | 2.21.0 | Optional alternative logger | Only if team prefers it. |
| imagehash | 4.3.2 (last release Feb 2025, stable) | Perceptual hashing to cluster near-duplicate leaves into groups before splitting | Mandatory for leak-free split (dev/training extra only). |
| safetensors | 0.8.0 | Weight format | Implicit via transformers; never save `.bin`/pickle. |
| pillow-heif | 1.8.1 | Decode iPhone HEIC uploads | Add if farmers upload from iPhones; Gradio itself does not decode HEIC. Optional. |
| typer | 0.27.3 | CLIs: `khetsetu data download`, `train`, `evaluate`, `scrape`, `build-index`, `publish` | Backend entrypoints are CLIs, not notebooks. |
| rich | 15.0.0 | CLI output | Optional. |
| structlog | 26.1.0 | Structured logging with request ids | Use stdlib `logging` + structlog; avoid loguru (harder to configure per-module, global singleton). |
| PyYAML | latest | `diseases.yaml`, source registry (`sources.yaml`: URL, crawl depth, language, license, refresh cadence) | Always. |
| onnxruntime | 1.31.0 (py>=3.11) | Optional CPU speed-up (ONNX export via `optimum` 2.3.0) | Only if measured CPU latency > 1.5 s; premature for tiny models. |
| timm | 1.0.30 | Needed only if you pick a `timm/*` checkpoint (transformers 5 wraps them via `TimmWrapper`; requires `timm>=1.0.23`) | Optional extra `[timm]`. |

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| ruff | 0.17.2 | Lint + format (replaces black, isort, flake8, pyupgrade) | Enable `E,F,W,I,UP,B,SIM,C4,PTH,RUF,S,ANN,D (google/numpy),PL,T20,TCH,PERF`; `target-version="py312"`; relax `S101`, `ANN`, `D` for `tests/`. Note ruff is pinned `==0.14.10` by transformers' own `quality` extra, irrelevant unless you install that extra. |
| mypy | 2.4.0 | Static typing | `strict = true` for `backend/` and `frontend/`; per-module `ignore_missing_imports` for `gradio`, `chromadb`, `trafilatura` as needed; add `pydantic.mypy` plugin. (`ty` is emerging but still beta; stay on mypy for senior-level reliability.) |
| pytest | 9.1.1 | Tests | With `pytest-cov` 7.1.0 (`--cov-fail-under` ratchet), `pytest-mock` 3.17.0, `pytest-xdist` 3.8.0 optional. `hypothesis` 6.170.8 for confidence-gate property tests (gate never emits a label when max-prob < threshold). |
| respx | 0.23.1 | Mock `httpx` for scraper/search tests | Scraper only; fake `LLMClient` at the port for HF calls. |
| pre-commit | 4.7.0 | ruff, mypy, end-of-file, large-file check (block files > 500 KB so nobody commits parquet), gitleaks | Add `gitleaks` hook; `data/` and `*.parquet` in `.gitignore` (note: `data/` currently untracked in git status). |
| pip-audit | 2.10.1 | Dependency CVE scan in CI | `uv export` -> `pip-audit -r`. |
| bandit | 1.9.4 | Optional (ruff `S` rules cover most) | Skip if ruff S is on. |
| import-linter | 2.15 | **Enforce `frontend` may import `backend`, never the reverse; `backend.rag` must not import `backend.training`** | This is what makes "clear module boundaries" machine-checked. Strongly recommended. |
| deptry | 0.25.1 | Detect unused/missing dependencies per package | Keeps the Space `requirements.txt` lean. |
| MkDocs / Sphinx | -- | Skip in v1 | Plain Markdown in `docs/` + docstrings. mkdocs 1.6.1 itself is stagnant (last release Aug 2024). |

## Installation

# One-time: uv workspace at repo root (members: backend, frontend), Python 3.12

# --- Local dev/training machine (RTX 3050, CUDA 13.2 driver) ---

# --- Core runtime (what the Space needs; CPU torch) ---

# requirements.txt (generated by `uv export --no-dev --no-hashes --package frontend`, then prefixed with CPU index):

#   --extra-index-url https://download.pytorch.org/whl/cpu

#   torch==2.14.1

#   torchvision==0.29.1

#   transformers==5.20.2

#   huggingface_hub==2.3.0

#   gradio==6.30.0

#   pillow>=12,<13

#   pydantic==2.14.1

#   pydantic-settings==2.16.1

#   sentence-transformers==6.2.0

#   chromadb==1.5.9

#   httpx==0.28.1

#   trafilatura==2.3.1

#   tavily-python==0.8.5

#   tenacity==9.2.1

#   structlog==26.1.0

#   pyyaml

#   ./backend ./frontend   # (validate in a skeleton Space; fall back to sys.path in app.py if pip rejects local paths)

# --- Training extra (backend[train]) ---

# --- Scrape/index extra (backend[ingest]) ---

# --- Dev group ---

## Recommended Training Recipe (transformers 5.20)

- `AutoImageProcessor` + `AutoModelForImageClassification.from_pretrained(ckpt, num_labels=39, id2label=..., label2id=..., ignore_mismatched_sizes=True)`.
- `TrainingArguments`: `eval_strategy="epoch"`, `save_strategy="epoch"`, `remove_unused_columns=False`, `bf16=True` (RTX 3050 Ampere supports bf16), `per_device_train_batch_size=32` (tiny models) with `gradient_accumulation_steps`, `learning_rate=5e-5` (ViT) / `1e-4` (ConvNeXt, with layer-wise decay optional), `warmup_steps=0.1`, `lr_scheduler_type="cosine"`, `label_smoothing_factor=0.1`, `load_best_model_at_end=True`, `metric_for_best_model="f1_macro"`, `report_to="trackio"`, `dataloader_num_workers=4`, `seed=42`. Pass `processing_class=image_processor` (v5: `tokenizer=` is removed).
- Data: `datasets.load_dataset("Project-AgML/plant_village_classification")` -> group-aware stratified split (imagehash clusters + `StratifiedGroupKFold`, 80/10/10) -> `.with_transform(...)`.
- Augmentation (`torchvision.transforms.v2`): `RandomResizedCrop(scale=(0.5,1))`, `RandomHorizontalFlip/VerticalFlip`, `RandomRotation(45)`, `ColorJitter(0.4,0.4,0.4,0.1)`, `RandomPerspective`, `GaussianBlur`, `RandomGrayscale(0.05)`, `JPEG compression` (v2 `JPEG`), `RandomErasing`, plus **background-swap augmentation** (paste leaf onto random background crops) because Noyan (arXiv 2206.04374) shows PlantVillage models can classify from background pixels alone.
- Confidence gate (all in `backend.inference.gate`, numpy/torch only, no extra dependency): (1) temperature scaling fit on the validation split; (2) reject if `p_top1 < tau`, or `p_top1 - p_top2 < margin`, or predicted class is `Background_without_leaves`; (3) report ECE; (4) choose `tau` so precision on accepted predictions >= target on a field-photo probe set; persist `{temperature, tau, margin}` in `gate.json` beside the weights so the Space has no hard-coded thresholds. Optional later upgrade: CLIP zero-shot "is this a plant leaf?" pre-filter (`openai/clip-vit-base-patch32`).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| transformers `Trainer` | Custom PyTorch loop / PyTorch Lightning | Only if you need custom losses or multi-stage training Trainer can't express. |
| `torchvision.transforms.v2` | Albumentations 2.0.8 | Never for new work here: last release 2025-05-27, development moved to **AlbumentationsX** (2.5.1) under a different license model (AGPL/commercial). Avoid licence risk and a stalled dependency. |
| `facebook/convnextv2-tiny-22k-224` default | ViT-Base 224 | If benchmark shows ViT-B wins by >1% macro-F1 on field probe set and CPU latency stays <1.5 s. |
| ChromaDB | LanceDB 0.40.0 | If Space build time/size from Chroma's dependency tree hurts, or you want hybrid FTS later. Pre-1.0 API is the cost. |
| ChromaDB | FAISS (`faiss-cpu` 1.15.1) + parquet | If corpus stays < ~20k chunks and you want zero server-ish deps; you re-implement metadata filtering. |
| bge-m3 | multilingual-e5-base (278M) | If cold-start memory/latency is a problem; remember `query:`/`passage:` prefixes. |
| bge-m3 | Qwen3-Embedding-0.6B (Apache-2.0, 8.1M downloads) | If bge-m3 loses on your Hindi retrieval mini-benchmark; Qwen3-Embedding uses instruction-style queries. |
| `InferenceClient` | OpenAI SDK pointed at `router.huggingface.co/v1` | If you want drop-in portability to another provider later. |
| Tavily | Brave Search API / Exa / `ddgs` | Brave/Exa if Tavily's domain filtering or quota is insufficient; `ddgs` only as keyless last resort. |
| In-process import (frontend -> backend) | FastAPI service + HTTP client | Only at the later two-Space split. Keep a clean service-layer interface now (`backend.services.DiagnosisService`, `ChatService`) so FastAPI (0.161.1) can wrap it later without refactor. |
| `sdk: gradio` Space | `sdk: docker` Space | If `requirements.txt` + local packages can't express the workspace cleanly, or you need system packages/multi-process. Docker Space also needs paid plan; team already has a Dockerfile convention. Start with `sdk: gradio`; fall back to Docker if packaging spike fails. |
| HF Jobs scheduled scrape | GitHub Actions cron / APScheduler in Space | GitHub Actions if Jobs credits are tight. **Not** APScheduler in the Space (sleeps, ephemeral disk). |
| trackio | Weights & Biases | If the team already has W&B; adds account/secret overhead. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Transformers v4 patterns (`tokenizer=` in Trainer, `evaluation_strategy`, `use_fast=` image processors, `torch_dtype`, `use_auth_token`, TF/Flax) | Removed/renamed in v5; most Stack Overflow/blog snippets are v4 | `processing_class=`, `eval_strategy=`, `backend="pil"` if needed, `token=` |
| `evaluate` 0.4.6 | Last release 2025-09, effectively stagnant, extra network fetch of metric scripts | `scikit-learn` + `torchmetrics` in `compute_metrics` |
| Albumentations | See Alternatives | `torchvision.transforms.v2` |
| LangChain / LlamaIndex | Heavy dependency trees, rapid API churn, obscure stack traces; unnecessary for single-hop RAG | Own ports/adapters (`backend/rag`) |
| In-Space scheduler (APScheduler, cron thread) | Free-tier Spaces sleep; disk is ephemeral; scrape would die silently | HF Jobs scheduled / GitHub Actions + published index |
| Writing the vector index to the Space's local disk as the source of truth | Lost on restart; "persistent storage" feature is removed | Build offline, publish to Dataset repo/Bucket, pull on boot |
| Downloading the 823 MB dataset at Space boot | Slow cold start, pointless at inference | Download in training/eval CLI only; `preload_from_hub` the model |
| `pillow>=13` (unpinned) | Gradio 6.30.0 requires `pillow<13` | `pillow>=12,<13` |
| Default CUDA torch wheels on the CPU Space | Multi-GB download, slow builds | `--extra-index-url https://download.pytorch.org/whl/cpu` |
| Random (non-grouped) train/val/test split | PlantVillage has many near-identical shots of the same leaf: inflated metrics and an overconfident model | imagehash clustering + `StratifiedGroupKFold` |
| Raw softmax max-prob as "confidence" without calibration | Transformers are overconfident; gate threshold becomes meaningless | Temperature scaling + margin + Background class + probe-set-tuned threshold |
| `langdetect`, `lingua` for language ID | Unmaintained / heavy; unnecessary for a 2-script problem | Unicode-block script ratio + LLM mirrors user language |
| `ddgs` as the primary search | Scrapes engines, frequent rate-limit/empty results; unsourced results harm "trustworthy" goal | Tavily with `include_domains`, `ddgs` as last resort |
| Letting the LLM answer pesticide/dosage questions from parametric memory | Safety constraint; hallucinated dosages cause crop loss | Retrieval-only dosage answers with citations; refuse + refer to local KVK/extension officer if no source |
| `AlbumentationsX`, `gr.Chatbot(type="tuples")`, Gradio 5 `gr.Blocks(theme=...)` | Wrong license / removed in Gradio 6 | Gradio 6 `launch(theme=..., css=...)`, messages format |
| `loguru` | Global singleton, awkward with library-grade module boundaries | stdlib `logging` + `structlog` |

## Stack Patterns by Variant

- Ship plain PyTorch eager inference, `torch.inference_mode()`, `torch.set_num_threads(2)`, single warmed-up model loaded once at startup. No ONNX.
- Export to ONNX with `optimum` 2.3.0, run with `onnxruntime` 1.31.0 (needs py>=3.11), or move the Space to CPU Upgrade (8 vCPU/32 GB, $0.03/h).
- Keep `max_tokens` capped (~600), retrieve top-4 chunks, cache answers per `(disease_id, language, question_hash)` in a small on-disk LRU, rate-limit per session in Gradio (`concurrency_limit`, `max_size` on queue), and add a budget kill-switch setting.
- Wrap `backend.services.*` with FastAPI 0.161.1; `frontend` swaps its in-process adapter for an `httpx` client behind the same Protocol. import-linter contracts guarantee the seam was never violated.
- Downscale client-side/early (`PIL.ImageOps.exif_transpose`, `thumbnail((1024,1024))`) before inference; add `pillow-heif`.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| gradio 6.30.0 | huggingface-hub >=1.16,<3; pillow <13; pydantic <=3; starlette >=1.0.1; fastapi <1.0 | **Pin pillow<13.** Python >=3.10. |
| transformers 5.20.2 | huggingface-hub >=1.31,<3; torch >=2.6; accelerate >=1.1; tokenizers >=0.23.1,<0.24; timm >=1.0.23 (extra) | torch-only. |
| datasets 5.1.0 | pyarrow >=24; huggingface-hub >=1.31,<3 | pyarrow 26.0.0 is current. |
| sentence-transformers 6.2.0 | transformers >=5,<6; torch >=2.2 | v6 requires transformers 5: don't mix with transformers 4. |
| huggingface_hub 2.3.0 | httpx2 >=2,<3 (not `requests`/`httpx`) | `respx` does not see its traffic; mock via ports. |
| pydantic-settings 2.16.1 | Python >=3.11 | Rules out the Spaces default of 3.10. |
| torch 2.14.1 | torchvision 0.29.1; `+cpu` cp312 wheels exist on download.pytorch.org/whl/cpu | torchvision 0.29.x excludes Python 3.14.1. |
| chromadb 1.5.9 | Python >=3.9; pulls onnxruntime, grpcio, kubernetes, opentelemetry | Heavy install; disable telemetry. |
| scikit-learn 1.9.1, onnxruntime 1.31.0, Pillow 13, pre-commit 4.7.0, hypothesis 6.170 | Python >=3.11 | Another reason for 3.12. |

## Open Questions / Spikes Required (flag for phase research)

## Sources

- PyPI JSON API (queried 2026-10-23): torch 2.14.1, torchvision 0.29.1, transformers 5.20.2, datasets 5.1.0, huggingface_hub 2.3.0, accelerate 1.15.0, gradio 6.30.0, pydantic 2.14.1, pydantic-settings 2.16.1, sentence-transformers 6.2.0, chromadb 1.5.9, lancedb 0.40.0, trafilatura 2.3.1, tavily-python 0.8.5, ruff 0.17.2, mypy 2.4.0, pytest 9.1.1, etc. (HIGH; requires_dist constraints read directly)
- https://huggingface.co/docs/transformers/tasks/image_classification (v5.20.2 recipe: `eval_strategy`, `processing_class`, `report_to="trackio"`) (HIGH)
- https://github.com/huggingface/transformers/blob/main/MIGRATION_GUIDE_V5.md (v5 breaking changes) (HIGH)
- https://www.gradio.app/main/guides/gradio-6-migration-guide (Gradio 6 breaking changes) (HIGH)
- https://huggingface.co/docs/hub/spaces-overview (hardware table, PRO requirement, ephemeral disk, secrets/variables) (HIGH)
- https://huggingface.co/docs/hub/spaces-config-reference (`python_version` default 3.10, `sdk_version`, `preload_from_hub`, persistent storage removed) (HIGH)
- https://huggingface.co/docs/hub/spaces-storage and https://huggingface.co/docs/hub/storage-buckets (bucket volumes, `sync_bucket`, `batch_bucket_files`) (HIGH)
- https://huggingface.co/docs/hub/jobs-overview (`hf jobs uv run`, cron-scheduled Jobs) (HIGH)
- https://huggingface.co/docs/inference-providers/index and /pricing (InferenceClient, router URL, `:fastest/:cheapest`, PRO $2 credits, free = purchase) (HIGH)
- https://router.huggingface.co/v1/models (live catalogue and per-provider pricing, queried 2026-10-23) (HIGH for availability/price on that date; volatile)
- https://huggingface.co/google/gemma-4-26B-A4B-it (MoE, Apache-2.0, 256K ctx, 35+ languages) (MEDIUM for Hindi quality: not explicitly listed)
- HF Hub API model metadata for bge-m3, multilingual-e5-small/base, Qwen3-Embedding-0.6B, embeddinggemma-300m (gated), ConvNeXt V2 / Swin / ViT checkpoints (HIGH for existence/license/size)
- Local: `/home/himanshu/Desktop/Aryan Project/KhetSetu-/data/plant_village_classification/README.md` (55,448 images, 39 classes, single `train` split, includes `Background_without_leaves`); `nvidia-smi` (RTX 3050 6 GB) (HIGH)
- https://docs.tavily.com (free plan 1,000 credits/month; per-credit cost per search depth only confirmed via third-party pages) (MEDIUM)
- https://arxiv.org/abs/2206.04374 "Uncovering bias in the PlantVillage dataset" (background-pixel shortcut) and Ahmad et al., IEEE Access 2023 (cross-dataset generalisation drop to ~77-82%) found via web search (MEDIUM; not read in full)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| fine-tuning-expert | "Use when fine-tuning LLMs, training custom models, or adapting foundation models for specific tasks. Invoke for configuring LoRA/QLoRA adapters, preparing JSONL training datasets, setting hyperparameters for fine-tuning runs, adapter training, transfer learning, finetuning with Hugging Face PEFT, OpenAI fine-tuning, instruction tuning, RLHF, DPO, or quantizing and deploying fine-tuned models. Trigger terms include: LoRA, QLoRA, PEFT, finetuning, fine-tuning, adapter tuning, LLM training, model training, custom model." | `.claude/skills/fine-tuning-expert/SKILL.md` |
| finetuning | This skill should be used when picking or diagnosing a training move (SFT, LoRA, DPO/KTO/ORPO, RFT, GRPO/PPO/RLOO, RLHF), or when the user mentions fine-tuning, post-training, training recipe, reward design, or weight updates. Decision tree by reward shape, smoke-run gate, three failure diagnostics, five false-progress patterns. Provider recipes and I/O contract in references/. | `.claude/skills/finetuning/SKILL.md` |
| huggingface-llm-trainer | Train or fine-tune language and vision models using TRL (Transformer Reinforcement Learning) or Unsloth with Hugging Face Jobs infrastructure. Covers SFT, DPO, GRPO and reward modeling training methods, plus GGUF conversion for local deployment. Includes guidance on the TRL Jobs package, UV scripts with PEP 723 format, dataset preparation and validation, hardware selection, cost estimation, Trackio monitoring, Hub authentication, model selection/leaderboards and model persistence. Use for tasks involving cloud GPU training, GGUF conversion, or when users mention training on Hugging Face Jobs without local GPU setup. | `.claude/skills/huggingface-llm-trainer/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
