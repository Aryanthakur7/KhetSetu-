# Architecture Research

**Domain:** Plant-disease image classification + multilingual (Hindi/English) RAG chat assistant, deployed as a single Hugging Face Space
**Researched:** 2026-10-23
**Confidence:** MEDIUM-HIGH (see "Confidence and Verification Notes" at the end)

## Headline Findings (read these first)

1. **The 823 MB training dataset is not a serving dependency.** The Space only needs the *fine-tuned model artifact*. "Download dataset on startup" is still implementable (idempotent `ensure_dataset()`), but it must run as the first step of *training/dev entrypoints* and as a low-priority background step in the Space, never ahead of model/index load on the serving path. This partially conflicts with the PROJECT.md wording "before anything else runs" and needs an explicit roadmap decision (recommended resolution below).
2. **The Space filesystem is ephemeral and free-tier Spaces sleep after 48 h idle.** HF's old "persistent storage" add-on is gone (config reference says the setting "will be ignored"); the replacement is Storage Buckets mounted as volumes. Therefore: do not keep the vector store only on the Space disk, and do not rely on an in-process cron to keep it fresh. Publish knowledge snapshots to a Hub **dataset repo** from an external scheduled job; the Space pulls and hot-swaps.
3. **Two account/cost facts affect the architecture** (official HF docs, fetched 2026-10-23): (a) creating a *Gradio or Docker* Space on compute "requires a paid plan" (PRO for personal accounts), CPU Basic hardware itself is $0; (b) free HF users get **no** Inference Providers credits (PRO gets $2/month, pay-as-you-go beyond that). The LLM client must therefore be budget-aware (rate limit, small max_tokens, response cache, graceful degradation). Roadmap should confirm account tier before Phase 1.
4. **Build the seams first.** Typed contracts (`contracts/`) and fake services let the Gradio UI, ingest pipeline, and model training proceed in parallel; the model-training long pole should start early.

## Standard Architecture

### System Overview

```
 FARMER (mobile browser, Hindi/English)
        |  HTTPS (single HF Space URL, port 7860)
        v
+-------------------------------------------------------------------------+
|                     HF SPACE  (cpu-basic: 2 vCPU / 16 GB / 50 GB eph.)  |
|                                                                         |
|  app.py  (COMPOSITION ROOT - only file that sees both packages)         |
|     |  load Settings -> build_services(settings) -> build_ui(services)  |
|     v                                                                   |
|  +-------------------------+        +--------------------------------+  |
|  | frontend/  (Gradio UI)  |        | backend/  (service layer)      |  |
|  |  tabs: Diagnose | Chat  | -----> |  contracts/  DTOs + Protocols  |  |
|  |  i18n en/hi, presenters |  DTOs  |  services/   Diagnosis | Chat  |  |
|  |  gr.State (session ctx) | <----- |              | Health          |  |
|  |  NO torch / NO HF libs  |        +---+-----------+-------+--------+  |
|  +-------------------------+            |           |       |           |
|                                         v           v       v           |
|                                  +---------+  +----------+ +---------+  |
|                                  | vision/ |  | chat/    | | health/ |  |
|                                  | classif.|  | orchestr.| | ready-  |  |
|                                  | + GATE  |  | prompts, | | ness    |  |
|                                  +----+----+  | citations| +----^----+  |
|                                       |       | safety   |      |       |
|                                       |       +--+----+--+      |       |
|                                       |          |    |         |       |
|                                       |    +-----v+  +v------+  |       |
|                                       |    |knowl-|  |search/|  |       |
|                                       |    |edge/ |  | live  |  |       |
|                                       |    |retr. |  |fallbk |  |       |
|                                       |    +--+---+  +---+---+  |       |
|   bootstrap/ BootstrapManager (background thread, staged) -------+       |
|     ensure_model -> ensure_knowledge -> warmup -> READY ; dataset (bg)  |
|     + KnowledgeRefresher (poll Hub for new snapshot, hot-swap)         |
+-----------------------+-----------------+-------------+----------------+
                        |                 |             |
        (HF Hub downloads)        (HTTPS API)     (HTTPS, allow-listed)
                        v                 v             v
+------------------+ +-----------------+ +-----------------+ +----------+
| Hub MODEL repo   | | Hub DATASET repo| | HF Inference    | | Search   |
| classifier +     | | knowledge       | | Providers       | | API / web|
| labels + gate    | | snapshot        | | (chat LLM)      | | (live    |
| calibration meta | | (parquet+manif.)| |                 | | fallback)|
+--------^---------+ +--------^--------+ +-----------------+ +----------+
         |                    |
         | publish            | publish (commit, versioned)
+--------+---------+  +-------+------------------------------+
| OFFLINE TRAINING |  | SCHEDULED INGEST JOB (NOT in Space)  |
| (Colab / HF Jobs |  | GitHub Actions cron or HF scheduled  |
|  / local GPU)    |  | Job: fetch -> clean -> chunk -> embed |
| reads Project-   |  | -> write snapshot -> push to dataset |
| AgML dataset     |  +--------------------------------------+
+------------------+
```

