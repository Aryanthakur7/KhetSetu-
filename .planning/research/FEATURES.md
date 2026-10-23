# Feature Research

**Domain:** Plant-disease image diagnosis + multilingual (Hindi/English) RAG advisory chat for farmers
**Researched:** 2026-10-23
**Confidence:** MEDIUM (competitor feature sets from web sources and training knowledge, not hands-on testing; product scope constraints from PROJECT.md and the local dataset README are HIGH)

## Context Findings That Shape Everything Below

- **Dataset reality (HIGH, read from local `data/plant_village_classification/README.md`):** 39 classes, 55,448 images, a single `train` split (no held-out test split, so we must create our own). Class 4 is `Background_without_leaves`, which gives a free "not a leaf" reject class. Crops are mostly temperate or horticultural (apple, blueberry, cherry, grape, peach, strawberry, squash) plus tomato, potato, corn, pepper, soybean, orange. **Rice, wheat, cotton, sugarcane, and mustard, the staples for Hindi-belt farmers, are absent.** Scope messaging has to be honest about this, because it is a product-level limit and not just a model-quality one.
- **Lab-to-field gap (MEDIUM-HIGH, [arXiv 2511.18989](https://arxiv.org/abs/2511.18989), [J. Econ. Entomology 2026](https://reference-global.com/article/10.2478/jee-2026-0043)):** PlantVillage-trained models show about 99% internal accuracy but drop to roughly 67% accuracy and 58% F1 on external field data in one study. ViTs generalise better than CNNs. This supports making the confidence gate and honest-uncertainty UX the core value, not polish.
- **Competitor landscape:**
  - **Plantix** ([plantix.net](https://plantix.net/en), [FreshFruitPortal](https://www.freshfruitportal.com/news/2019/12/12/crop-doctor-app-plantix-fills-farmer-advisory-gap-and-democratizes-knowledge/)): photo diagnosis of diseases, pests and nutrient deficiencies; treatment suggestions (active ingredients, chemical and biological); community Q&A with experts or other farmers; crop library; many interface languages; freemium with commissions from input sellers.
  - **Nuru / PlantVillage** ([IITA](https://iita.org/news-item/african-farmers-get-new-help-against-cassava-diseases-nuru-their-artificially-intelligent-assistant/)): on-device offline diagnosis; severity or percent-affected estimates for field scouting; offline advice; optional cloud upload for expert diagnosis; data sync to dashboards.
  - **Kisan e-Mitra** ([Wadhwani AI](https://www.wadhwaniai.org/empowering-millions-of-indian-farmers-with-instant-ai-chatbot-support/), [Vikaspedia](https://en.vikaspedia.in/agriculture/ict-applications-in-agriculture/kisan-emitra)): government voice and text chatbot in many Indian languages. It covers scheme and grievance queries (PM-KISAN, PMFBY, KCC), not agronomy.
  - **Farmer.CHAT** ([Digital Green](https://eng.ruralvoice.in/digital-green-ai-farming-assistant-crosses-10-lakh-users)): GPT-based assistant limited to trusted local agricultural content. Accepts voice, photo and text, which helps users with low literacy.
  - **Kisan Suvidha** (training knowledge, LOW; not independently verified here): a government app for weather, market prices, dealers, plant-protection advice and input information.
- **Takeaway:** The market splits into (a) image diagnosis apps (Plantix, Nuru), (b) conversational advisory bots (Farmer.CHAT, Kisan e-Mitra), and (c) information utility apps (Kisan Suvidha). KhetSetu's niche is the join of (a) and (b): chat that is grounded in the specific diagnosis. It should not drift into (c).

## Feature Landscape

### Table Stakes (Users Expect These)

Missing these means the product feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Photo upload (camera capture and gallery) returning disease name | Every competitor does this; it is the core promise | LOW | Gradio `gr.Image(sources=["upload","webcam"])` gives mobile camera. Resize and compress client-side or server-side for low bandwidth. |
| Top prediction plus confidence, shown in plain language | Users need to know how sure the app is; Plantix and Nuru both show a result with certainty cues | LOW | Show "High / Medium / Low confidence" labels, not only a raw percentage. A farmer does not read "0.83". |
| Top-3 alternative predictions | Plantix-style apps often show alternatives; guards against a wrong top-1 | LOW | Cheap, since softmax already exists. Hide below a minimum probability. |
| "Healthy" class handled explicitly | The dataset has `*___healthy` classes; telling a healthy leaf it is diseased is a trust-killer | LOW | Already in the label set. Needs a distinct UI message ("looks healthy"). |
| Confidence gate / "send a clearer photo" refusal | PROJECT.md core value. Needed because lab-trained models fail on field photos | MEDIUM | Combine max-softmax threshold, the `Background_without_leaves` class and possibly entropy. Calibrate (temperature scaling) on a held-out set. Add photo-quality tips ("single leaf, daylight, fill the frame"). |
| Short disease summary (symptoms, cause, spread) after diagnosis | Users expect an explanation, not only a label | LOW-MEDIUM | Generated or retrieved from the RAG store, not hard-coded. Pre-seed a per-class knowledge card for all 38 disease/healthy classes. |
| Remedy and treatment guidance (cultural, biological, chemical) | The main reason to use these apps is "what do I do now" | MEDIUM | Must come from RAG with citations. Prefer cultural and organic options first, then chemical by active ingredient. |
| Source citations on every remedy answer | PROJECT.md safety requirement; farmers act on this advice | MEDIUM | Return source title and URL per claim chunk. Refuse to answer treatment questions when no source is retrieved. |
| Pesticide safety framing | Wrong advice means crop loss or human harm | LOW-MEDIUM | Static, always-shown disclaimer. Instruct the LLM not to invent dosages. Say "check the product label and consult your local KVK / agriculture officer". |
| Hindi and English UI and chat | Target users; Plantix and Kisan e-Mitra are multilingual | MEDIUM | UI strings in both languages, a language toggle, and an LLM prompt that answers in the user's language. Disease names should show both scientific and Hindi common names. |
| Chat that is aware of the diagnosed disease | The product's stated purpose | MEDIUM | Inject diagnosis (label, confidence) into the chat context so the farmer does not retype it. Retrieval filter or boost by disease and crop. |
| Free-form follow-up questions in chat | Farmer.CHAT and similar bots work this way | MEDIUM | Standard RAG chat with conversation history; keep history short to save tokens. |
| "I don't know" / out-of-scope handling | Hallucinated agronomy is dangerous. Farmer.CHAT restricts itself to trusted content | MEDIUM | Retrieval score threshold, then the live-web fallback, then an explicit "I could not find a reliable answer". |
| Mobile-friendly, low-bandwidth UI | Users are mobile-first and low bandwidth | LOW-MEDIUM | Compress uploads, keep the page light, avoid heavy custom JS, show a loading state for slow HF Space cold starts. |
| Clear supported-crops list | The model only knows about 14 crops. Without a list, users will upload rice and get nonsense | LOW | Show the crop list on the landing view. Reject unsupported crops (via the gate) with a clear message instead of a wrong guess. |
| Graceful errors (HF API down, rate limit, Space asleep) | Free tier HF Inference and Spaces are flaky | LOW-MEDIUM | Timeouts, retries, and a user-visible fallback message. The diagnosis should still work if the LLM is down. |

### Differentiators (Competitive Advantage)

These align with the Core Value (a trustworthy diagnosis plus an honest "not sure").

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Calibrated uncertainty UX ("not sure, here is why, here is how to retake") | Most apps show a confident label. Honest refusal is KhetSetu's stated core value | MEDIUM | Calibration (temperature scaling), an out-of-distribution score, and actionable retake tips. Measure it: report selective-accuracy / coverage curves in the eval. |
| Diagnosis-grounded, cited RAG chat in Hindi | Plantix has community Q&A. Farmer.CHAT has no image diagnosis. The join of image diagnosis and cited chat in Hindi is the niche | HIGH | Cross-lingual retrieval (Hindi query against mostly English sources) is the hard part. Use a multilingual embedding model or translate the query. |
| Curated scheduled scrape (ICAR, SAUs, FAO) with live-search fallback | Trust by default, coverage as a fallback; most chatbots use one or the other | HIGH | Needs a scraper, chunker, embedder, vector store and schedule. Keep a source allowlist. Mark live-search answers as "from the web, lower trust". |
| Source-tier labelling in answers ("ICAR guidance" vs "web result") | Lets the farmer or an extension officer judge the advice | LOW-MEDIUM | Store a trust tier in chunk metadata, then render it in the citation. |
| Field-photo augmentation plus a field-style evaluation set | Directly attacks the lab-to-field gap, the dominant failure mode of PlantVillage models | MEDIUM-HIGH | Heavy augmentation (random crop, background replacement, colour jitter, blur, occlusion). Hold out a small hand-collected or PlantDoc-style field set for honest evaluation, since the dataset has no test split. |
| Benchmark of 2-3 transformer candidates (ViT / Swin / ConvNeXt) with chosen-model rationale | Matches the stated plan; ViTs are reported to generalise better under shift | MEDIUM | Choose by field-set accuracy and selective accuracy, not by PlantVillage accuracy. |
| Smart retake guidance driven by the gate reason | "Image too blurry / no leaf detected / multiple leaves" is more useful than a generic error | MEDIUM | Needs a few lightweight heuristics (blur variance, the background class) as well as the model score. |
| Two-lingual disease names and glossary | Farmers know diseases by local names (e.g. "jhulsa", "blight") | MEDIUM | Needs a curated mapping table of 38 classes. Partly manual work. |
| Evidence-limited pesticide answers ("active ingredient and where to verify", never invented doses) | Safety posture most chatbots lack | MEDIUM | Prompt guard plus a post-check: any dosage figure in the answer must appear in a retrieved chunk. |
| Suggested follow-up question chips ("How do I prevent it?", "Organic options?", "Is it spreading?") | Reduces typing for low-literacy and low-connectivity users | LOW | Static per-disease chips in Hindi and English. High value for the effort. |
| Transparent "how we decided" panel (top-3 plus confidence plus gate decision) | Builds trust, and helps debugging in the demo | LOW | Collapsed by default. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Always return a diagnosis, even at low confidence | Feels more helpful; competitors always answer | Directly contradicts the core value; confident wrong answers lead to wrong sprays | Refuse below the threshold and give retake tips. Optionally show "possible, unconfirmed" top-3 only above a floor. |
| Specific pesticide dosage and brand recommendations generated by the LLM | Farmers ask "how much do I spray?" | Hallucinated dosages cause crop loss or poisoning, and the legal and regulatory risk is real | Cite the label or source; give active ingredient and class only when a retrieved source states it; direct to the local KVK / agriculture officer. |
| Object detection / DETR / multi-leaf localisation | Looks advanced | No bounding boxes in the data (out of scope per PROJECT.md) | Single-leaf classification with clear photo guidance. |
| Severity or percent-infected estimation | Nuru offers it for scouting | Needs segmentation or severity-labelled data that does not exist here | Defer to v2 with a proper dataset. |
| Community forum / farmer-to-farmer or expert Q&A | Plantix's popular feature | Needs moderation, accounts, a database and an expert workforce. Wrong crowd advice also contradicts the "cited and safe" stance | Cited RAG answers only. Point to Kisan Call Centre (1551) or the local KVK for human help. |
| Weather, mandi prices, scheme information, soil advice | Kisan Suvidha and Kisan e-Mitra cover these; "one app for everything" appeal | Scope explosion; needs separate data feeds; dilutes the core value | Stay focused on disease. Link out to official apps. |
| Accounts, login, farm profiles, history sync | Standard in apps | Adds a database, privacy obligations and friction for low-literacy users, with little value for a v1 Space | Session-local state only. No PII is stored. |
| More Indian languages (Marathi, Telugu, Punjabi, ...) in v1 | Reach | Each language needs sources, evaluation and translation quality checks (out of scope per PROJECT.md) | Architect for a language setting. Ship Hindi and English only. |
| Voice input and output (full voice agent) in v1 | Great for low literacy; Farmer.CHAT and Kisan e-Mitra have it | Adds ASR/TTS, Hindi accuracy risk, latency and HF compute limits. It is a large addition for a first release | Defer to v1.x. Gradio's microphone input plus a Whisper API call is a small later addition. Do not build it now. |
| Auto-learning from farmer-uploaded photos | "Model improves itself" | Needs consent, labelling, a data pipeline and a quality filter (out of scope per PROJECT.md); unlabelled feedback can poison the model | Keep as v2, with an explicit data-collection and labelling pipeline. |
| Native mobile app / offline on-device model (Nuru-style) | Rural connectivity | Out of scope (Gradio web first). Distilling to on-device is a separate project | Keep the model small. Make uploads cheap and the web UI light. Revisit ONNX or TFLite export later. |
| In-app pesticide marketplace / affiliate links | Plantix's revenue source | Conflict of interest; it undermines trust in treatment advice | None. Provide neutral information only. |
| Streaming "agent" with autonomous multi-tool browsing | Trendy | Unbounded latency and cost, unpredictable sources, harder to cite | Fixed pipeline: curated retrieve, then fall back to a single search, then answer with citations. |

## Feature Dependencies

```
Dataset auto-download (idempotent)
    └──requires──> Model fine-tuning + benchmark (needs data + our own held-out split)
                       └──requires──> Calibration / confidence gate
                                          └──requires──> Diagnosis UI (label, confidence, top-3, retake tips)
                                                             └──requires──> Diagnosis-aware chat

Field-style augmentation ──enhances──> Model fine-tuning
Field-style eval set ──enhances──> Confidence gate (threshold tuning, selective accuracy)
Background_without_leaves class ──enhances──> Confidence gate (non-leaf reject)

Typed settings + .env  ──requires-by──> everything (HF token, model IDs, thresholds)

Source scrape + chunk + embed + vector store
    └──requires──> Retrieval (RAG)
                       ├──requires──> Cited answers
                       │                  └──requires──> Pesticide safety framing / dosage guard
                       └──enhances──> Live-web fallback (triggered by low retrieval score)

Multilingual embeddings / translation ──requires──> Hindi chat quality
Per-class knowledge card (38 classes) ──enhances──> Disease summary, Hindi glossary, follow-up chips

Voice I/O ──conflicts (for v1 scope)──> Single free-tier Space compute budget
Community forum ──conflicts──> Cited-and-safe advice stance
```

### Dependency Notes

- **Chat requires the diagnosis pipeline:** the chat injects the disease label and confidence, so the classifier and gate come first. Chat can be built against a stubbed diagnosis, but it cannot ship without one.
- **The confidence gate requires a held-out evaluation set:** the dataset ships only a `train` split. We must carve out a validation and test split (ideally grouped to avoid near-duplicate leaves leaking across splits) and ideally a small field-style set. Without this, any threshold is fiction.
- **Cited answers require retrieval metadata:** each chunk must carry source URL, title and trust tier at scrape time. Retrofitting this later means re-scraping.
- **The dosage guard requires retrieved chunks:** it is a post-check against the retrieved text, so it cannot exist without RAG.
- **Hindi chat quality requires a cross-lingual retrieval decision:** sources are mostly English, so either use a multilingual embedder or translate queries. This choice affects the whole RAG design and is the main phase research risk.
- **Live-web fallback enhances, and must not replace, curated retrieval:** it triggers only on a low retrieval score, and its answers carry a lower trust label.
- **Scheduled scraping is independent of the model track:** the ML track (data, training, gate) and the knowledge track (scrape, embed, retrieve) can run in parallel until the chat integration.

## MVP Definition

### Launch With (v1)

Minimum to validate "a farmer gets a trustworthy diagnosis and an honest refusal."

- [ ] Idempotent dataset download and our own train/val/test split — everything else depends on it
- [ ] Fine-tuned transformer classifier (benchmark 2-3 candidates) with field-style augmentation — core capability
- [ ] Calibrated confidence gate plus non-leaf rejection plus retake tips — the stated core value
- [ ] Photo upload UI showing label, confidence in plain words, top-3, healthy handling, supported-crops list — table stakes
- [ ] Per-class disease summary — table stakes, low cost with knowledge cards
- [ ] Diagnosis-aware chat in Hindi and English via HF Inference API — core feature
- [ ] RAG over a small curated source set with citations — trust requirement
- [ ] Pesticide safety framing and "no source, no dosage" guard — safety constraint
- [ ] Live-web fallback with a lower-trust label — coverage; can be a thin first version
- [ ] Typed config, `.env.example`, tests, lint, docs, single-Space deploy — explicit project requirements

### Add After Validation (v1.x)

- [ ] Follow-up question chips — add once the chat works and real questions are observed
- [ ] Hindi common-name glossary — add once knowledge cards exist
- [ ] Voice input (mic plus ASR) — add if users struggle with typing
- [ ] Scheduled-scrape expansion to more sources — add when answer-coverage gaps are logged
- [ ] Source-tier badges in citations — add after the first user feedback on trust
- [ ] Model-swap to a better backbone — add if the field set shows a clear winner

### Future Consideration (v2+)

- [ ] Retraining on collected farmer photos — needs a consent and labelling pipeline
- [ ] Rice, wheat, cotton and other staple crops — needs new datasets (the current one does not cover them); this is likely the largest real-world usefulness gap
- [ ] Additional Indian languages — needs sources and evaluation per language
- [ ] Offline or on-device model / mobile app — separate project
- [ ] Severity estimation, multi-leaf localisation — need new data
- [ ] Two-Space split — layout already allows it

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Dataset download + own split | HIGH | LOW | P1 |
| Fine-tuned classifier + augmentation | HIGH | MEDIUM-HIGH | P1 |
| Confidence gate + non-leaf rejection | HIGH | MEDIUM | P1 |
| Upload UI with plain-language confidence and top-3 | HIGH | LOW | P1 |
| Supported-crops list | HIGH | LOW | P1 |
| Per-class disease summary (knowledge cards) | HIGH | MEDIUM | P1 |
| Diagnosis-aware chat (Hindi + English) | HIGH | MEDIUM | P1 |
| RAG with citations | HIGH | HIGH | P1 |
| Pesticide safety framing + dosage guard | HIGH | MEDIUM | P1 |
| Graceful error and cold-start handling | MEDIUM | LOW-MEDIUM | P1 |
| Live-web fallback | MEDIUM | MEDIUM | P1 (thin) |
| Scheduled scraping | MEDIUM | MEDIUM-HIGH | P1 (small source set) / P2 (expansion) |
| Retake guidance by gate reason | MEDIUM | MEDIUM | P2 |
| Follow-up chips | MEDIUM | LOW | P2 |
| Hindi glossary | MEDIUM | MEDIUM | P2 |
| Source-tier badges | MEDIUM | LOW | P2 |
| "How we decided" panel | LOW | LOW | P2 |
| Voice I/O | HIGH (long term) | HIGH | P3 |
| Additional crops (rice, wheat) | HIGH (long term) | HIGH | P3 (needs data) |
| Community forum, marketplace, accounts | LOW | HIGH | Do not build |

**Priority key:** P1 = must have for launch, P2 = should have when possible, P3 = future consideration.

## Competitor Feature Analysis

| Feature | Plantix | Nuru (PlantVillage) | Farmer.CHAT / Kisan e-Mitra | Our Approach |
|---------|---------|---------------------|-----------------------------|--------------|
| Photo diagnosis | Yes, 30+ crops, 780+ damages claimed | Yes, cassava-focused, on-device | No (Farmer.CHAT accepts photos for chat; e-Mitra does not diagnose) | Yes, 14 crops / 38 classes, cloud-hosted |
| Honest uncertainty / refusal | Not a headline feature | Limited | N/A | **Core value: calibrated gate plus retake tips** |
| Treatment advice | Active ingredients, chemical and biological | Control advice offline | Grounded in trusted content (Farmer.CHAT); scheme answers only (e-Mitra) | Cited RAG, with a no-invented-dosage guard |
| Conversational follow-up | Limited (community Q&A) | Peer chat | Yes, core | Yes, diagnosis-aware |
| Languages | Many | Few (regional) | Many Indian languages | Hindi and English only in v1 |
| Voice | Not core | No | Yes | Deferred to v1.x |
| Offline | Partial caching | Yes, core | No | No (web) |
| Community / experts | Yes | Optional expert upload | No | No; point to Kisan Call Centre / KVK |
| Monetisation | Input-seller commissions | Free / grant-funded | Government / donor | None; neutral information |

## Sources

- Plantix product site: https://plantix.net/en (MEDIUM, vendor claims)
- Plantix feature coverage: https://www.freshfruitportal.com/news/2019/12/12/crop-doctor-app-plantix-fills-farmer-advisory-gap-and-democratizes-knowledge/ (MEDIUM, 2019 article; user counts and language counts vary by source)
- Nuru / PlantVillage: https://iita.org/news-item/african-farmers-get-new-help-against-cassava-diseases-nuru-their-artificially-intelligent-assistant/ and https://www.psu.edu/news/research/story/grant-will-support-expanded-use-artificial-intelligence-crop-health (MEDIUM; accuracy claim is self-reported)
- Kisan e-Mitra: https://www.wadhwaniai.org/empowering-millions-of-indian-farmers-with-instant-ai-chatbot-support/ and https://en.vikaspedia.in/agriculture/ict-applications-in-agriculture/kisan-emitra (MEDIUM; language count varies by source)
- Farmer.CHAT: https://eng.ruralvoice.in/digital-green-ai-farming-assistant-crosses-10-lakh-users and https://gooey.ai/farmer-chat (MEDIUM)
- Lab-to-field gap: https://arxiv.org/abs/2511.18989 and https://reference-global.com/article/10.2478/jee-2026-0043 (MEDIUM-HIGH; the second reports about 99.6% internal vs about 66.8% external accuracy for one EfficientNet-B2 vineyard study, so treat it as indicative rather than universal)
- Local dataset README: `data/plant_village_classification/README.md` (HIGH; 39 classes, 55,448 images, `train` split only)
- Kisan Suvidha: training knowledge only, not verified in this research (LOW)

---
*Feature research for: plant-disease diagnosis + multilingual RAG advisory (KhetSetu)*
*Researched: 2026-10-23*
