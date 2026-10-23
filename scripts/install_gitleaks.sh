#!/usr/bin/env bash
# Install a pinned, checksum-verified gitleaks into .tools/bin/ (gitignored).
#
# Used by developers and by the CI `secrets` job, so both run the same scanner version.
# To bump: look up the newest stable tag (git ls-remote --tags https://github.com/gitleaks/gitleaks),
# change GITLEAKS_VERSION, run this script, then re-run `make secrets`.
set -euo pipefail

# Latest stable release as of 2026-10-23: v8.30.1 (published 2026-03-21).
GITLEAKS_VERSION="8.30.1"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest_dir="${repo_root}/.tools/bin"

os="$(uname -s)"
cpu="$(uname -m)"
case "${os}/${cpu}" in
  Linux/x86_64) platform="linux_x64" ;;
  Darwin/arm64) platform="darwin_arm64" ;;
  Darwin/x86_64) platform="darwin_x64" ;;
  *)
    echo "Unsupported platform ${os}/${cpu}: install gitleaks ${GITLEAKS_VERSION} manually." >&2
    exit 2
    ;;
esac

tarball="gitleaks_${GITLEAKS_VERSION}_${platform}.tar.gz"
checksums="gitleaks_${GITLEAKS_VERSION}_checksums.txt"
base_url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

# GitHub release downloads can stall for minutes on slow links: bound and retry them.
fetch() {
  curl --fail --silent --show-error --location --retry 3 --retry-delay 5 \
    --connect-timeout 30 --max-time 600 --output "$1" "$2"
}
fetch "${tmp_dir}/${tarball}" "${base_url}/${tarball}"
fetch "${tmp_dir}/${checksums}" "${base_url}/${checksums}"

(
  cd "${tmp_dir}"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum --check --ignore-missing "${checksums}"
  else
    # macOS: shasum has no --ignore-missing, so check only the line for our tarball.
    grep " ${tarball}\$" "${checksums}" | shasum -a 256 -c -
  fi
) || {
  echo "Checksum verification FAILED for ${tarball}; refusing to install." >&2
  exit 1
}

mkdir -p "${dest_dir}"
tar -xzf "${tmp_dir}/${tarball}" -C "${tmp_dir}" gitleaks
install -m 0755 "${tmp_dir}/gitleaks" "${dest_dir}/gitleaks"

echo "Installed gitleaks $("${dest_dir}/gitleaks" version) to ${dest_dir}/gitleaks"
