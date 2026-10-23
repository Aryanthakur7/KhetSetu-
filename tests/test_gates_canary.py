"""Canary tests: prove each quality gate really fails on a planted violation (FND-04).

A gate nobody has seen fail is a hope, not a control. Every test here runs the real tool on a
deliberately bad input and asserts a NON-zero exit, then runs the clean counterpart and asserts
exit 0 so a gate that fails for the wrong reason (or always) is caught too.

Tools are located next to ``sys.executable`` so the tests do not depend on PATH. Nothing here
writes inside the repository: all inputs live under ``tmp_path``. No token-shaped literal exists
in this file; the fake secret is assembled at runtime so the repository's own secret scan stays
clean.
"""

from __future__ import annotations

import os
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.gates

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
GITLEAKS_CONFIG = REPO_ROOT / ".gitleaks.toml"
VENV_BIN = Path(sys.executable).parent

CLEAN_MODULE = '''"""A module that satisfies every gate."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right
'''


def _run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a gate tool without raising on a non-zero exit, capturing text output."""
    # The executable is always a fixed path next to the interpreter or a resolved binary and
    # every argument is a literal or a tmp_path value, so there is no untrusted input.
    return subprocess.run(  # noqa: S603
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )


def _tool(name: str) -> str:
    path = VENV_BIN / name
    assert path.exists(), f"{name} is not installed next to {sys.executable}; run `make sync`"
    return str(path)


# ----------------------------------------------------------------------------- ruff


def test_ruff_check_fails_on_unused_import_and_debug_print(tmp_path: Path) -> None:
    bad = tmp_path / "bad_lint.py"
    bad.write_text("import os\n\n\ndef noisy():\n    print('debug')\n", encoding="utf-8")
    good = tmp_path / "good_lint.py"
    good.write_text(CLEAN_MODULE, encoding="utf-8")

    failed = _run(
        [_tool("ruff"), "check", "--no-cache", "--config", str(PYPROJECT), str(bad)], cwd=tmp_path
    )
    passed = _run(
        [_tool("ruff"), "check", "--no-cache", "--config", str(PYPROJECT), str(good)], cwd=tmp_path
    )

    assert failed.returncode != 0, f"ruff check accepted a bad file:\n{failed.stdout}"
    assert "F401" in failed.stdout, "expected the unused-import rule to fire"
    assert passed.returncode == 0, f"ruff check rejected a clean file:\n{passed.stdout}"


def test_ruff_format_check_fails_on_irregular_formatting(tmp_path: Path) -> None:
    bad = tmp_path / "bad_format.py"
    bad.write_text("x = {  'a':1,'b' :2 }\n", encoding="utf-8")
    good = tmp_path / "good_format.py"
    good.write_text(CLEAN_MODULE, encoding="utf-8")

    failed = _run(
        [_tool("ruff"), "format", "--check", "--no-cache", "--config", str(PYPROJECT), str(bad)],
        cwd=tmp_path,
    )
    passed = _run(
        [_tool("ruff"), "format", "--check", "--no-cache", "--config", str(PYPROJECT), str(good)],
        cwd=tmp_path,
    )

    assert failed.returncode != 0, f"ruff format --check accepted bad formatting:\n{failed.stdout}"
    assert passed.returncode == 0, f"ruff format --check rejected clean code:\n{passed.stdout}"


# ----------------------------------------------------------------------------- mypy


def test_strict_mypy_fails_on_a_type_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad_types.py"
    bad.write_text(
        '"""Bad."""\n\n\ndef number() -> int:\n    """Claim an int, return a str."""\n'
        '    return "not an int"\n',
        encoding="utf-8",
    )
    good = tmp_path / "good_types.py"
    good.write_text(CLEAN_MODULE, encoding="utf-8")
    base = [_tool("mypy"), "--config-file", str(PYPROJECT), "--cache-dir", str(tmp_path / ".mc")]

    failed = _run([*base, str(bad)], cwd=tmp_path)
    passed = _run([*base, str(good)], cwd=tmp_path)

    assert failed.returncode != 0, f"strict mypy accepted a type error:\n{failed.stdout}"
    assert "return-value" in failed.stdout or "incompatible" in failed.stdout.lower()
    assert passed.returncode == 0, f"strict mypy rejected clean code:\n{passed.stdout}"
    assert "Success: no issues found" in passed.stdout


# ------------------------------------------------------------------------ import-linter

PACKAGES = ("khetsetu_contracts", "khetsetu_backend", "khetsetu_frontend")


def _import_tree(root: Path, extra_imports: dict[str, str]) -> None:
    """Build a minimal three-package tree plus the repo's real import-linter config."""
    allowed = {
        # Legitimate edges: the UI may use gradio and contracts; the backend may use contracts.
        "khetsetu_frontend": "import gradio\nimport khetsetu_contracts\n",
        "khetsetu_backend": "import khetsetu_contracts\n",
        "khetsetu_contracts": "import pydantic\n",
    }
    for package in PACKAGES:
        directory = root / package
        directory.mkdir(parents=True)
        body = allowed[package] + extra_imports.get(package, "")
        (directory / "__init__.py").write_text(body, encoding="utf-8")
    shutil.copy(PYPROJECT, root / "pyproject.toml")


