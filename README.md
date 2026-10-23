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

<!-- plan 01-06 adds the "run the app" section here -->
<!-- plan 01-06 adds the "dataset" section here -->
<!-- plan 01-06 adds the "quality gates" section here -->
<!-- plan 01-06 adds the "deploy" section here -->

## Repository layout

| Path | Purpose |
| --- | --- |
| `contracts/` | Shared data types (`khetsetu_contracts`). A leaf package: depends on nothing in this repo. |
| `backend/` | Services, configuration and the `khetsetu` command line (`khetsetu_backend`). No UI code. |
| `frontend/` | The Gradio user interface (`khetsetu_frontend`). Depends on `contracts/`, never on `backend/`. |
| `tests/` | Repository-wide tests (git hygiene, workspace structure). Each package also has its own `tests/`. |
| `docs/` | Reference documentation. |
| `.planning/` | Project planning artefacts (roadmap, requirements, phase plans). |

## Configuration

All settings come from environment variables or a `.env` file and are validated at startup. See [docs/configuration.md](docs/configuration.md) for every setting, its default and whether it is required.