Key shape: **one runtime process (the Space), two offline producers (training, ingest) that publish versioned artifacts to the Hub, and the Space is a read-only consumer of those artifacts.** This is the standard pattern for HF-hosted ML apps because the Hub is the only durable storage you get for free.

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `app.py` (composition root) | Load settings, build services, build UI, launch. The only module allowed to import both packages. | ~30 lines; HF `app_file`. |
| `frontend/` Gradio UI | Render, i18n, session state, map DTOs to components. Zero business logic (no thresholds, no prompt text). | `gr.Blocks`, `gr.Image`, `gr.Chatbot` (streaming), `gr.State`. Receives a `Services` object by injection. |
| `backend/contracts/` | Pure-pydantic DTOs (`DiagnosisResult`, `GateStatus`, `ChatRequest`, `ChatChunk`, `Citation`, `Readiness`) and `typing.Protocol`s (`DiagnosisService`, `ChatService`, `HealthService`). No torch/HF imports. | pydantic v2 models. This is the stable seam that makes a later 2-Space split cheap. |
| `backend/config/` | Typed settings from env/`.env`; fail fast on missing required values; secrets as `SecretStr`. | `pydantic-settings` `BaseSettings`. `.env` optional (local only); on a Space the same fields come from Space Variables/Secrets (exposed as env vars). |
| `backend/bootstrap/` | Staged startup: ensure model, ensure knowledge snapshot, (optionally) dataset, warm-up, publish readiness. Background refresher. | `BootstrapManager` running stages in a daemon thread; `ReadinessReport` object read by UI/Health. |
| `backend/vision/` | Preprocess, forward pass, calibrated probabilities, **confidence gate**, label to disease mapping. | `transformers` `AutoModelForImageClassification` + `AutoImageProcessor`, `torch.inference_mode`, semaphore-limited. |
| `backend/knowledge/` | Load snapshot, hybrid retrieval (dense + BM25), metadata filter by disease/crop/lang, sufficiency scoring. | Parquet snapshot -> in-memory index behind a `VectorStore` Protocol (numpy or FAISS flat; corpus is small). |
| `backend/ingest/` | Source registry, polite fetch, clean, chunk, embed, dedupe, build+publish snapshot. Runs as CLI, never imported by the serving path. | `python -m khetsetu_backend.ingest run`; `httpx`, `trafilatura`/`selectolax`, sentence-transformers. |
| `backend/search/` | Live web-search fallback behind a provider Protocol; domain allow-list/ranking; snippet fetch+clean. | One provider impl chosen by settings (Tavily/Brave/Exa/DDG). Results tagged `origin="live"`. |
| `backend/llm/` | Thin typed wrapper over HF Inference Providers chat completions: timeout, retry, streaming, token/budget limits. | `huggingface_hub.InferenceClient.chat_completion(stream=True)` (or OpenAI-compatible router endpoint). |
| `backend/chat/` | RAG orchestration: build query, retrieve, sufficiency check, fallback, prompt assembly, citation validation, **deterministic** safety framing, language handling. | Plain Python orchestrator class; prompts as versioned files. |
| `backend/services/` | Public facade implementing the Protocols; wires vision/chat/health. Exposes `build_services(settings)`. | Thin classes; the only backend API the frontend may call. |
| `backend/training/` (offline) | Dataset prep, augmentation, benchmark 2-3 backbones, calibration, push model + meta to Hub. | Optional dependency group `[train]`; HF `Trainer`/PEFT; kept out of Space `requirements.txt`. |

## Recommended Project Structure

```
KhetSetu-/
├── README.md                    # HF Space YAML front-matter (sdk: gradio, app_file: app.py,
│                                #   python_version, preload_from_hub, startup_duration_timeout)
├── app.py                       # composition root (only place FE + BE meet)
├── requirements.txt             # Space runtime deps (slim; no training libs)
├── .env.example                 # committed; every setting documented
├── Makefile                     # bootstrap, train, ingest, test, lint, run
├── backend/
│   ├── pyproject.toml           # package: khetsetu-backend ; extras: [train], [ingest], [dev]
│   ├── src/khetsetu_backend/
│   │   ├── contracts/           # DTOs + Protocols (pure pydantic; zero heavy imports)
│   │   ├── config/              # Settings (pydantic-settings), enums (DatasetMode, LLM provider)
│   │   ├── bootstrap/           # manager.py, readiness.py, artifacts.py (model/snapshot), dataset.py
│   │   ├── vision/              # classifier.py, gate.py, preprocess.py, labels.py
│   │   ├── knowledge/           # store.py (Protocol+impl), embedder.py, retriever.py, snapshot.py, refresher.py
│   │   ├── ingest/              # sources.yaml loader, fetch.py, clean.py, chunk.py, pipeline.py, publish.py, cli.py
│   │   ├── search/              # provider.py (Protocol), tavily.py|brave.py, allowlist.py
│   │   ├── llm/                 # client.py (InferenceClient wrapper), budget.py
│   │   ├── chat/                # orchestrator.py, prompts/, citations.py, safety.py, language.py
│   │   ├── domain/              # diseases.yaml (class id -> crop, EN/HI names, aliases), loaders
│   │   ├── services/            # diagnosis.py, chat.py, health.py, container.py (build_services)
│   │   └── training/            # offline only: data.py, augment.py, train.py, calibrate.py, publish.py
│   ├── tests/                   # unit (fakes), integration (marked), contract tests
│   ├── scripts/                 # thin CLIs: bootstrap_data.py, train.py, ingest.py
│   └── docs/
├── frontend/
│   ├── pyproject.toml           # package: khetsetu-frontend ; depends on backend CONTRACTS only
│   ├── src/khetsetu_frontend/
│   │   ├── ui.py                # build_ui(services) -> gr.Blocks
│   │   ├── components/          # diagnose_tab.py, chat_tab.py, readiness_banner.py
│   │   ├── presenters.py        # DTO -> display strings/markdown (pure, testable)
│   │   ├── i18n/                # en.json, hi.json
│   │   └── theme.py             # mobile-first, large touch targets, low-bandwidth
│   └── tests/                   # run with FakeServices; no model needed
├── data/                        # gitignored (dataset cache, local snapshots)
└── .github/workflows/           # ci.yml, ingest.yml (cron), sync-to-space.yml
```

