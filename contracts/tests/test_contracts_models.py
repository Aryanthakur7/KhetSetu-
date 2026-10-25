"""Tests for the DTO rules: a refusal can never carry a disease name."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from khetsetu_contracts import (
    ContractError,
    DiagnosisRequest,
    DiagnosisResult,
    GateStatus,
    ImageTooLargeError,
    InvalidImageError,
    MessageKey,
    NotReadyError,
    Readiness,
    ReadyState,
    ScoredLabel,
    ServiceMode,
)

_KEY_FOR = {
    GateStatus.DIAGNOSED: MessageKey.DIAGNOSED,
    GateStatus.LOW_CONFIDENCE: MessageKey.LOW_CONFIDENCE,
    GateStatus.NOT_A_LEAF: MessageKey.NOT_A_LEAF,
    GateStatus.UNSUPPORTED_CROP: MessageKey.UNSUPPORTED_CROP,
}
_REFUSALS = [GateStatus.LOW_CONFIDENCE, GateStatus.NOT_A_LEAF, GateStatus.UNSUPPORTED_CROP]


def _label(disease_id: str = "A", score: float = 0.6) -> ScoredLabel:
    return ScoredLabel(disease_id=disease_id, display_name=f"Name {disease_id}", score=score)


def _result(status: GateStatus, **overrides: Any) -> DiagnosisResult:
    """Build a result with sensible defaults for ``status``, then apply ``overrides``."""
    fields: dict[str, Any] = {
        "status": status,
        "confidence": 0.5,
        "message_key": _KEY_FOR[status],
    }
    if status is GateStatus.DIAGNOSED:
        fields.update(disease_id="A", display_name="Name A", top_k=(_label("A"),))
    fields.update(overrides)
    return DiagnosisResult(**fields)


def test_diagnosed_result_is_valid_with_names() -> None:
    result = _result(GateStatus.DIAGNOSED, crop="Tomato")
    assert result.display_name == "Name A"
    assert result.top_k[0].disease_id == "A"


@pytest.mark.parametrize("missing", ["disease_id", "display_name"])
def test_diagnosed_requires_a_disease_id_and_display_name(missing: str) -> None:
    with pytest.raises(ValidationError):
        _result(GateStatus.DIAGNOSED, **{missing: None})


@pytest.mark.parametrize("status", _REFUSALS)
@pytest.mark.parametrize(
    "extra",
    [
        {"disease_id": "x"},
        {"display_name": "Late blight"},
        {"crop": "Tomato"},
        {"top_k": (_label(),)},
    ],
)
def test_a_refusal_can_never_carry_a_name_crop_or_alternatives(
    status: GateStatus, extra: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        _result(status, **extra)


@pytest.mark.parametrize("status", _REFUSALS)
def test_a_plain_refusal_is_valid(status: GateStatus) -> None:
    result = _result(status)
    assert result.disease_id is None
    assert result.top_k == ()


def test_top_k_holds_at_most_three_entries() -> None:
    labels = tuple(_label(name) for name in ("A", "B", "C", "D"))
    with pytest.raises(ValidationError):
        _result(GateStatus.DIAGNOSED, top_k=labels)


def test_first_top_k_entry_must_be_the_diagnosed_disease() -> None:
    with pytest.raises(ValidationError):
        _result(GateStatus.DIAGNOSED, top_k=(_label("Other"),))


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_scores_and_confidence_must_be_between_zero_and_one(score: float) -> None:
    with pytest.raises(ValidationError):
        _label(score=score)
    with pytest.raises(ValidationError):
        _result(GateStatus.NOT_A_LEAF, confidence=score)


def test_message_key_must_match_the_status() -> None:
    with pytest.raises(ValidationError):
        _result(GateStatus.NOT_A_LEAF, message_key=MessageKey.DIAGNOSED)


def test_request_rejects_empty_bytes_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DiagnosisRequest(image=b"")
    with pytest.raises(ValidationError):
        DiagnosisRequest(image=b"x", filename="leaf.png")  # type: ignore[call-arg]


def test_models_are_frozen() -> None:
    request = DiagnosisRequest(image=b"x")
    with pytest.raises(ValidationError):
        request.image = b"y"  # type: ignore[misc]


def test_readiness_carries_state_mode_and_version() -> None:
    readiness = Readiness(state=ReadyState.LOADING, mode=ServiceMode.REAL, version="1.2.3")
    assert (readiness.state, readiness.mode, readiness.version) == (
        ReadyState.LOADING,
        ServiceMode.REAL,
        "1.2.3",
    )
    assert {state.value for state in ReadyState} == {"ready", "loading", "failed"}


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (InvalidImageError, MessageKey.INVALID_IMAGE),
        (ImageTooLargeError, MessageKey.IMAGE_TOO_LARGE),
        (NotReadyError, MessageKey.NOT_READY),
        (ContractError, MessageKey.UNAVAILABLE),
    ],
)
def test_every_contract_error_exposes_its_message_key(
    error: type[ContractError], key: MessageKey
) -> None:
    assert error("detail").message_key is key
