"""KhetSetu composition root: the only module that imports both backend and frontend."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

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

from khetsetu_backend.config import load_settings  # noqa: E402
from khetsetu_backend.services import build_services  # noqa: E402
from khetsetu_frontend.ui import build_ui  # noqa: E402

if TYPE_CHECKING:
    import gradio as gr

    from khetsetu_backend.config import Settings


def build_demo(settings: Settings) -> gr.Blocks:
    """Wire the backend services into the frontend and return the Gradio app."""
    return build_ui(build_services(settings))


def main() -> None:
    """Load settings, build the demo and launch it."""
    settings = load_settings()
    build_demo(settings).launch(ssr_mode=False)


if __name__ == "__main__":
    main()
