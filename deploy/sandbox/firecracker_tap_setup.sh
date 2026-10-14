#!/usr/bin/env bash
# ==============================================================================
# deploy/sandbox/firecracker_tap_setup.sh
# ==============================================================================
# AEIB Milestone 3: Option 3 Firecracker Hypervisor TAP Redirection Setup
#
# Epistemic Notice (AGENTS.md §1 & §5):
#   This script configures a Linux TAP interface and packet redirection rules
#   for Firecracker microVM execution boundaries under the stated model.
#   It requires Linux root / CAP_NET_ADMIN privileges on the host hypervisor.
#   In non-Linux or CI environments, this file serves as structural deployment
#   scaffolding.
# ==============================================================================

set -euo pipefail

TAP_DEV="${TAP_DEV:-tap0}"
TAP_USER="${TAP_USER:-$(id -un)}"
HOST_IP="${HOST_IP:-192.168.100.1}"
GUEST_IP="${GUEST_IP:-192.168.100.2}"
NETMASK="${NETMASK:-24}"
AEIB_PROXY_PORT="${AEIB_PROXY_PORT:-8765}"

echo "=== AEIB Firecracker TAP & Redirection Setup ==="
echo "Host Interface: ${TAP_DEV}"
echo "Host IP:        ${HOST_IP}/${NETMASK}"
echo "Target Proxy:   127.0.0.1:${AEIB_PROXY_PORT}"

# 1. Verify environment prerequisites
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "[!] Non-Linux host detected ($(uname -s)). This script is structural scaffolding for Linux KVM hosts."
    exit 0
fi

if [[ $EUID -ne 0 ]]; then
    echo "[-] Error: This setup script must be executed with root/CAP_NET_ADMIN privileges." >&2
    exit 1
fi

cleanup() {
    echo "[*] Cleaning up TAP device and redirection rules..."
    ip link delete "${TAP_DEV}" 2>/dev/null || true
    if command -v nft >/dev/null 2>&1; then
        nft delete table inet aeib_filter 2>/dev/null || true
    fi
    echo "[+] Cleanup complete."
}

trap cleanup EXIT INT TERM

# 2. Create and configure virtual TAP device
echo "[*] Creating TAP device ${TAP_DEV} for user ${TAP_USER}..."
ip tuntap add dev "${TAP_DEV}" mode tap user "${TAP_USER}"
ip addr add "${HOST_IP}/${NETMASK}" dev "${TAP_DEV}"
ip link set "${TAP_DEV}" up

# 3. Enable loopback redirect sysctl
sysctl -w net.ipv4.conf.all.route_localnet=1 >/dev/null
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# 4. Install fail-closed nftables redirection rules
echo "[*] Installing fail-closed nftables rules for ${TAP_DEV} -> port ${AEIB_PROXY_PORT}..."
if command -v nft >/dev/null 2>&1; then
    nft -f - <<EOF
table inet aeib_filter {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        # Redirect all outbound HTTP/HTTPS from microVM TAP to AEIB Wire Interceptor
        iif "${TAP_DEV}" tcp dport { 80, 443, 8080 } redirect to :${AEIB_PROXY_PORT}
    }

    chain forward {
        type filter hook forward priority filter; policy drop;
        # Deny direct ambient forwarding to host LAN or public internet
        iif "${TAP_DEV}" drop
    }
}
EOF
else
    echo "[*] nftables not found; applying iptables fallback..."
    iptables -t nat -A PREROUTING -i "${TAP_DEV}" -p tcp -m multiport --dports 80,443,8080 -j REDIRECT --to-ports "${AEIB_PROXY_PORT}"
    iptables -A FORWARD -i "${TAP_DEV}" -j DROP
fi

echo "[+] Hypervisor boundary configured successfully."
echo "[+] Traffic from Firecracker guest (${GUEST_IP}) is redirected to 127.0.0.1:${AEIB_PROXY_PORT} fail-closed."
echo "[+] Press Ctrl+C to tear down interface and rules."

# Maintain interface until signal received
sleep infinity
