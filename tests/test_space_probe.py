"""Tests for the Space probe tool, using a fake Hub client (no network, no real token)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from scripts import space_probe
from scripts.space_bundle import Packaging
from scripts.space_probe import (
    ProbeOutcome,
    ProbeReport,
    classify_exception,
    cmd_create_space,
    cmd_deploy,
    cmd_llm_probe,
    cmd_smoke,
    cmd_wait,
    cmd_whoami,
    redact,
    status_of,
    write_report,
)

# Built at runtime from fragments so no token-shaped literal exists in the repository.
DUMMY_TOKEN = "hf_" + "Dummy" * 6


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeHubError(Exception):
    def __init__(self, status: int | None, message: str = "boom") -> None:
        super().__init__(message)
        if status is not None:
            self.response = FakeResponse(status)


@dataclass
class FakeRuntime:
    stage: str


@dataclass
class FakeApi:
    """Records calls like HfApi would receive them."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    error: Exception | None = None
    stages: list[str] = field(default_factory=lambda: ["RUNNING"])
    logs: list[str] = field(default_factory=list)
    account: dict[str, Any] = field(default_factory=dict)

    def _record(self, name: str, **kwargs: Any) -> None:
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error

    def whoami(self) -> dict[str, Any]:
        self._record("whoami")
        return self.account

    def create_repo(self, **kwargs: Any) -> None:
        self._record("create_repo", **kwargs)

    def add_space_variable(self, repo_id: str, key: str, value: str) -> None:
        self._record("add_space_variable", repo_id=repo_id, key=key, value=value)

    def upload_folder(self, **kwargs: Any) -> None:
        self._record("upload_folder", **kwargs)

    def get_space_runtime(self, repo_id: str) -> FakeRuntime:
        self._record("get_space_runtime", repo_id=repo_id)
        stage = self.stages.pop(0) if len(self.stages) > 1 else self.stages[0]
        return FakeRuntime(stage)

    def fetch_space_logs(self, repo_id: str, *, build: bool = False) -> list[str]:
        self._record("fetch_space_logs", repo_id=repo_id, build=build)
        return self.logs


# -- Probe 1 ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ProbeOutcome.UNAUTHORIZED),
        (402, ProbeOutcome.PAYMENT_REQUIRED),
        (403, ProbeOutcome.FORBIDDEN),
        (404, ProbeOutcome.NOT_FOUND),
        (429, ProbeOutcome.RATE_LIMITED),
        (500, ProbeOutcome.ERROR),
        (None, ProbeOutcome.ERROR),
    ],
)
def test_exceptions_are_classified_by_status(status: int | None, expected: ProbeOutcome) -> None:
    error = FakeHubError(status)
    assert classify_exception(error) is expected
    assert status_of(error) == status


# -- Probe 2 ------------------------------------------------------------------------
def test_redact_removes_given_secrets_and_token_shaped_text() -> None:
    other = "hf_" + "Other" * 6
    text = f"a {DUMMY_TOKEN} b my-secret c {other}"
    cleaned = redact(text, ["my-secret"])
    assert DUMMY_TOKEN not in cleaned
    assert other not in cleaned
    assert "my-secret" not in cleaned


# -- Probe 3 ------------------------------------------------------------------------
def test_create_space_is_private_gradio_and_idempotent_by_default() -> None:
    api = FakeApi()
    report = cmd_create_space(api, "me/space", "cpu-basic")
    name, kwargs = api.calls[0]
    assert name == "create_repo"
    assert kwargs == {
        "repo_id": "me/space",
        "repo_type": "space",
        "space_sdk": "gradio",
        "space_hardware": "cpu-basic",
        "private": True,
        "exist_ok": True,
    }
    assert report.outcome is ProbeOutcome.OK
    assert report.detail["result"] == "ALLOWED"


def test_create_space_public_needs_the_explicit_flag() -> None:
    api = FakeApi()
    cmd_create_space(api, "me/space", "zero-a10g", public=True)
    assert api.calls[0][1]["private"] is False