### Structure Rationale

- **`contracts/` is its own tiny layer.** The frontend's only compile-time dependency on the backend is `contracts` (types). `app.py` is the only place that calls `build_services`. Enforce with an import-linter rule in CI ("`khetsetu_frontend` may import only `khetsetu_backend.contracts`"). When the team later splits into two Spaces, add a `RemoteServices` (HTTP client) implementing the same Protocols and swap one line in the new FE `app.py`.
- **`ingest/` and `training/` live in the backend package but behind extras.** They share domain code (embedder, chunk schema, label map) with serving, which prevents train/serve skew (e.g. embedding model mismatch), but the Space installs neither extra, keeping cold-start and image size small.
- **`domain/diseases.yaml` is a curated artifact, not code.** It maps the dataset's class ids (PlantVillage style `Crop___Disease`, to be confirmed after dataset inspection) to canonical English/Hindi names and aliases. Both the retrieval query builder and the UI use it; this is what makes Hindi answers and Hindi keyword retrieval possible.
- **Root `app.py` + root `README.md` front-matter** are forced by HF Spaces (repo root = Space root). `backend/` and `frontend/` stay separate packages inside it.
- **Importability on a Gradio-SDK Space (verify in a Phase 1 spike):** simplest robust approach is `app.py` inserting `backend/src` and `frontend/src` into `sys.path` (or `requirements.txt` containing `-e ./backend -e ./frontend`). Whether a relative editable install resolves during the Space build was not confirmed from docs (LOW); test it on a throwaway Space before committing to one.

## Architectural Patterns

### Pattern 1: Composition root + Protocol-based service layer

**What:** The frontend receives service objects typed by Protocols; it never constructs backend classes. `app.py` wires everything.
**When to use:** Always here; it is what satisfies "Gradio FE imports the BE service layer" while keeping the later 2-Space split cheap.
**Trade-offs:** A little ceremony (Protocols, DTOs) for large payoff: UI tests run with fakes in milliseconds, and training/ingest/UI can proceed in parallel.

```python
# backend/contracts/services.py  (pure: no torch, no huggingface_hub)
class GateStatus(StrEnum):
    DIAGNOSED = "diagnosed"
    LOW_CONFIDENCE = "low_confidence"
    NOT_A_LEAF = "not_a_leaf"

class DiagnosisResult(BaseModel):
    status: GateStatus
    disease_id: str | None
    crop: str | None
    top_k: list[ScoredLabel]          # for transparency / debugging
    confidence: float                 # calibrated
    message_key: str                  # i18n key; FE chooses language

class DiagnosisService(Protocol):
    def diagnose(self, image: PIL.Image.Image) -> DiagnosisResult: ...

class ChatService(Protocol):
    def stream(self, req: ChatRequest) -> Iterator[ChatChunk]: ...  # tokens, then final Citations
```

```python
# app.py
settings = Settings()                         # fails fast if HF_TOKEN etc. missing
services = build_services(settings)           # starts BootstrapManager (non-blocking)
build_ui(services).queue(max_size=20, default_concurrency_limit=2).launch(
    server_name="0.0.0.0", server_port=7860)
```

### Pattern 2: Staged, non-blocking bootstrap with a readiness report

**What:** Bind the port and serve the UI immediately; a `BootstrapManager` runs stages in a background thread and updates a thread-safe `ReadinessReport` (`vision: pending|loading|ready|failed`, `knowledge: ...`, `dataset: ...`). Each service checks its own readiness and raises a typed `NotReady` the UI renders as a "warming up" banner. Failed stages surface a retry button and logs, instead of an opaque "Runtime error" Space.
**When to use:** Any Space whose cold start exceeds a few seconds. HF's default `startup_duration_timeout` is 30 min, so blocking would *work*, but gives the first visitor after a sleep a long blank page and an all-or-nothing failure mode.
**Trade-offs:** More states to test. Mitigated by making stages small pure functions with injected dependencies.

