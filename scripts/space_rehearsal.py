"""Run the Space bundle on this machine the way Hugging Face would, without touching the Hub.

Steps (each one is reported, and the run stops at the first failure):

1. build the bundle with :mod:`scripts.space_bundle`
2. copy ``requirements.txt`` OUTSIDE the bundle (Hugging Face installs from such a copy, so
   relative paths like ``./backend`` cannot work there)
3. create a fresh virtual environment and install ``gradio[oauth,mcp]==<locked version>``
   first, then the copied requirements file (the same order as the Space build)
4. check that no ``khetsetu_*`` package is installed, so the app can only work through the
   ``sys.path`` fallback in ``app.py``
5. start ``python app.py`` with ``KHETSETU_APP_ENV=space`` and a clean environment, and call
   it through the public Gradio client API
6. stop the app and check that no dataset folder appeared

Simplification: installs use ``uv pip`` (fast) instead of plain ``pip``; the dependency set
that ends up installed is what matters, and the real Space build log is compared in plan 01-07.

Usage::

    uv run python -m scripts.space_rehearsal [--packaging syspath|editable] [--json]
        [--work-dir DIR] [--keep]
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from scripts.space_bundle import REPO_ROOT, Packaging, build_bundle, locked_version

if TYPE_CHECKING:
    from collections.abc import Callable

_DETAIL_LIMIT = 400
_WORKSPACE_MODULES = ("khetsetu_contracts", "khetsetu_backend", "khetsetu_frontend")


class RehearsalStep(BaseModel):
    """One step of the rehearsal."""

    model_config = ConfigDict(frozen=True)

    name: str
    ok: bool
    seconds: float
    detail: str


class RehearsalResult(BaseModel):
    """The outcome of a whole rehearsal."""

    ok: bool
    packaging: Packaging
    sdk_version: str
    steps: list[RehearsalStep]
    response_excerpt: str = ""


class _StepFailedError(Exception):
    """Raised inside a step function to mark the step as failed."""


def child_environment(*, home: Path, port: int) -> dict[str, str]:
    """Return the environment for the launched app: small, and free of the developer's setup.

    Nothing is inherited except ``PATH``. In particular no ``HF_*`` token, no
    ``KHETSETU_DATASET_*`` setting, no ``PYTHONPATH`` and no ``VIRTUAL_ENV``.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "KHETSETU_APP_ENV": "space",
        "GRADIO_SERVER_NAME": "127.0.0.1",
        "GRADIO_SERVER_PORT": str(port),
        "GRADIO_ANALYTICS_ENABLED": "False",
        "PYTHONUNBUFFERED": "1",
    }


def _free_port() -> int:
    """Return a TCP port that is free right now (bind to port 0)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _png_bytes() -> bytes:
    """Return a small solid-green PNG (the demo service reads green as a healthy leaf)."""
    from PIL import Image  # noqa: PLC0415 - only needed when a rehearsal actually runs

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (30, 160, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _run(command: list[str], *, cwd: Path, timeout_s: float) -> str:
    """Run a command, returning its output; raise :class:`_StepFailedError` if it fails."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument lists, no shell
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        msg = f"timed out after {timeout_s:.0f}s: {' '.join(command[:4])}"
        raise _StepFailedError(msg) from None
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        msg = f"exit code {done.returncode}: {output[-_DETAIL_LIMIT:]}"
        raise _StepFailedError(msg)
    return output


