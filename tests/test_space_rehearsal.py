"""Tests for the local Space rehearsal (FND-05, plan 01-06)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts.space_bundle import REPO_ROOT, Packaging
from scripts.space_rehearsal import child_environment, rehearse

if TYPE_CHECKING:
    from pathlib import Path


def test_child_environment_is_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Things the developer's shell may have set must not leak into the rehearsal.
    monkeypatch.setenv("HF_TOKEN", "x")
    monkeypatch.setenv("KHETSETU_DATASET_MODE", "blocking")
    monkeypatch.setenv("PYTHONPATH", "/somewhere")
    monkeypatch.setenv("VIRTUAL_ENV", "/somewhere/venv")
    env = child_environment(home=tmp_path, port=7860)
    assert not [name for name in env if name.startswith(("HF_", "KHETSETU_DATASET_"))]
    assert "PYTHONPATH" not in env
    assert "VIRTUAL_ENV" not in env
    assert env["KHETSETU_APP_ENV"] == "space"
    assert env["GRADIO_SERVER_NAME"] == "127.0.0.1"
    assert env["GRADIO_SERVER_PORT"] == "7860"
    assert env["HOME"] == str(tmp_path)


@pytest.mark.rehearsal
def test_full_rehearsal_runs_the_bundle_like_a_space(tmp_path: Path) -> None:
    """Slow (installs packages from PyPI). Run with `uv run pytest -m rehearsal`."""
    result = rehearse(REPO_ROOT, tmp_path / "work", Packaging.SYSPATH)
    print(json.dumps(result.model_dump(mode="json"), indent=2))  # noqa: T201 - shown on failure
    assert result.ok
    names = {step.name: step for step in result.steps}
    assert names["workspace_packages_not_installed"].ok
    assert "Demo mode" in names["client_call"].detail
    assert not (tmp_path / "work" / "bundle" / "data").exists()
