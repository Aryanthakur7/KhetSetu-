"""Probe the real Hugging Face account: can it host and run the hello-world Space?

Each command does one small job against the live Hub and writes a JSON report under
``build/space-probe/``. Plan 01-07 runs them with a real token. Every function takes the
Hub client as an argument, so the tests pass a fake and nothing here needs a network.

Commands, in the order an operator runs them::

    whoami                        who am I, which plan, which organisations?
    create-space --hardware H     create the Space (PRIVATE unless --public)
    deploy --packaging P          build the bundle and upload it
    wait                          wait until the Space is RUNNING (or failed)
    smoke                         call the running Space like a user would
    llm-probe                     ONE tiny chat call to learn whether the LLM is funded

Fallback ladder (what the operator tries, in order, and how to read the answer):

1. ``create-space --hardware cpu-basic`` (a normal free-CPU Gradio Space).
2. If that is blocked (status 402 or 403 = plan or billing gate), try
   ``create-space --hardware zero-a10g`` (the one Gradio Space type free accounts may get).
3. If both are blocked, use one of the alternatives named in PROJECT.md (a Static Space
   frontend with an external backend, or other hosting) and record the decision.

The token is read from settings only when the real clients are built in :func:`main`; it is
never printed and never written to a report (:func:`redact` is applied to everything).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from khetsetu_backend.config import Settings, SettingsError, load_settings
from scripts.space_bundle import REPO_ROOT, Packaging, build_bundle

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

# The Hub client is only used through a few methods (listed in the command functions), so it
# is typed loosely; the tests pass a small fake with the same methods.
type HubApi = Any
# A gradio_client.Client and an InferenceClient (or the fakes the tests pass in).
type GradioClient = Any
type LlmClient = Any

HARDWARE_CHOICES = ("cpu-basic", "zero-a10g")
EXIT_BAD_CONFIG = 2
LLM_PROMPT = "Reply with the single word: ok"
_LOG_LINES = 80
_STOP_STAGES = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"}
# Shape of a Hugging Face token, so even one we were not told about is hidden.
_TOKEN_SHAPE = re.compile(r"hf_[A-Za-z0-9]{16,}")


class ProbeOutcome(StrEnum):
    """The classified result of one probe."""

    OK = "ok"
    UNAUTHORIZED = "unauthorized"
    PAYMENT_REQUIRED = "payment_required"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


_BY_STATUS = {
    401: ProbeOutcome.UNAUTHORIZED,
    402: ProbeOutcome.PAYMENT_REQUIRED,
    403: ProbeOutcome.FORBIDDEN,
    404: ProbeOutcome.NOT_FOUND,
    429: ProbeOutcome.RATE_LIMITED,
}


class ProbeReport(BaseModel):
    """What one command found. Written to ``build/space-probe/<name>.json``."""

    command: str
    outcome: ProbeOutcome
    detail: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    variant: str | None = None


def status_of(exc: BaseException) -> int | None:
    """Return the HTTP status carried by an exception (``exc.response.status_code``), if any."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def classify_exception(exc: BaseException) -> ProbeOutcome:
    """Map an exception to an outcome using its HTTP status; anything else is ``ERROR``."""
    status = status_of(exc)
    return _BY_STATUS.get(status, ProbeOutcome.ERROR) if status is not None else ProbeOutcome.ERROR


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Replace every given secret, and anything shaped like a token, with ``[redacted]``."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return _TOKEN_SHAPE.sub("[redacted]", text)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _failure(
    command: str, exc: Exception, secrets: Iterable[str], variant: str | None = None
) -> ProbeReport:
    """Build the report for a command whose Hub call raised ``exc``."""
    outcome = classify_exception(exc)
    detail = {
        "status": status_of(exc),
        "error_class": type(exc).__name__,
        "message": redact(str(exc), secrets)[:300],
    }
    return ProbeReport(
        command=command, outcome=outcome, detail=detail, started_at=_now(), variant=variant
    )


def cmd_whoami(api: HubApi, secrets: Iterable[str] = ()) -> ProbeReport:
    """Report the account name, type, PRO flag and organisations (no email, no token)."""
    started = _now()
    try:
        info = api.whoami()
    except Exception as error:
        return _failure("whoami", error, secrets)
    orgs = [{"name": org.get("name"), "plan": org.get("plan")} for org in info.get("orgs") or []]
    detail = {
        "name": info.get("name"),
        "type": info.get("type"),
        "is_pro": bool(info.get("isPro", False)),
        "orgs": orgs,
    }
    return ProbeReport(command="whoami", outcome=ProbeOutcome.OK, detail=detail, started_at=started)


