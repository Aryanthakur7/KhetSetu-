"""Tests for the messages and the pure presenter functions."""

from __future__ import annotations

import pytest

from khetsetu_contracts import (
    ContractError,
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
from khetsetu_frontend.messages import MESSAGES, message_for
from khetsetu_frontend.presenters import (
    render_banner,
    render_error,
    render_no_image,
    render_result,
)

_DISEASE = "Tomato - Late blight"


def _diagnosed() -> DiagnosisResult:
    return DiagnosisResult(
        status=GateStatus.DIAGNOSED,
        disease_id="Tomato___Late_blight",
        display_name=_DISEASE,
        crop="Tomato",
        confidence=0.6,
        top_k=(ScoredLabel(disease_id="Tomato___Late_blight", display_name=_DISEASE, score=0.6),),
        message_key=MessageKey.DIAGNOSED,
    )


def _refusal(status: GateStatus, key: MessageKey) -> DiagnosisResult:
    return DiagnosisResult(status=status, confidence=0.1, message_key=key)


def test_every_message_key_has_an_english_string() -> None:
    assert set(MESSAGES) == set(MessageKey)
    assert all(message_for(key).strip() for key in MessageKey)


def test_diagnosed_result_shows_the_name_and_crop() -> None:
    text = render_result(_diagnosed())
    assert _DISEASE in text
    assert "Tomato" in text


def test_low_confidence_asks_for_a_clearer_photo() -> None:
    text = render_result(_refusal(GateStatus.LOW_CONFIDENCE, MessageKey.LOW_CONFIDENCE))
    assert "clearer photo" in text


def test_not_a_leaf_says_it_does_not_look_like_a_leaf() -> None:
    text = render_result(_refusal(GateStatus.NOT_A_LEAF, MessageKey.NOT_A_LEAF))
    assert "does not look like a leaf" in text


def test_unsupported_crop_says_the_crop_is_not_supported() -> None:
    text = render_result(_refusal(GateStatus.UNSUPPORTED_CROP, MessageKey.UNSUPPORTED_CROP))
    assert "not supported" in text


@pytest.mark.parametrize("key", [k for k in MessageKey if k is not MessageKey.DIAGNOSED])
def test_no_message_other_than_diagnosed_contains_a_disease_name(key: MessageKey) -> None:
    lowered = message_for(key).lower()
    assert "blight" not in lowered
    assert "tomato" not in lowered


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (InvalidImageError("x"), MessageKey.INVALID_IMAGE),
        (ImageTooLargeError("x"), MessageKey.IMAGE_TOO_LARGE),
        (NotReadyError("x"), MessageKey.NOT_READY),
        (ContractError("x"), MessageKey.UNAVAILABLE),
    ],
)
def test_render_error_uses_the_message_key_not_the_exception_text(
    error: ContractError, key: MessageKey
) -> None:
    assert render_error(error) == message_for(key)


def test_banner_says_demo_mode_for_a_fake_service() -> None:
    banner = render_banner(
        Readiness(state=ReadyState.READY, mode=ServiceMode.FAKE, version="0.1.0")
    )
    assert "Demo mode" in banner


def test_banner_says_the_service_is_starting_while_loading() -> None:
    banner = render_banner(
        Readiness(state=ReadyState.LOADING, mode=ServiceMode.REAL, version="0.1.0")
    )
    assert "starting" in banner
    assert "Demo mode" not in banner


def test_banner_is_empty_when_real_and_ready() -> None:
    banner = render_banner(Readiness(state=ReadyState.READY, mode=ServiceMode.REAL, version="1"))
    assert banner == ""


def test_banner_reports_a_failed_service() -> None:
    banner = render_banner(Readiness(state=ReadyState.FAILED, mode=ServiceMode.REAL, version="1"))
    assert banner == message_for(MessageKey.UNAVAILABLE)


def test_render_no_image_is_the_no_image_prompt() -> None:
    assert render_no_image() == message_for(MessageKey.NO_IMAGE)
