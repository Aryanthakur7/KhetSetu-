"""Service wiring: the one place that decides which implementations are used."""

from __future__ import annotations

from typing import TYPE_CHECKING

from khetsetu_backend import __version__
from khetsetu_backend.services.fakes import FakeDiagnosisService, FakeHealthService
from khetsetu_contracts import Services

if TYPE_CHECKING:
    from khetsetu_backend.config import Settings


def build_services(settings: Settings) -> Services:
    """Build the service container for ``settings`` (fakes in the walking skeleton)."""
    return Services(
        diagnosis=FakeDiagnosisService(
            max_upload_bytes=settings.max_upload_bytes,
            max_image_pixels=settings.max_image_pixels,
        ),
        health=FakeHealthService(version=__version__),
    )
