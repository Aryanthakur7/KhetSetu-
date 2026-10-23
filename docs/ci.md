# Continuous integration and quality gates

This runbook covers how a change is **blocked** unless it passes the quality gates (requirement
FND-04), how secrets are kept out of the repository (FND-02), how the frontend/backend boundary is
enforced (FND-06) and how oversized files are kept out of git (OPS-03).

## The gates

| Gate | Command | What it protects | Where it runs |
| --- | --- | --- | --- |
| ruff lint | `make lint` (`ruff check .`) | bugs, security smells (`S`), missing docs/annotations, stray `print` | local, pre-commit, CI `quality` |
| ruff format | `make lint` (`ruff format --check .`) | one code style, no formatting churn in reviews | local, pre-commit, CI `quality` |
| mypy strict | `make type` | type errors in `contracts/`, `backend/`, `frontend/` and tests | local, pre-commit, CI `quality` |
| import-linter | `make imports` | the frontend/backend/contracts boundary (FND-06, brief decision B-01) | local, pre-commit, CI `quality` |
| pytest + coverage | `make test` | behaviour; coverage floor `fail_under = 80` in `pyproject.toml` | local, CI `quality` |
| pip-audit | `make audit` | known CVEs in the runtime dependency set | CI `audit` |
| gitleaks | `make secrets` | secrets in the full git history (FND-02, T-01-06) | CI `secrets`; staged scan in pre-commit |
| large-file guard | pre-commit `check-added-large-files` | files over 500 KB such as parquet or weights (OPS-03); `uv.lock` is the only exclusion | pre-commit |
| private-key guard | pre-commit `detect-private-key` | PEM and SSH private keys | pre-commit |

The coverage floor is a ratchet: later phases raise `fail_under`, never lower it.

### Import boundaries (`[tool.importlinter]` in `pyproject.toml`)

1. **Frontend depends on contracts only**: `khetsetu_frontend` may not import `khetsetu_backend`,
   `torch`, `transformers`, `huggingface_hub`, `datasets`, `chromadb` or `sentence_transformers`.
2. **Backend has no UI**: `khetsetu_backend` may not import `khetsetu_frontend` or `gradio`.
3. **Contracts is a leaf**: `khetsetu_contracts` is pure pydantic plus the standard library.

## Running locally

```bash
make sync      # uv sync --locked --all-packages
make check     # lint + type + imports + test (what the CI quality job runs)
make secrets   # gitleaks over the whole git history (run scripts/install_gitleaks.sh first)
make audit     # pip-audit over the exported runtime requirements (needs network)
make hooks     # one-time per clone: install the git pre-commit hooks
```

`make help` lists every target. The Makefile is the single source of truth: the workflow calls the
same targets (`make lint`, `make type`, `make imports`, `make test`, `make audit`, `make secrets`)
and holds no command list of its own, so a green `make check` means a green `quality` job.

`make hooks` is a one-time step because installing git hooks writes into `.git/`. After it,
every `git commit` runs ruff, mypy, import-linter, gitleaks on the staged changes, the 500 KB
limit and the hygiene hooks. `git commit --no-verify` skips them locally, which is exactly why the
same checks also run in CI and must be required by branch protection.

## How the workflow is built

`.github/workflows/ci.yml` has three jobs, named exactly as branch protection needs them:

| Job | Steps |
| --- | --- |
| `quality` | checkout, setup-uv, `make sync`, then separate steps `make lint`, `make type`, `make imports`, `make test` |
| `audit` | checkout, setup-uv, `make sync`, `make audit` |
| `secrets` | checkout with `fetch-depth: 0`, `scripts/install_gitleaks.sh`, `make secrets` |

Hardening choices (threats T-01-06 to T-01-09):

- Triggers are `push` to `main` and `pull_request`. `pull_request_target` is never used.
- Top-level `permissions` is `contents: read`; no job widens it.
- Third-party actions are pinned to a full 40-character commit SHA (tag kept in a comment).
- No secret is referenced and none is available: no HF token reaches CI in phase 1. There is no
  `set -x`, and gitleaks runs with `--redact` so a finding never prints the secret.
- The `secrets` job scans the **full history**. The upstream gitleaks pre-commit hook only looks
  at staged changes, so running it in CI would pass on an empty index.

`tests/test_ci_workflow.py` asserts all of the above, so removing a gate step, unpinning an action,
adding `pull_request_target` or referencing a secret fails the build.
`tests/test_gates_canary.py` runs every gate against a planted violation (unused import, bad
formatting, type error, forbidden import, failing test, planted fake token) and against the clean
counterpart. The fake token is assembled at runtime from fragments, so no token-shaped literal
exists in the repository. The gitleaks canary skips with an explicit reason on a machine without
the binary, but fails if the `CI` environment variable is set.

