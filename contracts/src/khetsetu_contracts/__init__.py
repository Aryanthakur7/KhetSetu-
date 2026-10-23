"""KhetSetu contracts: typed DTOs and service Protocols shared across packages."""

from khetsetu_contracts.models import DiagnosisRequest, DiagnosisResult, GateStatus
from khetsetu_contracts.protocols import DiagnosisService, Services

__version__ = "0.1.0"

__all__ = [
    "DiagnosisRequest",
    "DiagnosisResult",
    "DiagnosisService",
    "GateStatus",
    "Services",
    "__version__",
]
