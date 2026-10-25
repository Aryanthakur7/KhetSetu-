"""Tests for the dataset manifest and ``ensure_dataset`` (FND-03), with no network."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from khetsetu_backend.config import AppEnv, Settings
from khetsetu_backend.data import (
    DatasetDownloadError,
    DatasetIntegrityError,
    DatasetManifest,
    DownloadOutcome,
    ensure_dataset,
)
from khetsetu_backend.data.ensure import dataset_dir
from khetsetu_backend.data.manifest import DatasetFile

if TYPE_CHECKING:
    from pathlib import Path

REPO = "Project-AgML/plant_village_classification"
REVISION = "cb08789a92460034ced0449eac1dba72bb4883da"
FILES = {"README.md": b"hello card", "data/train-00000-of-00001.parquet": b"pretend parquet"}


def _settings(data_dir: Path, **extra: Any) -> Settings:
    return Settings(_env_file=None, app_env=AppEnv.LOCAL, data_dir=data_dir, **extra)


def _manifest(*, hashes: bool = True) -> DatasetManifest:
    files = tuple(
        DatasetFile(
            path=path,
            size=len(body),
            sha256=hashlib.sha256(body).hexdigest() if hashes else None,
        )
        for path, body in FILES.items()
    )
    return DatasetManifest(repo_id=REPO, revision=REVISION, files=files)


def _write_files(root: Path, files: dict[str, bytes]) -> None:
    for path, body in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


class FakeDownloader:
    """Records calls and writes the given files, like the real downloader would."""

    def __init__(self, files: dict[str, bytes], *, error: Exception | None = None) -> None:
        self.files = files
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        _write_files(kwargs["local_dir"], self.files)


class ExplodingDownloader:
    """Fails the test if it is ever called (proves 'no network on a cache hit')."""

    def __call__(self, **kwargs: Any) -> None:
        msg = "the downloader must not be called"
        raise AssertionError(msg)


# ----------------------------------------------------------------------------- manifest


def test_packaged_manifest_pins_the_known_revision_and_files() -> None:
    manifest = DatasetManifest.load_packaged()
    assert manifest.repo_id == REPO
    assert manifest.revision == REVISION
    assert len(manifest.files) == 3
    assert manifest.allow_patterns()[0] == "README.md"


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a\\b", "a/../b", "", "a//b"])
def test_manifest_rejects_paths_that_could_escape_the_dataset_folder(bad: str) -> None:
    with pytest.raises(ValidationError):
        DatasetFile(path=bad, size=1)


def test_manifest_rejects_a_malformed_sha256() -> None:
    with pytest.raises(ValidationError):
        DatasetFile(path="a.txt", size=1, sha256="not-a-hash")


# ------------------------------------------------------------------------------ ensure


def test_complete_dataset_is_a_cache_hit_and_never_downloads(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_files(dataset_dir(settings), FILES)
    handle = ensure_dataset(settings, manifest=_manifest(), downloader=ExplodingDownloader())
    assert handle.outcome is DownloadOutcome.CACHE_HIT
    assert handle.revision == REVISION
    assert handle.readme.name == "README.md"
    assert [p.name for p in handle.parquet_files] == ["train-00000-of-00001.parquet"]


def test_missing_files_are_downloaded_once_then_reused(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    downloader = FakeDownloader(FILES)
    first = ensure_dataset(settings, manifest=_manifest(), downloader=downloader)
    assert first.outcome is DownloadOutcome.DOWNLOADED
    assert len(downloader.calls) == 1
    call = downloader.calls[0]
    assert call["repo_type"] == "dataset"
    assert call["revision"] == REVISION
    assert call["local_dir"] == dataset_dir(settings)
    assert call["allow_patterns"] == list(FILES)

    second = ensure_dataset(settings, manifest=_manifest(), downloader=ExplodingDownloader())
    assert second.outcome is DownloadOutcome.CACHE_HIT
    assert len(downloader.calls) == 1


def test_a_wrong_size_file_triggers_a_download(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_files(dataset_dir(settings), {**FILES, "README.md": b"truncated"})
    downloader = FakeDownloader(FILES)
    handle = ensure_dataset(settings, manifest=_manifest(), downloader=downloader)
    assert handle.outcome is DownloadOutcome.DOWNLOADED
    assert len(downloader.calls) == 1


def test_a_download_that_writes_a_wrong_size_file_fails_naming_the_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    downloader = FakeDownloader({**FILES, "README.md": b"x"})
    with pytest.raises(DatasetIntegrityError, match=r"README\.md"):
        ensure_dataset(settings, manifest=_manifest(), downloader=downloader)


def test_a_download_with_the_wrong_hash_fails_naming_the_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    same_size_different_bytes = {**FILES, "README.md": b"X" * len(FILES["README.md"])}
    downloader = FakeDownloader(same_size_different_bytes)
    with pytest.raises(DatasetIntegrityError, match=r"README\.md.*sha256"):
        ensure_dataset(settings, manifest=_manifest(), downloader=downloader)


def test_a_failing_downloader_is_reported_without_leaking_the_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_SECRET_TOKEN_VALUE")
    settings = _settings(tmp_path)
    downloader = FakeDownloader(FILES, error=RuntimeError("401 for hf_SECRET_TOKEN_VALUE"))
    with caplog.at_level(logging.DEBUG), pytest.raises(DatasetDownloadError) as caught:
        ensure_dataset(settings, manifest=_manifest(), downloader=downloader)
    text = str(caught.value)
    assert REPO in text
    assert REVISION in text
    assert "hf_SECRET_TOKEN_VALUE" not in text
    assert "hf_SECRET_TOKEN_VALUE" not in caplog.text
    # The token is passed to the downloader as an argument, and only there.
    assert downloader.calls[0]["token"] == "hf_SECRET_TOKEN_VALUE"  # noqa: S105


def test_no_token_means_the_downloader_gets_none(tmp_path: Path) -> None:
    downloader = FakeDownloader(FILES)
    ensure_dataset(_settings(tmp_path), manifest=_manifest(), downloader=downloader)
    assert downloader.calls[0]["token"] is None


def test_settings_that_disagree_with_the_manifest_are_rejected(tmp_path: Path) -> None:
    other_revision = _settings(tmp_path, dataset_revision="main")
    with pytest.raises(DatasetIntegrityError, match="KHETSETU_DATASET_REVISION"):
        ensure_dataset(other_revision, manifest=_manifest(), downloader=ExplodingDownloader())
    other_repo = _settings(tmp_path, dataset_repo_id="someone/else")
    with pytest.raises(DatasetIntegrityError, match="KHETSETU_DATASET_REPO_ID"):
        ensure_dataset(other_repo, manifest=_manifest(), downloader=ExplodingDownloader())


def test_verify_hashes_catches_corruption_that_keeps_the_size(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_files(dataset_dir(settings), {**FILES, "README.md": b"X" * len(FILES["README.md"])})
    # Without hashing, a same-size file looks fine.
    quick = ensure_dataset(settings, manifest=_manifest(), downloader=ExplodingDownloader())
    assert quick.outcome is DownloadOutcome.CACHE_HIT
    # With hashing it is noticed, and the (fake) download repairs it.
    repaired = ensure_dataset(
        settings, manifest=_manifest(), downloader=FakeDownloader(FILES), verify_hashes=True
    )
    assert repaired.outcome is DownloadOutcome.DOWNLOADED


def test_a_manifest_path_through_a_symlink_cannot_escape_the_dataset_folder(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path / "data")
    root = dataset_dir(settings)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"abc")
    root.mkdir(parents=True)
    (root / "link").symlink_to(outside)
    manifest = DatasetManifest(
        repo_id=REPO, revision=REVISION, files=(DatasetFile(path="link/secret.txt", size=3),)
    )
    with pytest.raises(DatasetIntegrityError, match="escapes"):
        ensure_dataset(settings, manifest=manifest, downloader=FakeDownloader({}))
