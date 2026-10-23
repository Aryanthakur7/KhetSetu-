"""Structure assertions on the CI workflow, the Makefile and the pre-commit config (FND-04).

These tests fail if a gate step is removed, an action is not pinned to a commit SHA, a
``pull_request_target`` trigger appears, or the workflow starts referencing a secret. They
read the files as data: nothing here executes a gate (the canary module does that).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
MAKEFILE = REPO_ROOT / "Makefile"
PRE_COMMIT = REPO_ROOT / ".pre-commit-config.yaml"

REQUIRED_JOBS = {"quality", "audit", "secrets"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _workflow() -> dict[Any, Any]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "ci.yml must parse to a mapping"
    return loaded


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML (YAML 1.1) reads the bare key `on` as the boolean True; accept both spellings.
    raw = workflow["on"] if "on" in workflow else workflow[True]
    assert isinstance(raw, dict), "the workflow must declare triggers as a mapping"
    return {str(key): value for key, value in raw.items()}


def _run_lines(job: dict[str, Any]) -> list[str]:
    return [str(step["run"]).strip() for step in job["steps"] if "run" in step]


def test_permissions_are_read_only_and_triggers_are_safe() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}, (
        "top-level permissions must be exactly {contents: read}"
    )
    for name, job in workflow["jobs"].items():
        assert "permissions" not in job, f"job {name!r} must not widen the read-only token"
    triggers = _triggers(workflow)
    assert "push" in triggers, "CI must run on push"
    assert "pull_request" in triggers, "CI must run on pull_request"
    assert "pull_request_target" not in triggers, (
        "pull_request_target runs untrusted code with a privileged token (T-01-07)"
    )


def test_every_external_action_is_pinned_to_a_full_commit_sha() -> None:
    uses = [
        str(step["uses"])
        for job in _workflow()["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]
    assert uses, "expected at least one `uses:` step"
    for reference in uses:
        if reference.startswith("./"):
            continue
        action, _, ref = reference.partition("@")
        assert FULL_SHA.match(ref), f"{action} must be pinned to a 40-hex commit SHA, got {ref!r}"


def test_jobs_are_exactly_the_three_required_checks_and_call_make() -> None:
    jobs = _workflow()["jobs"]
    assert set(jobs) == REQUIRED_JOBS, "branch protection requires exactly quality, audit, secrets"
    quality = _run_lines(jobs["quality"])
    for target in ("make lint", "make type", "make imports", "make test"):
        assert target in quality, f"quality job lost its `{target}` step"
    assert "make audit" in _run_lines(jobs["audit"]), "audit job lost its `make audit` step"
    assert "make secrets" in _run_lines(jobs["secrets"]), "secrets job lost `make secrets`"


def test_workflow_references_no_secret_and_secrets_job_has_full_history() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"\bsecrets\.", text), "CI must not reference the secrets context"
    assert "HF_TOKEN" not in text, "no HF token may reach CI in this phase (T-01-08)"
    assert not re.search(r"\bset -x\b", text), "set -x would echo commands into logs"
    checkout = [
        step
        for step in _workflow()["jobs"]["secrets"]["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert len(checkout) == 1, "the secrets job must check out the repository exactly once"
    assert checkout[0].get("with", {}).get("fetch-depth") == 0, (
        "fetch-depth: 0 is required so old commits are scanned"
    )


def _make_target(name: str) -> list[str]:
    match = re.search(rf"^{re.escape(name)}:(?P<deps>[^#\n]*)", MAKEFILE.read_text(), re.MULTILINE)
    assert match, f"Makefile has no `{name}:` target"
    return match.group("deps").split()


def test_makefile_check_depends_on_every_gate_and_hides_no_failure() -> None:
    deps = _make_target("check")
    for gate in ("lint", "type", "imports", "test"):
        assert gate in deps, f"`make check` must depend on {gate}"
    recipe = [line for line in MAKEFILE.read_text().splitlines() if line.startswith("\t")]
    for line in recipe:
        assert "|| true" not in line, f"recipe hides a failure: {line.strip()}"
        assert not line.startswith("\t-"), f"recipe ignores errors with a - prefix: {line.strip()}"


def test_pre_commit_config_contains_the_required_hooks() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hook_ids = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}
    required = {
        "ruff-check",
        "ruff-format",
        "mypy",
        "lint-imports",
        "gitleaks",
        "check-added-large-files",
        "detect-private-key",
    }
    assert required <= hook_ids, f"pre-commit lost hooks: {sorted(required - hook_ids)}"


def test_pre_commit_external_revs_are_version_tags() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    external = [repo for repo in config["repos"] if repo["repo"] != "local"]
    assert len(external) == 2, "expected the pre-commit-hooks and ruff-pre-commit repos"
    for repo in external:
        rev = str(repo["rev"])
        assert re.fullmatch(r"v\d+(\.\d+)*", rev), (
            f"{repo['repo']}: rev {rev!r} must be a release tag, not a branch"
        )


def test_large_file_hook_enforces_500kb_and_excludes_only_the_lockfile() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}
    large = hooks["check-added-large-files"]
    assert "--maxkb=500" in large["args"], "OPS-03: the limit must be 500 KB"
    assert large["exclude"] == r"^uv\.lock$", "only uv.lock may be excluded from the size limit"
