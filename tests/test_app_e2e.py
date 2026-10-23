"""End-to-end tests: drive the real composition root over HTTP (FND-06, plan 01-04)."""

from __future__ import annotations

import io
import socket
from typing import TYPE_CHECKING

import pytest
from gradio_client import Client, handle_file
from PIL import Image

from app import build_demo
from khetsetu_backend.config import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import gradio as gr

pytestmark = pytest.mark.e2e


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


@pytest.fixture
def running_demo() -> Iterator[str]:
    """Launch the real demo on a free local port and yield its URL."""
    settings = Settings(_env_file=None, app_env="ci")  # type: ignore[call-arg]
    demo: gr.Blocks = build_demo(settings)
    port = _free_port()
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        prevent_thread_lock=True,
        ssr_mode=False,
        quiet=True,
    )
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        demo.close()


def test_upload_returns_a_fake_diagnosis_over_http(running_demo: str, tmp_path: Path) -> None:
    """An image uploaded over HTTP reaches the service through the contracts and renders."""
    image = _png(tmp_path / "leaf.png", (30, 160, 40))
    client = Client(running_demo, verbose=False)
    result = client.predict(handle_file(str(image)), api_name="/diagnose")
    assert "Tomato - Late blight" in result
