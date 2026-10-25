"""Command line interface: ``khetsetu config check`` and ``khetsetu data ...``.

Exit codes: 0 success, 2 invalid configuration, 3 dataset problem.
"""

from __future__ import annotations

import typer

from khetsetu_backend.config import Settings, SettingsError, load_settings
from khetsetu_backend.data import (
    DatasetError,
    DatasetHandle,
    active_dataset,
    ensure_dataset,
    requires_dataset,
)

app = typer.Typer(name="khetsetu", no_args_is_help=True, add_completion=False)
config_app = typer.Typer(name="config", no_args_is_help=True, add_completion=False)
data_app = typer.Typer(name="data", no_args_is_help=True, add_completion=False)
app.add_typer(config_app, name="config", help="Inspect and validate configuration.")
app.add_typer(data_app, name="data", help="Download and inspect the training dataset.")

EXIT_INVALID_CONFIG = 2
EXIT_DATASET_PROBLEM = 3


def _load_settings_or_exit() -> Settings:
    """Load settings, or print what is wrong and exit with code 2."""
    try:
        return load_settings()
    except SettingsError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=EXIT_INVALID_CONFIG) from None


def _echo_handle(handle: DatasetHandle) -> None:
    """Print the lines shared by ``data inspect`` and ``data download``."""
    typer.echo(f"outcome: {handle.outcome.value}")
    typer.echo(f"revision: {handle.revision}")
    typer.echo(f"path: {handle.root}")


@config_app.command("check")
def check() -> None:
    """Validate configuration from the environment and ``.env``; secrets are never printed."""
    settings = _load_settings_or_exit()
    for env_var, value in settings.redacted_items().items():
        typer.echo(f"{env_var}={value}")
    typer.echo("OK: configuration is valid")


@data_app.command("download")
def download(
    verify: bool = typer.Option(
        False,
        "--verify/--no-verify",
        help="Also re-check sha256 of files already on disk (slow: reads about 860 MB).",
    ),
) -> None:
    """Make sure the dataset is on disk; downloads it only if it is missing or incomplete."""
    settings = _load_settings_or_exit()
    try:
        handle = ensure_dataset(settings, verify_hashes=verify)
    except DatasetError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=EXIT_DATASET_PROBLEM) from None
    _echo_handle(handle)


@data_app.command("inspect")
@requires_dataset
def inspect_dataset() -> None:
    """Ensure the dataset, then print its row, class and shard counts."""
    # Imported here because it needs pyarrow and yaml (the optional `data` extra).
    from khetsetu_backend.data.summary import summarize_dataset  # noqa: PLC0415

    handle = active_dataset()
    try:
        summary = summarize_dataset(handle)
    except DatasetError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=EXIT_DATASET_PROBLEM) from None
    _echo_handle(handle)
    typer.echo(f"rows: {summary.num_rows}")
    typer.echo(f"classes: {summary.num_classes}")
    typer.echo(f"shards: {summary.num_shards}")


if __name__ == "__main__":
    app()
