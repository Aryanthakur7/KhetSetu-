"""Service Protocols the frontend depends on and the backend implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from khetsetu_contracts.models import DiagnosisRequest, DiagnosisResult


class DiagnosisService(Protocol):
    """Diagnoses a leaf photo."""

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        """Return the diagnosis for ``request``."""
        ...


@dataclass(frozen=True, slots=True)
class Services:
    """The service objects the composition root hands to the frontend."""

    diagnosis: DiagnosisService
