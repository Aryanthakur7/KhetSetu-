"""Pure functions that turn contract objects into Markdown text.

No Gradio here, so these are trivial to test. They only use the DTO fields and the message
table: no thresholds, no parsing of labels, and the uploaded file name is never shown.
"""

from __future__ import annotations

from khetsetu_contracts import (
    ContractError,
    DiagnosisResult,
    GateStatus,
    MessageKey,
    Readiness,
    ReadyState,
    ServiceMode,
)
from khetsetu_frontend.messages import DEMO_BANNER, STARTING_BANNER, message_for


def render_result(result: DiagnosisResult) -> str:
    """Render a diagnosis; refusals show only guidance, never a disease name."""
    text = message_for(result.message_key)
    if result.status is GateStatus.DIAGNOSED and result.display_name is not None:
        lines = [text, "", f"**{result.display_name}**"]
        if result.crop is not None:
            lines.append(f"Crop: {result.crop}")
        return "\n".join(lines)
    return text


def render_error(error: ContractError) -> str:
    """Render a contract error by its message key (never its exception text)."""
    return message_for(error.message_key)


def render_banner(readiness: Readiness) -> str:
    """Render the status banner shown at the top of the page."""
    lines: list[str] = []
    if readiness.state is ReadyState.LOADING:
        lines.append(STARTING_BANNER)
    elif readiness.state is ReadyState.FAILED:
        lines.append(message_for(MessageKey.UNAVAILABLE))
    if readiness.mode is ServiceMode.FAKE:
        lines.append(DEMO_BANNER)
    return "\n\n".join(lines)


def render_no_image() -> str:
    """Render the prompt shown when the button is pressed with no photo."""
    return message_for(MessageKey.NO_IMAGE)