```python
class BootstrapManager:
    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="bootstrap").start()

    def _run(self) -> None:
        self._stage("vision",    self._load_classifier)     # critical path #1
        self._stage("knowledge", self._load_knowledge)      # critical path #2 (parallel download)
        self._stage("warmup",    self._warmup)              # dummy forward + dummy embed
        if self._s.dataset_mode is DatasetMode.BACKGROUND:
            self._stage("dataset", ensure_dataset)          # low priority, non-blocking
        self._refresher.start()                             # snapshot poll thread
```

### Pattern 3: Publish-and-pull artifacts (Hub as the durable store)

**What:** Everything durable is a versioned Hub artifact: the classifier (model repo), the knowledge snapshot (dataset repo, parquet + `manifest.json`), the training data (upstream dataset). The Space only *pulls* (`snapshot_download`, content-addressed cache, so idempotent and resumable). Producers are offline jobs.
**When to use:** Free/low-tier Spaces with ephemeral disk and sleep. It makes restarts cheap and freshness independent of Space uptime.
**Trade-offs:** Snapshot publishing adds a step and a Hub commit per ingest run (keep cadence daily/weekly and skip commits when nothing changed). Hub dataset repos keep git history (grows with every snapshot); use one overwritten file set per run and squash history periodically, or use a Storage Bucket for the mutable "latest" pointer if Bucket cost is acceptable.

`manifest.json` must record: `schema_version`, `embedding_model_id`, `embedding_dim`, `created_at`, `n_chunks`, per-source counts, `ingest_git_sha`. **Runtime must refuse to load a snapshot whose `embedding_model_id` differs from its configured embedder** (the single most common silent RAG failure).

### Pattern 4: Confidence gate as a first-class domain component (three-state, calibrated)

**What:** `vision/gate.py` converts raw logits into `GateStatus`. Inputs: temperature-scaled max probability, top-1/top-2 margin, entropy, and a non-leaf/OOD signal (recommended: add an explicit "background/not-leaf" class trained on non-leaf images, plus max-logit/energy score threshold). Thresholds are **calibrated at training time and shipped inside the model repo** (`khetsetu_meta.json`: label map, temperature, thresholds, model card of calibration set), with `.env` override for emergencies.
**When to use:** Core to the project's stated Core Value (honest "not sure" beats confident wrong).
**Trade-offs:** Needs a small field-photo validation set (even ~100-200 phone photos) to set thresholds honestly; lab-only validation will produce overconfident gates. Treat acquiring that set as a roadmap item, not an afterthought.
The UI never decides: it renders by `GateStatus` only.

### Pattern 5: Two-tier retrieval with explicit sufficiency decision (curated first, live fallback)

**What:** `chat/orchestrator.py` runs: (1) hybrid retrieval on curated store, filtered by `disease_id`/crop when diagnosis context exists; (2) a **sufficiency check** (top score >= threshold AND >= N distinct chunks AND, optionally, the lexical match covers the disease alias); (3) if insufficient, call `search/` live fallback, fetch+clean top results from allow-listed/ranked domains; (4) assemble prompt with numbered sources, each tagged `origin: curated|live`; (5) stream LLM; (6) validate citations; (7) append deterministic safety footer; (8) if still no sources, return a templated honest "I could not find a reliable source" rather than letting the LLM answer from memory.
**When to use:** Always for remedy questions. Generic chit-chat can skip RAG.
**Trade-offs:** Sufficiency thresholds need an eval set (20-50 Hindi+English question/expected-source pairs) to tune.

```python
def answer(self, req: ChatRequest) -> Iterator[ChatChunk]:
    ctx = req.diagnosis                                   # DiagnosisContext | None
    query = self._query_builder.build(req, ctx)           # EN canonical disease + crop + user question
    hits = self._retriever.search(query, disease_id=ctx and ctx.disease_id, k=6)
    sources = hits
    if not self._sufficient(hits):
        sources = hits + self._live.search(query, lang=req.lang)   # tagged origin="live"
    if not sources:
        yield from self._no_source_reply(req.lang); return
    prompt = self._prompts.render(req, sources)           # "answer ONLY from sources; cite [n]; no dosages unless in a source"
    text_parts = []
    for tok in self._llm.stream(prompt):
        text_parts.append(tok); yield ChatChunk(token=tok)
    cites = validate_citations("".join(text_parts), sources)      # drop/flag dangling [n]
    yield ChatChunk(citations=cites, footer=self._safety.footer(req.lang, "".join(text_parts)))
```

### Pattern 6: Decoupled scheduled ingest (trigger is a thin, swappable shell)

