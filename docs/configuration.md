# Configuration reference

All application settings are typed and validated by `khetsetu_backend.config.Settings`. Every entrypoint loads them once at startup. A missing or invalid setting stops startup immediately with a message that names the environment variable.

## Quick start

```bash
cp .env.example .env
uv run khetsetu config check
```

## Settings

| Environment variable | Type | Default | Required | Purpose | Notes |
| --- | --- | --- | --- | --- | --- |
| `KHETSETU_APP_ENV` | `local`, `ci` or `space` | none | **yes** | Where the app runs. | The deployed Space must use `space`; blocking dataset mode is rejected there. |
| `KHETSETU_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR` | `INFO` | no | Logging verbosity. | |
| `KHETSETU_SERVER_HOST` | text | unset | no | Interface the web server binds to. | Unset lets the server choose its own default. |
| `KHETSETU_SERVER_PORT` | integer 1-65535 | unset | no | Port the web server listens on. | Unset lets the server choose its own default. |
| `KHETSETU_MAX_UPLOAD_BYTES` | integer 1-52428800 | `10485760` (10 MiB) | no | Largest accepted upload, in bytes. | |
| `KHETSETU_MAX_IMAGE_PIXELS` | integer 1-200000000 | `40000000` | no | Largest accepted image, as width times height. | Guards against decompression bombs. |
| `KHETSETU_DATA_DIR` | path | `data` | no | Directory holding the downloaded training dataset. | Git-ignored. Relative paths resolve against the current directory. |
| `KHETSETU_DATASET_REPO_ID` | `owner/name` | `Project-AgML/plant_village_classification` | no | Hugging Face dataset repository. | |
| `KHETSETU_DATASET_REVISION` | 40-hex commit sha or ref name | `cb08789a92460034ced0449eac1dba72bb4883da` | no | Pinned dataset revision. | Pin a sha for reproducible training. |
| `KHETSETU_DATASET_MODE` | `blocking` or `off` | unset | no | Whether tools may download the dataset. | When unset: `blocking` for `local`, `off` for `ci` and `space`. A Space rejects `blocking`: the deployed Space never downloads the training dataset. |
| `KHETSETU_LLM_MODEL` | model id, no spaces | `google/gemma-4-26B-A4B-it` | no | Chat model served by Hugging Face Inference Providers. | Model ids change often, so this is a setting, never a constant. |
| `HF_TOKEN` | secret text | unset | no | Hugging Face access token. | **Secret.** Never commit it. On a Space use a Secret, not a Variable. Shown only as `(set)` or `(unset)` everywhere. |
| `HF_SPACE_ID` | `owner/name` | unset | no | This Space's id. | `SPACE_ID`, which Hugging Face sets inside a running Space, is accepted as an alias; `HF_SPACE_ID` wins if both are set. |

`HF_TOKEN` and `HF_SPACE_ID` keep their standard Hugging Face names and carry no `KHETSETU_` prefix. An empty value (`KHETSETU_SERVER_PORT=`) is treated as unset.

## How loading works

1. Values are read from the process environment and from a `.env` file in the **current directory**. Run commands from the repository root.
2. A real environment variable overrides the same name in `.env`.
3. Unknown variables are ignored.
4. The settings object is immutable once loaded.

## Failing fast

If anything is wrong, loading fails at once and reports every problem together, by environment variable name. Rejected values and secrets are never echoed. Example:

```text
Invalid configuration (2 problem(s)):
  - KHETSETU_SERVER_PORT: Input should be less than or equal to 65535
  - KHETSETU_MAX_UPLOAD_BYTES: Input should be greater than 0
See .env.example and docs/configuration.md for every setting.
```

`uv run khetsetu config check` exits with code 0 when the configuration is valid and code 2 when it is not.

## Adding a new setting

1. Add the field to `Settings` in `backend/src/khetsetu_backend/config.py`.
2. Add a commented entry (what it does, its default, when it is required) to `.env.example`. Secrets stay blank.
3. Add a row to the table above.

Two tests fail if you forget: `backend/tests/test_backend_env_example.py` (template matches the model) and `backend/tests/test_backend_docs.py` (this page covers every setting).
