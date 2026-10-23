"""Keeps the onboarding documentation true to the code (FND-02)."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from khetsetu_backend.cli import app
from khetsetu_backend.config import Settings, env_var_name

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()

# `khetsetu config check`, optionally preceded by `uv run`, as written in README code.
COMMAND = re.compile(r"\bkhetsetu((?: [a-z][a-z-]*)+)")


def test_configuration_reference_covers_every_setting() -> None:
    """Each setting's environment variable appears in docs/configuration.md."""
    text = (REPO_ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    missing = [
        env_var_name(name, field)
        for name, field in Settings.model_fields.items()
        if f"`{env_var_name(name, field)}`" not in text
    ]
    assert not missing, f"undocumented settings: {missing}"


def test_readme_quickstart_commands_exist_in_the_cli() -> None:
    """Every `khetsetu <command>` in the README quickstart is a real CLI command."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    code_blocks = re.findall(r"```bash\n(.*?)```", readme, re.DOTALL)
    commands = [m.group(1).split() for block in code_blocks for m in COMMAND.finditer(block)]
    assert ["config", "check"] in commands
    for words in commands:
        for depth, word in enumerate(words):
            result = runner.invoke(app, [*words[:depth], "--help"])
            assert result.exit_code == 0, words
            assert word in result.stdout, f"`khetsetu {' '.join(words)}` is not a CLI command"


def test_readme_links_the_configuration_reference() -> None:
    """The README points new developers at the configuration reference."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/configuration.md" in readme
