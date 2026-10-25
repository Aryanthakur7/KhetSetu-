"""app.main() prepares the dataset first when local, and never on a Space or in CI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

import app
from khetsetu_backend.data import DatasetDownloadError

if TYPE_CHECKING:
    from khetsetu_backend.config import Settings


class FakeDemo:
    """Stands in for the Gradio app so no server starts."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def queue(self, **kwargs: Any) -> None:
        self.events.append("queue")

    def launch(self, **kwargs: Any) -> None:
        self.events.append("launch")


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch, isolated_cwd: object) -> list[str]:
    """Replace the slow parts of main() and record the order things happen in."""
    recorded: list[str] = []
    monkeypatch.setattr(app, "configure_logging", lambda settings: recorded.append("logging"))

    def fake_build_demo(settings: Settings) -> FakeDemo:
        recorded.append("build_demo")
        return FakeDemo(recorded)

    monkeypatch.setattr(app, "build_demo", fake_build_demo)
    return recorded


def test_local_run_prepares_the_dataset_after_logging_and_before_building_the_demo(
    events: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")

    def fake_prepare(settings: Settings) -> None:
        events.append("prepare")

    monkeypatch.setattr(app, "prepare_runtime", fake_prepare)
    app.main()
    assert events == ["logging", "prepare", "build_demo", "queue", "launch"]


def test_a_dataset_error_exits_three_and_the_demo_is_never_built(
    events: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")

    def failing_prepare(settings: Settings) -> None:
        msg = "dataset is unavailable"
        raise DatasetDownloadError(msg)

    monkeypatch.setattr(app, "prepare_runtime", failing_prepare)
    with pytest.raises(SystemExit) as exit_info:
        app.main()
    assert exit_info.value.code == 3
    assert "dataset is unavailable" in capsys.readouterr().err
    assert "build_demo" not in events


@pytest.mark.parametrize("env", ["space", "ci"])
def test_space_and_ci_never_call_the_downloader(
    env: str, events: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", env)
    downloads: list[object] = []
    # The real prepare_runtime and ensure_dataset are used. The working directory is empty,
    # so if anything tried to ensure the dataset it would reach this (fake) Hub download.
    monkeypatch.setattr(
        "khetsetu_backend.data.ensure._hub_download", lambda **kwargs: downloads.append(kwargs)
    )
    app.main()
    assert downloads == []
    assert events == ["logging", "build_demo", "queue", "launch"]