## Branch protection (required, one-time, manual)

"Blocked" is enforced by **branch protection plus the local hooks**, not by the workflow file
alone. A failing check only prevents a merge once GitHub is told the check is required. This is a
repository admin setting, so it is a manual step for the maintainer:

1. Open the repository **Settings -> Branches** (or **Rules -> Rulesets**) and add a rule for
   `main`.
2. Enable **Require status checks to pass before merging** and **Require branches to be up to
   date before merging**.
3. Add the three required checks: **`quality`**, **`audit`** and **`secrets`**. (A check only
   appears in the picker after it has run once, so push a branch and open a pull request first.)
4. Verify: open a pull request containing a deliberate lint error and confirm it cannot be merged.

The first real GitHub Actions run happens when the maintainer pushes; until then the workflow has
been validated structurally and its commands have been run locally through the same Makefile.

## Bumping pinned versions

| What | How |
| --- | --- |
| GitHub Action SHAs | `git ls-remote --tags https://github.com/actions/checkout` (and `astral-sh/setup-uv`). Use the commit shown for the tag (the `^{}` line if the tag is annotated). Update the SHA and the trailing `# vX.Y.Z` comment. |
| gitleaks | Change `GITLEAKS_VERSION` in `scripts/install_gitleaks.sh` (newest stable tag from `git ls-remote --tags https://github.com/gitleaks/gitleaks`), run the script (it verifies the release checksum), then `make secrets`. |
| pre-commit revs | `git ls-remote --tags` for each repo in `.pre-commit-config.yaml`. The ruff rev must match the ruff version locked in `uv.lock`. Every `rev` must stay a version tag, never a branch. |
| uv | `version:` under `setup-uv` in `ci.yml`, plus `required-version` in `pyproject.toml`. |

## Secret scanning policy

- Config: `.gitleaks.toml` extends the default rules (`useDefault = true`).
- Allowlist policy: an allowlist entry must be **narrow** (a path pattern and, where possible, a
  content pattern), justified with a comment in `.gitleaks.toml`, and listed in the table below.
  A finding that looks like a real credential is never allowlisted.
- Current allowlist entries: **none**. The first full-history scan, and a scan of every
  non-ignored working-tree file, found no false positives, so none were needed.

| Path pattern | Content pattern | Reason |
| --- | --- | --- |
| (none) | (none) | (none) |

### If a real secret leaks

1. **Revoke and rotate the credential first** (for a Hugging Face token: Settings -> Access Tokens
   -> invalidate it and create a new one). Assume it is compromised the moment it was pushed.
2. Remove it from the current tree and add the new value only to your local, git-ignored `.env`
   or to Space secrets.
3. Rewriting history (`git filter-repo`) is secondary and does not un-leak a pushed secret; do it
   only after rotation, and coordinate with everyone who has a clone.

`.env` is git-ignored and must stay untracked. A secret inside the ignored `.env` is expected
local state; the scans exist to catch it anywhere it could be committed.

## Handling a `pip-audit` finding

1. Prefer upgrading the vulnerable package within the project's constraints and re-locking
   (`uv lock`, then `make sync` and `make check`).
2. If the version is held back by a constraint (for example the pydantic cap needed by Gradio, see
   `[tool.uv] constraint-dependencies`), check whether a patched release satisfies it.
3. If no fix exists, add a dated, justified ignore to the `pip-audit` call in the Makefile
   (`--ignore-vuln <ID>`) and record it here:

| Vulnerability ID | Package | Date added | Rationale | Review by |
| --- | --- | --- | --- | --- |
| (none) | | | | |

### Open finding at the time of writing (2026-10-24): Pillow 12.3.0

The first `make audit` run reported **35 known vulnerabilities in `pillow 12.3.0`, every one of
them fixed only in Pillow 13.0.0**. Gradio 6.30.0 declares `pillow<13`, so the fix is not
installable under the current pin and no ignore has been added: Pillow decodes farmer-uploaded
photos, so these are not findings to wave through unreviewed. Until the maintainer decides, the
CI `audit` job is expected to be red. The options are:

1. Override Gradio's cap (`override-dependencies = ["pillow>=13"]` under `[tool.uv]`), re-lock and
   smoke-test the Gradio upload path (plans 01-04 and 01-06 exercise it).
2. Record a dated `--ignore-vuln` for each ID in the table above with a rationale (for example,
   the affected decoders are not reachable because uploads are restricted to JPEG/PNG and
   re-encoded) and a review-by date.
3. Wait for a Gradio release that allows Pillow 13.

Whichever is chosen, update this section and the table.
