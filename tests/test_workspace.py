"""Workspace membership and dependency-direction invariants (FND-06, brief B-01).

The contracts layer is a leaf, the backend depends on contracts only, the frontend
depends on contracts only (never on the backend), and the root application project
depends on all three.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTRACTS = "khetsetu-contracts"
BACKEND = "khetsetu-backend"
FRONTEND = "khetsetu-frontend"


def _load(relative: str) -> dict[str, Any]:
    """Parse a ``pyproject.toml`` relative to the repo root."""
    with (REPO_ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def _requirements(pyproject: dict[str, Any]) -> dict[str, Requirement]:
    """Return a project's runtime dependencies keyed by canonical name."""
    raw: list[str] = pyproject["project"].get("dependencies", [])
    parsed = (Requirement(item) for item in raw)
    return {str(canonicalize_name(req.name)): req for req in parsed}


def test_workspace_members_are_the_three_packages() -> None:
    """The uv workspace has exactly backend, contracts and frontend as members."""
    members = set(_load("pyproject.toml")["tool"]["uv"]["workspace"]["members"])
    assert members == {"backend", "contracts", "frontend"}


def test_contracts_depends_on_no_khetsetu_package() -> None:
    """Contracts is a leaf: no dependency whose name starts with ``khetsetu-``."""
    deps = _requirements(_load("contracts/pyproject.toml"))
    assert [name for name in deps if name.startswith("khetsetu-")] == []


def test_backend_depends_on_contracts_not_frontend() -> None:
    """Backend declares contracts and never the frontend."""
    deps = _requirements(_load("backend/pyproject.toml"))
    assert CONTRACTS in deps
    assert FRONTEND not in deps


def test_frontend_depends_on_contracts_not_backend() -> None:
    """Frontend declares contracts and NEVER the backend (B-01)."""
    deps = _requirements(_load("frontend/pyproject.toml"))
    assert CONTRACTS in deps
    assert BACKEND not in deps


def test_root_project_depends_on_all_three_and_is_unpackaged() -> None:
    """The application root depends on every member and is not built as a wheel."""
    root = _load("pyproject.toml")
    deps = _requirements(root)
    assert {CONTRACTS, BACKEND, FRONTEND} <= set(deps)
    assert root["tool"]["uv"]["package"] is False


def test_frontend_pins_gradio_exactly() -> None:
    """Gradio is pinned with ``==`` to 6.30.0 (the Space ``sdk_version`` must equal it)."""
    gradio = _requirements(_load("frontend/pyproject.toml"))["gradio"]
    assert str(gradio.specifier) == "==6.30.0"


def test_backend_bounds_pillow_below_13() -> None:
    """Pillow is bounded ``>=12,<13`` because Gradio 6.30.0 declares ``pillow<13``."""
    pillow = _requirements(_load("backend/pyproject.toml"))["pillow"]
    assert {str(spec) for spec in pillow.specifier} == {">=12", "<13"}