**What:** The ingest pipeline is an idempotent CLI (`ingest run --sources sources.yaml --publish`). *What triggers it* is separate: recommended primary = **GitHub Actions cron** (free, independent of Space sleep, secrets in repo settings); alternative = **HF scheduled Job** (`hf jobs scheduled uv run @daily ...`, confirmed to exist; billed against HF compute credits, so verify cost); dev fallback = an in-Space `APScheduler`/thread behind `INGEST_IN_PROCESS=true` for local demos only.
**Why not in-Space scheduling as primary:** free-tier Spaces sleep after 48 h idle (jobs silently stop), a restart loses disk, replicas would double-run, and scraping + embedding competes with 2 vCPU that also serve inference.
**Trade-offs:** Needs a write-scoped HF token as a CI secret; two deploy surfaces (Space + workflow). Worth it.
Pipeline stages: `fetch (robots.txt, rate limit, ETag/If-Modified-Since cache) -> extract main text -> language tag -> chunk (heading-aware, ~300-500 tokens, overlap) -> attach metadata {source, url, crop, disease_ids[], lang, fetched_at, license} -> dedupe (hash) -> embed -> write parquet+manifest -> publish if changed`.

## Data Flow

### Flow A: Cold start / bootstrap (the sequencing question)

```
HF build time (free, cached in image):
  README preload_from_hub -> classifier repo + embedding model  ==> ~/.cache/huggingface/hub

Process start (t=0):
  1. Settings() validate                                  [<1 s, fail fast]
  2. build_services(): construct services in NotReady state, start BootstrapManager thread
  3. Gradio launches, port 7860 bound  ==> Space = "Running"  [UI shows warming-up banner]

Bootstrap thread (parallel I/O, serialized CPU-heavy loads):
  4a. [I/O]  snapshot_download(classifier)   -> from preload cache: instant; else ~0.1-0.4 GB
  4b. [I/O]  snapshot_download(knowledge dataset repo) -> MBs
  5.  [CPU]  load classifier (eval, torch.set_num_threads(2)) + warm-up forward on a dummy image
  6.  [CPU]  load embedder + load snapshot into in-memory index + check manifest.embedding_model_id
  7.  readiness: vision=READY (Diagnose tab enabled), knowledge=READY (Chat enabled)
  8.  [background, lowest priority] ensure_dataset()  if DATASET_MODE=background
  9.  start KnowledgeRefresher (every N hours: compare dataset repo head sha; if new, download, build index off to the side, atomic swap)
```

Ordering rationale: classifier first because it is the Core Value path and the only blocker for the primary use case; knowledge second because chat is only meaningful after a diagnosis anyway (the farmer needs a few seconds to upload a photo), so its load overlaps with user think-time; dataset last because nothing at serve time needs it. Total warm path with preload should be on the order of 1-2 minutes on 2 vCPU (estimate, MEDIUM-LOW; measure in Phase 1).

`DatasetMode` setting (typed enum): `BLOCKING` (default for `make bootstrap` / training / local dev, satisfies "before anything else runs"), `BACKGROUND` (Space default if a runtime consumer exists), `OFF` (Space default otherwise). Recommended resolution of the PROJECT.md wording: **dataset download is the first step of every entrypoint that needs it (training, EDA, calibration, tests with real data); on the Space it is a background step.**

### Flow B: Diagnosis request

```
Farmer uploads photo (gr.Image, type="pil")
  -> frontend/diagnose_tab handler
  -> services.diagnosis.diagnose(image)               [DTO in]
       -> vision.preprocess (RGB, resize, normalize; EXIF-orient; downscale huge phone photos first)
       -> semaphore(2) -> torch.inference_mode forward -> logits
       -> temperature scale -> softmax -> gate.evaluate()
  <- DiagnosisResult{status, disease_id, crop, confidence, top_k, message_key}
  -> presenters.render(result, lang)
       DIAGNOSED       -> disease name (EN/HI), confidence, short summary, enable chat with DiagnosisContext in gr.State
       LOW_CONFIDENCE  -> "send a clearer photo" guidance (lighting, single leaf, close-up), chat locked to general mode
       NOT_A_LEAF      -> "this doesn't look like a leaf" message
```

### Flow C: Chat turn (RAG + fallback)

```
User message (Hindi or English) + DiagnosisContext (from gr.State) + trimmed history (last ~6 turns)
  -> services.chat.stream(ChatRequest)
  -> chat.orchestrator: query build -> curated retrieve -> sufficiency?
        yes -> sources = curated
        no  -> live search (allow-list ranked) -> sources = curated + live
  -> prompt (lang-specific system prompt; sources numbered) -> llm.stream (HF Inference Providers)
  -> tokens streamed back to gr.Chatbot
  -> final chunk: citations [(n, title, url, origin)] + deterministic safety footer
```

### Flow D: Knowledge freshness

```
cron (GitHub Actions) -> ingest CLI -> build parquet+manifest -> push to Hub dataset repo (skip if no change)
Space KnowledgeRefresher (poll, e.g. 6 h, + on startup) -> sha changed? -> download -> build index -> atomic swap -> readiness log
```

### Flow E: Model lifecycle (offline)

