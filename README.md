# KhetSetu

KhetSetu is a plant-disease assistant for farmers. A farmer uploads a photo of a diseased leaf, a fine-tuned Hugging Face image-classification transformer identifies the disease, and the farmer can then chat (in Hindi or English) about that disease and get remedies grounded in a knowledge base built from agricultural sources plus live web search. It deploys as a single Hugging Face Space with a Gradio frontend.

Its core promise: a correct, trustworthy diagnosis from a leaf photo, and an honest "I'm not sure, send a clearer photo" instead of a confident wrong answer.

## Prerequisites

- git
- [uv](https://docs.astral.sh/uv/) 0.11 or newer. uv installs and manages Python 3.12 for you.

## Quickstart

1. Install every package of the workspace from the lockfile:

   ```bash
   uv sync --locked --all-packages
   ```

2. Create your local configuration from the committed template:

   ```bash
   cp .env.example .env
   ```

3. Check that the configuration is valid:

   ```bash
   uv run khetsetu config check
   ```

   A valid setup prints each setting and `OK: configuration is valid`. An invalid one exits with code 2 and names every offending environment variable.

`.env` is git-ignored: never commit it and never paste real secrets into `.env.example`.

## Run the app

```bash
cp .env.example .env        # skip if you already did this in the quickstart
uv run python app.py
```

Open the URL printed in the terminal (usually http://127.0.0.1:7860). Upload a leaf photo and press **Diagnose**. The page shows a **Demo mode** banner: for now the answers come from a fake service, so a mostly green image gets a made-up "Tomato - Late blight" diagnosis, red is "not a leaf", blue is an unsupported crop and a very dark image is "not sure". Real diagnosis arrives in a later phase.

When you run it locally, `app.py` first makes sure the training dataset is on disk (see below). Set `KHETSETU_DATASET_MODE=off` in `.env` to skip that.

## Dataset

Training uses the pinned Hugging Face dataset `Project-AgML/plant_village_classification` (55,448 images, 39 classes). It is downloaded once into `data/` (git-ignored) and an existing copy is reused without any network access. Check it with `uv run khetsetu data inspect`; the details are in [docs/dataset.md](docs/dataset.md).

## Quality gates

```bash
make check     # lint, format check, types, import rules and tests in one go
make secrets   # scan the git history for leaked secrets (needs scripts/install_gitleaks.sh once)
make hooks     # install the git pre-commit hooks (once per clone)
```

`make check` is what the GitHub Actions workflow runs too. New to these tools? Read [docs/engineering-guide.md](docs/engineering-guide.md); the CI details are in [docs/ci.md](docs/ci.md).

## Deploy

The app is meant to run as a single Hugging Face Space. Whether our account can host one, and how the LLM will be paid for, is checked by a small spike instead of being assumed. [docs/hosting.md](docs/hosting.md) is the runbook (build the Space folder, rehearse it locally, then probe the real account), and the decision is recorded in the architecture decision record written when the spike is run.


## Repository layout

| Path | Purpose |
| --- | --- |
| `contracts/` | Shared data types (`khetsetu_contracts`). A leaf package: depends on nothing in this repo. |
| `backend/` | Services, configuration and the `khetsetu` command line (`khetsetu_backend`). No UI code. |
| `frontend/` | The Gradio user interface (`khetsetu_frontend`). Depends on `contracts/`, never on `backend/`. |
| `app.py` | The composition root: builds the services, hands them to the UI and launches Gradio. |
| `scripts/` | Space tooling (`space_bundle.py`, `space_rehearsal.py`, `space_probe.py`) and the gitleaks helpers. |
| `tests/` | Repository-wide tests (git hygiene, workspace structure, the app end to end). Each package also has its own `tests/`. |
| `.github/` | The GitHub Actions workflow that runs the quality gates. |
| `Makefile` | Shortcuts for the quality gates (`make check` and friends). |
| `docs/` | Reference documentation. |
| `.planning/` | Project planning artefacts (roadmap, requirements, phase plans). |

## Configuration

All settings come from environment variables or a `.env` file and are validated at startup. See [docs/configuration.md](docs/configuration.md) for every setting, its default and whether it is required.
