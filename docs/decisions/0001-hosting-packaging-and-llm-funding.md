# ADR 0001: Hosting, packaging and LLM funding

Status: Accepted (updated 2026-10-25: team chose to stay on ZeroGPU and use the Gemini API for the LLM)
Date: 2026-10-25

An ADR ("architecture decision record") is a short note that says what we decided, why, and what we do if it stops working. This one answers three questions for the team's real Hugging Face account: can it host our Gradio app, how do our `backend/` and `frontend/` folders get installed on the Space, and how will the chatbot's LLM calls be paid for?

**Short version.** Hosting works, but only on a temporary kind of free hardware (ZeroGPU). The normal free CPU Space needs a PRO subscription. The LLM is not funded yet: the account has no Inference credits. So hosting is settled for now, and funding is waiting for a decision from the team (that is why Status says Blocked).

## Context

Two claims from our research (`.planning/research/STACK.md`, critical findings 1 and 3) decided whether the "one Gradio Space" plan could work, and nobody had tried them on our account:

1. Creating a Gradio or Docker Space on compute needs a paid plan (PRO for a personal account). Free accounts may only get ZeroGPU Gradio Spaces.
2. Inference Providers (the paid LLM service) gives free users no credits, so chat could return HTTP 402 ("payment required").

We tested both with `scripts/space_probe.py` (see `docs/hosting.md`). Every line below was copied from a report in `build/space-probe/` (those reports are generated and not committed). Nothing here is assumed.

## Findings

### Account and Space creation

Account type: user (personal account, handle HimanshuGoyal2004)
Paid plan: none (the `is_pro` flag was false; the one organisation on the account, MCP-1st-Birthday, reported no plan)
Space creation (cpu-basic Gradio): BLOCKED (HTTP 402)
Space creation (zero-a10g Gradio): ALLOWED

Details:

- The cpu-basic attempt was refused by Hugging Face with this message: "Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription." So research claim 1 is **confirmed** for this account.
- The zero-a10g attempt worked. The Space `HimanshuGoyal2004/khetsetu-skeleton` was created as **private** (we never passed the public flag). It is still there; we did not delete it.
- Nothing was bought or upgraded. No payment method was added.

### Build and run

Space build and run: RUNNING on zero-a10g after 2 deploys of the sys.path packaging (first deploy RUNTIME_ERROR, second RUNNING)
Hello-world smoke call: OK (an image upload through the public Gradio client returned the fake "Tomato - Late blight" diagnosis and the Demo mode banner; 8.2 to 8.6 seconds per call)

What happened on the way:

- **Deploy 1 stopped with RUNTIME_ERROR.** The app itself started normally (the log shows Gradio listening on port 7860 and the page answering). The platform then stopped it with: "No @spaces.GPU function detected during startup". ZeroGPU hardware refuses any app that has no function marked with `@spaces.GPU`. This is a platform rule, not a bug in our app, but only ZeroGPU has it.
- **Fix (small, with a test).** `app.py` now has `mark_zerogpu_ready()`, which registers one empty function with `@spaces.GPU` when the `spaces` package exists (it only exists on Hugging Face) and does nothing everywhere else. The function is never called, so no GPU time is used. The test is in `tests/test_composition_root.py`.
- **Deploy 2 reached RUNNING** and the smoke call passed.
- The build log shows the platform's base image: Python 3.12.12, `gradio[oauth,mcp]==6.30.0` (matches our lock file), `spaces==0.51.3`, and a `torch<=2.13.0` limit that the platform adds itself. Our locked torch is 2.14.1, which is **newer than that limit**. The hello-world has no torch in it, so nothing broke, but Phase 4 must keep this in mind (see Consequences).

### Packaging

Packaging tried (sys.path fallback): OK (build succeeded, RUNNING, smoke call OK; only third-party libraries are installed and `app.py` adds `contracts/src`, `backend/src` and `frontend/src` to `sys.path`)
Packaging tried (editable requirements): BUILD_ERROR (the build died while installing requirements: "Invalid requirement: './contracts': Expected package name at the start of dependency specifier ... File './contracts' does not exist.")
Packaging decision: sys.path fallback. The editable variant fails on the real Hugging Face build for the same reason the local rehearsal predicted: Hugging Face installs `requirements.txt` from a copy in `/tmp`, so relative folder paths like `./contracts` cannot be found. (The local rehearsal showed a slightly different error message, "Distribution not found", with the same cause.) After the comparison we redeployed the sys.path variant, and the Space is RUNNING with a passing smoke call.

### LLM funding

