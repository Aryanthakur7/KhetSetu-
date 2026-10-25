"""Fake services for the walking skeleton (replaced by real services in later phases).

The fake diagnosis is deterministic and looks only at the average colour of the photo, so
tests and demos can trigger every outcome on purpose. This colour rule is a DEMO rule and
Phase 4 replaces it with the real model and confidence gate:

* very dark image            -> LOW_CONFIDENCE (the farmer should retake the photo)
* mostly green (or a tie)    -> DIAGNOSED (always the same fake disease)
* mostly red                 -> NOT_A_LEAF
* mostly blue                -> UNSUPPORTED_CROP

The image checks (size in bytes, size in pixels, decompression bombs) are the real safety
pattern and are meant to be copied by the real service.
"""

from __future__ import annotations

import io
import warnings

from PIL import Image, ImageStat, UnidentifiedImageError

from khetsetu_contracts import (
    DiagnosisRequest,
    DiagnosisResult,
    GateStatus,
    ImageTooLargeError,
    InvalidImageError,
    MessageKey,
    Readiness,
    ReadyState,
    ScoredLabel,
    ServiceMode,
)

_DARK_LUMA = 50
_SAMPLE_SIZE = (64, 64)
_FAKE_CONFIDENCE = 0.62
_REFUSAL_CONFIDENCE = 0.1


def _mean_rgb(image: Image.Image) -> tuple[float, float, float]:
    """Return the mean red, green and blue of a small copy of ``image``."""
    small = image.convert("RGB")
    small.thumbnail(_SAMPLE_SIZE)
    red, green, blue = ImageStat.Stat(small).mean
    return red, green, blue


def _status_for(red: float, green: float, blue: float) -> GateStatus:
    """Apply the demo colour rule described in the module docstring."""
    luma = 0.299 * red + 0.587 * green + 0.114 * blue
    if luma < _DARK_LUMA:
        return GateStatus.LOW_CONFIDENCE
    if green >= red and green >= blue:
        return GateStatus.DIAGNOSED
    if red >= blue:
        return GateStatus.NOT_A_LEAF
    return GateStatus.UNSUPPORTED_CROP


def _diagnosed() -> DiagnosisResult:
    """Return the one fixed fake diagnosis."""
    return DiagnosisResult(
        status=GateStatus.DIAGNOSED,
        disease_id="Tomato___Late_blight",
        display_name="Tomato - Late blight",
        crop="Tomato",
        confidence=_FAKE_CONFIDENCE,
        top_k=(
            ScoredLabel(
                disease_id="Tomato___Late_blight",
                display_name="Tomato - Late blight",
                score=_FAKE_CONFIDENCE,
            ),
            ScoredLabel(
                disease_id="Tomato___Early_blight",
                display_name="Tomato - Early blight",
                score=0.21,
            ),
            ScoredLabel(
                disease_id="Tomato___Septoria_leaf_spot",
                display_name="Tomato - Septoria leaf spot",
                score=0.08,
            ),
        ),
        message_key=MessageKey.DIAGNOSED,
    )


def _refusal(status: GateStatus, key: MessageKey) -> DiagnosisResult:
    """Return a refusal: no names, no alternatives, low confidence."""
    return DiagnosisResult(status=status, confidence=_REFUSAL_CONFIDENCE, message_key=key)


_REFUSAL_KEYS = {
    GateStatus.LOW_CONFIDENCE: MessageKey.LOW_CONFIDENCE,
    GateStatus.NOT_A_LEAF: MessageKey.NOT_A_LEAF,
    GateStatus.UNSUPPORTED_CROP: MessageKey.UNSUPPORTED_CROP,
}


class FakeDiagnosisService:
    """Deterministic fake: the average colour of the photo decides the outcome."""

    def __init__(self, *, max_upload_bytes: int, max_image_pixels: int) -> None:
        """Remember the upload limits (they come from ``Settings``)."""
        self._max_upload_bytes = max_upload_bytes
        self._max_image_pixels = max_image_pixels

    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        """Check the image safely, then pick an outcome from its colour.

        Raises:
            InvalidImageError: The bytes are not a readable image.
            ImageTooLargeError: Too many bytes, or too many pixels.
        """
        # Cheapest check first: never decode something that is already too big.
        if len(request.image) > self._max_upload_bytes:
            msg = "upload is larger than the byte limit"
            raise ImageTooLargeError(msg)
        # Treat Pillow's "this looks like a decompression bomb" warning as an error.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with Image.open(io.BytesIO(request.image)) as image:
                    # Pixel count is known from the header, before any pixels are decoded.
                    if image.width * image.height > self._max_image_pixels:
                        msg = "image has more pixels than the limit"
                        raise ImageTooLargeError(msg)
                    status = _status_for(*_mean_rgb(image))
            except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
                msg = "image looks like a decompression bomb"
                raise ImageTooLargeError(msg) from error
            except (UnidentifiedImageError, OSError, ValueError) as error:
                msg = "bytes are not a readable image"
                raise InvalidImageError(msg) from error
        if status is GateStatus.DIAGNOSED:
            return _diagnosed()
        return _refusal(status, _REFUSAL_KEYS[status])


class FakeHealthService:
    """Always ready, and always says it is a fake."""

    def __init__(self, *, version: str) -> None:
        """Remember the backend version to report."""
        self._version = version

    def readiness(self) -> Readiness:
        """Report READY in FAKE mode."""
        return Readiness(state=ReadyState.READY, mode=ServiceMode.FAKE, version=self._version)
