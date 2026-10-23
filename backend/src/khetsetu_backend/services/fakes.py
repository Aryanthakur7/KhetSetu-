"""Fake services for the walking skeleton (replaced by real services in later phases)."""

from __future__ import annotations

from khetsetu_contracts import DiagnosisRequest, DiagnosisResult, GateStatus


class FakeDiagnosisService:
    """Returns a fixed diagnosis for any non-empty image."""

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        """Return the fixed fake diagnosis."""
        del request
        return DiagnosisResult(
            status=GateStatus.DIAGNOSED,
            disease_id="Tomato___Late_blight",
            display_name="Tomato - Late blight",
        )
