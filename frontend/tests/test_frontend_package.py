"""Smoke tests for the ``khetsetu_frontend`` package."""

from __future__ import annotations

from pathlib import Path

import khetsetu_frontend


def test_frontend_package_imports_with_expected_version() -> None:
    """The frontend package imports and exposes the single version source."""
    assert khetsetu_frontend.__version__ == "0.1.0"


def test_frontend_package_ships_py_typed_marker() -> None:
    """A PEP 561 ``py.typed`` marker sits next to the package ``__init__``."""
    assert khetsetu_frontend.__file__ is not None
    marker = Path(khetsetu_frontend.__file__).parent / "py.typed"
    assert marker.is_file()
