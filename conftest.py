"""Repository-wide pytest fixtures.

Tests must be hermetic. A developer's real ``.env`` file (which may hold ``HF_TOKEN``) and
any ``KHETSETU_*`` variables exported in their shell must never leak into a test run, or a
green suite would depend on whose machine it runs on. The ``hermetic_environment`` fixture
therefore scrubs those variables for every test, and ``isolated_cwd`` moves the working
directory away from the repository root so a relative ``.env`` is never picked up.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_EXACT_NAMES = ("HF_TOKEN", "HF_SPACE_ID", "SPACE_ID", "HF_HUB_OFFLINE")
_PREFIX = "KHETSETU_"


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every environment variable the application reads, for every test."""
    for name in list(os.environ):
        if name.startswith(_PREFIX) or name in _EXACT_NAMES:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run the test from an empty temporary directory and return it."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path