```
ensure_dataset() -> prepare splits + augmentation (field-like: random-resized-crop, color jitter, blur, noise,
  background replacement/cutout, perspective, JPEG compression) -> benchmark 2-3 backbones -> pick
  -> calibrate (temperature, thresholds) on held-out + field photos -> push model + khetsetu_meta.json to Hub model repo
  -> bump pinned revision in Settings/README preload -> redeploy Space
```

### State Management

```
Per-session (Gradio gr.State, server-side memory keyed by session):
  DiagnosisContext {disease_id, crop, confidence, image_hash}, chat history, selected language
Process-global (read-only after init, swapped atomically):
  classifier, embedder, KnowledgeIndex (replaced as a whole on refresh)
Not stored anywhere: uploaded photos (process in memory, do not log or persist in v1; privacy default)
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users (v1 target) | Single Space, single process (do **not** run multiple uvicorn workers - each would load the model). Gradio queue with `default_concurrency_limit` ~2 and `max_size` to shed load. Everything above is sufficient. |
| 1k-100k users | First bottleneck: CPU classifier latency under concurrency (2 vCPU). Fix: smaller backbone / ONNX or int8 dynamic quantization, then CPU Upgrade (8 vCPU, $0.03/h) or GPU. Second: LLM cost/quotas - add response cache keyed by `(disease_id, lang, normalized_question)`, per-session rate limit. |
| 100k+ users | Split into two Spaces (the contracts layer makes this a `RemoteServices` swap), replicas on paid hardware, move vector store to a managed service, queue ingest. Not a v1 concern. |

### Scaling Priorities

1. **First bottleneck:** classifier inference on 2 vCPU with concurrent users. Mitigate with `torch.inference_mode`, thread cap, input downscale, semaphore, and picking the smallest backbone that meets accuracy (benchmark latency alongside accuracy in the model bake-off).
2. **Second bottleneck:** LLM budget. Free accounts have no inference credits; PRO has $2/month. Budget guard + cache + short answers (max_tokens) from day one.

## Anti-Patterns

### Anti-Pattern 1: Blocking the entire app on dataset + model + index download

**What people do:** `ensure_dataset(); load_model(); build_index(); demo.launch()` at import time.
**Why it's wrong:** 823 MB of irrelevant training data delays the first byte; any failure yields an unhealthy Space with no UI; the first visitor after every 48 h sleep waits minutes.
**Do this instead:** Pattern 2 (serve first, staged bootstrap, readiness banner), `preload_from_hub` for model weights, dataset as background/off in the Space.

### Anti-Pattern 2: In-process scheduler as the system of record for freshness

**What people do:** `APScheduler` inside the Gradio app scrapes daily into a local Chroma folder.
**Why it's wrong:** The Space sleeps, restarts wipe the disk, replicas duplicate work, scraping steals CPU from inference, and a crashed scrape leaves a half-written store.
**Do this instead:** External cron produces immutable snapshots; Space pulls and atomically swaps (Pattern 3 + 6).

### Anti-Pattern 3: Frontend importing backend internals (or torch)

**What people do:** `from backend.vision.classifier import Classifier` in a Gradio callback.
**Why it's wrong:** Defeats the separation requirement, drags heavy deps into the FE package, makes the 2-Space split a rewrite.
**Do this instead:** FE depends on `contracts` only; composition root injects services; CI import-linter rule.

### Anti-Pattern 4: Letting live web results flow into the curated store automatically

**What people do:** "Cache" live-search hits into the vector store so the next query is faster.
**Why it's wrong:** Unvetted pages poison the trusted store, breaks the "curated = trustworthy default" promise and pesticide-safety posture.
**Do this instead:** Keep `origin="live"` ephemeral; log candidate URLs to a review queue; promote to `sources.yaml` by human decision.

### Anti-Pattern 5: Safety framing generated by the LLM

**What people do:** Ask the prompt to "add a safety warning."
**Why it's wrong:** Non-deterministic, can be dropped or hallucinated, and worse in Hindi.
**Do this instead:** Deterministic, reviewed, bilingual footer text appended by `chat/safety.py` whenever the answer or sources contain chemical/pesticide terms (or always for remedy intents). Prompt forbids dosages not present in a cited source; a post-check can strip numeric dosage patterns not found in any source text.

### Anti-Pattern 6: Thresholds and class names hard-coded in app code

**What people do:** `if prob < 0.7:` in the UI; label list typed into a Python file.
**Why it's wrong:** Thresholds are a property of a specific trained+calibrated model; changing the model silently invalidates them.
**Do this instead:** Ship `khetsetu_meta.json` with the model (labels, temperature, thresholds); pin model revision in settings; settings override only for emergencies.

### Anti-Pattern 7: Different embedding models in ingest vs serving

**What people do:** Re-embed with whatever default is installed.
**Why it's wrong:** Silent retrieval garbage.
**Do this instead:** Single `Embedder` class in shared code; manifest check on load (Pattern 3).

### Anti-Pattern 8: Persisting user photos / secrets casually

**What people do:** Log images, put tokens in `gr.State`, commit `.env`.
**Why it's wrong:** Privacy for farmers and token leakage; public Spaces expose source code.
**Do this instead:** Process photos in memory only (v1), secrets as Space Secrets + `SecretStr`, `.env` gitignored, `.env.example` committed.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| HF Hub (model repo) | `snapshot_download` at build (`preload_from_hub`) and/or startup; pin `revision` | Preload only works for **public** repos and writes to the default `~/.cache/huggingface/hub`; do not change `HF_HOME` or preload won't be found. |
| HF Hub (knowledge dataset repo) | `snapshot_download` + head-sha poll; ingest job writes via `upload_folder` | Treat as append-mostly; skip commits when unchanged. `CommitScheduler` is append-only by design - not suitable for replacing a snapshot. |
| HF Hub (training dataset `Project-AgML/plant_village_classification`) | `snapshot_download(repo_type="dataset")` (idempotent via cache) in `ensure_dataset()` | ~823 MB, two parquet shards. Needed only for training/eval. |
| HF Inference Providers (LLM) | `InferenceClient.chat_completion(stream=True)` via `HF_TOKEN` Space secret | Free accounts: no included credits; PRO: $2/month; then pay-as-you-go. Choose a small multilingual instruct model; confirm Hindi quality empirically. Wrap with timeout, retry (idempotent), budget guard. Model ids on providers churn - keep model id in settings. |
| Live search API | Provider Protocol + settings-selected impl | Key as Space Secret; enforce allow-list/ranking; cap fetched pages and tokens. |
| Source websites (ICAR, SAUs, FAO...) | Ingest job only, never from the Space; honor robots.txt, rate limit, cache with ETag | Record license/terms per source; Hindi sources are scarcer - plan translation/aliasing strategy. |
| GitHub Actions | Cron ingest, CI (lint/type/test), optional sync-to-Space | Write-scoped HF token as encrypted secret. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `frontend` -> `backend.contracts` | Typed DTOs + Protocol calls (in-process) | Only allowed import edge; later becomes HTTP via `RemoteServices`. |
| `app.py` -> `backend.services.container` | `build_services(settings)` | Composition root only. |
| `services` -> `vision` / `chat` / `bootstrap` | Direct calls; readiness checked per call | `NotReady` typed exception for the UI. |
| `chat` -> `knowledge` / `search` / `llm` | Constructor-injected Protocols | Easy to fake in tests; orchestration holds no I/O. |
| `bootstrap` -> `vision` / `knowledge` | Loader callbacks; atomic swap for knowledge | Index swap must be a single reference assignment (no partial state). |
| `ingest` -> `knowledge.snapshot` | Shared schema + `Embedder` + manifest writer | The only coupling between producer and consumer; version it (`schema_version`). |
| `training` -> `vision.labels` / `gate` | Shared label map and meta schema | Prevents train/serve skew. |

## Suggested Build Order (dependencies for roadmap)

```
0 Foundation ──> 1 Data+Model track (long pole) ──────────────┐
      │                                                        v
      ├──────> 2 Knowledge track (ingest -> snapshot -> retrieve) ──> 4 Chat orchestration ──> 5 Live fallback
      │                                                        │              │
      └──────> 3 Vision service + gate + FE Diagnose tab <─────┘              v
                                                             6 Bootstrap/ops hardening (readiness, refresher, cron) ──> 7 Quality pass (Hindi, evals, docs)
