#!/usr/bin/env bash
# Run the pinned gitleaks over the repository.
#
#   scripts/gitleaks.sh history   scan every commit reachable from HEAD (CI `secrets` job)
#   scripts/gitleaks.sh staged    scan only staged changes (pre-commit hook)
#
# --redact is mandatory: findings must never print secret values to terminals or CI logs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

mode="${1:-}"

if [ -x "${repo_root}/.tools/bin/gitleaks" ]; then
  gitleaks_bin="${repo_root}/.tools/bin/gitleaks"
elif command -v gitleaks >/dev/null 2>&1; then
  gitleaks_bin="$(command -v gitleaks)"
else
  echo "gitleaks not found: run scripts/install_gitleaks.sh" >&2
  exit 3
fi

common_flags=(--redact --no-banner --verbose --config "${repo_root}/.gitleaks.toml")

case "${mode}" in
  history)
    exec "${gitleaks_bin}" git "${common_flags[@]}" "${repo_root}"
    ;;
  staged)
    exec "${gitleaks_bin}" git --pre-commit --staged "${common_flags[@]}" "${repo_root}"
    ;;
  *)
    echo "usage: scripts/gitleaks.sh {history|staged}" >&2
    exit 2
    ;;
esac
