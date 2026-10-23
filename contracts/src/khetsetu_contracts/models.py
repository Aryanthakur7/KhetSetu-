"""Data transfer objects that cross the frontend/backend seam."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class GateStatus(StrEnum):
    """Outcome of one diagnosis request."""

    DIAGNOSED = "diagnosed"
    LOW_CONFIDENCE = "low_confidence"
    NOT_A_LEAF = "not_a_leaf"
    UNSUPPORTED_CROP = "unsupported_crop"


class DiagnosisRequest(BaseModel):
    """A leaf photo, as encoded image bytes."""

    model_config = ConfigDict(frozen=True)

    image: bytes


class DiagnosisResult(BaseModel):
    """The service's answer to a :class:`DiagnosisRequest`."""

    model_config = ConfigDict(frozen=True)

    status: GateStatus
    disease_id: str | None
    display_name: str | None
