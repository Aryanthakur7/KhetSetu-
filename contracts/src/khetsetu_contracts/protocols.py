"""Service Protocols the frontend depends on and the backend implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from khetsetu_contracts.models import DiagnosisRequest, DiagnosisResult, Readiness


class DiagnosisService(Protocol):
    """Diagnoses a leaf photo."""

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        """Return the diagnosis for ``request``.

        Raises:
            InvalidImageError: The bytes are not a readable image.
            ImageTooLargeError: The image is too large in bytes or pixels.
            NotReadyError: The service is still starting.
        """
        ...


class HealthService(Protocol):
    """Reports whether the services are up, and whether they are fakes."""

    def readiness(self) -> Readiness:
        """Return the current readiness."""
        ...


@dataclass(frozen=True, slots=True)
class Services:
    """The service objects the composition root hands to the frontend."""

    diagnosis: DiagnosisService
    health: HealthService
