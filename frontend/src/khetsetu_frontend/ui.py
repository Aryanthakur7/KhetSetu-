"""Gradio user interface; talks to services only through the contracts layer."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import gradio as gr

from khetsetu_contracts import DiagnosisRequest, Services


def diagnose_upload(services: Services, filepath: str | None) -> str:
    """Diagnose the uploaded file and return Markdown for the result panel."""
    if filepath is None:
        return "Please choose a photo of a leaf first."
    request = DiagnosisRequest(image=Path(filepath).read_bytes())
    result = services.diagnosis.diagnose(request)
    return f"**{result.display_name}**"


def build_ui(services: Services) -> gr.Blocks:
    """Build the Gradio app bound to the injected ``services``."""
    with gr.Blocks(title="KhetSetu") as demo:
        gr.Markdown("# KhetSetu\nUpload a photo of a leaf.")
        image = gr.Image(type="filepath", sources=["upload", "webcam"], label="Leaf photo")
        button = gr.Button("Diagnose")
        output = gr.Markdown()
        button.click(
            partial(diagnose_upload, services),
            inputs=image,
            outputs=output,
            api_name="diagnose",
        )
    return demo
