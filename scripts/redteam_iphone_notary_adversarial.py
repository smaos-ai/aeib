#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
scripts/redteam_iphone_notary_adversarial.py
================================================================================
Adversarial Red-Team Verification Probe Suite for Apple Silicon Biometric Notary.

Evaluated under the stated model (A18 Pro Secure Enclave + Mac M3 Pro verifier).
Enforces zero-mock real cryptography (SECP256R1 and Ed25519).
Validates resistance against:
  Probe 1: WYSIWYS Bait-and-Switch Payload Alteration
  Probe 2: Replay of Expired Biometric Warrant
  Probe 3: Forged Public Key Injection (Unpinned Hardware Key)
  Probe 4: 1-Byte Corrupted DER Signature Tamper
  Probe 5: Operator Human VETO Fail-Closed Latch Halt

Each probe evaluates both an adversarial probe (must be DEFENDED) and a
positive control (must be HELD/SUCCESSFUL). If the positive control fails,
the probe is marked INCONCLUSIVE.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.eo1_biometric_gate import (
    BiometricEO1InterlockAdapter,
    BiometricGatePolicy,
    BiometricHumanVetoError,
    BiometricVerificationFailedError,
)
from src.eo1_write_before_execute import PreDispatchIntentInterlock, compute_caid
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    sha256_jcs_caid,
)
from src.iphone_rpc_client import IPhoneNotaryRPCClient
from src.jcs_canonicalizer import encode_jcs


def _generate_real_p256_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    """Generates a real SECP256R1 keypair and returns (private_key, x963_hex)."""
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return priv, pub_bytes.hex()


def _build_warrant(
    priv_key: ec.EllipticCurvePrivateKey,
    pub_hex: str,
    proposal: T3ActionProposal,
) -> EnclaveSignedWarrant:
    """Signs canonical proposal bytes with real SECP256R1 ECDSA."""
    canonical_bytes = proposal.to_canonical_jcs_bytes()
    caid = sha256_jcs_caid(canonical_bytes)
    sig_der = priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))
    return EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_bytes.decode("utf-8"),
        payload_sha256_caid=caid,
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )


def probe_1_wysiwys_payload_alteration() -> Tuple[bool, str]:
    """Probe 1: WYSIWYS Bait-and-Switch Payload Alteration."""
    priv, pub_hex = _generate_real_p256_keypair()

    proposal_original = T3ActionProposal(
        action_type="T3_READ_SYSTEM_LOGS",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=2000000000,
        intent_caid="caid_orig",
        operation_id="op_orig",
        target_resource="https://internal/logs",
    )
    warrant = _build_warrant(priv, pub_hex, proposal_original)

    # Attack: Attacker presents a different malicious proposal with the warrant from proposal_original
    proposal_malicious = T3ActionProposal(
        action_type="T3_DROP_PRODUCTION_DATABASE",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=2000000000,
        intent_caid="caid_malicious",
        operation_id="op_orig",
        target_resource="https://internal/db/drop",
    )

    attack_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal_malicious,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1900000000,
    )
    adversary_defended = (
        not attack_verdict.latch_released
        and attack_verdict.reason_code == "HALT_WYSIWYS_PAYLOAD_MISMATCH"
    )

    # Positive control: Untampered proposal must succeed
    control_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal_original,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1900000000,
    )
    control_passed = (
        control_verdict.latch_released
        and control_verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    )

    if not control_passed:
        return False, "INCONCLUSIVE: Positive control failed"
    return adversary_defended, "DEFENDED (Bait-and-switch rejected by WYSIWYS payload mismatch)"


