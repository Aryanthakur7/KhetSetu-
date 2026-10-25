"""Make sure the training dataset is on disk, downloading it at most once (FND-03).

``ensure_dataset`` is the single function every dataset-consuming command calls first:

* If every file in the manifest is already present with the right size, it returns at once
  (``cache_hit``) without touching the network. This is how the dataset you downloaded by
  hand under ``data/plant_village_classification/`` is reused.
* Otherwise it downloads exactly the manifest files at the pinned revision, checks their
  size and sha256, and returns ``downloaded``.

This module must stay importable on the deployed Space, so it does not import ``pyarrow``,
``yaml`` or ``huggingface_hub`` at module level (the downloader is imported when needed).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from khetsetu_backend.data.manifest import DatasetManifest

if TYPE_CHECKING:
    from pathlib import Path

    from khetsetu_backend.config import Settings

logger = logging.getLogger(__name__)

_HASH_CHUNK = 1024 * 1024  # hash big files 1 MiB at a time so memory stays small


class DatasetError(Exception):
    """Base class for every dataset problem; the command line turns it into exit code 3."""


class DatasetDownloadError(DatasetError):
    """The download itself failed (network, permissions, unknown revision)."""


class DatasetIntegrityError(DatasetError):
    """Files are missing, the wrong size, have the wrong hash, or settings disagree."""


class DownloadOutcome(StrEnum):
    """What ``ensure_dataset`` had to do."""

    CACHE_HIT = "cache_hit"
    DOWNLOADED = "downloaded"


@dataclass(frozen=True)
class DatasetHandle:
    """A verified dataset on disk."""

    root: Path
    readme: Path
    parquet_files: tuple[Path, ...]
    revision: str
    outcome: DownloadOutcome


class Downloader(Protocol):
    """The shape of ``huggingface_hub.snapshot_download`` that we rely on."""

    def __call__(  # noqa: PLR0913
        self,
        *,
        repo_id: str,
        repo_type: str,
        revision: str,
        local_dir: Path,
        allow_patterns: list[str],
        token: str | None,
    ) -> object:
        """Fetch ``allow_patterns`` of ``repo_id`` at ``revision`` into ``local_dir``."""
        ...


def _hub_download(  # noqa: PLR0913
    *,
    repo_id: str,
    repo_type: str,
    revision: str,
    local_dir: Path,
    allow_patterns: list[str],
    token: str | None,
) -> object:
    """Download with the real Hugging Face client (imported here to keep startup light)."""
    from huggingface_hub import snapshot_download  # noqa: PLC0415

    return snapshot_download(
        repo_id=repo_id,
        repo_type=repo_type,
        revision=revision,
        local_dir=local_dir,
        allow_patterns=allow_patterns,
        token=token,
    )


def dataset_dir(settings: Settings) -> Path:
    """Return the folder holding the dataset, e.g. ``data/plant_village_classification``."""
    return settings.data_dir / settings.dataset_repo_id.rsplit("/", maxsplit=1)[-1]


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _find_problems(root: Path, manifest: DatasetManifest, *, check_hashes: bool) -> list[str]:
    """Return a description of every manifest file that is missing or wrong."""
    problems: list[str] = []
    resolved_root = root.resolve()
    for file in manifest.files:
        path = root / file.path
        if not path.resolve().is_relative_to(resolved_root):
            problems.append(f"{file.path} (path escapes the dataset directory)")
        elif not path.is_file():
            problems.append(f"{file.path} (missing)")
        elif path.stat().st_size != file.size:
            problems.append(f"{file.path} (size {path.stat().st_size}, expected {file.size})")
        elif check_hashes and file.sha256 is not None and _sha256_of(path) != file.sha256:
            problems.append(f"{file.path} (sha256 does not match the manifest)")
    return problems


def _handle(root: Path, manifest: DatasetManifest, outcome: DownloadOutcome) -> DatasetHandle:
    return DatasetHandle(
        root=root,
        readme=root / "README.md",
        parquet_files=tuple(root / f.path for f in manifest.files if f.path.endswith(".parquet")),
        revision=manifest.revision,
        outcome=outcome,
    )


def ensure_dataset(
    settings: Settings,
    *,
    manifest: DatasetManifest | None = None,
    downloader: Downloader | None = None,
    verify_hashes: bool = False,
) -> DatasetHandle:
    """Return the dataset, downloading it first only if it is not already complete.

    Args:
        settings: Validated settings (data directory, repository id and revision).
        manifest: Expected files; defaults to the packaged, pinned manifest.
        downloader: Function that fetches files; defaults to the Hugging Face client.
            Tests pass a fake so no network is used.
        verify_hashes: Also check sha256 of files already on disk (slow: reads 823 MB).

    Returns:
        A handle with the file locations and whether a download was needed.

    Raises:
        DatasetIntegrityError: Settings disagree with the manifest, or a file is wrong
            even after downloading.
        DatasetDownloadError: The downloader failed.
    """
    manifest = manifest or DatasetManifest.load_packaged()
    if settings.dataset_repo_id != manifest.repo_id:
        msg = (
            f"KHETSETU_DATASET_REPO_ID is {settings.dataset_repo_id!r} but the packaged "
            f"manifest describes {manifest.repo_id!r}"
        )
        raise DatasetIntegrityError(msg)
    if settings.dataset_revision != manifest.revision:
        msg = (
            f"KHETSETU_DATASET_REVISION is {settings.dataset_revision!r} but the packaged "
            f"manifest is pinned to {manifest.revision!r}; regenerate the manifest "
            "(see docs/dataset.md)"
        )
        raise DatasetIntegrityError(msg)

    root = dataset_dir(settings)
    started = time.monotonic()
    if not _find_problems(root, manifest, check_hashes=verify_hashes):
        logger.info("dataset ready (cache_hit) at %s", root)
        return _handle(root, manifest, DownloadOutcome.CACHE_HIT)

    logger.info("dataset incomplete, downloading %s@%s", manifest.repo_id, manifest.revision)
    token = settings.hf_token.get_secret_value() if settings.hf_token else None
    try:
        (downloader or _hub_download)(
            repo_id=manifest.repo_id,
            repo_type="dataset",
            revision=manifest.revision,
            local_dir=root,
            allow_patterns=manifest.allow_patterns(),
            token=token,
        )
    except Exception as error:
        # Build the message from names only: the exception text could echo request headers.
        msg = (
            f"Could not download {manifest.repo_id} at revision {manifest.revision} "
            f"({type(error).__name__}). Check your network connection and HF_TOKEN."
        )
        raise DatasetDownloadError(msg) from None

    problems = _find_problems(root, manifest, check_hashes=True)
    if problems:
        msg = (
            f"Downloaded dataset failed verification: {', '.join(problems)}. "
            "Delete the offending file(s) and run `khetsetu data download` again."
        )
        raise DatasetIntegrityError(msg)
    logger.info("dataset downloaded in %.1fs", time.monotonic() - started)
    return _handle(root, manifest, DownloadOutcome.DOWNLOADED)
