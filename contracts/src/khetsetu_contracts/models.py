"""Data transfer objects (DTOs) that cross the frontend/backend seam.

These are the "shape of the conversation" between the screen and the engine. The most
important rule is written into :class:`DiagnosisResult` itself: only a ``DIAGNOSED`` result
may carry a disease name. A refusal ("send a clearer photo") can never accidentally show a
guessed disease, because the model refuses to be built that way.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_Score = Annotated[float, Field(ge=0.0, le=1.0)]
_MAX_TOP_K = 3


class GateStatus(StrEnum):
    """Outcome of one diagnosis request."""

    DIAGNOSED = "diagnosed"
    LOW_CONFIDENCE = "low_confidence"
    NOT_A_LEAF = "not_a_leaf"
    UNSUPPORTED_CROP = "unsupported_crop"


class MessageKey(StrEnum):
    """Keys for every user-facing message; the frontend maps each key to text."""

    DIAGNOSED = "diagnosis.diagnosed"
    LOW_CONFIDENCE = "diagnosis.low_confidence"
    NOT_A_LEAF = "diagnosis.not_a_leaf"
    UNSUPPORTED_CROP = "diagnosis.unsupported_crop"
    INVALID_IMAGE = "error.invalid_image"
    IMAGE_TOO_LARGE = "error.image_too_large"
    NOT_READY = "error.not_ready"
    UNAVAILABLE = "error.unavailable"
    NO_IMAGE = "input.no_image"


# Which message key each outcome must use.
STATUS_MESSAGE_KEYS: dict[GateStatus, MessageKey] = {
    GateStatus.DIAGNOSED: MessageKey.DIAGNOSED,
    GateStatus.LOW_CONFIDENCE: MessageKey.LOW_CONFIDENCE,
    GateStatus.NOT_A_LEAF: MessageKey.NOT_A_LEAF,
    GateStatus.UNSUPPORTED_CROP: MessageKey.UNSUPPORTED_CROP,
}


class DiagnosisRequest(BaseModel):
    """A leaf photo, as encoded image bytes (not a PIL object, so the seam stays pure)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    image: bytes = Field(min_length=1)


class ScoredLabel(BaseModel):
    """One candidate disease with its score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    disease_id: str
    display_name: str
    score: _Score


class DiagnosisResult(BaseModel):
    """The service's answer to a :class:`DiagnosisRequest`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: GateStatus
    disease_id: str | None = None
    display_name: str | None = None
    crop: str | None = None
    confidence: _Score
    top_k: tuple[ScoredLabel, ...] = ()
    message_key: MessageKey

    @model_validator(mode="after")
    def _check_status_rules(self) -> Self:
        """Enforce the honesty rules: a refusal never carries a name or alternatives."""
        if self.message_key is not STATUS_MESSAGE_KEYS[self.status]:
            msg = f"message_key {self.message_key.value!r} is wrong for {self.status.value!r}"
            raise ValueError(msg)
        if len(self.top_k) > _MAX_TOP_K:
            msg = f"top_k holds at most {_MAX_TOP_K} entries"
            raise ValueError(msg)
        if self.status is GateStatus.DIAGNOSED:
            if self.disease_id is None or self.display_name is None:
                msg = "a DIAGNOSED result needs disease_id and display_name"
                raise ValueError(msg)
            if self.top_k and self.top_k[0].disease_id != self.disease_id:
                msg = "the first top_k entry must be the diagnosed disease"
                raise ValueError(msg)
        elif (
            self.disease_id is not None
            or self.display_name is not None
            or self.crop is not None
            or self.top_k
        ):
            msg = f"a {self.status.value} result must not carry a disease, crop or alternatives"
            raise ValueError(msg)
        return self


class ReadyState(StrEnum):
    """Whether the services can answer requests yet."""

    READY = "ready"
    LOADING = "loading"
    FAILED = "failed"


class ServiceMode(StrEnum):
    """Whether the services are fakes (demo) or real."""

    FAKE = "fake"
    REAL = "real"


class Readiness(BaseModel):
    """Health information shown in the page banner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: ReadyState
    mode: ServiceMode
    version: str