def probe_2_replay_expired_warrant() -> Tuple[bool, str]:
    """Probe 2: Replay of Expired Biometric Warrant."""
    priv, pub_hex = _generate_real_p256_keypair()

    proposal = T3ActionProposal(
        action_type="T3_SETTLE_PAYMENT",
        amount_minor=100000,
        attempt_fence=1,
        expires_at_epoch_sec=1000,
        intent_caid="caid_replay",
        operation_id="op_replay",
        target_resource="https://internal/pay",
    )
    warrant = _build_warrant(priv, pub_hex, proposal)

    # Attack: Replaying after expiry (current epoch 1005 > 1000)
    attack_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1005,
    )
    adversary_defended = (
        not attack_verdict.latch_released
        and attack_verdict.reason_code == "HALT_FACEID_WARRANT_EXPIRED"
    )

    # Positive control: Unexpired warrant must succeed (current epoch 995 < 1000)
    control_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=995,
    )
    control_passed = (
        control_verdict.latch_released
        and control_verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    )

    if not control_passed:
        return False, "INCONCLUSIVE: Positive control failed"
    return adversary_defended, "DEFENDED (Expired warrant rejected fail-closed)"


def probe_3_unpinned_key_forgery() -> Tuple[bool, str]:
    """Probe 3: Forged Public Key Injection (Unpinned Hardware Key)."""
    legit_priv, legit_pub_hex = _generate_real_p256_keypair()
    forger_priv, forger_pub_hex = _generate_real_p256_keypair()

    proposal = T3ActionProposal(
        action_type="T3_TRANSFER_ESCROW",
        amount_minor=500000,
        attempt_fence=1,
        expires_at_epoch_sec=2000,
        intent_caid="caid_key",
        operation_id="op_key",
        target_resource="https://internal/escrow",
    )
    # Attack: Warrant signed with forger key
    forged_warrant = _build_warrant(forger_priv, forger_pub_hex, proposal)

    attack_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=forged_warrant,
        pinned_enclave_pubkey_x963_hex=legit_pub_hex,
        current_epoch_sec=1500,
    )
    adversary_defended = (
        not attack_verdict.latch_released
        and attack_verdict.reason_code == "HALT_UNRECOGNIZED_ENCLAVE_PUBLIC_KEY"
    )

    # Positive control: Legitimate warrant signed with pinned key must succeed
    legit_warrant = _build_warrant(legit_priv, legit_pub_hex, proposal)
    control_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=legit_warrant,
        pinned_enclave_pubkey_x963_hex=legit_pub_hex,
        current_epoch_sec=1500,
    )
    control_passed = (
        control_verdict.latch_released
        and control_verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    )

    if not control_passed:
        return False, "INCONCLUSIVE: Positive control failed"
    return adversary_defended, "DEFENDED (Unpinned public key rejected fail-closed)"


def probe_4_corrupted_der_signature() -> Tuple[bool, str]:
    """Probe 4: 1-Byte Corrupted DER Signature Tamper."""
    priv, pub_hex = _generate_real_p256_keypair()

    proposal = T3ActionProposal(
        action_type="T3_EXECUTE_SWAP",
        amount_minor=300000,
        attempt_fence=1,
        expires_at_epoch_sec=2000,
        intent_caid="caid_sig",
        operation_id="op_sig",
        target_resource="https://internal/swap",
    )
    warrant = _build_warrant(priv, pub_hex, proposal)

    # Attack: Bit-flip 1 byte of the DER signature
    sig_raw = list(bytes.fromhex(warrant.signature_der_hex))
    sig_raw[4] ^= 0xFF
    tampered_sig_hex = bytes(sig_raw).hex()

    tampered_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=warrant.canonical_payload_utf8,
        payload_sha256_caid=warrant.payload_sha256_caid,
        public_key_x963_hex=warrant.public_key_x963_hex,
        signature_der_hex=tampered_sig_hex,
        algorithm=warrant.algorithm,
    )

    attack_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=tampered_warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1500,
    )
    adversary_defended = (
        not attack_verdict.latch_released
        and attack_verdict.reason_code == "HALT_ENCLAVE_SIGNATURE_INVALID"
    )

    # Positive control: Unmodified signature must succeed
    control_verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1500,
    )
    control_passed = (
        control_verdict.latch_released
        and control_verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    )

    if not control_passed:
        return False, "INCONCLUSIVE: Positive control failed"
    return adversary_defended, "DEFENDED (Corrupted DER signature rejected by ECDSA verifier)"