def test_create_space_records_the_blocking_status() -> None:
    api = FakeApi(error=FakeHubError(402, "payment required"))
    report = cmd_create_space(api, "me/space", "cpu-basic")
    assert report.outcome is ProbeOutcome.PAYMENT_REQUIRED
    assert report.detail["status"] == 402


# -- Probe 4 ------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is needed to build the bundle")
def test_deploy_builds_uploads_and_sets_only_the_app_env_variable(tmp_path: Path) -> None:
    api = FakeApi()
    report = cmd_deploy(api, "me/space", Packaging.SYSPATH, work_dir=tmp_path / "b")
    names = [name for name, _ in api.calls]
    assert names == ["add_space_variable", "upload_folder"]
    variables = [kwargs for name, kwargs in api.calls if name == "add_space_variable"]
    assert variables == [{"repo_id": "me/space", "key": "KHETSETU_APP_ENV", "value": "space"}]
    upload = dict(api.calls)["upload_folder"]
    assert upload["repo_type"] == "space"
    assert (Path(upload["folder_path"]) / "app.py").is_file()
    assert report.outcome is ProbeOutcome.OK
    assert report.variant == "syspath"


# -- Probe 5 ------------------------------------------------------------------------
def _wait(api: FakeApi, timeout_s: float = 100) -> ProbeReport:
    ticks = iter(range(0, 10_000, 10))
    return cmd_wait(
        api,
        "me/space",
        timeout_s,
        secrets=[DUMMY_TOKEN],
        poll_s=0,
        sleep=lambda _s: None,
        clock=lambda: float(next(ticks)),
    )


def test_wait_returns_when_running() -> None:
    report = _wait(FakeApi(stages=["BUILDING", "RUNNING_BUILDING", "RUNNING"]))
    assert report.outcome is ProbeOutcome.OK
    assert report.detail["stage"] == "RUNNING"


@pytest.mark.parametrize("stage", ["BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"])
def test_wait_stops_early_on_failure_with_redacted_log_tail(stage: str) -> None:
    logs = [f"line {n} {DUMMY_TOKEN}" for n in range(200)]
    report = _wait(FakeApi(stages=["BUILDING", stage], logs=logs))
    assert report.outcome is ProbeOutcome.ERROR
    assert report.detail["stage"] == stage
    tail = report.detail["log_tail"]
    assert len(tail) == 80
    assert tail[-1].startswith("line 199")
    assert DUMMY_TOKEN not in json.dumps(report.detail)


def test_wait_reports_a_timeout() -> None:
    report = _wait(FakeApi(stages=["BUILDING"]), timeout_s=30)
    assert report.outcome is ProbeOutcome.ERROR
    assert report.detail["result"] == "timeout"


# -- Probe 6 ------------------------------------------------------------------------
class FakeGradioClient:
    def __init__(self, banner: str) -> None:
        self.banner = banner
        self.calls: list[str | None] = []

    def predict(self, *args: Any, api_name: str) -> str:
        self.calls.append(api_name)
        return "This looks like: Tomato" if api_name == "/diagnose" else self.banner


def test_smoke_calls_diagnose_and_records_latency_and_demo_mode() -> None:
    client = FakeGradioClient("**Demo mode:** fake service")
    report = cmd_smoke(client)
    assert client.calls == ["/diagnose", "/readiness"]
    assert report.outcome is ProbeOutcome.OK
    assert report.detail["demo_mode"] is True
    assert "latency_s" in report.detail


def test_smoke_without_the_demo_banner_is_not_ok() -> None:
    report = cmd_smoke(FakeGradioClient("something else"))
    assert report.detail["demo_mode"] is False
    assert report.outcome is ProbeOutcome.ERROR


# -- Probe 7 ------------------------------------------------------------------------
@dataclass
class FakeUsage:
    prompt_tokens: int = 12
    completion_tokens: int = 2


@dataclass
class FakeCompletion:
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeLlm:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def chat_completion(self, **kwargs: Any) -> FakeCompletion:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeCompletion()


