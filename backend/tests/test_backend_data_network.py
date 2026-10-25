"""Opt-in test of the real download path: ``uv run pytest -m network``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from khetsetu_backend.config import AppEnv, Settings
from khetsetu_backend.data import DatasetManifest, DownloadOutcome, ensure_dataset
from khetsetu_backend.data.ensure import dataset_dir
from khetsetu_backend.data.manifest import DatasetFile

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.network


def _fail_if_called(**kwargs: Any) -> None:
    msg = "second call must be a cache hit and must not download"
    raise AssertionError(msg)


def test_real_hub_download_of_the_dataset_card_then_cache_hit(tmp_path: Path) -> None:
    """Download only the 4 KB dataset card from the Hub, then reuse it without network.

    This proves the pinned revision, the ``local_dir`` layout and the allow-pattern
    handling work against the real Hub without pulling the 823 MB of images.
    """
    settings = Settings(_env_file=None, app_env=AppEnv.LOCAL, data_dir=tmp_path)
    manifest = DatasetManifest(
        repo_id=settings.dataset_repo_id,
        revision=settings.dataset_revision,
        files=(DatasetFile(path="README.md", size=4193),),
    )
    first = ensure_dataset(settings, manifest=manifest)
    assert first.outcome is DownloadOutcome.DOWNLOADED
    assert (dataset_dir(settings) / "README.md").stat().st_size == 4193

    second = ensure_dataset(settings, manifest=manifest, downloader=_fail_if_called)
    assert second.outcome is DownloadOutcome.CACHE_HIT
