"""Command line interface: ``khetsetu config check``."""

from __future__ import annotations

import typer

from khetsetu_backend.config import SettingsError, load_settings

app = typer.Typer(name="khetsetu", no_args_is_help=True, add_completion=False)
config_app = typer.Typer(name="config", no_args_is_help=True, add_completion=False)
app.add_typer(config_app, name="config", help="Inspect and validate configuration.")

EXIT_INVALID_CONFIG = 2


@config_app.command("check")
def check() -> None:
    """Validate configuration from the environment and ``.env``; secrets are never printed."""
    try:
        settings = load_settings()
    except SettingsError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=EXIT_INVALID_CONFIG) from None
    for env_var, value in settings.redacted_items().items():
        typer.echo(f"{env_var}={value}")
    typer.echo("OK: configuration is valid")


if __name__ == "__main__":
    app()
