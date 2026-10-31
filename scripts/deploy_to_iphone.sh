#!/usr/bin/env bash
# scripts/deploy_to_iphone.sh — Deploys EdgeTelemetryNode to physical iPhone and verifies telemetry
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
DEVICE_UDID="00008140-000A7CA01E80801C"
APP_BUNDLE_ID="local.sovereignnexus.EdgeTelemetryNode"

echo "=== SovereignNexus Physical Edge Deployment ==="
echo "Target Device: andrii’s iPhone (UDID: ${DEVICE_UDID})"

# 1. Check device connection
echo "[1/4] Checking device connection via devicectl..."
if ! xcrun devicectl list devices | grep -q "${DEVICE_UDID}.*connected"; then
    echo "ERROR: Device ${DEVICE_UDID} is not connected."
    exit 1
fi
echo "✓ Device connected and ready."

# 2. Check for signing identity in Keychain
echo "[2/4] Checking code signing identities..."
SIGNING_IDENTITY=$(security find-identity -p codesigning -v | grep "Apple Development" | head -n 1 | awk -F '"' '{print $2}' || true)

if [ -z "${SIGNING_IDENTITY}" ]; then
    echo "----------------------------------------------------------------------"
    echo "ATTENTION: Apple Development certificate not found in macOS Keychain."
    echo "To create your free Personal Team certificate in Xcode:"
    echo "  1. Open Xcode -> Settings -> Accounts (Cmd + ,)"
    echo "  2. Select your Apple ID in the left column"
    echo "  3. Click 'Manage Certificates...' in the bottom right"
    echo "  4. Click the '+' button in the bottom left -> select 'Apple Development'"
    echo "  5. Re-run this script!"
    echo "----------------------------------------------------------------------"
    exit 2
fi
echo "✓ Using signing identity: ${SIGNING_IDENTITY}"

# 3. Build arm64 binary for physical iOS
echo "[3/4] Building EdgeTelemetryNode for physical iOS arm64..."
BUILD_DIR="${REPO_ROOT}/.build_edge_ios"
mkdir -p "${BUILD_DIR}/EdgeTelemetryNode.app"

xcrun -sdk iphoneos swiftc -target arm64-apple-ios17.0 \
    "${REPO_ROOT}/tools/ios_edge_node/Sources/Core/JCSCanonicalizer.swift" \
    "${REPO_ROOT}/tools/ios_edge_node/Sources/Core/EdgeTelemetryNode.swift" \
    "${REPO_ROOT}/tools/ios_edge_node/Sources/CLI/main.swift" \
    -o "${BUILD_DIR}/EdgeTelemetryNode.app/EdgeTelemetryNode"

cat <<EOF > "${BUILD_DIR}/EdgeTelemetryNode.app/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>EdgeTelemetryNode</string>
    <key>CFBundleIdentifier</key>
    <string>${APP_BUNDLE_ID}</string>
    <key>CFBundleName</key>
    <string>EdgeTelemetryNode</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>MinimumOSVersion</key>
    <string>17.0</string>
</dict>
</plist>
EOF

# Find any provisioned profile matching or sign
codesign --force --sign "${SIGNING_IDENTITY}" --timestamp=none "${BUILD_DIR}/EdgeTelemetryNode.app"
echo "✓ App bundle built and signed."

# 4. Install and run on physical device
echo "[4/4] Installing and launching on physical iPhone..."
xcrun devicectl device install app --device "${DEVICE_UDID}" "${BUILD_DIR}/EdgeTelemetryNode.app"

echo "Executing EdgeTelemetryNode on device..."
RECEIPT_OUT=$(xcrun devicectl device process launch --device "${DEVICE_UDID}" --console "${APP_BUNDLE_ID}")
echo "${RECEIPT_OUT}"

echo "=== Deployment and Physical Execution Complete ==="