class _Rehearsal:
    """Holds the state shared by the steps of one rehearsal run."""

    def __init__(
        self, repo_root: Path, work_dir: Path, packaging: Packaging, timeout_s: float
    ) -> None:
        self.repo_root = repo_root
        self.work_dir = work_dir
        self.packaging = packaging
        self.timeout_s = timeout_s
        self.bundle_dir = work_dir / "bundle"
        self.venv_dir = work_dir / "venv"
        self.python = self.venv_dir / "bin" / "python"
        self.sdk_version = locked_version(repo_root, "gradio")
        self.steps: list[RehearsalStep] = []
        self.port = _free_port()
        self.child: subprocess.Popen[bytes] | None = None
        self.log_path = work_dir / "app.log"
        self.response_excerpt = ""

    # -- the steps -----------------------------------------------------------------
    def build(self) -> str:
        report = build_bundle(self.repo_root, self.bundle_dir, self.packaging)
        return f"{len(report.files)} files, sdk_version {report.sdk_version}"

    def copy_requirements(self) -> str:
        shutil.copy2(self.bundle_dir / "requirements.txt", self.work_dir / "requirements.txt")
        return "copied outside the bundle"

    def create_venv(self) -> str:
        return _run(
            ["uv", "venv", "--python", "3.12", str(self.venv_dir)],
            cwd=self.work_dir,
            timeout_s=self.timeout_s,
        )

    def install_gradio(self) -> str:
        spec = f"gradio[oauth,mcp]=={self.sdk_version}"
        _run(
            ["uv", "pip", "install", "--python", str(self.python), spec],
            cwd=self.work_dir,
            timeout_s=self.timeout_s,
        )
        return spec

    def install_requirements(self) -> str:
        # cwd is the work dir (not the bundle): relative paths such as ./backend must fail
        # here exactly as they may on the real Space.
        _run(
            ["uv", "pip", "install", "--python", str(self.python), "-r", "requirements.txt"],
            cwd=self.work_dir,
            timeout_s=self.timeout_s,
        )
        return "requirements.txt installed"

    def pip_check(self) -> str:
        output = _run(
            ["uv", "pip", "check", "--python", str(self.python)],
            cwd=self.work_dir,
            timeout_s=self.timeout_s,
        )
        freeze = _run(
            ["uv", "pip", "freeze", "--quiet", "--python", str(self.python)],
            cwd=self.work_dir,
            timeout_s=self.timeout_s,
        )
        (self.work_dir / "freeze.txt").write_text(freeze + "\n", encoding="utf-8")
        return output.splitlines()[-1] if output else "no conflicts"

    def packages_not_installed(self) -> str:
        code = (
            "import importlib.util as u;"
            f"found=[m for m in {_WORKSPACE_MODULES!r} if u.find_spec(m)];"
            "print(found);raise SystemExit(1 if found else 0)"
        )
        # -I ignores the current directory and PYTHONPATH, so only site-packages counts.
        _run([str(self.python), "-I", "-c", code], cwd=self.work_dir, timeout_s=60)
        return "no khetsetu_* package is installed"

    def launch(self) -> str:
        env = child_environment(home=self.work_dir / "home", port=self.port)
        (self.work_dir / "home").mkdir(exist_ok=True)
        with self.log_path.open("wb") as log:
            self.child = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
                [str(self.python), "app.py"],
                cwd=self.bundle_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        return f"python app.py on port {self.port}"

    def wait_for_page(self) -> str:
        url = f"http://127.0.0.1:{self.port}/"
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if self.child is not None and self.child.poll() is not None:
                msg = f"app exited early ({self.child.returncode}): {self._log_tail()}"
                raise _StepFailedError(msg)
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:  # noqa: PLR2004
                        return "HTTP 200"
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        msg = f"no HTTP 200 within {self.timeout_s:.0f}s: {self._log_tail()}"
        raise _StepFailedError(msg)

    def client_call(self) -> str:
        from gradio_client import Client, handle_file  # noqa: PLC0415 - dev tool, lazy

        image = self.work_dir / "leaf.png"
        image.write_bytes(_png_bytes())
        client = Client(f"http://127.0.0.1:{self.port}", verbose=False)
        try:
            diagnosis = str(client.predict(handle_file(str(image)), api_name="/diagnose"))
            banner = str(client.predict(api_name="/readiness"))
        finally:
            client.close()
        self.response_excerpt = diagnosis[:200]
        if "Demo mode" not in banner or not diagnosis.strip():
            msg = f"unexpected responses: diagnose={diagnosis[:100]!r} readiness={banner[:100]!r}"
            raise _StepFailedError(msg)
        return f"diagnose: {diagnosis[:80]!r}; readiness: {banner[:80]!r}"

    def no_data_directory(self) -> str:
        self.stop()
        if (self.bundle_dir / "data").exists():
            msg = "a data directory appeared inside the bundle"
            raise _StepFailedError(msg)
        return "no data directory was created"

    # -- helpers -------------------------------------------------------------------
    def _log_tail(self) -> str:
        if not self.log_path.exists():
            return ""
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        return text[-_DETAIL_LIMIT:]

    def stop(self) -> None:
        """Stop the app: SIGTERM first, then kill."""
        child = self.child
        if child is None or child.poll() is not None:
            return
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    def run_step(self, name: str, function: Callable[[], str]) -> bool:
        """Run one step, record it, and return whether it passed."""
        started = time.monotonic()
        try:
            detail, ok = function(), True
        except Exception as error:
            detail, ok = f"{type(error).__name__}: {error}", False
        self.steps.append(
            RehearsalStep(
                name=name,
                ok=ok,
                seconds=round(time.monotonic() - started, 2),
                detail=detail[:_DETAIL_LIMIT],
            )
        )
        return ok


def rehearse(
    repo_root: Path, work_dir: Path, packaging: Packaging, timeout_s: float = 240
) -> RehearsalResult:
    """Run the whole rehearsal inside ``work_dir`` and return the result."""
    work_dir = work_dir.resolve()  # the steps run in other directories
    work_dir.mkdir(parents=True, exist_ok=True)
    run = _Rehearsal(repo_root, work_dir, packaging, timeout_s)
    steps: list[tuple[str, Callable[[], str]]] = [
        ("build_bundle", run.build),
        ("copy_requirements_outside_bundle", run.copy_requirements),
        ("create_venv", run.create_venv),
        ("install_gradio_first", run.install_gradio),
        ("install_requirements", run.install_requirements),
        ("pip_check", run.pip_check),
        ("workspace_packages_not_installed", run.packages_not_installed),
        ("launch_app", run.launch),
        ("wait_for_page", run.wait_for_page),
        ("client_call", run.client_call),
        ("no_data_directory", run.no_data_directory),
    ]
    try:
        for name, function in steps:
            if not run.run_step(name, function):
                break
    finally:
        run.stop()  # always clean up the child process, even after a failure
    return RehearsalResult(
        ok=len(run.steps) == len(steps) and all(step.ok for step in run.steps),
        packaging=packaging,
        sdk_version=run.sdk_version,
        steps=run.steps,
        response_excerpt=run.response_excerpt,
    )


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; returns 0 only when the rehearsal passed."""
    parser = argparse.ArgumentParser(description="Rehearse a Space deployment locally.")
    parser.add_argument("--packaging", type=Packaging, choices=list(Packaging), default="syspath")
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--keep", action="store_true", help="keep the work directory")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)
    work_dir: Path = args.work_dir or Path(tempfile.mkdtemp(prefix="khetsetu-rehearsal-"))
    result = rehearse(REPO_ROOT, work_dir, Packaging(args.packaging))
    if args.json:
        sys.stdout.write(result.model_dump_json(indent=2) + "\n")
    else:
        for step in result.steps:
            sys.stdout.write(f"{'ok  ' if step.ok else 'FAIL'} {step.name} ({step.seconds}s)\n")
            if not step.ok:
                sys.stdout.write(f"     {step.detail}\n")
        sys.stdout.write("PASSED\n" if result.ok else "FAILED\n")
    if not args.keep and args.work_dir is None:
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
