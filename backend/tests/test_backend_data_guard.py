"""Tests for ``@requires_dataset`` and the ``khetsetu data`` commands."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from khetsetu_backend.cli import app
from khetsetu_backend.config import AppEnv, Settings
from khetsetu_backend.data import (
    DatasetDownloadError,
    DatasetHandle,
    DownloadOutcome,
    active_dataset,
    guard,
    requires_dataset,
)

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def _handle(tmp_path: Path) -> DatasetHandle:
    return DatasetHandle(
        root=tmp_path,
        readme=tmp_path / "README.md",
        parquet_files=(),
        revision="abc",
        outcome=DownloadOutcome.CACHE_HIT,
    )


def test_the_dataset_is_ensured_before_the_body_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    order: list[str] = []

    def fake_ensure(settings: Settings) -> DatasetHandle:
        order.append("ensure")
        return _handle(tmp_path)

    monkeypatch.setattr(guard, "ensure_dataset", fake_ensure)

    @requires_dataset
    def body(number: int) -> str:
        order.append("body")
        assert active_dataset().revision == "abc"
        return f"ran {number}"

    assert body(7) == "ran 7"
    assert order == ["ensure", "body"]


def test_active_dataset_outside_a_guarded_call_is_an_error() -> None:
    with pytest.raises(RuntimeError, match="requires_dataset"):
        active_dataset()


def test_the_decorated_function_keeps_its_signature() -> None:
    @requires_dataset
    def body(count: int, *, name: str = "x") -> None:
        """Doc."""

    assert list(inspect.signature(body).parameters) == ["count", "name"]
    assert body.__doc__ == "Doc."


def test_bad_settings_exit_two_without_running_the_body(
    isolated_cwd: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ran = False

    @requires_dataset
    def body() -> None:
        nonlocal ran
        ran = True

    with pytest.raises(SystemExit) as exit_info:
        body()
    assert exit_info.value.code == 2
    assert "KHETSETU_APP_ENV" in capsys.readouterr().err
    assert not ran


def test_a_dataset_problem_exits_three_without_running_the_body(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")

    def failing_ensure(settings: Settings) -> DatasetHandle:
        msg = "could not download the dataset"
        raise DatasetDownloadError(msg)

    monkeypatch.setattr(guard, "ensure_dataset", failing_ensure)
    ran = False

    @requires_dataset
    def body() -> None:
        nonlocal ran
        ran = True

    with pytest.raises(SystemExit) as exit_info:
        body()
    assert exit_info.value.code == 3
    assert "could not download" in capsys.readouterr().err
    assert not ran


def test_data_inspect_ensures_then_prints_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "ci")
    called: list[Settings] = []

    def fake_ensure(settings: Settings) -> DatasetHandle:
        called.append(settings)
        return _handle(tmp_path)

    monkeypatch.setattr(guard, "ensure_dataset", fake_ensure)
    card = tmp_path / "README.md"
    card.write_text(
        "---\ndataset_info:\n  features:\n  - name: label\n    dtype:\n      class_label:\n"
        "        names:\n          '0': A\n          '1': B\n---\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["data", "inspect"])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.splitlines() == [
        "outcome: cache_hit",
        "revision: abc",
        f"path: {tmp_path}",
        "rows: 0",
        "classes: 2",
        "shards: 0",
    ]
    assert len(called) == 1
    assert called[0].app_env is AppEnv.CI


def test_data_inspect_with_bad_settings_exits_two(isolated_cwd: Path) -> None:
    result = runner.invoke(app, ["data", "inspect"])
    assert result.exit_code == 2
    assert "KHETSETU_APP_ENV" in result.stderr


def test_data_download_prints_the_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "ci")
    seen: dict[str, object] = {}

    def fake_ensure(settings: Settings, *, verify_hashes: bool = False) -> DatasetHandle:
        seen["verify"] = verify_hashes
        return _handle(tmp_path)

    monkeypatch.setattr("khetsetu_backend.cli.ensure_dataset", fake_ensure)
    result = runner.invoke(app, ["data", "download", "--verify"])
    assert result.exit_code == 0, result.stderr
    assert "outcome: cache_hit" in result.stdout
    assert seen["verify"] is True


def test_data_download_failure_exits_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "ci")

    def failing(settings: Settings, *, verify_hashes: bool = False) -> DatasetHandle:
        msg = "no network"
        raise DatasetDownloadError(msg)

    monkeypatch.setattr("khetsetu_backend.cli.ensure_dataset", failing)
    result = runner.invoke(app, ["data", "download"])
    assert result.exit_code == 3
    assert "no network" in result.stderr