def _lint_imports(root: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(root)}
    return _run([_tool("lint-imports")], cwd=root, env=env)


def test_import_linter_accepts_the_legitimate_dependency_edges(tmp_path: Path) -> None:
    _import_tree(tmp_path, {})
    result = _lint_imports(tmp_path)
    assert result.returncode == 0, f"clean tree was rejected:\n{result.stdout}\n{result.stderr}"
    assert "3 kept, 0 broken" in result.stdout


@pytest.mark.parametrize(
    ("violator", "forbidden_import"),
    [
        pytest.param(
            "khetsetu_frontend", "import khetsetu_backend\n", id="frontend-imports-backend"
        ),
        pytest.param(
            "khetsetu_frontend", "import huggingface_hub\n", id="frontend-imports-heavy-dependency"
        ),
        pytest.param(
            "khetsetu_backend", "import khetsetu_frontend\n", id="backend-imports-frontend"
        ),
        pytest.param("khetsetu_backend", "import gradio\n", id="backend-imports-gradio"),
        pytest.param("khetsetu_contracts", "import gradio\n", id="contracts-imports-gradio"),
        pytest.param(
            "khetsetu_contracts", "import khetsetu_backend\n", id="contracts-imports-backend"
        ),
    ],
)
def test_import_linter_fails_on_a_boundary_violation(
    tmp_path: Path, violator: str, forbidden_import: str
) -> None:
    _import_tree(tmp_path, {violator: forbidden_import})
    result = _lint_imports(tmp_path)
    assert result.returncode != 0, f"boundary violation was accepted:\n{result.stdout}"
    assert "BROKEN" in result.stdout, f"expected a BROKEN contract marker:\n{result.stdout}"


# ----------------------------------------------------------------------------- pytest


def test_pytest_fails_on_a_failing_assertion(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert 1 == 2\n", encoding="utf-8")
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (good_dir / "test_good.py").write_text(
        "def test_good():\n    assert 1 == 1\n", encoding="utf-8"
    )
    base = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]

    failed = _run(
        [*base, "--rootdir", str(tmp_path), "-c", str(tmp_path / "pytest.ini")], cwd=tmp_path
    )
    passed = _run(
        [*base, "--rootdir", str(good_dir), "-c", str(good_dir / "pytest.ini")], cwd=good_dir
    )

    assert failed.returncode != 0, f"pytest accepted a failing test:\n{failed.stdout}"
    assert "1 failed" in failed.stdout
    assert passed.returncode == 0, f"pytest rejected a passing test:\n{passed.stdout}"


# --------------------------------------------------------------------------- gitleaks


def _gitleaks_binary() -> str | None:
    local = REPO_ROOT / ".tools" / "bin" / "gitleaks"
    if local.exists():
        return str(local)
    return shutil.which("gitleaks")


def _fake_hf_token() -> str:
    """Return a Hugging Face access-token-shaped string built at runtime from fragments."""
    letters = "".join(secrets.choice(string.ascii_letters) for _ in range(34))
    return "hf" + "_" + letters


def _git(repo: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    git = shutil.which("git")
    assert git is not None
    result = _run(
        [
            git,
            "-c",
            "user.name=canary",
            "-c",
            "user.email=canary@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        env=env,
    )
    assert result.returncode == 0, f"git {args} failed:\n{result.stderr}"


def _scan(binary: str, repo: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            binary,
            "git",
            "--redact",
            "--no-banner",
            "--no-color",
            "--config",
            str(GITLEAKS_CONFIG),
            str(repo),
        ],
        cwd=repo,
    )


def test_gitleaks_history_scan_fails_on_a_planted_token(tmp_path: Path) -> None:
    binary = _gitleaks_binary()
    if binary is None:
        if os.environ.get("CI"):
            pytest.fail("gitleaks is required in CI: run scripts/install_gitleaks.sh")
        pytest.skip("gitleaks not installed; run scripts/install_gitleaks.sh to enable this canary")
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    token = _fake_hf_token()
    dirty = tmp_path / "dirty"
    clean = tmp_path / "clean"
    for repo in (dirty, clean):
        repo.mkdir()
        _git(repo, "init", "-q")
    (dirty / "settings.txt").write_text(f"HF_TOKEN={token}\n", encoding="utf-8")
    (clean / "settings.txt").write_text("HF_TOKEN=\n", encoding="utf-8")
    for repo in (dirty, clean):
        _git(repo, "add", "settings.txt")
        _git(repo, "commit", "-q", "-m", "canary")

    leaked = _scan(binary, dirty)
    untouched = _scan(binary, clean)

    assert leaked.returncode != 0, (
        f"gitleaks missed a planted token:\n{leaked.stdout}{leaked.stderr}"
    )
    assert "leaks found" in leaked.stdout + leaked.stderr
    assert token not in leaked.stdout + leaked.stderr, "--redact must keep the secret out of logs"
    assert untouched.returncode == 0, f"gitleaks flagged a clean repo:\n{untouched.stdout}"
