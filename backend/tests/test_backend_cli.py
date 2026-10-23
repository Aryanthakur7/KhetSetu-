"""Tests for the ``khetsetu`` command line interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from khetsetu_backend.cli import app

if TYPE_CHECKING:
    import pytest

runner = CliRunner()


def test_config_check_valid_prints_setting_and_exits_zero(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid configuration prints KHETSETU_APP_ENV=local and exits 0."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 0
    assert "KHETSETU_APP_ENV=local" in result.stdout
    assert "OK: configuration is valid" in result.stdout


def test_config_check_missing_exits_two_naming_variable(isolated_cwd: Path) -> None:
    """A missing setting exits 2 with the variable name on stderr."""
    result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 2
    assert "KHETSETU_APP_ENV" in result.stderr


def test_config_check_invalid_exits_two_naming_variable(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid setting exits 2 with the variable name on stderr."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "prod")
    result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 2
    assert "KHETSETU_APP_ENV" in result.stderr


def test_console_script_exits_two_for_missing_setting(isolated_cwd: Path) -> None:
    """The installed ``khetsetu`` console script is wired and fails fast."""
    script = Path(sys.executable).parent / "khetsetu"
    assert script.exists(), "console script not installed: run `uv sync --all-packages`"
    completed = subprocess.run(  # noqa: S603  (fixed local executable, no shell, no user input)
        [str(script), "config", "check"],
        cwd=isolated_cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 2
    assert "KHETSETU_APP_ENV" in completed.stderr
