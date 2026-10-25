"""Tests for ``prepare_runtime``: local runs fetch the dataset, Space and CI never do."""

from __future__ import annotations

from pathlib import Path

import pytest

from khetsetu_backend.bootstrap import prepare_runtime
from khetsetu_backend.config import AppEnv, DatasetMode, Settings
from khetsetu_backend.data import DatasetHandle, DownloadOutcome


def _handle() -> DatasetHandle:
    return DatasetHandle(
        root=Path("x"),
        readme=Path("x/README.md"),
        parquet_files=(),
        revision="r",
        outcome=DownloadOutcome.CACHE_HIT,
    )


class Recorder:
    """A stand-in for ``ensure_dataset`` that counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, settings: Settings) -> DatasetHandle:
        self.calls += 1
        return _handle()


def test_local_environment_prepares_the_dataset_once() -> None:
    recorder = Recorder()
    settings = Settings(_env_file=None, app_env=AppEnv.LOCAL)
    assert prepare_runtime(settings, ensure=recorder) == _handle()
    assert recorder.calls == 1


@pytest.mark.parametrize(
    "settings",
    [
        Settings(_env_file=None, app_env=AppEnv.CI),
        Settings(_env_file=None, app_env=AppEnv.SPACE),
        Settings(_env_file=None, app_env=AppEnv.SPACE, dataset_mode=DatasetMode.OFF),
        Settings(_env_file=None, app_env=AppEnv.LOCAL, dataset_mode=DatasetMode.OFF),
    ],
)
def test_space_ci_and_explicit_off_never_download(settings: Settings) -> None:
    recorder = Recorder()
    assert prepare_runtime(settings, ensure=recorder) is None
    assert recorder.calls == 0
