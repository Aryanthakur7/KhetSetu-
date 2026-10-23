"""Keeps ``.env.example`` and the ``Settings`` model in lockstep (FND-02, T-01-05)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import AliasChoices, SecretStr

from khetsetu_backend.config import AppEnv, Settings, load_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
# An assignment line, active or commented out with a hash: `NAME=value` / `# NAME=value`.
ASSIGNMENT = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=(.*)$")


def expected_env_vars() -> dict[str, bool]:
    """Map each documented env var to whether its setting is a secret."""
    names: dict[str, bool] = {}
    for field_name, field in Settings.model_fields.items():
        alias = field.validation_alias
        if isinstance(alias, str):
            name = alias
        elif isinstance(alias, AliasChoices):
            first = alias.choices[0]
            assert isinstance(first, str)
            name = first
        else:
            name = f"KHETSETU_{field_name.upper()}"
        names[name] = SecretStr in _annotation_args(field.annotation)
    return names


def _annotation_args(annotation: object) -> tuple[object, ...]:
    """Return the annotation and the members of a union annotation."""
    args = getattr(annotation, "__args__", ())
    return (annotation, *args)


def declared() -> dict[str, str]:
    """Parse ``.env.example`` into ``{name: value}`` (commented or active lines)."""
    found: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            found[match.group(1)] = match.group(2).strip()
    return found


def test_env_example_declares_exactly_the_settings() -> None:
    """No setting is missing from the template and no stale name lingers in it."""
    assert set(declared()) == set(expected_env_vars())


def test_secret_settings_are_blank_in_the_template() -> None:
    """A committed template must never carry a secret value."""
    secrets = [name for name, is_secret in expected_env_vars().items() if is_secret]
    assert "HF_TOKEN" in secrets
    values = declared()
    for name in secrets:
        assert values[name] == "", f"{name} must be blank in .env.example"
    assert re.search(r"^HF_TOKEN=$", ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE)


def test_env_example_loads_as_a_valid_configuration() -> None:
    """Copying the template to .env yields a valid configuration."""
    settings = load_settings(env_file=ENV_EXAMPLE)
    assert settings.app_env is AppEnv.LOCAL
    assert settings.hf_token is None


def test_env_example_has_the_do_not_commit_header() -> None:
    """The first line warns against committing secrets."""
    first = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()[0]
    assert first == "# Copy to .env. Never commit .env. Never put real secrets in this file."


@pytest.mark.parametrize("name", ["KHETSETU_APP_ENV"])
def test_required_setting_is_active_not_commented(name: str) -> None:
    """The one required setting is an active line so a copy works unedited."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert re.search(rf"^{name}=\S+$", text, re.MULTILINE)
