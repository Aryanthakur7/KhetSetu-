"""Tests for the Space bundle builder (FND-05, plan 01-06)."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
import yaml

from scripts.space_bundle import (
    REPO_ROOT,
    BundleError,
    Packaging,
    assert_bundle_clean,
    build_bundle,
    locked_version,
    render_space_readme,
)

if TYPE_CHECKING:
    from pathlib import Path

needs_uv = pytest.mark.skipif(
    shutil.which("uv") is None, reason="uv is needed to export requirements"
)


def _front_matter(readme: str) -> dict[str, object]:
    """Parse the YAML header of a Space README."""
    _, header, _body = readme.split("---\n", 2)
    parsed: dict[str, object] = yaml.safe_load(header)
    return parsed


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real bundle (sys.path packaging) built from this repository."""
    if shutil.which("uv") is None:
        pytest.skip("uv is needed to export requirements")
    out_dir = tmp_path_factory.mktemp("bundle") / "space"
    build_bundle(REPO_ROOT, out_dir, Packaging.SYSPATH)
    return out_dir


@needs_uv
def test_bundle_contains_only_the_allow_list(bundle: Path) -> None:
    files = sorted(str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file())
    assert "app.py" in files
    assert "README.md" in files
    assert "requirements.txt" in files
    top_level = {name.split("/")[0] for name in files}
    assert top_level == {
        "app.py",
        "README.md",
        "requirements.txt",
        "contracts",
        "backend",
        "frontend",
    }
    assert not [f for f in files if "/tests/" in f or "__pycache__" in f or f.endswith(".pyc")]
    assert not [f for f in files if f.endswith("pyproject.toml")]
    # The backend data *package* is source code and is allowed; the dataset itself is not.
    assert "backend/src/khetsetu_backend/data/__init__.py" in files
    assert not (bundle / "data").exists()


@needs_uv
def test_readme_header_matches_the_locked_gradio(bundle: Path) -> None:
    header = _front_matter((bundle / "README.md").read_text(encoding="utf-8"))
    assert header["sdk"] == "gradio"
    assert header["app_file"] == "app.py"
    assert header["sdk_version"] == locked_version(REPO_ROOT, "gradio")
    # Must be the *string* 3.12: a bare 3.12 would be read as a float.
    assert header["python_version"] == "3.12"
    assert "python_version: '3.12'" in (bundle / "README.md").read_text(encoding="utf-8")


def test_readme_renders_python_version_as_a_string() -> None:
    header = _front_matter(render_space_readme(sdk_version="1.2.3"))
    assert header["python_version"] == "3.12"
    assert header["sdk_version"] == "1.2.3"


@needs_uv
def test_requirements_are_pinned_without_workspace_packages(bundle: Path) -> None:
    lines = (bundle / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("pillow==12.") for line in lines)
    assert not [line for line in lines if line.startswith(("khetsetu", "./"))]
    assert not [line for line in lines if "--hash" in line]


@needs_uv
def test_editable_packaging_adds_the_package_paths(tmp_path: Path) -> None:
    out_dir = tmp_path / "space"
    build_bundle(REPO_ROOT, out_dir, Packaging.EDITABLE)
    lines = (out_dir / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert {"./contracts", "./backend", "./frontend"} <= set(lines)
    for package in ("contracts", "backend", "frontend"):
        assert (out_dir / package / "pyproject.toml").is_file()


@pytest.mark.parametrize(
    "planted",
    [
        ".env",
        ".env.local",
        "weights/model.safetensors",
        "table.parquet",
        "data/images.txt",
        ".planning/x.md",
        ".claude/x.md",
        ".git/config",
        ".tools/x",
        "build/x",
        "backend/model.bin",
    ],
)
def test_planted_forbidden_file_is_refused(tmp_path: Path, planted: str) -> None:
    target = tmp_path / planted
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")
    with pytest.raises(BundleError):
        assert_bundle_clean(tmp_path)


def test_a_nested_data_package_is_allowed(tmp_path: Path) -> None:
    nested = tmp_path / "backend" / "src" / "khetsetu_backend" / "data"
    nested.mkdir(parents=True)
    (nested / "__init__.py").write_text("", encoding="utf-8")
    assert_bundle_clean(tmp_path)


@needs_uv
def test_same_inputs_give_identical_bytes(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    build_bundle(REPO_ROOT, first, Packaging.SYSPATH)
    build_bundle(REPO_ROOT, second, Packaging.SYSPATH)
    files_a = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
    assert files_a == files_b
    for relative in files_a:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
