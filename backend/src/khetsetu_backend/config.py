"""Typed, validated application settings (FND-01).

Every entrypoint loads settings once at startup with :func:`load_settings` and passes the
object down; there is deliberately no module-level global. A missing or invalid setting
raises :class:`SettingsError`, whose message names the *environment variable* (not the Python
field) so an operator can fix it without reading code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

ENV_PREFIX = "KHETSETU_"


class AppEnv(StrEnum):
    """Where the application is running."""

    LOCAL = "local"
    CI = "ci"
    SPACE = "space"


class LogLevel(StrEnum):
    """Standard logging levels accepted by ``KHETSETU_LOG_LEVEL``."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DatasetMode(StrEnum):
    """Whether starting a tool may download the training dataset."""

    BLOCKING = "blocking"
    OFF = "off"


# owner/name on the Hugging Face Hub.
_REPO_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
# A 40-character commit sha or a simple branch/tag name; never starts with a dash.
_REVISION_PATTERN = r"^(?:[0-9a-f]{40}|[A-Za-z0-9][A-Za-z0-9._/-]*)$"


class Settings(BaseSettings):
    """All application settings, read from the environment and an optional ``.env`` file."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        frozen=True,
        case_sensitive=False,
    )

    # Declaration order matters: validators read earlier fields through ``info.data`` and
    # ``khetsetu config check`` prints settings in this order.
    app_env: AppEnv
    log_level: LogLevel = LogLevel.INFO
    server_host: str | None = None
    server_port: Annotated[int, Field(ge=1, le=65535)] | None = None
    max_upload_bytes: Annotated[int, Field(gt=0, le=52_428_800)] = 10_485_760
    max_image_pixels: Annotated[int, Field(gt=0, le=200_000_000)] = 40_000_000
    data_dir: Path = Path("data")
    dataset_repo_id: str = Field(
        default="Project-AgML/plant_village_classification", pattern=_REPO_ID_PATTERN
    )
    dataset_revision: str = Field(
        default="cb08789a92460034ced0449eac1dba72bb4883da", pattern=_REVISION_PATTERN
    )
    dataset_mode: DatasetMode | None = None
    llm_model: str = Field(default="google/gemma-4-26B-A4B-it", pattern=r"^\S+$")
    hf_token: SecretStr | None = Field(default=None, validation_alias="HF_TOKEN")
    # HF sets SPACE_ID inside a running Space; HF_SPACE_ID wins when both are present.
    hf_space_id: str | None = Field(  # type: ignore[pydantic-alias]
        default=None,
        validation_alias=AliasChoices("HF_SPACE_ID", "SPACE_ID"),
        pattern=_REPO_ID_PATTERN,
    )

    @field_validator("dataset_mode")
    @classmethod
    def _space_never_downloads_dataset(
        cls, value: DatasetMode | None, info: ValidationInfo
    ) -> DatasetMode | None:
        """Reject blocking dataset mode on a deployed Space (the Space is inference-only)."""
        if value is DatasetMode.BLOCKING and info.data.get("app_env") is AppEnv.SPACE:
            msg = (
                "not allowed when KHETSETU_APP_ENV is 'space': the deployed Space never "
                "downloads the training dataset; use 'off' or leave it unset"
            )
            raise ValueError(msg)
        return value

    @property
    def effective_dataset_mode(self) -> DatasetMode:
        """Return the explicit dataset mode, else blocking locally and off elsewhere."""
        if self.dataset_mode is not None:
            return self.dataset_mode
        return DatasetMode.BLOCKING if self.app_env is AppEnv.LOCAL else DatasetMode.OFF

    def redacted_items(self) -> dict[str, str]:
        """Return ``{ENV_VAR: display value}`` in declaration order, safe to print."""
        items: dict[str, str] = {}
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            items[env_var_name(name, field)] = _display(value)
        return items


def _display(value: object) -> str:
    """Render one setting value for humans; a secret shows only whether it is set."""
    if value is None:
        return "(unset)"
    if isinstance(value, SecretStr):
        return "(set)"
    if isinstance(value, StrEnum):
        return str(value.value)
    return str(value)


def env_var_name(field_name: str, field: FieldInfo) -> str:
    """Return the environment variable an operator sets for ``field_name``."""
    alias = field.validation_alias
    if isinstance(alias, str):
        return alias
    if isinstance(alias, AliasChoices):
        first = alias.choices[0]
        if isinstance(first, str):
            return first
    return f"{ENV_PREFIX}{field_name.upper()}"


@dataclass(frozen=True)
class SettingProblem:
    """One invalid setting: the environment variable and what is wrong with it."""

    env_var: str
    message: str


class SettingsError(Exception):
    """Raised when configuration is missing or invalid; lists every problem at once."""

    def __init__(self, problems: tuple[SettingProblem, ...]) -> None:
        """Store the problems and build the operator-facing message."""
        self.problems = problems
        super().__init__(self._render())

    def _render(self) -> str:
        lines = [f"Invalid configuration ({len(self.problems)} problem(s)):"]
        lines.extend(f"  - {problem.env_var}: {problem.message}" for problem in self.problems)
        lines.append("See .env.example and docs/configuration.md for every setting.")
        return "\n".join(lines)

    def __str__(self) -> str:
        """Return the rendered message (never contains rejected input values)."""
        return self._render()


def _env_names_by_location() -> dict[str, str]:
    """Map pydantic error locations (field names and aliases) to environment variables."""
    mapping: dict[str, str] = {}
    for name, field in Settings.model_fields.items():
        primary = env_var_name(name, field)
        mapping[name] = primary
        alias = field.validation_alias
        if isinstance(alias, str):
            mapping[alias] = alias
        elif isinstance(alias, AliasChoices):
            mapping.update({choice: choice for choice in alias.choices if isinstance(choice, str)})
    return mapping


def _problems_from(error: ValidationError) -> tuple[SettingProblem, ...]:
    """Convert a pydantic error using only location and message, never the input value."""
    names = _env_names_by_location()
    problems: list[SettingProblem] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = str(item["loc"][0]) if item["loc"] else "(settings)"
        env_var = names.get(location, location)
        if item["type"] == "missing":
            message = "required, not set"
        else:
            message = str(item["msg"]).removeprefix("Value error, ")
        problems.append(SettingProblem(env_var=env_var, message=message))
    return tuple(problems)


def load_settings(*, env_file: str | Path | None = ".env") -> Settings:
    """Load and validate settings, raising :class:`SettingsError` on any problem.

    Args:
        env_file: ``.env`` file to read (relative paths resolve against the current
            directory), or ``None`` to read the process environment only.

    Returns:
        The validated, immutable settings.

    Raises:
        SettingsError: One or more settings are missing or invalid.
    """
    kwargs: dict[str, Any] = {"_env_file": env_file}
    try:
        return Settings(**kwargs)
    except ValidationError as error:
        raise SettingsError(_problems_from(error)) from None