def cmd_create_space(
    api: HubApi,
    space_id: str,
    hardware: str,
    *,
    public: bool = False,
    secrets: Iterable[str] = (),
) -> ProbeReport:
    """Try to create a Gradio Space. Private unless ``public`` is set."""
    started = _now()
    try:
        api.create_repo(
            repo_id=space_id,
            repo_type="space",
            space_sdk="gradio",
            space_hardware=hardware,
            private=not public,
            exist_ok=True,
        )
    except Exception as error:
        return _failure("create-space", error, secrets, variant=hardware)
    detail = {
        "result": "ALLOWED",
        "space_id": space_id,
        "hardware": hardware,
        "private": not public,
    }
    return ProbeReport(
        command="create-space",
        outcome=ProbeOutcome.OK,
        detail=detail,
        started_at=started,
        variant=hardware,
    )


def cmd_deploy(
    api: HubApi,
    space_id: str,
    packaging: Packaging,
    *,
    work_dir: Path | None = None,
    secrets: Iterable[str] = (),
) -> ProbeReport:
    """Build the bundle, set ``KHETSETU_APP_ENV=space`` and upload the folder."""
    started = _now()
    out_dir = work_dir or REPO_ROOT / "build" / "space"
    try:
        bundle = build_bundle(REPO_ROOT, out_dir, packaging)
        # A plain Variable (not a Secret): it is only the word "space". No dataset setting,
        # and no token, is ever put on the Space.
        api.add_space_variable(space_id, "KHETSETU_APP_ENV", "space")
        api.upload_folder(
            repo_id=space_id,
            repo_type="space",
            folder_path=str(bundle.out_dir),
            commit_message=f"Deploy hello-world bundle ({packaging.value} packaging)",
        )
    except Exception as error:
        return _failure("deploy", error, secrets, variant=packaging.value)
    detail = {"space_id": space_id, "files": len(bundle.files), "sdk_version": bundle.sdk_version}
    return ProbeReport(
        command="deploy",
        outcome=ProbeOutcome.OK,
        detail=detail,
        started_at=started,
        variant=packaging.value,
    )


def _log_tail(api: HubApi, space_id: str, stage: str, secrets: Iterable[str]) -> list[str]:
    """Return the last redacted log lines (build log for a build error, else run log)."""
    try:
        lines = [str(line) for line in api.fetch_space_logs(space_id, build=stage == "BUILD_ERROR")]
    except Exception as error:
        return [f"(could not read logs: {type(error).__name__})"]
    return [redact(line, secrets) for line in lines[-_LOG_LINES:]]


