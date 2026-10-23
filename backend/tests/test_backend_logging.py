"""Tests for ``khetsetu_backend.logging_setup``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from khetsetu_backend.config import load_settings
from khetsetu_backend.logging_setup import configure_logging

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    """Put the root logger back as found so other tests are unaffected."""
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    yield
    root.setLevel(level)
    root.handlers[:] = handlers


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_sets_level_and_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The root level follows settings and repeated calls add no duplicate handler."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv("KHETSETU_LOG_LEVEL", "WARNING")
    settings = load_settings(env_file=None)
    root = logging.getLogger()
    before = len(root.handlers)

    configure_logging(settings)
    configure_logging(settings)

    assert root.level == logging.WARNING
    assert len(root.handlers) == before + 1


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_level_change_replaces_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call with a different level re-levels the root without stacking handlers."""
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    root = logging.getLogger()
    before = len(root.handlers)

    monkeypatch.setenv("KHETSETU_LOG_LEVEL", "DEBUG")
    configure_logging(load_settings(env_file=None))
    assert root.level == logging.DEBUG

    monkeypatch.setenv("KHETSETU_LOG_LEVEL", "ERROR")
    configure_logging(load_settings(env_file=None))
    assert root.level == logging.ERROR
    assert len(root.handlers) == before + 1
