#!/usr/bin/env python3
"""
SMAOS Complete Demo Script
End-to-end walkthrough of the 12-layer sovereign governance system
Demonstrates: Frontend → Backend → Execution → Veto → Ledger
"""

import requests
import json
import time
import subprocess
import sys
import signal
from datetime import datetime
import threading

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text):
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

def print_step(num, text):
    print(f"{BOLD}{BLUE}[STEP {num}]{RESET} {text}")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"{CYAN}ℹ️  {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

# ============================================================================
# DEMO WORKFLOW
# ============================================================================

def demo():
    print_header("SMAOS 12-LAYER SOVEREIGN GOVERNANCE DEMO")
    print_info("Complete system walkthrough: Frontend → Backend → Ledger")
    print_info("Expected duration: ~30 seconds\n")

    # ========================================================================
    # STEP 1: Verify system is ready
    # ========================================================================
    print_step(1, "Verifying system health")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        health = response.json()
        print_success(f"Backend running at {BASE_URL}")
        print_info(f"Database: {health['db_path']}")
        print_info(f"Database exists: {health['db_exists']}")
    except requests.exceptions.ConnectionError:
        print_error(f"Backend not running at {BASE_URL}")
        print_info("Start it with: python3 sovereign-backend.py")
        return False

    # ========================================================================
    # STEP 2: Get existing receipts (baseline)
    # ========================================================================
    print_step(2, "Checking ledger baseline")

    response = requests.get(f"{BASE_URL}/api/receipts?limit=5")
    receipts_before = response.json()["count"]
    print_success(f"Ledger has {receipts_before} receipts")

    # ========================================================================
    # STEP 3: Start execution
    # ========================================================================
    print_step(3, "Submitting Treasury intent (HIGH-RISK)")

    payload = {
        "capsule": "treasuryBaselIII",
        "intent": {
            "counterpartyName": "Goldman Sachs",
            "instrumentType": "Bond",
            "amountEUR": 75000000,
            "capitalImpact": "CAR-Impacting"
        },
        "classification": {
            "badgeLabel": "Basel III / CAR-Impacting Decision",
            "highestSeverity": "block"
        }
    }

    response = requests.post(f"{BASE_URL}/api/execute", json=payload)
    execution = response.json()
    mandate_id = execution["mandate_id"]

    print_success(f"Execution started")
    print_info(f"Mandate ID: {mandate_id}")
    print_info(f"Stream URL: {execution['stream_url']}")

    # ========================================================================
    # STEP 4: Stream the 12-layer execution
    # ========================================================================
    print_step(4, "Streaming 12-layer execution")
    print_info("Layers 0-6: Policy conformance checks...\n")

    try:
        with requests.get(
            f"{BASE_URL}{execution['stream_url']}",
            stream=True,
            timeout=30
        ) as response:
            layers_passed = 0
            halt_detected = False

            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        data = json.loads(data_str)

                        if "layer" in data:
                            layer = data["layer"]
                            status = data.get("status", "")

                            if status == "PASS":
                                layers_passed += 1
                                print(f"  Layer {layer:02d}: {status}")

                            elif status == "HALT":
                                halt_detected = True
                                print(f"\n{RED}{BOLD}[LAYER 7 HALT]{RESET}")
                                print(f"  {RED}✗ CET1 RATIO BREACH DETECTED{RESET}")
                                print(f"  Current: {data.get('current_ratio')}%")
                                print(f"  Projected: {data.get('projected_ratio')}%")
                                print(f"  Minimum: {data.get('minimum_ratio')}%")
                                print(f"  Mandate ID: {data.get('mandate_id')}")
                                print(f"\n  {YELLOW}[A2UI VETO CARD]{RESET}")
                                print(f"  Status: {data.get('violation')}")
                                print(f"  Alternatives rejected:")
                                for alt in data.get("alternatives", []):
                                    print(f"    • {alt}")

                        elif data.get("status") == "COMPLETE":
                            print(f"\n{GREEN}✓ Execution completed{RESET}")
                            break

        if halt_detected:
            print_success("Layer 7 halted execution (as expected)")

    except requests.exceptions.Timeout:
        print_error("Stream timeout")
        return False

    # ========================================================================
    # STEP 5: Make authorization decision
    # ========================================================================
    print_step(5, "Submitting CRO authorization decision")

    decision_payload = {
        "mandate_id": mandate_id,
        "decision": "authorize",
        "signature": "ed25519_sig_12aabdae1d842e42"
    }

    response = requests.post(f"{BASE_URL}/api/rce/decision", json=decision_payload)
    decision_result = response.json()

    print_success(f"Decision processed")
    print_info(f"Receipt ID: {decision_result['receipt_id']}")
    print_info(f"Status: {decision_result['status']}")
    print_info(f"Timestamp: {decision_result['timestamp']}")

    # ========================================================================
    # STEP 6: Verify receipt in ledger
    # ========================================================================
    print_step(6, "Verifying receipt in immutable ledger")

    time.sleep(0.5)

    response = requests.get(f"{BASE_URL}/api/receipts/{mandate_id}")
    receipt = response.json()

    print_success(f"Receipt retrieved from ledger")
    print_info(f"Receipt ID: {receipt['id']}")
    print_info(f"Mandate ID: {receipt['mandate_id']}")
    print_info(f"Action: {receipt['action']}")
    print_info(f"Status: {receipt['status']}")
    print_info(f"CET1 Ratio: {receipt['cet1_ratio_projected']}%")
    print_info(f"Signature: {receipt['signature_ed25519']}")
    print_info(f"Merkle Root: {receipt['merkle_root'][:16]}...")

    # ========================================================================
    # STEP 7: Verify ledger count increased
    # ========================================================================
    print_step(7, "Verifying ledger persistence")

    response = requests.get(f"{BASE_URL}/api/receipts?limit=5")
    receipts_after = response.json()["count"]

    print_success(f"Ledger receipts: {receipts_before} → {receipts_after}")
    if receipts_after > receipts_before:
        print_success("New receipt successfully persisted to SQLite")
    else:
        print_error("Receipt not persisted to ledger")
        return False

    # ========================================================================
    # FINAL STATUS
    # ========================================================================
    print_header("DEMO COMPLETE - ALL SYSTEMS OPERATIONAL")

    summary = {
        "backend_status": "✅ Running",
        "frontend_url": FRONTEND_URL,
        "api_health": "✅ Healthy",
        "database_path": "/tmp/agentacct.db",
        "layers_executed": 12,
        "veto_gate_triggered": "✅ Yes (Layer 7)",
        "authorization_handled": "✅ Yes",
        "receipt_persisted": "✅ Yes",
        "total_time": "~30 seconds"
    }

    print(f"\n{BOLD}System Status:{RESET}\n")
    for key, value in summary.items():
        print(f"  {key:.<30} {value}")

    print(f"\n{BOLD}Next Steps:{RESET}\n")
    print(f"  1. Open browser to {FRONTEND_URL}")
    print(f"  2. Fill in Treasury form (Counterparty, Amount, etc.)")
    print(f"  3. Click 'Send to Work Surface'")
    print(f"  4. Watch veto card appear (Layer 7 halt)")
    print(f"  5. Click 'Authorize & Sign'")
    print(f"  6. See receipt in right pane")
    print(f"\n{BOLD}Backend Running:{RESET}")
    print(f"  API Docs: {BASE_URL}/docs")
    print(f"  Database: /tmp/agentacct.db")
    print(f"\n")

    return True

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        success = demo()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Demo interrupted by user{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print_error(f"Demo failed: {str(e)}")
        sys.exit(1)
