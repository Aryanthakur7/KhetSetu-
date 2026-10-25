"""The pinned list of dataset files: what we expect on disk, and how big it must be.

The manifest is a small JSON file shipped inside the package. It pins one exact dataset
commit and records each file's size (and sha256 when known), so a truncated or tampered
download is detected instead of silently used for training.
"""

from __future__ import annotations

import re
from importlib import resources
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DatasetFile(BaseModel):
    """One file of the dataset repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    size: Annotated[int, Field(gt=0)]
    sha256: str | None = None

    @field_validator("path")
    @classmethod
    def _path_stays_inside_the_dataset(cls, value: str) -> str:
        """Reject paths that could escape the dataset directory (path traversal)."""
        parts = value.split("/")
        if not value or value.startswith("/") or "\\" in value or ".." in parts or "" in parts:
            msg = f"unsafe dataset file path: {value!r}"
            raise ValueError(msg)
        return value

    @field_validator("sha256")
    @classmethod
    def _sha256_is_hex(cls, value: str | None) -> str | None:
        """Require 64 lowercase hex characters when a hash is given."""
        if value is not None and not _SHA256.match(value):
            msg = "sha256 must be 64 lowercase hex characters"
            raise ValueError(msg)
        return value


class DatasetManifest(BaseModel):
    """The dataset repository, one pinned revision and its files."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_id: str
    revision: str
    files: Annotated[tuple[DatasetFile, ...], Field(min_length=1)]

    def allow_patterns(self) -> list[str]:
        """Return the file paths to pass to the downloader (download only these)."""
        return [file.path for file in self.files]

    @classmethod
    def load_packaged(cls) -> DatasetManifest:
        """Load ``dataset_manifest.json`` that ships inside this package."""
        text = (
            resources.files("khetsetu_backend.data")
            .joinpath("dataset_manifest.json")
            .read_text(encoding="utf-8")
        )
        return cls.model_validate_json(text)
