"""End-to-end tests: drive the real composition root over HTTP (FND-06, plan 01-04)."""

from __future__ import annotations

import importlib.util
import io
import os
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gradio_client import Client, handle_file
from PIL import Image

import app
from app import build_demo, launch_options
from khetsetu_backend.config import AppEnv, Settings

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [
    pytest.mark.e2e,
    # gradio_client opens the uploaded file and never closes it; ignored for this module only.
    pytest.mark.filterwarnings("ignore:unclosed file:ResourceWarning"),
]

APP_PY = Path(app.__file__).resolve()
GREEN = (30, 160, 40)
RED = (220, 40, 40)
BLUE = (60, 60, 255)
DARK = (10, 10, 10)


def _free_port() -> int:
    """Return a TCP port that is free right now (bind to port 0)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _png(path: Path, colour: tuple[int, int, int]) -> Path:
    """Write a small solid-colour PNG to ``path`` and return it."""
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), colour).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return path


@contextmanager
def _running(settings: Settings, *, use_launch_options: bool = False) -> Iterator[Client]:
    """Launch the real demo on a free local port and yield a connected client."""
    demo = build_demo(settings)
    port = _free_port()
    options: dict[str, object] = {"ssr_mode": False}
    if use_launch_options:
        options.update(launch_options(settings))
    options.update(server_name="127.0.0.1", server_port=port)
    demo.launch(prevent_thread_lock=True, quiet=True, **options)  # type: ignore[arg-type]
    client = Client(f"http://127.0.0.1:{port}", verbose=False)
    try:
        yield client
    finally:
        client.close()
        demo.close()


@pytest.fixture(scope="module")
def client() -> Iterator[Client]:
    """One running demo with default settings, shared by the tests in this module."""
    with _running(Settings(_env_file=None, app_env=AppEnv.CI)) as running:
        yield running


def _diagnose(client: Client, path: Path) -> str:
    result: str = client.predict(handle_file(str(path)), api_name="/diagnose")
    return result


def test_upload_returns_a_fake_diagnosis_over_http(client: Client, tmp_path: Path) -> None:
    """An image uploaded over HTTP reaches the service through the contracts and renders."""
    result = _diagnose(client, _png(tmp_path / "leaf.png", GREEN))
    assert "Tomato - Late blight" in result


def test_the_four_demo_colours_give_four_different_renderings(
    client: Client, tmp_path: Path
) -> None:
    outputs = {
        name: _diagnose(client, _png(tmp_path / f"{name}.png", colour))
        for name, colour in {"green": GREEN, "red": RED, "blue": BLUE, "dark": DARK}.items()
    }
    assert len(set(outputs.values())) == 4
    assert "clearer photo" in outputs["dark"]
    assert "does not look like a leaf" in outputs["red"]
    assert "not supported" in outputs["blue"]
    for name in ("dark", "red", "blue"):
        assert "blight" not in outputs[name].lower()


def test_a_text_file_renamed_to_png_gives_the_invalid_image_message(
    client: Client, tmp_path: Path
) -> None:
    fake = tmp_path / "notes.png"
    fake.write_text("this is not an image", encoding="utf-8")
    result = _diagnose(client, fake)
    assert "could not read this file" in result
    assert "Traceback" not in result


def test_the_page_banner_says_demo_mode(client: Client) -> None:
    banner: str = client.predict(api_name="/readiness")
    assert "Demo mode" in banner


def test_an_upload_above_the_byte_limit_gives_the_too_large_message(tmp_path: Path) -> None:
    # Gradio's own cap is not applied here, so the service's byte check is what answers.
    settings = Settings(_env_file=None, app_env=AppEnv.CI, max_upload_bytes=100)
    with _running(settings) as small_client:
        result = _diagnose(small_client, _png(tmp_path / "leaf.png", GREEN))
    assert "too large" in result


def test_gradio_refuses_an_upload_above_max_file_size(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, app_env=AppEnv.CI, max_upload_bytes=100)
    with (
        _running(settings, use_launch_options=True) as small_client,
        pytest.raises(Exception, match=r".+"),
    ):
        _diagnose(small_client, _png(tmp_path / "leaf.png", GREEN))


def _clean_env() -> dict[str, str]:
    """The current environment without any KHETSETU_ or HF_ variables."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("KHETSETU_", "HF_")) and key != "SPACE_ID"
    }


def _run_app(tmp_path: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``python app.py`` in an empty directory so no ``.env`` file is found."""
    return subprocess.run(  # noqa: S603 - fixed arguments, no user input
        [sys.executable, str(APP_PY)],
        cwd=tmp_path,
        env={**_clean_env(), **extra_env},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_app_exits_2_at_once_when_app_env_is_missing(tmp_path: Path) -> None:
    done = _run_app(tmp_path, {})
    assert done.returncode == 2
    assert "KHETSETU_APP_ENV" in done.stderr
    assert "Traceback" not in done.stderr


def test_app_exits_2_when_the_space_asks_for_a_blocking_dataset_download(tmp_path: Path) -> None:
    done = _run_app(tmp_path, {"KHETSETU_APP_ENV": "space", "KHETSETU_DATASET_MODE": "blocking"})
    assert done.returncode == 2
    assert "KHETSETU_DATASET_MODE" in done.stderr


def test_launch_options_come_from_settings() -> None:
    unset = launch_options(Settings(_env_file=None, app_env=AppEnv.CI, max_upload_bytes=1234))
    assert unset["max_file_size"] == 1234
    assert unset["ssr_mode"] is False
    assert unset["show_error"] is False
    assert unset["server_name"] is None
    assert unset["server_port"] is None
    configured = launch_options(
        Settings(_env_file=None, app_env=AppEnv.CI, server_host="0.0.0.0", server_port=7861)  # noqa: S104
    )
    assert configured["server_name"] == "0.0.0.0"  # noqa: S104
    assert configured["server_port"] == 7861


def test_app_adds_missing_workspace_sources_to_sys_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the packages are not installed (a Space bundle) their src folders are added."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    app._ensure_workspace_importable()
    root = APP_PY.parent
    for relative in ("contracts/src", "backend/src", "frontend/src"):
        assert str(root / relative) in sys.path
