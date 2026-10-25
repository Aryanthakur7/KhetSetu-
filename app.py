"""KhetSetu composition root: the only module that imports both backend and frontend."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

_PACKAGE_SOURCES = {
    "khetsetu_contracts": "contracts/src",
    "khetsetu_backend": "backend/src",
    "khetsetu_frontend": "frontend/src",
}


def _ensure_workspace_importable() -> None:
    """Make the workspace packages importable when they are not installed.

    In the dev environment the packages are editable installs and this is a no-op. In a
    Space bundle only third-party dependencies are installed, so the matching ``src``
    directories next to this file are prepended to ``sys.path``.
    """
    root = Path(__file__).resolve().parent
    for module, relative in _PACKAGE_SOURCES.items():
        if importlib.util.find_spec(module) is None:
            sys.path.insert(0, str(root / relative))


_ensure_workspace_importable()

from khetsetu_backend.bootstrap import prepare_runtime  # noqa: E402
from khetsetu_backend.config import SettingsError, load_settings  # noqa: E402
from khetsetu_backend.data import DatasetError  # noqa: E402
from khetsetu_backend.logging_setup import configure_logging  # noqa: E402
from khetsetu_backend.services import build_services  # noqa: E402
from khetsetu_frontend.ui import build_ui  # noqa: E402

if TYPE_CHECKING:
    import gradio as gr

    from khetsetu_backend.config import Settings

# Exit code for "the configuration is wrong" (the usual convention for command-line misuse).
EXIT_BAD_CONFIG = 2
# Exit code for "the training dataset could not be prepared".
EXIT_DATASET_PROBLEM = 3


class LaunchOptions(TypedDict):
    """The keyword arguments passed to ``demo.launch()``."""

    server_name: str | None
    server_port: int | None
    max_file_size: int
    ssr_mode: bool
    show_error: bool


def build_demo(settings: Settings) -> gr.Blocks:
    """Wire the backend services into the frontend and return the Gradio app."""
    return build_ui(build_services(settings))


def launch_options(settings: Settings) -> LaunchOptions:
    """Return the launch arguments derived from ``settings``."""
    return {
        "server_name": settings.server_host,
        "server_port": settings.server_port,
        # Gradio rejects uploads above this size before our code ever sees them.
        "max_file_size": settings.max_upload_bytes,
        # Server-side rendering needs a Node runtime, which a Space does not provide.
        "ssr_mode": False,
        # Never show Python errors in the browser; they are logged on the server instead.
        "show_error": False,
    }


def mark_zerogpu_ready() -> bool:
    """Register one do-nothing GPU function so a ZeroGPU Space accepts the app.

    ZeroGPU hardware refuses to start an app that has no function decorated with
    ``@spaces.GPU`` ("No @spaces.GPU function detected during startup"). Our hello-world
    does not use a GPU, so this adds an empty marker function. The ``spaces`` package only
    exists on Hugging Face Spaces; anywhere else this does nothing and returns ``False``.
    """
    try:
        spaces = importlib.import_module("spaces")
    except ImportError:
        return False
    gpu = getattr(spaces, "GPU", None)
    if gpu is None:
        return False

    @gpu  # type: ignore[untyped-decorator]
    def gpu_marker() -> None:
        """Never called; its only job is to exist."""

    return True


def main() -> None:
    """Load settings (exit 2 if they are wrong), build the demo and launch it."""
    try:
        settings = load_settings()
    except SettingsError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(EXIT_BAD_CONFIG) from None
    configure_logging(settings)
    # Locally this makes sure the training dataset is on disk; on a Space or in CI it does nothing.
    try:
        prepare_runtime(settings)
    except DatasetError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(EXIT_DATASET_PROBLEM) from None
    mark_zerogpu_ready()
    demo = build_demo(settings)
    # A small queue keeps a free CPU Space responsive: at most 2 requests run at once.
    demo.queue(max_size=20, default_concurrency_limit=2)
    demo.launch(**launch_options(settings))


if __name__ == "__main__":
    main()
