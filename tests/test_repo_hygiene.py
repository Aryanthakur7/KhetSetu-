"""Repository hygiene guards (OPS-03).

Proves with ``git`` itself that datasets, secrets and model weights cannot be
committed by accident, and that root-anchored ignore rules do not hide source
packages such as ``backend/src/khetsetu_backend/data/``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(
    GIT is None or not (REPO_ROOT / ".git").exists(),
    reason="git executable or .git directory not available (for example a source tarball)",
)

MUST_BE_IGNORED = [
    "data/plant_village_classification/data/train-00000-of-00002.parquet",
    "data/anything.txt",
    ".env",
    ".env.local",
    "model.safetensors",
    "weights/best.pt",
    "x.parquet",
    ".cache/huggingface/token",
    "build/space/app.py",
    ".tools/bin/gitleaks",
]

MUST_NOT_BE_IGNORED = [
    ".env.example",
    "uv.lock",
    "pyproject.toml",
    "backend/src/khetsetu_backend/data/ensure.py",
    "backend/src/khetsetu_backend/data/dataset_manifest.json",
    ".planning/STATE.md",
    ".claude/CLAUDE.md",
    "app.py",
    "docs/decisions/0001-hosting-packaging-and-llm-funding.md",
]

FORBIDDEN_SUFFIXES = (".parquet", ".safetensors", ".env")
FORBIDDEN_INDEX_SUFFIXES = (
    ".parquet",
    ".arrow",
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".gguf",
    ".h5",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git`` in the repository root and capture text output."""
    assert GIT is not None  # narrowed by the module-level skipif
    return subprocess.run(  # noqa: S603  # fixed git executable, test-controlled arguments
        [GIT, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_ignored_paths(path: str) -> None:
    """Data, secrets, weights and caches are git-ignored."""
    result = _git("check-ignore", "-q", "--no-index", path)
    assert result.returncode == 0, f"{path} must be ignored"


@pytest.mark.parametrize("path", MUST_NOT_BE_IGNORED)
def test_not_ignored_paths(path: str) -> None:
    """Source, lockfile and planning paths stay trackable."""
    result = _git("check-ignore", "-q", "--no-index", path)
    assert result.returncode == 1, f"{path} must not be ignored"


def test_working_tree_has_no_untracked_data() -> None:
    """The root ``data/`` directory never shows up as untracked."""
    result = _git("status", "--porcelain", "--untracked-files=all")
    assert result.returncode == 0, result.stderr
    offenders = [line for line in result.stdout.splitlines() if line.startswith("?? data/")]
    assert offenders == []


def test_history_never_tracked_data() -> None:
    """No commit in any ref ever touched ``data/``, parquet, safetensors or ``.env`` files."""
    result = _git("log", "--all", "--name-only", "--pretty=format:")
    assert result.returncode == 0, result.stderr
    paths = [line for line in result.stdout.splitlines() if line]
    offenders = [
        path for path in paths if path.startswith("data/") or path.endswith(FORBIDDEN_SUFFIXES)
    ]
    assert offenders == []


def test_index_has_no_forbidden_files() -> None:
    """The index holds no ``.env`` file and no weight or table files."""
    result = _git("ls-files")
    assert result.returncode == 0, result.stderr
    tracked = [line for line in result.stdout.splitlines() if line]
    offenders = [
        path
        for path in tracked
        if Path(path).name == ".env" or path.endswith(FORBIDDEN_INDEX_SUFFIXES)
    ]
    assert offenders == []
