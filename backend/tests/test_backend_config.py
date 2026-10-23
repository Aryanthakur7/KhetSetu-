"""Tests for ``khetsetu_backend.config`` (FND-01: typed settings that fail fast)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from khetsetu_backend.cli import app
from khetsetu_backend.config import (
    AppEnv,
    DatasetMode,
    LogLevel,
    SettingsError,
    load_settings,
)

runner = CliRunner()


def test_missing_app_env_names_the_variable_and_says_required() -> None:
    """Without KHETSETU_APP_ENV the load fails and names the variable."""
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    text = str(excinfo.value)
    assert "KHETSETU_APP_ENV" in text
    assert "required" in text


def test_invalid_app_env_lists_allowed_values_without_echoing_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown environment name is rejected and the allowed names are listed."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "prod")
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    text = str(excinfo.value)
    assert "KHETSETU_APP_ENV" in text
    for allowed in ("local", "ci", "space"):
        assert allowed in text
    assert "prod" not in text


def test_valid_app_env_loads_with_default_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """KHETSETU_APP_ENV=local loads and the log level defaults to INFO."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    settings = load_settings(env_file=None)
    assert settings.app_env is AppEnv.LOCAL
    assert settings.log_level is LogLevel.INFO


def test_env_file_supplies_value_and_real_environment_overrides_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A .env file is read, and a real environment variable wins over it."""
    env_file = tmp_path / ".env"
    env_file.write_text("KHETSETU_APP_ENV=ci\n", encoding="utf-8")
    assert load_settings(env_file=env_file).app_env is AppEnv.CI

    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    assert load_settings(env_file=env_file).app_env is AppEnv.LOCAL


# --------------------------------------------------------------------------- Task 2

_DEFAULTS = {
    "server_host": None,
    "server_port": None,
    "max_upload_bytes": 10485760,
    "max_image_pixels": 40000000,
    "dataset_repo_id": "Project-AgML/plant_village_classification",
    "dataset_revision": "cb08789a92460034ced0449eac1dba72bb4883da",
    "dataset_mode": None,
    "llm_model": "google/gemma-4-26B-A4B-it",
    "hf_token": None,
    "hf_space_id": None,
}


def _dummy_secret() -> str:
    """Build a token-shaped value at runtime so no secret-looking literal is committed."""
    return "-".join(["dummy", "secret", "value", "0042"])


def test_defaults_when_only_app_env_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every optional setting has its documented default."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    settings = load_settings(env_file=None)
    for name, expected in _DEFAULTS.items():
        assert getattr(settings, name) == expected, name
    assert settings.data_dir == Path("data")


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("KHETSETU_SERVER_PORT", "70000"),
        ("KHETSETU_SERVER_PORT", "0"),
        ("KHETSETU_MAX_UPLOAD_BYTES", "0"),
        ("KHETSETU_MAX_UPLOAD_BYTES", "99999999999"),
        ("KHETSETU_MAX_IMAGE_PIXELS", "-5"),
        ("KHETSETU_DATASET_REPO_ID", "not-a-repo"),
        ("KHETSETU_DATASET_REVISION", "-rf bad"),
        ("KHETSETU_LLM_MODEL", "has space"),
        ("HF_SPACE_ID", "no-slash"),
        ("KHETSETU_LOG_LEVEL", "LOUD"),
    ],
)
def test_invalid_value_names_the_exact_variable(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    """Each rejected setting is reported by its environment variable name."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv(variable, value)
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    assert [problem.env_var for problem in excinfo.value.problems] == [variable]
    if len(value) > 3:  # short values like '0' legitimately occur inside the messages
        assert value not in str(excinfo.value)


def test_several_problems_are_reported_in_one_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two bad variables produce one error naming both."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv("KHETSETU_SERVER_PORT", "70000")
    monkeypatch.setenv("KHETSETU_MAX_UPLOAD_BYTES", "0")
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    text = str(excinfo.value)
    assert "KHETSETU_SERVER_PORT" in text
    assert "KHETSETU_MAX_UPLOAD_BYTES" in text
    assert "2 problem(s)" in text


def test_space_cannot_use_blocking_dataset_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployed Space never downloads the training dataset."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "space")
    monkeypatch.setenv("KHETSETU_DATASET_MODE", "blocking")
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    assert "KHETSETU_DATASET_MODE" in str(excinfo.value)
    assert "never downloads" in str(excinfo.value)


def test_space_may_use_off_dataset_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``off`` is fine on a Space."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "space")
    monkeypatch.setenv("KHETSETU_DATASET_MODE", "off")
    assert load_settings(env_file=None).effective_dataset_mode is DatasetMode.OFF


@pytest.mark.parametrize(
    ("app_env", "explicit", "expected"),
    [
        ("local", None, DatasetMode.BLOCKING),
        ("ci", None, DatasetMode.OFF),
        ("space", None, DatasetMode.OFF),
        ("local", "off", DatasetMode.OFF),
        ("ci", "blocking", DatasetMode.BLOCKING),
    ],
)
def test_effective_dataset_mode(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
    explicit: str | None,
    expected: DatasetMode,
) -> None:
    """The effective dataset mode follows the environment unless set explicitly."""
    monkeypatch.setenv("KHETSETU_APP_ENV", app_env)
    if explicit is not None:
        monkeypatch.setenv("KHETSETU_DATASET_MODE", explicit)
    assert load_settings(env_file=None).effective_dataset_mode is expected


def test_secret_never_appears_in_any_rendering(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HF_TOKEN is absent from repr, str, JSON dump, CLI output and error text."""
    secret = _dummy_secret()
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv("HF_TOKEN", secret)
    settings = load_settings(env_file=None)
    assert settings.hf_token is not None
    assert settings.hf_token.get_secret_value() == secret
    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert secret not in settings.model_dump_json()
    assert secret not in str(settings.model_dump())
    assert settings.redacted_items()["HF_TOKEN"] == "(set)"  # noqa: S105  (display text)

    ok = runner.invoke(app, ["config", "check"])
    assert ok.exit_code == 0
    assert secret not in ok.stdout + ok.stderr
    assert "HF_TOKEN=(set)" in ok.stdout

    monkeypatch.setenv("KHETSETU_SERVER_PORT", "70000")
    bad = runner.invoke(app, ["config", "check"])
    assert bad.exit_code == 2
    assert secret not in bad.stdout + bad.stderr
    with pytest.raises(SettingsError) as excinfo:
        load_settings(env_file=None)
    assert secret not in str(excinfo.value)
    assert secret not in repr(excinfo.value.problems)


def test_space_id_alias_and_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPACE_ID (set by Hugging Face) fills hf_space_id; HF_SPACE_ID wins when both are set."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "space")
    monkeypatch.setenv("SPACE_ID", "owner/from-hf")
    assert load_settings(env_file=None).hf_space_id == "owner/from-hf"
    monkeypatch.setenv("HF_SPACE_ID", "owner/explicit")
    assert load_settings(env_file=None).hf_space_id == "owner/explicit"


def test_empty_string_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """``KHETSETU_SERVER_PORT=`` means not set, not an invalid integer."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv("KHETSETU_SERVER_PORT", "")
    monkeypatch.setenv("HF_TOKEN", "")
    settings = load_settings(env_file=None)
    assert settings.server_port is None
    assert settings.hf_token is None


def test_settings_are_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loaded settings cannot be mutated by accident."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    settings = load_settings(env_file=None)
    with pytest.raises(ValidationError):
        settings.log_level = LogLevel.DEBUG  # type: ignore[misc]
