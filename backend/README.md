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

## Modules

| Module | Purpose |
| --- | --- |
| `khetsetu_backend.config` | `Settings`, `load_settings` and `SettingsError`: typed settings that fail fast. |
| `khetsetu_backend.logging_setup` | `configure_logging(settings)`: idempotent standard-library logging setup. |
| `khetsetu_backend.cli` | The `khetsetu` command line (`config check`). |

## Tests

From the repository root:

```bash
uv run pytest backend/tests -q
```
