#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "${SCRIPT_DIR}/aeib-native-runtime" ]; then
    ROOT_PROJECT_DIR="${SCRIPT_DIR}/aeib-native-runtime"
else
    ROOT_PROJECT_DIR="${SCRIPT_DIR}"
fi

GRADLE_BIN=""
if command -v gradle >/dev/null 2>&1; then
    GRADLE_BIN="gradle"
elif [ -x "/opt/homebrew/bin/gradle" ]; then
    GRADLE_BIN="/opt/homebrew/bin/gradle"
elif [ -x "/usr/local/bin/gradle" ]; then
    GRADLE_BIN="/usr/local/bin/gradle"
fi

if [ -z "${JAVA_HOME:-}" ]; then
    if [ -d "/opt/homebrew/opt/openjdk" ]; then
        export JAVA_HOME="/opt/homebrew/opt/openjdk"
        export PATH="${JAVA_HOME}/bin:${PATH}"
    fi
fi

if [ -n "$GRADLE_BIN" ]; then
    exec "$GRADLE_BIN" -p "$ROOT_PROJECT_DIR" "$@"
fi

echo "================================================================================" >&2
echo "AEIB Portable Gradle Wrapper: Gradle binary not located in PATH." >&2
echo "Install Gradle via 'brew install gradle' or execute in GitHub Actions CI runner." >&2
echo "================================================================================" >&2
exit 127
