# Hosting runbook: can our Hugging Face account run the Space?

The project assumes it can deploy one Gradio Space on a free-tier account and call an LLM through Hugging Face Inference Providers. Research says both may need a paid plan, and nobody has tried it. This runbook turns the guess into a recorded fact. Everything that does not need the account is already built and tested; the live part is a handful of commands.

## Prerequisites

1. A Hugging Face account (or an organisation) you are allowed to create Spaces in.
2. A **write-capable access token**, created on the Hugging Face token settings page. Prefer a *fine-grained* token restricted to the namespace you will deploy into, with permission to call Inference Providers.
3. Put it only in the untracked `.env` file, never in a command line, a chat message or a commit:

   ```bash
   HF_TOKEN=...your token...
   HF_SPACE_ID=your-namespace/khetsetu
   KHETSETU_APP_ENV=local
   ```

   `HF_TOKEN` is the secret. `HF_SPACE_ID` is the `owner/name` of the Space to create.

Run every command below from the repository root, after `uv sync --locked --all-packages`.

## Step 1: build and rehearse locally (no account needed)

```bash
uv run python -m scripts.space_bundle                      # writes build/space/
uv run python -m scripts.space_rehearsal --json            # installs it in a fresh venv and runs it
```

The bundle contains only `app.py`, the three `src` folders, a generated `README.md` (its YAML header is the Space configuration: `sdk: gradio`, `sdk_version` equal to the locked Gradio version, `python_version: '3.12'`, `app_file: app.py`) and a pinned `requirements.txt`. It refuses to include `.env`, the dataset, weights or planning files. It never contains the 823 MB dataset, and the Space never downloads it.

## Step 2: probe the real account

Each command prints one line of JSON and writes a report to `build/space-probe/`. The token is never printed or stored in a report.

| Command | What it does | Cost |
| --- | --- | --- |
| `uv run python -m scripts.space_probe whoami` | Shows the account name, type, whether it is PRO, and your organisations with their plans. | free |
| `uv run python -m scripts.space_probe create-space --hardware cpu-basic` | Tries to create a **private** Gradio Space on free CPU hardware. Add `--public` only if you want it public. | free if allowed |
| `uv run python -m scripts.space_probe deploy --packaging syspath` | Builds the bundle, sets the Variable `KHETSETU_APP_ENV=space` and uploads the folder. | free |
| `uv run python -m scripts.space_probe wait --timeout 900` | Waits for the Space to be `RUNNING`; on a build or runtime error it saves the last 80 log lines. | free |
| `uv run python -m scripts.space_probe smoke` | Uploads a small image to the running Space and checks the **Demo mode** banner. | free |
| `uv run python -m scripts.space_probe llm-probe` | Sends exactly one 8-token chat request to the model in `KHETSETU_LLM_MODEL`. | a fraction of a cent |

Add `--space-id owner/name` to override `HF_SPACE_ID`. A missing token or Space id stops with exit code 2 and a message naming `HF_TOKEN` or `HF_SPACE_ID`.

## Fallback ladder

Try these in order and stop at the first one that works.

1. **`cpu-basic` Gradio Space** (the plan): `create-space --hardware cpu-basic`.
2. **`zero-a10g` Gradio Space**, if step 1 is blocked: `create-space --hardware zero-a10g`. Free accounts may create these (the number is limited).
3. **Something else** if both are blocked: a Static Space for the page plus an external backend, or other hosting. These are the alternatives already named in `.planning/PROJECT.md`.

How to read an outcome (the `outcome` field in each report):

| Outcome | Meaning | What to do |
| --- | --- | --- |
| `ok` | It worked. | Continue. |
| `unauthorized` (401) | The token is missing, wrong or expired. | Create a new token and update `.env`. |
| `payment_required` (402) or `forbidden` (403) | A plan or billing gate, or the token lacks permission. | Check the token's permissions first; if they are right, this is the plan gate: go down the ladder. |
| `not_found` (404) | The namespace or Space does not exist. | Check `HF_SPACE_ID`. |
| `rate_limited` (429) | Too many requests. | Wait and retry once; the `llm-probe` itself never retries. |
| `error` | Anything else (see `detail`). | Read the message and, for `wait`, the log tail. |

## The two packaging options

The three workspace packages must be importable on the Space. Both options were rehearsed locally with the order Hugging Face uses (`gradio[oauth,mcp]` at the locked version first, then `requirements.txt` from a copy outside the repository).

| Option | Result of the local rehearsal |
| --- | --- |
| `syspath` (default): only third-party libraries are installed and `app.py` adds the three `src` folders to `sys.path` | **Passed.** Fresh Python 3.12 venv, `uv pip check` found no conflicts, no `khetsetu_*` package was installed, `python app.py` with `KHETSETU_APP_ENV=space` answered a real upload through the Gradio client (a fake "Tomato - Late blight" result) and the readiness endpoint showed **Demo mode**. No dataset folder appeared. About 11 seconds from launch to page. |
| `editable`: `requirements.txt` also lists `./contracts`, `./backend`, `./frontend` | **Failed** at "install requirements": the installer reported `Distribution not found` for `.../contracts`, because the relative path does not resolve when the file is installed from outside the bundle. This matches the expectation. |

The live deploy in plan 01-07 confirms the same behaviour against the real Space build logs.

## Dependency audit

`pip-audit` was run once over the package set the rehearsal installed (including the `oauth` and `mcp` extras). The only finding is **Pillow 12.3.0** (37 advisories, all fixed in Pillow 13.0.0). Gradio 6.30.0 requires `pillow<13`, so it cannot be upgraded until Gradio allows it. This is the same known issue that keeps `make audit` red. Revisit it when the Gradio pin moves; the images the app accepts are size-checked before decoding.

## Secrets and Variables

On a Space, **Secrets** are private and **Variables** are visible to anyone who can see the Space settings. A token always goes in a Secret. Nothing in this phase puts a token on the Space at all: the deploy sets one Variable, `KHETSETU_APP_ENV=space`, and the demo needs nothing else. Later phases that call the LLM from the Space will add `HF_TOKEN` as a Secret.

## Observed results (2026-10-25)

The commands above were run once against the team's real account. The full write-up is in [ADR 0001](decisions/0001-hosting-packaging-and-llm-funding.md); the short version:

| Question | What happened |
| --- | --- |
| Free CPU Basic Gradio Space | Refused with HTTP 402: Gradio Spaces on free cpu-basic need a PRO subscription. Static Spaces are free. |
| ZeroGPU Gradio Space | Allowed (private). It needs one function marked `@spaces.GPU`, which `app.py` now registers through `mark_zerogpu_ready()`. Then RUNNING, and the smoke call returned the fake diagnosis and the Demo mode banner. |
| `sys.path` packaging | Works on the real build. |
| Editable packaging | Fails on the real build (`./contracts` is not a valid requirement when the file is read from `/tmp`). |
| LLM call | HTTP 402: the account has no Inference credits yet. Funding is an open decision. |

If you re-run the probe after upgrading the plan, update the ADR with the new results.

## Where the result is recorded

The outcome (what the account allowed, which rung of the ladder worked, how the LLM will be funded) is written down in `docs/decisions/0001-hosting-packaging-and-llm-funding.md`.
