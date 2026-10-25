"""Tests for the fake services: deterministic outcomes and safe image handling."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from khetsetu_backend import __version__
from khetsetu_backend.config import AppEnv, Settings
from khetsetu_backend.services import build_services
from khetsetu_backend.services.fakes import FakeDiagnosisService, FakeHealthService
from khetsetu_contracts import (
    DiagnosisRequest,
    GateStatus,
    ImageTooLargeError,
    InvalidImageError,
    ReadyState,
    ServiceMode,
)

_BIG = 10_000_000


def _png(colour: tuple[int, int, int], size: tuple[int, int] = (32, 32)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _service(max_bytes: int = _BIG, max_pixels: int = _BIG) -> FakeDiagnosisService:
    return FakeDiagnosisService(max_upload_bytes=max_bytes, max_image_pixels=max_pixels)


@pytest.mark.parametrize(
    ("colour", "status"),
    [
        ((30, 160, 40), GateStatus.DIAGNOSED),
        ((220, 40, 40), GateStatus.NOT_A_LEAF),
        ((60, 60, 255), GateStatus.UNSUPPORTED_CROP),
        ((10, 10, 10), GateStatus.LOW_CONFIDENCE),
    ],
)
def test_each_demo_colour_gives_its_documented_status(
    colour: tuple[int, int, int], status: GateStatus
) -> None:
    result = _service().diagnose(DiagnosisRequest(image=_png(colour)))
    assert result.status is status


def test_diagnosed_result_is_the_fixed_fake_disease() -> None:
    result = _service().diagnose(DiagnosisRequest(image=_png((30, 160, 40))))
    assert result.display_name == "Tomato - Late blight"
    assert result.crop == "Tomato"
    scores = [label.score for label in result.top_k]
    assert len(scores) == 3
    assert scores == sorted(scores, reverse=True)


def test_a_green_red_tie_favours_green() -> None:
    result = _service().diagnose(DiagnosisRequest(image=_png((100, 100, 20))))
    assert result.status is GateStatus.DIAGNOSED


def test_the_same_bytes_always_give_the_same_result() -> None:
    request = DiagnosisRequest(image=_png((220, 40, 40)))
    service = _service()
    assert service.diagnose(request) == service.diagnose(request)


def test_garbage_bytes_raise_invalid_image() -> None:
    with pytest.raises(InvalidImageError):
        _service().diagnose(DiagnosisRequest(image=b"not an image"))


def test_too_many_bytes_are_rejected_before_decoding() -> None:
    # The bytes are garbage: if decoding ran first we would get InvalidImageError instead.
    with pytest.raises(ImageTooLargeError):
        _service(max_bytes=10).diagnose(DiagnosisRequest(image=b"x" * 11))


def test_too_many_pixels_are_rejected() -> None:
    with pytest.raises(ImageTooLargeError):
        _service(max_pixels=100).diagnose(DiagnosisRequest(image=_png((30, 160, 40), (11, 10))))


def test_exactly_the_pixel_limit_is_accepted() -> None:
    result = _service(max_pixels=110).diagnose(
        DiagnosisRequest(image=_png((30, 160, 40), (11, 10)))
    )
    assert result.status is GateStatus.DIAGNOSED


def test_a_pillow_decompression_bomb_warning_becomes_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 40x40 = 1600 pixels is above Pillow's limit (1000) but below twice the limit, which
    # is when Pillow only warns instead of raising.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImageTooLargeError):
        _service().diagnose(DiagnosisRequest(image=_png((30, 160, 40), (40, 40))))


def test_a_pillow_decompression_bomb_error_becomes_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ImageTooLargeError):
        _service().diagnose(DiagnosisRequest(image=_png((30, 160, 40), (40, 40))))


def test_health_reports_ready_fake_and_version() -> None:
    readiness = FakeHealthService(version="9.9.9").readiness()
    assert readiness.state is ReadyState.READY
    assert readiness.mode is ServiceMode.FAKE
    assert readiness.version == "9.9.9"


def test_build_services_passes_the_settings_limits_to_the_fake() -> None:
    settings = Settings(
        _env_file=None, app_env=AppEnv.CI, max_upload_bytes=100_000, max_image_pixels=4
    )
    services = build_services(settings)
    with pytest.raises(ImageTooLargeError):
        services.diagnosis.diagnose(DiagnosisRequest(image=b"x" * 100_001))
    with pytest.raises(ImageTooLargeError):
        services.diagnosis.diagnose(DiagnosisRequest(image=_png((30, 160, 40), (3, 3))))
    assert services.health.readiness().version == __version__
