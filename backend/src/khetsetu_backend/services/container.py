"""Service wiring: the one place that decides which implementations are used."""

from __future__ import annotations

from typing import TYPE_CHECKING

from khetsetu_backend.services.fakes import FakeDiagnosisService
from khetsetu_contracts import Services

if TYPE_CHECKING:
    from khetsetu_backend.config import Settings


def build_services(settings: Settings) -> Services:
    """Build the service container for ``settings`` (fakes in the walking skeleton)."""
    del settings
    return Services(diagnosis=FakeDiagnosisService())
