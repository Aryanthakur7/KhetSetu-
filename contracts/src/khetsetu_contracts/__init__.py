"""KhetSetu contracts: typed DTOs and service Protocols shared across packages."""

from khetsetu_contracts.errors import (
    ContractError,
    ImageTooLargeError,
    InvalidImageError,
    NotReadyError,
)
from khetsetu_contracts.models import (
    DiagnosisRequest,
    DiagnosisResult,
    GateStatus,
    MessageKey,
    Readiness,
    ReadyState,
    ScoredLabel,
    ServiceMode,
)
from khetsetu_contracts.protocols import DiagnosisService, HealthService, Services

__version__ = "0.1.0"

__all__ = [
    "ContractError",
    "DiagnosisRequest",
    "DiagnosisResult",
    "DiagnosisService",
    "GateStatus",
    "HealthService",
    "ImageTooLargeError",
    "InvalidImageError",
    "MessageKey",
    "NotReadyError",
    "Readiness",
    "ReadyState",
    "ScoredLabel",
    "ServiceMode",
    "Services",
    "__version__",
]