def test_llm_probe_sends_exactly_one_small_request() -> None:
    llm = FakeLlm()
    report = cmd_llm_probe(llm, "some/model")
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["max_tokens"] == 8
    assert call["stream"] is False
    assert call["model"] == "some/model"
    assert call["messages"] == [{"role": "user", "content": "Reply with the single word: ok"}]
    assert report.outcome is ProbeOutcome.OK
    assert report.detail["prompt_tokens"] == 12


def test_llm_probe_does_not_retry_and_classifies_the_failure() -> None:
    llm = FakeLlm(error=FakeHubError(402))
    report = cmd_llm_probe(llm, "some/model")
    assert len(llm.calls) == 1
    assert report.outcome is ProbeOutcome.PAYMENT_REQUIRED


# -- Probe 8 ------------------------------------------------------------------------
def test_whoami_records_plan_information_but_no_email_or_token() -> None:
    account = {
        "name": "alice",
        "type": "user",
        "isPro": True,
        "email": "alice@example.com",
        "auth": {"accessToken": {"displayName": DUMMY_TOKEN}},
        "orgs": [{"name": "team", "plan": "team", "email": "t@example.com"}],
    }
    report = cmd_whoami(FakeApi(account=account), [DUMMY_TOKEN])
    text = report.model_dump_json()
    assert report.detail["is_pro"] is True
    assert report.detail["orgs"] == [{"name": "team", "plan": "team"}]
    assert "example.com" not in text
    assert DUMMY_TOKEN not in text


# -- Probe 9 ------------------------------------------------------------------------
def test_reports_are_written_with_the_expected_names_and_never_hold_the_token(
    tmp_path: Path,
) -> None:
    leaky = FakeHubError(500, f"failed using {DUMMY_TOKEN}")
    reports = [
        cmd_whoami(FakeApi(account={"name": "a"}), [DUMMY_TOKEN]),
        cmd_create_space(FakeApi(error=leaky), "me/s", "cpu-basic", secrets=[DUMMY_TOKEN]),
        cmd_create_space(FakeApi(), "me/s", "zero-a10g", secrets=[DUMMY_TOKEN]),
        _wait(FakeApi()),
        cmd_smoke(FakeGradioClient("Demo mode")),
        cmd_llm_probe(FakeLlm(error=leaky), "m", secrets=[DUMMY_TOKEN]),
    ]
    names = sorted(write_report(r, tmp_path, [DUMMY_TOKEN]).name for r in reports)
    assert names == [
        "create-space-cpu-basic.json",
        "create-space-zero-a10g.json",
        "llm-probe.json",
        "smoke.json",
        "wait.json",
        "whoami.json",
    ]
    for path in tmp_path.iterdir():
        text = path.read_text(encoding="utf-8")
        assert DUMMY_TOKEN not in text
        data = json.loads(text)
        assert {"command", "outcome", "detail", "started_at"} <= set(data)


def test_deploy_report_name_includes_the_packaging(tmp_path: Path) -> None:
    report = ProbeReport(
        command="deploy", outcome=ProbeOutcome.OK, started_at="now", variant="editable"
    )
    assert write_report(report, tmp_path).name == "deploy-editable.json"


# -- command line -------------------------------------------------------------------
def test_main_without_a_token_exits_2_and_names_it(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    assert space_probe.main(["whoami", "--out", str(isolated_cwd / "out")]) == 2
    assert "HF_TOKEN" in capsys.readouterr().err


def test_main_without_a_space_id_exits_2_and_names_it(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KHETSETU_APP_ENV", "local")
    monkeypatch.setenv("HF_TOKEN", DUMMY_TOKEN)
    assert space_probe.main(["deploy", "--out", str(isolated_cwd / "out")]) == 2
    captured = capsys.readouterr()
    assert "HF_SPACE_ID" in captured.err
    assert DUMMY_TOKEN not in captured.err + captured.out


def test_help_lists_all_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        space_probe.main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for command in ("whoami", "create-space", "deploy", "wait", "smoke", "llm-probe"):
        assert command in out