def cmd_wait(  # noqa: PLR0913 - the clock and sleep are injectable so tests run instantly
    api: HubApi,
    space_id: str,
    timeout_s: float,
    *,
    secrets: Iterable[str] = (),
    poll_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ProbeReport:
    """Wait until the Space is RUNNING; stop early on a build, runtime or config error."""
    started = _now()
    deadline = clock() + timeout_s
    stage = "UNKNOWN"
    while True:
        try:
            stage = str(api.get_space_runtime(space_id).stage)
        except Exception as error:
            return _failure("wait", error, secrets)
        if stage == "RUNNING":
            return ProbeReport(
                command="wait", outcome=ProbeOutcome.OK, detail={"stage": stage}, started_at=started
            )
        if stage in _STOP_STAGES:
            detail: dict[str, Any] = {
                "stage": stage,
                "log_tail": _log_tail(api, space_id, stage, secrets),
            }
            return ProbeReport(
                command="wait", outcome=ProbeOutcome.ERROR, detail=detail, started_at=started
            )
        if clock() >= deadline:
            detail = {"result": "timeout", "stage": stage, "timeout_s": timeout_s}
            return ProbeReport(
                command="wait", outcome=ProbeOutcome.ERROR, detail=detail, started_at=started
            )
        sleep(poll_s)


def _demo_png() -> bytes:
    """A small green PNG; the demo service reads green as a healthy leaf."""
    from PIL import Image  # noqa: PLC0415 - only needed when smoke actually runs

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (30, 160, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def cmd_smoke(client: GradioClient, *, secrets: Iterable[str] = ()) -> ProbeReport:
    """Upload an image to the running Space and check the demo banner, like a user would."""
    from gradio_client import handle_file  # noqa: PLC0415 - dev tool, imported lazily

    started = _now()
    began = time.monotonic()
    try:
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "leaf.png"
            image.write_bytes(_demo_png())
            diagnosis = str(client.predict(handle_file(str(image)), api_name="/diagnose"))
        banner = str(client.predict(api_name="/readiness"))
    except Exception as error:
        return _failure("smoke", error, secrets)
    detail = {
        "latency_s": round(time.monotonic() - began, 2),
        "demo_mode": "Demo mode" in banner,
        "diagnosis_excerpt": redact(diagnosis[:120], secrets),
    }
    outcome = ProbeOutcome.OK if detail["demo_mode"] and diagnosis.strip() else ProbeOutcome.ERROR
    return ProbeReport(command="smoke", outcome=outcome, detail=detail, started_at=started)


def cmd_llm_probe(llm: LlmClient, model: str, *, secrets: Iterable[str] = ()) -> ProbeReport:
    """Send exactly one tiny chat request (no retry) to see whether the LLM is available."""
    started = _now()
    try:
        response = llm.chat_completion(
            messages=[{"role": "user", "content": LLM_PROMPT}],
            model=model,
            max_tokens=8,
            stream=False,
        )
    except Exception as error:
        return _failure("llm-probe", error, secrets)
    usage = getattr(response, "usage", None)
    detail = {
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }
    return ProbeReport(
        command="llm-probe", outcome=ProbeOutcome.OK, detail=detail, started_at=started
    )


def report_filename(report: ProbeReport) -> str:
    """Return e.g. ``whoami.json`` or ``deploy-syspath.json``."""
    suffix = f"-{report.variant}" if report.variant else ""
    return f"{report.command}{suffix}.json"


def write_report(report: ProbeReport, directory: Path, secrets: Iterable[str] = ()) -> Path:
    """Write the report as JSON (redacted once more as a safety net) and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    text = redact(report.model_dump_json(indent=2), secrets)
    path = directory / report_filename(report)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.space_probe", description="Probe the Hugging Face account."
    )
    # The shared options work before or after the sub-command name.
    parser.add_argument("--space-id", default=None, help="owner/name (default: HF_SPACE_ID)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "build" / "space-probe")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--space-id", default=argparse.SUPPRESS)
    common.add_argument("--out", type=Path, default=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("whoami", parents=[common], help="show account, plan and organisations")
    create = commands.add_parser("create-space", parents=[common], help="create the Space")
    create.add_argument("--hardware", choices=HARDWARE_CHOICES, default="cpu-basic")
    create.add_argument("--public", action="store_true", help="create a PUBLIC Space")
    deploy = commands.add_parser("deploy", parents=[common], help="build and upload the bundle")
    deploy.add_argument("--packaging", choices=[p.value for p in Packaging], default="syspath")
    wait = commands.add_parser("wait", parents=[common], help="wait until the Space runs")
    wait.add_argument("--timeout", type=float, default=900.0, help="seconds")
    commands.add_parser("smoke", parents=[common], help="call the running Space")
    commands.add_parser("llm-probe", parents=[common], help="one tiny LLM request")
    return parser


def _fail_config(message: str) -> int:
    sys.stderr.write(f"{message}\n")
    return EXIT_BAD_CONFIG


def _run_command(
    args: argparse.Namespace, settings: Settings, token: str, space_id: str
) -> ProbeReport:
    """Build the real clients (the only place they exist) and run the chosen command."""
    from huggingface_hub import HfApi, InferenceClient  # noqa: PLC0415 - not needed by tests

    secrets = (token,)
    api = HfApi(token=token)
    if args.command == "whoami":
        return cmd_whoami(api, secrets)
    if args.command == "create-space":
        return cmd_create_space(api, space_id, args.hardware, public=args.public, secrets=secrets)
    if args.command == "deploy":
        return cmd_deploy(api, space_id, Packaging(args.packaging), secrets=secrets)
    if args.command == "wait":
        return cmd_wait(api, space_id, args.timeout, secrets=secrets)
    if args.command == "smoke":
        from gradio_client import Client  # noqa: PLC0415 - dev tool, imported lazily

        client = Client(space_id, token=token, verbose=False)
        try:
            return cmd_smoke(client, secrets=secrets)
        finally:
            client.close()
    return cmd_llm_probe(InferenceClient(token=token), settings.llm_model, secrets=secrets)


def main(argv: list[str] | None = None) -> int:
    """Command line entry point. Exit codes: 0 = ok, 1 = probe failed, 2 = bad configuration."""
    args = _build_parser().parse_args(argv)
    try:
        settings = load_settings()
    except SettingsError as error:
        return _fail_config(str(error))
    if settings.hf_token is None:
        return _fail_config("HF_TOKEN is not set. Put it in your untracked .env file.")
    space_id = args.space_id or settings.hf_space_id
    if args.command not in {"whoami", "llm-probe"} and not space_id:
        return _fail_config(
            "HF_SPACE_ID is not set (owner/name). Pass --space-id or set it in .env."
        )
    token = settings.hf_token.get_secret_value()
    report = _run_command(args, settings, token, space_id or "")
    path = write_report(report, args.out, (token,))
    sys.stdout.write(json.dumps({"report": str(path), "outcome": report.outcome.value}) + "\n")
    return 0 if report.outcome is ProbeOutcome.OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