LLM probe result: BLOCKED (HTTP 402) for google/gemma-4-26B-A4B-it. One tiny request (8 tokens) to the Inference Providers router was refused with "You have no remaining ..." credits. Research claim 2 is **confirmed**. This is a funding gate, not a token-permission problem (a permission problem would be HTTP 403), so we did not retry and did not try the other models: a model change cannot fix a missing balance.
Funding decision: UNRESOLVED. As of today nothing pays for LLM calls. The options, in the order we recommend them:

1. Upgrade the owning namespace to PRO (about 9 USD per month). This is the only option that fixes both problems at once: it includes a small monthly Inference credit (about 2 USD) and unlocks normal free CPU Basic Spaces.
2. Buy Inference credits (pay as you go) on the same account.
3. Bring your own key: Phase 6 builds the LLM behind a provider interface, so a different provider (one that has a free tier) can be plugged in with a `.env` setting, and no chat code changes.
4. Last resort: load a small open model inside the Space. This needs a speed test first and is weak at Hindi.

Whichever option is chosen, the Phase 7 budget limit and per-session rate limits stay required.

## Decision

Hosting decision: Use a private ZeroGPU Gradio Space (`HimanshuGoyal2004/khetsetu-skeleton`) as interim hosting, with the sys.path packaging. It runs the hello-world today at no cost. Move to a normal CPU Basic Space as soon as the namespace has a PRO plan (the app code does not change; only the hardware setting changes). Limits seen or documented: the app needs one `@spaces.GPU` function (done), the platform pins torch to 2.13.0 or older, and research says free accounts get at most two ZeroGPU Spaces (documented, not tested by us).
Fallback: if the ZeroGPU Space stops being allowed or cannot run the real model (Phase 4), the next rung is a Static Space for the page plus an external backend (Hugging Face says Static Spaces are free for everyone). The first action is to ask the team whether to (a) pay for PRO, which makes the first plan work again, or (b) split the app into a Static Space and a backend hosted elsewhere, then re-run plan 01-07's probe steps against the chosen target and update this ADR.

Status was **Blocked** only because the funding question was open; it is now resolved by the update below (Gemini API key). Hosting is resolved for now.

## Update (2026-10-25): team decisions

The team looked at the options above and decided, for this college project:

1. **Hosting: keep the private ZeroGPU Gradio Space.** No PRO upgrade and no Static Space split. The earlier "Fallback" line stays as the plan B if ZeroGPU stops working for the real model in Phase 4.
2. **LLM: use the Google Gemini API with the team's own API key**, instead of Hugging Face Inference Providers. This is option 3 above ("bring your own key"). Hugging Face is still used for the dataset, the model weights and the Space, just not for chat inference. The key goes in the local `.env` (planned name `GEMINI_API_KEY`, to be added to `.env.example` in Phase 6), is never committed, and on the Space it is stored as a Space **secret**, never a Variable. Chat code talks to a provider interface, so swapping providers later is a settings change.

What this does NOT change: the budget limit, per-session rate limits and the "degraded mode" message (for when the API key runs out of quota or the API is down) stay required in Phase 6/7. Free API tiers have request limits, and the free tier's data terms should be re-read before real farmers use the app. The exact Gemini model id will be picked and tested (including Hindi quality) at the start of Phase 6.

## Consequences for later phases

- **Phase 4 (real diagnosis):** may deploy to the interim ZeroGPU Space. Check three things first: (1) the real model must work with the platform's torch limit (2.13.0 or older) or the CPU torch wheel must be allowed to override it; (2) measure cold-start time, since the model has to be downloaded or preloaded; (3) the real model should use the GPU function properly, or keep running on CPU, and the empty marker function in `app.py` should then be replaced by the real one.
- **Phase 6 (chat and LLM):** must not start LLM work until the team picks a funding option above. Build the LLM client behind the provider interface and read the model id and provider from `.env`. Because funding may be missing, the chat must have a clear "degraded mode" message (no LLM available) instead of crashing on HTTP 402.
- **Phase 7 (hardening and docs):** the budget guard and rate limits are required whichever option is chosen. Update `docs/hosting.md` with the final hardware and funding path. Remind the owner to revoke the access token used for this test when it is no longer needed.
- **Phases that touch deployment:** keep using `uv run python -m scripts.space_probe ...` and `build/space/` to deploy; do not upload `.env`, `data/` or planning files.

## Current state of the test Space

- URL: https://huggingface.co/spaces/HimanshuGoyal2004/khetsetu-skeleton (private, so only the owner can open it)
- State when this ADR was written: RUNNING on zero-a10g with the sys.path packaging, `KHETSETU_APP_ENV=space` set as a Space Variable, and no secrets stored on the Space.
- It was left running on purpose. The owner decides whether to delete it.
