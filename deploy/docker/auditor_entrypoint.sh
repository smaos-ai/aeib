#!/bin/sh
set -e

# deploy/docker/auditor_entrypoint.sh
# =============================================================================
# Offline Auditor Appliance CLI Entrypoint
# =============================================================================

echo "========================================================================"
echo "  AEIB AIR-GAPPED AUDITOR APPLIANCE (OFFLINE MODE)"
echo "========================================================================"

case "$1" in
  self-test)
    echo "[*] Executing offline self-test suite..."
    python3 /opt/aeib/tools/verify_cose_scitt_receipts.py --self-test
    python3 /opt/aeib/compliance/check_zone_boundary.py
    python3 /opt/aeib/compliance/no_mock_enforcer.py
    echo "[✓] All offline verification gates passed successfully."
    ;;
  verify-scitt)
    if [ -z "$2" ]; then
      echo "Usage: verify-scitt <path-to-transparent-statement.scitt.cose>"
      exit 1
    fi
    python3 /opt/aeib/tools/verify_cose_scitt_receipts.py verify-scitt --transparent-statement "$2"
    ;;
  check-boundary)
    python3 /opt/aeib/compliance/check_zone_boundary.py
    ;;
  check-purity)
    python3 /opt/aeib/compliance/no_mock_enforcer.py
    ;;
  *)
    exec "$@"
    ;;
esac