def probe_5_operator_human_veto() -> Tuple[bool, str]:
    """Probe 5: Operator Human VETO (Immediate Kill Latch)."""
    priv, pub_hex = _generate_real_p256_keypair()

    class DynamicHandler(BaseHTTPRequestHandler):
        veto: bool = False

        def do_GET(self):
            if self.path == "/pubkey":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(pub_hex)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(pub_hex.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/approve":
                if self.veto:
                    body = b'{"error":"HALT_HUMAN_VETOED_ON_IPHONE"}'
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                length = int(self.headers.get("Content-Length", 0))
                payload = self.rfile.read(length)
                caid = sha256_jcs_caid(payload)
                sig = priv.sign(payload, ec.ECDSA(hashes.SHA256()))
                resp = json.dumps({
                    "canonical_payload_utf8": payload.decode("utf-8"),
                    "payload_sha256_caid": caid,
                    "public_key_x963_hex": pub_hex,
                    "signature_der_hex": sig.hex(),
                    "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), DynamicHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger_path = Path(tmp_dir) / "veto.ledger"
        interlock = PreDispatchIntentInterlock(
            ledger_path=ledger_path,
            boundary_private_key=Ed25519PrivateKey.generate(),
        )
        rpc_client = IPhoneNotaryRPCClient(
            iphone_host="127.0.0.1",
            port=port,
            pinned_enclave_pubkey_x963_hex=pub_hex,
        )
        adapter = BiometricEO1InterlockAdapter(
            interlock=interlock,
            notary_client=rpc_client,
            policy=BiometricGatePolicy(timeout_sec=5),
        )

        # Test VETO condition
        DynamicHandler.veto = True
        vetoed = False
        dispatched_on_veto = False

        def _bad_dispatch():
            nonlocal dispatched_on_veto
            dispatched_on_veto = True

        try:
            adapter.dispatch_guarded(
                target_uri="https://internal/pay",
                tool_name="T3_pay",
                payload={"amount_minor": 1000000},
                dispatch_fn=_bad_dispatch,
            )
        except BiometricHumanVetoError:
            vetoed = True

        adversary_defended = vetoed and not dispatched_on_veto and (
            not ledger_path.exists() or ledger_path.stat().st_size == 0
        )

        # Positive control: Operator approval
        DynamicHandler.veto = False
        dispatched_on_approval = False

        def _good_dispatch():
            nonlocal dispatched_on_approval
            dispatched_on_approval = True
            return {"status": "SUCCESS"}

        result = adapter.dispatch_guarded(
            target_uri="https://internal/pay",
            tool_name="T3_pay",
            payload={"amount_minor": 1000000},
            dispatch_fn=_good_dispatch,
        )
        control_passed = dispatched_on_approval and result.response == {"status": "SUCCESS"}

    server.shutdown()
    server.server_close()

    if not control_passed:
        return False, "INCONCLUSIVE: Positive control failed"
    return adversary_defended, "DEFENDED (Operator veto killed dispatch fail-closed with 0 ledger writes)"


def main() -> int:
    print("================================================================================")
    print("  ADVERSARIAL RED-TEAM PROBE: APPLE SILICON BIOMETRIC NOTARY (A18 PRO / M3 PRO) ")
    print("================================================================================")

    probes = [
        ("Probe 1 [WYSIWYS Alteration]", probe_1_wysiwys_payload_alteration),
        ("Probe 2 [Expired Replay]", probe_2_replay_expired_warrant),
        ("Probe 3 [Unpinned Key Forgery]", probe_3_unpinned_key_forgery),
        ("Probe 4 [Corrupted DER Signature]", probe_4_corrupted_der_signature),
        ("Probe 5 [Operator Human VETO]", probe_5_operator_human_veto),
    ]

    all_defended = True
    for name, probe_fn in probes:
        passed, detail = probe_fn()
        status_tag = "[DEFENDED]" if passed else "[FAILED]"
        print(f"  {status_tag:12} {name:32} -> {detail}")
        if not passed:
            all_defended = False

    print("--------------------------------------------------------------------------------")
    if all_defended:
        print("  RESULT: ALL 5 ADVERSARIAL ATTACK PROBES DEFENDED WITH POSITIVE CONTROLS HELD.")
        return 0
    else:
        print("  RESULT: ONE OR MORE ADVERSARIAL PROBES FAILED OR WERE INCONCLUSIVE.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
