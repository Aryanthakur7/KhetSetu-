"""Every sentence the farmer can read, in one place.

The diagnosis screen is English in v1 (Hindi is planned for later). Keeping all text in this
one module means translating later is just swapping this mapping.

Rules for writing messages: short plain sentences, readable on a phone, and no technical
words. The refusal messages must never name a disease.
"""

from __future__ import annotations

from khetsetu_contracts import MessageKey

MESSAGES: dict[MessageKey, str] = {
    MessageKey.DIAGNOSED: "This looks like:",
    MessageKey.LOW_CONFIDENCE: (
        "We are not sure about this photo, so we will not guess. "
        "Please send a clearer photo: one leaf, filling the frame, in daylight, "
        "no flash, and hold the phone steady."
    ),
    MessageKey.NOT_A_LEAF: "This does not look like a leaf. Please take a photo of one plant leaf.",
    MessageKey.UNSUPPORTED_CROP: (
        "This crop is not supported yet, so we cannot say what is wrong with it."
    ),
    MessageKey.INVALID_IMAGE: "We could not read this file. Please upload a photo (JPG or PNG).",
    MessageKey.IMAGE_TOO_LARGE: "This photo is too large. Please upload a smaller photo.",
    MessageKey.NOT_READY: "The service is still starting. Please try again in a minute.",
    MessageKey.UNAVAILABLE: "Something went wrong on our side. Please try again.",
    MessageKey.NO_IMAGE: "Please choose a photo of a leaf first.",
}

DEMO_BANNER = "**Demo mode:** results come from a fake service and are not real diagnoses."
STARTING_BANNER = "The service is starting. Please wait a moment."


def message_for(key: MessageKey) -> str:
    """Return the English text for ``key``."""
    return MESSAGES[key]
