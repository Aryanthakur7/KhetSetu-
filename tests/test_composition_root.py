"""FND-06: app.py is the one place where the backend and the frontend meet."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import app

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = "khetsetu_backend"
FRONTEND = "khetsetu_frontend"
# Tests, helper scripts and third-party agent files are not application code.
_IGNORED_PARTS = {"tests", "scripts", ".claude", ".planning", ".venv", "build"}


def _python_files() -> list[Path]:
    """Return the repository's Python files (tracked, or new and not git-ignored)."""
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = [Path(line) for line in listing.stdout.splitlines() if line]
    return [p for p in paths if not _IGNORED_PARTS & set(p.parts) and p.name != "conftest.py"]


def _imported_top_level_packages(path: Path) -> set[str]:
    """Return the top-level package names a Python file imports."""
    tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_only_app_py_imports_both_backend_and_frontend() -> None:
    """Exactly one module wires the two packages together, and it is app.py."""
    files = _python_files()
    assert Path("app.py") in files
    both = [path for path in files if {BACKEND, FRONTEND} <= _imported_top_level_packages(path)]
    assert both == [Path("app.py")]


def test_zerogpu_marker_is_registered_only_when_spaces_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ZeroGPU needs one @spaces.GPU function; elsewhere the helper must do nothing."""
    monkeypatch.setitem(sys.modules, "spaces", None)  # simulates "package not installed"
    assert app.mark_zerogpu_ready() is False

    seen: list[str] = []

    def fake_gpu(func: Callable[[], None]) -> Callable[[], None]:
        seen.append(func.__name__)
        return func

    fake = types.ModuleType("spaces")
    fake.GPU = fake_gpu  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spaces", fake)
    assert app.mark_zerogpu_ready() is True
    assert seen == ["gpu_marker"]
