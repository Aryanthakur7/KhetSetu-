# khetsetu-backend

Services, configuration and the command line for KhetSetu. It contains no UI code and depends only on `khetsetu-contracts`.

## Install

From the repository root, which installs every workspace package:

```bash
uv sync --locked --all-packages
```

## Command line

```bash
cp .env.example .env
uv run khetsetu config check
```

`khetsetu config check` validates the configuration and prints every setting (secrets as `(set)` or `(unset)`). Exit code 0 means valid, 2 means invalid, with each offending environment variable named on stderr. See [../docs/configuration.md](../docs/configuration.md).

## Data

```bash
uv run khetsetu data download   # make sure the training dataset is on disk (add --verify to re-check sha256)
uv run khetsetu data inspect    # ensure the dataset, then print rows, classes and shards
```

Both reuse an existing copy under `data/plant_village_classification/` without any network. Exit codes: 0 success, 2 invalid configuration, 3 dataset problem. See [../docs/dataset.md](../docs/dataset.md) for how the dataset is pinned, verified and kept off the Space.

## Modules

| Module | Purpose |
| --- | --- |
| `khetsetu_backend.config` | `Settings`, `load_settings` and `SettingsError`: typed settings that fail fast. |
| `khetsetu_backend.logging_setup` | `configure_logging(settings)`: idempotent standard-library logging setup. |
| `khetsetu_backend.cli` | The `khetsetu` command line (`config check`, `data download`, `data inspect`). |
| `khetsetu_backend.data` | Pinned dataset manifest, `ensure_dataset` (download once, then cache hit), `@requires_dataset`; `data.summary` reads the counts (needs the `data` extra). |
| `khetsetu_backend.bootstrap` | `prepare_runtime(settings)`: fetches the dataset locally, does nothing on a Space or in CI. |

## Tests

From the repository root:

```bash
uv run pytest backend/tests -q
```