```

| # | Slice | Depends on | Why this position |
|---|-------|------------|-------------------|
| 0 | **Foundation:** repo skeleton, typed Settings + `.env.example`, `contracts/`, FakeServices, minimal Gradio shell **deployed to a real Space**, CI (ruff, mypy/pyright, pytest, import-linter), `ensure_dataset()` | none | Surfaces account/plan constraint (paid plan for Gradio Space), import-path question, preload behavior, and Space deploy flow *before* any ML work. Cheap and de-risks everything. |
| 1 | **Dataset inspection + training + calibration + publish model** (augmentation, 2-3 backbone bake-off incl. CPU latency, field-photo validation set, non-leaf handling) | 0 (dataset bootstrap) | Longest, riskiest, uncertain (dataset not inspected yet: classes/split/sizes unknown). Start early; everything else can use a stub classifier meanwhile. |
| 2 | **Knowledge track:** `sources.yaml`, ingest pipeline, snapshot schema/manifest, embedder choice (multilingual), retriever (hybrid), eval set | 0 | Independent of model training; parallelizable with 1. Source curation (and Hindi coverage) is content work that benefits from starting early. |
| 3 | **Vision service + gate + FE Diagnose tab** (real model replaces stub) | 1 (or stub), 0 | First user-visible vertical slice delivering the Core Value. |
| 4 | **Chat orchestration:** LLM client, prompts (EN/HI), citations, deterministic safety, DiagnosisContext handoff, FE Chat tab with streaming | 2, 3 (context shape), 0 | Needs a populated store to test meaningfully. |
| 5 | **Live-search fallback** + sufficiency tuning | 4 | Layers onto the working curated path; thresholds need the eval set from 2. |
| 6 | **Operational hardening:** staged `BootstrapManager`/readiness UI, KnowledgeRefresher, cron workflow (GitHub Actions), budget guard/cache, logging | 1-5 | Can start a skeleton in 0, but real behavior is only testable once the artifacts exist. |
| 7 | **Quality pass:** Hindi UX/quality review, field-photo evaluation of the gate, RAG evals, docs, README/Space card, `CLAUDE.md`/`AGENTS.md` | all | Matches "senior-level" requirement; keep docs incremental per phase, not only here. |

**Phases likely to need dedicated deeper research:** 1 (backbone choice, OOD/non-leaf gating technique, augmentation for field photos, CPU latency/quantization), 2 (source licensing and scrape feasibility, Hindi corpus availability, embedding model choice), 4 (Hindi-capable LLM availability/quality on Inference Providers, prompt design). Phases 0, 3, 6 follow standard patterns.

## Open Decisions for the Roadmap / User

1. **Account tier:** Is there a PRO (paid) HF account? Required to create a Gradio Space; also determines Inference Providers credits. If not, alternatives (a Static Space frontend + elsewhere-hosted backend; ZeroGPU free tier only applies to ZeroGPU Spaces) would change the "single Space" constraint.
2. **Dataset-on-startup semantics** (see Flow A): recommended `DatasetMode` enum with the defaults above.
3. **Ingest trigger:** GitHub Actions cron (recommended) vs HF scheduled Job vs in-Space (dev only).
4. **Knowledge snapshot store:** Hub dataset repo (free, versioned, recommended) vs Storage Bucket mounted into the Space (mutable, billed beyond free allowance).
5. **Chat without a diagnosis:** allow general questions (`DiagnosisContext | None`)? Architecture supports it; product decision pending.

## Sources

- Hugging Face Spaces overview (hardware: CPU Basic 2 vCPU/16 GB/50 GB non-persistent disk; Gradio/Docker Spaces require a paid plan to create; secrets/variables exposed as env vars; sleep on free hardware): https://huggingface.co/docs/hub/spaces-overview (fetched 2026-10-23) - MEDIUM-HIGH
- Spaces config reference (`preload_from_hub`, `startup_duration_timeout` default 30m, `python_version` default 3.10, `suggested_storage` ignored because persistent storage no longer available): https://huggingface.co/docs/hub/spaces-config-reference - MEDIUM-HIGH
- Spaces disk usage and storage (ephemeral disk; Storage Buckets as recommended persistence; repos mountable read-only): https://huggingface.co/docs/hub/spaces-storage - MEDIUM-HIGH
- Storage Buckets (mutable, non-versioned, free allowance then per-TB pricing): https://huggingface.co/docs/hub/storage-buckets - MEDIUM-HIGH
- Spaces GPU/hardware page (cpu-basic sleeps after 48 h inactivity; replicas only on paid hardware): https://huggingface.co/docs/hub/spaces-gpus - MEDIUM-HIGH
- Inference Providers pricing (free users: no included credits; PRO $2/month; routed via HF, pay-as-you-go): https://huggingface.co/docs/inference-providers/pricing - MEDIUM-HIGH
- huggingface_hub upload guide (`CommitScheduler` append-only semantics, background thread, `upload_folder`, `run_as_future`): https://huggingface.co/docs/huggingface_hub/guides/upload - MEDIUM-HIGH
- HF Jobs scheduled jobs (cron/`@daily` syntax): https://huggingface.co/docs/hub/jobs-schedule - MEDIUM
- Gradio Spaces guide (`app_file`, `requirements.txt`): https://huggingface.co/docs/hub/spaces-sdks-gradio - MEDIUM-HIGH
- Gradio `mount_gradio_app` / FastAPI lifespan patterns (web search, community examples only; not adopted as primary approach): LOW
- Architecture patterns (composition root, ports/adapters, publish-and-pull artifacts, calibrated OOD gating, hybrid retrieval): author synthesis from established practice; not individually source-verified - MEDIUM-LOW

## Confidence and Verification Notes

- HF platform facts (hardware, sleep, persistence, paid-plan requirement, pricing, preload) come from official HF documentation pages fetched directly on 2026-10-23, and the paid-plan claim was found consistently on two separate pages. The `classify-confidence` seam returns LOW for the generic `webfetch` provider regardless of domain, so these are rated MEDIUM-HIGH on the basis of official-domain + cross-page agreement, not seam tier. Re-verify the plan/credit rules at account-setup time since HF changes them often.
- NOT verified: exact cold-start timings on cpu-basic, whether relative editable installs (`-e ./backend`) resolve during a Gradio-SDK Space build, Hindi quality of models currently served by Inference Providers, and current package versions (the version lookup was unavailable in this environment; STACK research should pin versions).
- The dataset has not been inspected (classes, split, image size unknown); class-to-disease mapping (`domain/diseases.yaml`) and the number of output classes in the gate depend on that.

---
*Architecture research for: plant-disease classifier + multilingual RAG chat on a single HF Space*
*Researched: 2026-10-23*
