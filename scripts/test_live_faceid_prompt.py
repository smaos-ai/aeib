#!/usr/bin/env python3
"""Interactive test script for Live iPhone 16 Pro Max FaceID Notary Gate.

Connects to the iPhone running EdgeTelemetryApp over USB-C Ethernet or Wi-Fi,
presents a T3 Irreversible Action Proposal on the iPhone screen,
and waits for biometric approval or operator veto.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.iphone_enclave_notary_bridge import (
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
)
from src.iphone_rpc_client import IPhoneNotaryRPCClient


def run_live_test(host: str = "andriis-iphone.local", port: int = 8080) -> int:
    print("=" * 70)
    print("   SOVEREIGN NEXUS: A18 PRO SECURE ENCLAVE BIOMETRIC NOTARY TEST")
    print("=" * 70)
    print(f"Connecting to iPhone at {host}:{port}...")

    client = IPhoneNotaryRPCClient(iphone_host=host, port=port)

    # 1. Fetch hardware Enclave public key
    try:
        enclave_pubkey_hex = client.fetch_enclave_pubkey_hex(timeout_sec=5)
        client.pinned_pubkey_hex = enclave_pubkey_hex
        print(f"✓ Connected to iPhone Secure Enclave!")
        print(f"  Hardware P-256 Public Key: {enclave_pubkey_hex[:32]}...{enclave_pubkey_hex[-16:]}")
    except Exception as e:
        print(f"FAILED to reach iPhone at {host}:{port}: {e}")
        print("Fallback tip: Ensure iPhone is unlocked and EdgeTelemetryApp is open.")
        return 1

    # 2. Prepare T3 Action Proposal
    expires_at = int(time.time()) + 120
    proposal = T3ActionProposal(
        action_type="T3_EXECUTE_IRREVERSIBLE_SETTLEMENT",
        amount_minor=5000000,  # $50,000.00
        attempt_fence=1,
        expires_at_epoch_sec=expires_at,
        intent_caid="sha256:4f53997781b49a5628de0b2e8ca92e4e1a06ae1540f2ee8d0cfa6deea1ab046e",
        operation_id=f"op_live_{int(time.time())}",
        target_resource="treasury_escrow_alpha",
    )

    print("\n----------------------------------------------------------------------")
    print("Dispatching T3 Irreversible Action Proposal to iPhone:")
    print(f"  • Action Type:      {proposal.action_type}")
    print(f"  • Target Resource:  {proposal.target_resource}")
    print(f"  • Amount:           ${proposal.amount_minor / 100:.2f}")
    print(f"  • Operation ID:     {proposal.operation_id}")
    print(f"  • Expires In:       120 seconds")
    print("----------------------------------------------------------------------")
    print(">>> LOOK AT YOUR IPHONE SCREEN NOW! <<<")
    print("The T3 Approval Sheet should appear on your phone.")
    print("  - Tap [APPROVE WITH A18 PRO FACEID] and scan face to approve.")
    print("  - OR tap [VETO & HALT OPERATION] to trigger emergency kill.")
    print("----------------------------------------------------------------------\n")

    start_time = time.time()
    try:
        verdict = client.request_faceid_warrant(proposal, timeout_sec=120)
        elapsed = time.time() - start_time

        if verdict.latch_released:
            print(f"\n✓ BIOMETRIC FACEID WARRANT RECEIVED & VERIFIED from A18 Pro SEP in {elapsed:.2f}s!")
            print(f"  • Verified Proposal CAID: {verdict.verified_proposal_caid}")
            print(f"  • Warrant Receipt CAID:   {verdict.warrant_receipt_caid}")
            print(f"  • Reason Code:            {verdict.reason_code}")
            print("\n======================================================================")
            print("  SUCCESS: T3 EXECUTION LATCH CRYPTOGRAPHICALLY RELEASED!")
            print("  Biometric non-repudiation anchored to physical A18 Pro silicon.")
            print("======================================================================")
            return 0
        elif verdict.refusal_reason == "HALT_HUMAN_VETOED_ON_IPHONE":
            print(f"\n🛑 OPERATOR VETO TRIGGERED ON IPHONE ({elapsed:.2f}s)!")
            print("   The operation was explicitly vetoed by the human operator.")
            print("   T3 Execution Latch remained LOCKED. Zero funds transmitted.")
            return 0
        elif verdict.refusal_reason == "HALT_IPHONE_FACEID_TIMEOUT":
            print(f"\n⏱️ TIMEOUT: No biometric input received within deadline ({elapsed:.2f}s).")
            print("   T3 Execution Latch timed out and remained locked.")
            return 3
        else:
            print(f"\n❌ LATCH VERIFICATION REFUSED ({elapsed:.2f}s): {verdict.refusal_reason}")
            return 2

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR during warrant request ({elapsed:.2f}s): {e}")
        return 4


if __name__ == "__main__":
    host_arg = sys.argv[1] if len(sys.argv) > 1 else "169.254.252.8"
    sys.exit(run_live_test(host=host_arg))
