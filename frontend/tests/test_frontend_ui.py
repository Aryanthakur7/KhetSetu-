"""Tests for the upload handler and the page layout, using local stub services.

The stubs implement the contract Protocols. They deliberately do not import the backend.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gradio as gr
import pytest

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
    ServiceMode,
    Services,
)
from khetsetu_frontend.messages import message_for
from khetsetu_frontend.ui import build_ui, diagnose_upload, load_banner

if TYPE_CHECKING:
    from pathlib import Path


class _StubDiagnosis:
    """Returns a canned result, or raises a canned error."""

    def __init__(self, result: DiagnosisResult | Exception) -> None:
        self._result = result
        self.requests: list[DiagnosisRequest] = []

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        self.requests.append(request)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _StubHealth:
    def __init__(self, readiness: Readiness | Exception) -> None:
        self._readiness = readiness

    def readiness(self) -> Readiness:
        if isinstance(self._readiness, Exception):
            raise self._readiness
        return self._readiness


_READY_FAKE = Readiness(state=ReadyState.READY, mode=ServiceMode.FAKE, version="0")
_NOT_A_LEAF = DiagnosisResult(
    status=GateStatus.NOT_A_LEAF, confidence=0.1, message_key=MessageKey.NOT_A_LEAF
)


def _services(
    result: DiagnosisResult | Exception = _NOT_A_LEAF,
    readiness: Readiness | Exception = _READY_FAKE,
) -> tuple[Services, _StubDiagnosis]:
    diagnosis = _StubDiagnosis(result)
    return Services(diagnosis=diagnosis, health=_StubHealth(readiness)), diagnosis


def _upload(tmp_path: Path, name: str = "leaf.png") -> str:
    path = tmp_path / name
    path.write_bytes(b"pretend image bytes")
    return str(path)


def test_handler_sends_the_file_bytes_to_the_service(tmp_path: Path) -> None:
    services, diagnosis = _services()
    text = diagnose_upload(services, _upload(tmp_path))
    assert diagnosis.requests[0].image == b"pretend image bytes"
    assert text == message_for(MessageKey.NOT_A_LEAF)


def test_handler_without_a_file_gives_the_no_image_prompt() -> None:
    services, diagnosis = _services()
    assert diagnose_upload(services, None) == message_for(MessageKey.NO_IMAGE)
    assert diagnosis.requests == []


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (InvalidImageError("bad"), MessageKey.INVALID_IMAGE),
        (ImageTooLargeError("big"), MessageKey.IMAGE_TOO_LARGE),
        (NotReadyError("wait"), MessageKey.NOT_READY),
    ],
)
def test_handler_maps_contract_errors_to_friendly_messages(
    tmp_path: Path, error: ContractError, key: MessageKey
) -> None:
    services, _ = _services(error)
    assert diagnose_upload(services, _upload(tmp_path)) == message_for(key)


def test_handler_hides_unexpected_errors_but_logs_them(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    services, _ = _services(RuntimeError("secret internal detail"))
    with caplog.at_level(logging.ERROR):
        text = diagnose_upload(services, _upload(tmp_path))
    assert text == message_for(MessageKey.UNAVAILABLE)
    assert "secret internal detail" not in text
    assert "secret internal detail" in caplog.text
    assert "Traceback" in caplog.text


def test_handler_survives_a_missing_file() -> None:
    services, _ = _services()
    assert diagnose_upload(services, "/no/such/file.png") == message_for(MessageKey.UNAVAILABLE)


def test_uploaded_file_name_never_appears_in_the_output(tmp_path: Path) -> None:
    name = "my-secret-farm-photo-123.png"
    path = _upload(tmp_path, name)
    for outcome in (_NOT_A_LEAF, InvalidImageError("bad"), RuntimeError("boom")):
        services, _ = _services(outcome)
        text = diagnose_upload(services, path)
        assert name not in text
        assert "my-secret-farm-photo" not in text


def test_load_banner_shows_demo_mode_for_a_fake_service() -> None:
    services, _ = _services()
    assert "Demo mode" in load_banner(services)


def test_load_banner_survives_a_broken_health_check() -> None:
    services, _ = _services(readiness=RuntimeError("health down"))
    assert load_banner(services) == message_for(MessageKey.UNAVAILABLE)


def test_build_ui_returns_a_blocks_app_with_the_two_api_endpoints() -> None:
    services, _ = _services()
    demo = build_ui(services)
    assert isinstance(demo, gr.Blocks)
    api_names = {fn.api_name for fn in demo.fns.values()}
    assert {"diagnose", "readiness"} <= api_names
