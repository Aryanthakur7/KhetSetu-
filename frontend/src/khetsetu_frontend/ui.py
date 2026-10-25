"""Gradio user interface; talks to services only through the contracts layer."""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

import gradio as gr

from khetsetu_contracts import ContractError, DiagnosisRequest, MessageKey, Services
from khetsetu_frontend.messages import message_for
from khetsetu_frontend.presenters import (
    render_banner,
    render_error,
    render_no_image,
    render_result,
)

_LOGGER = logging.getLogger(__name__)


def diagnose_upload(services: Services, filepath: str | None) -> str:
    """Diagnose the uploaded file and return Markdown for the result panel.

    Any failure becomes a friendly message. Unexpected errors are logged with their
    traceback on the server, and the farmer only sees the generic "try again" text.
    """
    if filepath is None:
        return render_no_image()
    try:
        request = DiagnosisRequest(image=Path(filepath).read_bytes())
        return render_result(services.diagnosis.diagnose(request))
    except ContractError as error:
        return render_error(error)
    except Exception:
        _LOGGER.exception("diagnosis failed unexpectedly")
        return message_for(MessageKey.UNAVAILABLE)


def load_banner(services: Services) -> str:
    """Return the status banner text for a page load."""
    try:
        return render_banner(services.health.readiness())
    except Exception:
        _LOGGER.exception("readiness check failed")
        return message_for(MessageKey.UNAVAILABLE)


def build_ui(services: Services) -> gr.Blocks:
    """Build the Gradio app bound to the injected ``services`` (no module-level state)."""
    demo = gr.Blocks(title="KhetSetu")
    with demo:
        banner = gr.Markdown()
        gr.Markdown("# KhetSetu\nUpload a photo of a leaf.")
        # gr.File, not gr.Image: gr.Image opens every upload with Pillow before our code
        # runs, so a file that is not a picture would end in Gradio's generic error. With
        # gr.File the service does the checking and can answer with a clear message.
        image = gr.File(label="Leaf photo", file_types=["image"], file_count="single")
        button = gr.Button("Diagnose")
        output = gr.Markdown()
        button.click(
            partial(diagnose_upload, services),
            inputs=image,
            outputs=output,
            api_name="diagnose",
        )
        demo.load(partial(load_banner, services), outputs=banner, api_name="readiness")
    return demo
