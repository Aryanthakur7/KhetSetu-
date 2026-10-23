"""Smoke tests for the ``khetsetu_contracts`` package."""

from __future__ import annotations

from pathlib import Path

import khetsetu_contracts


def test_contracts_package_imports_with_expected_version() -> None:
    """The contracts package imports and exposes the single version source."""
    assert khetsetu_contracts.__version__ == "0.1.0"


def test_contracts_package_ships_py_typed_marker() -> None:
    """A PEP 561 ``py.typed`` marker sits next to the package ``__init__``."""
    assert khetsetu_contracts.__file__ is not None
    marker = Path(khetsetu_contracts.__file__).parent / "py.typed"
    assert marker.is_file()
