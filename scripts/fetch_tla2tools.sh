#!/usr/bin/env bash
# Fetch tla2tools.jar (TLA+ tools, includes TLC) and verify its SHA-256 before it is usable.
# This is the ONLY step that touches the network; run it deliberately, never from a gate.
#
# Pin provenance (checked 2026-10-27):
#   * GitHub release API digest for tlaplus/tlaplus tag v1.8.0 asset tla2tools.jar:
#       sha256:78f7e2c6bf9a8b65eda665a23e94431255587e0b43a834a4e2af1723562d9b4a (4503382 bytes)
#   * the file downloaded over TLS matched that digest.
#   * v1.8.0 is marked "prerelease" upstream (published 2026-10-26); the latest stable release
#     is v1.7.4. Trust is "first use over TLS + upstream-published digest", not a signature.
set -euo pipefail

VERSION="v1.8.0"
EXPECTED_SHA256="78f7e2c6bf9a8b65eda665a23e94431255587e0b43a834a4e2af1723562d9b4a"
URL="https://github.com/tlaplus/tlaplus/releases/download/${VERSION}/tla2tools.jar"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/formal/bin/tla2tools.jar"
TMP="$(mktemp "${TMPDIR:-/tmp}/tla2tools.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

mkdir -p "$(dirname "$DEST")"
echo "[fetch] ${URL}"
curl -fsSL --max-time 180 -o "$TMP" "$URL"
ACTUAL="$(shasum -a 256 "$TMP" | awk '{print $1}')"
if [ "$ACTUAL" != "$EXPECTED_SHA256" ]; then
    echo "[FAIL] SHA-256 mismatch (jar not installed)" >&2
    echo "       expected ${EXPECTED_SHA256}" >&2
    echo "       actual   ${ACTUAL}" >&2
    exit 1
fi
mv "$TMP" "$DEST"
chmod 644 "$DEST"
trap - EXIT
echo "[ok] installed ${DEST} sha256=${ACTUAL}"
