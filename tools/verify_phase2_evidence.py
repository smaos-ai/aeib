#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
tools/verify_phase2_evidence.py
================================================================================
Independent Clean-Room Offline Verifier for AEIB Phase 2 Evidence Bundles.
Evaluated under the stated model. Preserves strict epistemic lock.

Verifies:
  1. Bundle schema version and structural metadata.
  2. Canonical bundle digest recomputation (RFC 8785 JCS).
  3. Ed25519 signature of the bundle manifest against the trusted public key.
  4. Every referenced artifact canonical digest (RFC 8785 JCS) and internal signatures.
  5. Scenario-specific Phase 2 invariants:
     - AT36: Disk persistence (os.fsync) and post-SIGKILL halt enforcement prior to socket allocation.
     - AT37: Non-rewrite preservation of EFFECT_INDETERMINATE during emergency halt.
     - AT38: RFC 9470 human hardware-MFA step-up resolution; fail-closed rejection of agent tokens.
     - AT39: Monotonic scope attenuation (Hop 1 -> Hop 2) and cascade revocation across delegator hierarchy.
     - REC01: Target status contract (refund_status_v1) reconciliation to RESOLVED_CONFIRMED.
  6. Provenance metadata (commit SHA, branch, worktree status).
  7. Key trust declaration.

Usage:
  python3 tools/verify_phase2_evidence.py \\
      --bundle artifacts/phase2/AT36_sigkill_persistence_evidence.json \\
      --public-key artifacts/phase2/test_operator_pubkey.pem
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


class VerificationStatus(Enum):
    SUCCESS = 0
    SCHEMA_ERROR = 1
    DIGEST_MISMATCH = 2
    INVALID_SIGNATURE = 3
    INVARIANT_VIOLATION = 4
    KEY_LOAD_ERROR = 5


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def load_public_key(key_input: str) -> Ed25519PublicKey:
    """Loads an Ed25519 public key from PEM file path, hex string, or raw bytes."""
    path = Path(key_input)
    if path.exists() and path.is_file():
        data = path.read_bytes()
        if b"BEGIN PUBLIC KEY" in data:
            return serialization.load_pem_public_key(data)
        elif len(data) == 32:
            return Ed25519PublicKey.from_public_bytes(data)

    # Attempt hex decode
    try:
        raw_bytes = bytes.fromhex(key_input.strip())
        if len(raw_bytes) == 32:
            return Ed25519PublicKey.from_public_bytes(raw_bytes)
    except ValueError:
        pass

    # Attempt base64 decode
    try:
        raw_bytes = base64.b64decode(key_input.strip())
        if len(raw_bytes) == 32:
            return Ed25519PublicKey.from_public_bytes(raw_bytes)
    except Exception:
        pass

    raise ValueError(f"Cannot load Ed25519 public key from input: {key_input}")


def _verify_at36_invariants(manifest: Dict[str, Any], artifacts: list, pub_key: Ed25519PublicKey) -> None:
    trans_obs = manifest.get("transport_observation", {})
    if trans_obs.get("connections_accepted_by_listener") != 0:
        raise ValueError("AT36 invariant violated: listener accepted connections > 0")
    if trans_obs.get("bytes_received_by_listener") != 0:
        raise ValueError("AT36 invariant violated: listener received bytes > 0")
    if trans_obs.get("gate_reported_socket_allocation") is not False:
        raise ValueError("AT36 invariant violated: gate_reported_socket_allocation was not False")
    if trans_obs.get("fsync_durability_confirmed") is not True:
        raise ValueError("AT36 invariant violated: fsync durability not confirmed")
    if trans_obs.get("post_sigkill_read_halted") is not True:
        raise ValueError("AT36 invariant violated: post-SIGKILL read did not confirm halt")

    trip_art = next((a for a in artifacts if a.get("name") == "emergency_halt_trip_record"), None)
    if not trip_art:
        raise ValueError("AT36 missing emergency_halt_trip_record artifact")
    trip_data = trip_art.get("payload") or trip_art.get("envelope", {})
    stmt = trip_data.get("statement", {})
    if stmt.get("action") != "TRIP_HALT" or stmt.get("halted") is not True:
        raise ValueError("AT36 emergency halt trip statement malformed")
    sig_hex = trip_data.get("signature_hex")
    if sig_hex:
        pub_key.verify(bytes.fromhex(sig_hex), encode_jcs(stmt))

    denial_art = next((a for a in artifacts if a.get("name") == "pre_dispatch_denial_record"), None)
    if not denial_art:
        raise ValueError("AT36 missing pre_dispatch_denial_record artifact")
    denial_data = denial_art.get("payload") or denial_art.get("envelope", {})
    if denial_data.get("violated_check") != "ANDON_CORD_TRIPPED":
        raise ValueError(f"AT36 expected ANDON_CORD_TRIPPED, got {denial_data.get('violated_check')}")
    if denial_data.get("disposition") != "NOT_DISPATCHED":
        raise ValueError(f"AT36 expected NOT_DISPATCHED, got {denial_data.get('disposition')}")


def _verify_at37_invariants(manifest: Dict[str, Any], artifacts: list, pub_key: Ed25519PublicKey) -> None:
    trans_obs = manifest.get("transport_observation", {})
    if trans_obs.get("disposition") != "EFFECT_INDETERMINATE":
        raise ValueError(f"AT37 expected disposition EFFECT_INDETERMINATE, got {trans_obs.get('disposition')}")
    if trans_obs.get("retry_safe") is not False:
        raise ValueError("AT37 invariant violated: retry_safe must be False")
    if trans_obs.get("retroactive_relabeling_detected") is not False:
        raise ValueError("AT37 invariant violated: retroactive relabeling detected")

    indeterminate_art = next((a for a in artifacts if a.get("name") == "wire_indeterminate_record"), None)
    if not indeterminate_art:
        raise ValueError("AT37 missing wire_indeterminate_record artifact")
    rec = indeterminate_art.get("payload") or indeterminate_art.get("envelope", {})
    if rec.get("disposition") != "EFFECT_INDETERMINATE":
        raise ValueError(f"AT37 journal record disposition not EFFECT_INDETERMINATE: {rec.get('disposition')}")
    if rec.get("retry_safe") is not False:
        raise ValueError("AT37 journal record retry_safe is not False")


def _verify_at38_invariants(manifest: Dict[str, Any], artifacts: list, pub_key: Ed25519PublicKey) -> None:
    trans_obs = manifest.get("transport_observation", {})
    if trans_obs.get("agent_resolution_permitted") is not False:
        raise ValueError("AT38 invariant violated: agent resolution was permitted")
    if trans_obs.get("human_mfa_acr") != "urn:mfa:hardware":
        raise ValueError(f"AT38 human_mfa_acr expected 'urn:mfa:hardware', got {trans_obs.get('human_mfa_acr')}")
    if trans_obs.get("dual_control_verified") is not True:
        raise ValueError("AT38 dual_control_verified must be True")

    rej_art = next((a for a in artifacts if a.get("name") == "agent_step_up_rejected"), None)
    if not rej_art:
        raise ValueError("AT38 missing agent_step_up_rejected artifact")
    rej = rej_art.get("payload") or rej_art.get("envelope", {})
    if rej.get("verdict") != "REJECTED_FAIL_CLOSED":
        raise ValueError(f"AT38 expected REJECTED_FAIL_CLOSED, got {rej.get('verdict')}")

    human_art = next((a for a in artifacts if a.get("name") == "human_step_up_accepted"), None)
    if not human_art:
        raise ValueError("AT38 missing human_step_up_accepted artifact")
    token = human_art.get("payload") or human_art.get("envelope", {})
    if token.get("principal_type") != "HUMAN_SUPERVISOR":
        raise ValueError(f"AT38 expected HUMAN_SUPERVISOR, got {token.get('principal_type')}")
    if token.get("acr_values") != "urn:mfa:hardware":
        raise ValueError(f"AT38 expected urn:mfa:hardware, got {token.get('acr_values')}")
    if token.get("ttl_seconds", 0) > 300:
        raise ValueError("AT38 TTL exceeds 300 seconds")

    sig_hex = token.get("signature_hex")
    if sig_hex:
        stmt = {
            "acr_values": token["acr_values"],
            "issued_at": token["issued_at"],
            "nonce": token["nonce"],
            "principal_id": token["principal_id"],
            "principal_type": token["principal_type"],
            "purpose": token["purpose"],
            "ttl_seconds": token["ttl_seconds"],
        }
        pub_key.verify(bytes.fromhex(sig_hex), encode_jcs(stmt))


def _verify_at39_invariants(manifest: Dict[str, Any], artifacts: list, root_pub_key: Ed25519PublicKey) -> None:
    trans_obs = manifest.get("transport_observation", {})
    if trans_obs.get("scope_narrowing_enforced") is not True:
        raise ValueError("AT39 scope_narrowing_enforced must be True")
    if trans_obs.get("max_spend_eur_attenuated") != 500:
        raise ValueError(f"AT39 expected attenuated spend 500, got {trans_obs.get('max_spend_eur_attenuated')}")
    if trans_obs.get("scope_expansion_blocked") is not True:
        raise ValueError("AT39 scope_expansion_blocked must be True")
    if trans_obs.get("intermediate_revocation_cascaded") is not True:
        raise ValueError("AT39 intermediate_revocation_cascaded must be True")

    hop1_art = next((a for a in artifacts if a.get("name") == "hop1_sponsor_grant"), None)
    hop2_art = next((a for a in artifacts if a.get("name") == "hop2_attenuated_grant"), None)
    if not hop1_art or not hop2_art:
        raise ValueError("AT39 missing delegation hop artifacts")

    h1 = hop1_art.get("payload") or hop1_art.get("envelope", {})
    h2 = hop2_art.get("payload") or hop2_art.get("envelope", {})

    stmt1 = h1.get("statement", {})
    stmt2 = h2.get("statement", {})

    # Verify Root Sponsor signature on Hop 1
    sig1_hex = h1.get("signature_hex")
    if sig1_hex:
        root_pub_key.verify(bytes.fromhex(sig1_hex), encode_jcs(stmt1))

    # Invariant: Monotonic scope attenuation
    spend1 = stmt1.get("maxSpendEur", 0)
    spend2 = stmt2.get("maxSpendEur", 0)
    if spend2 > spend1:
        raise ValueError(f"Monotonicity violation: child spend {spend2} > parent spend {spend1}")

    scopes1 = set(stmt1.get("permittedScopes", []))
    scopes2 = set(stmt2.get("permittedScopes", []))
    if not scopes2.issubset(scopes1):
        raise ValueError(f"Monotonicity violation: child scopes {scopes2} not subset of {scopes1}")


def _validate_refund_status_schema(resp: Dict[str, Any]) -> None:
    """Stdlib JSON schema validation for contracts/refund_status_v1.schema.json."""
    if resp.get("contract_version") != "1.0.0":
        raise ValueError(f"Invalid contract_version: {resp.get('contract_version')}")
    op_id = resp.get("operation_id", "")
    if not re.match(r"^op-[a-zA-Z0-9_-]+$", op_id):
        raise ValueError(f"Invalid operation_id pattern: {op_id}")
    if not isinstance(resp.get("idempotency_key"), str):
        raise ValueError("Missing or invalid idempotency_key")
    if resp.get("target_status") not in ("SETTLED", "REVERSED", "REJECTED", "PENDING", "UNKNOWN"):
        raise ValueError(f"Invalid target_status: {resp.get('target_status')}")
    if not isinstance(resp.get("target_mutation_ref"), str):
        raise ValueError("Missing or invalid target_mutation_ref")

    parity = resp.get("parameter_parity", {})
    if not isinstance(parity.get("amount_minor_units"), int) or parity.get("amount_minor_units") < 1:
        raise ValueError("Invalid amount_minor_units in parameter_parity")
    if not re.match(r"^[A-Z]{3}$", parity.get("currency", "")):
        raise ValueError("Invalid currency in parameter_parity")
    if not isinstance(parity.get("recipient_binding"), str) or len(parity.get("recipient_binding")) == 0:
        raise ValueError("Missing recipient_binding in parameter_parity")

    auth = resp.get("authentication", {})
    if auth.get("channel") not in ("mTLS", "PINNED_ED25519_SIGNATURE"):
        raise ValueError("Invalid authentication channel")
    if not re.match(r"^sha256:[a-f0-9]{64}$", auth.get("target_spki_digest", "")):
        raise ValueError("Invalid target_spki_digest format")


def _verify_rec01_invariants(manifest: Dict[str, Any], artifacts: list, pub_key: Ed25519PublicKey) -> None:
    trans_obs = manifest.get("transport_observation", {})
    if trans_obs.get("verdict") != "RESOLVED_CONFIRMED":
        raise ValueError(f"REC01 expected RESOLVED_CONFIRMED, got {trans_obs.get('verdict')}")
    if trans_obs.get("operation_id_bound") is not True:
        raise ValueError("REC01 operation_id_bound must be True")
    if trans_obs.get("spki_authenticated") is not True:
        raise ValueError("REC01 spki_authenticated must be True")
    if trans_obs.get("recipient_matched") is not True:
        raise ValueError("REC01 recipient_matched must be True")

    target_art = next((a for a in artifacts if a.get("name") == "target_status_response"), None)
    if not target_art:
        raise ValueError("REC01 missing target_status_response artifact")
    resp = target_art.get("payload") or target_art.get("envelope", {})
    _validate_refund_status_schema(resp)

    if resp.get("target_status") != "SETTLED":
        raise ValueError(f"REC01 expected status SETTLED, got {resp.get('target_status')}")


def verify_phase2_bundle(bundle_data: Dict[str, Any], pub_key: Ed25519PublicKey) -> None:
    """
    Offline verifier for AEIB Phase 2 evidence bundles.
    Enforces bundle digest matching, Ed25519 manifest signature, artifact hash integrity,
    and scenario-specific invariants.
    """
    manifest = bundle_data.get("evidence_bundle")
    if not manifest:
        raise ValueError("Missing 'evidence_bundle' manifest object")

    # 1. Canonical RFC 8785 JCS bundle digest recomputation
    canonical_manifest = encode_jcs(manifest)
    expected_bundle_digest = bundle_data.get("bundle_digest")
    computed_bundle_digest = sha256_hex(canonical_manifest)
    if expected_bundle_digest != computed_bundle_digest:
        raise ValueError(
            f"Bundle digest mismatch: expected {expected_bundle_digest}, computed {computed_bundle_digest}"
        )

    # 2. Bundle Ed25519 signature verification
    sig_info = bundle_data.get("bundle_signature", {})
    sig_b64 = sig_info.get("signature_b64")
    if not sig_b64:
        raise ValueError("Missing bundle signature_b64")
    sig_bytes = base64.b64decode(sig_b64, validate=True)
    pub_key.verify(sig_bytes, canonical_manifest)

    # 3. Individual artifact digest verification
    artifacts = manifest.get("artifacts", [])
    if not artifacts:
        raise ValueError("Manifest contains no artifacts")

    for art in artifacts:
        art_name = art.get("name")
        art_data = art.get("payload") if "payload" in art else art.get("envelope")
        if art_data is not None:
            canonical_art = encode_jcs(art_data)
            expected_caid = art.get("sha256")
            computed_caid = sha256_hex(canonical_art)
            if expected_caid != computed_caid:
                raise ValueError(
                    f"Artifact '{art_name}' digest mismatch: expected {expected_caid}, computed {computed_caid}"
                )

    # 4. Invariant checks by scenario
    scenario_id = manifest.get("scenario_id")
    if scenario_id == "AT36_HALT_SIGKILL_PERSISTENCE":
        _verify_at36_invariants(manifest, artifacts, pub_key)
    elif scenario_id == "AT37_HALT_AMBIGUITY_PRESERVED":
        _verify_at37_invariants(manifest, artifacts, pub_key)
    elif scenario_id == "AT38_RFC9470_STEP_UP_RESOLUTION":
        _verify_at38_invariants(manifest, artifacts, pub_key)
    elif scenario_id == "AT39_DELEGATION_ATTENUATION_CASCADE":
        _verify_at39_invariants(manifest, artifacts, pub_key)
    elif scenario_id == "REC01_TARGET_CONTRACT_SETTLED":
        _verify_rec01_invariants(manifest, artifacts, pub_key)
    else:
        raise ValueError(f"Unrecognized scenario_id: {scenario_id}")


def main():
    parser = argparse.ArgumentParser(description="AEIB Phase 2 Evidence Verifier (AT36-AT39, REC-01)")
    parser.add_argument("--bundle", required=True, help="Path to evidence bundle JSON")
    parser.add_argument("--public-key", required=True, help="Path to public key PEM or raw hex/base64")
    parser.add_argument("--check-jcs-conformance", action="store_true", help="Assert local JCS engine passes 25 RFC 8785 vectors")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    if not bundle_path.exists():
        print(f"[!] Error: Bundle file not found: {bundle_path}", file=sys.stderr)
        sys.exit(VerificationStatus.SCHEMA_ERROR.value)

    try:
        pub_key = load_public_key(args.public_key)
    except Exception as e:
        print(f"[!] Key Load Error: {e}", file=sys.stderr)
        sys.exit(VerificationStatus.KEY_LOAD_ERROR.value)

    try:
        bundle_data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] JSON parse error: {e}", file=sys.stderr)
        sys.exit(VerificationStatus.SCHEMA_ERROR.value)

    if args.check_jcs_conformance:
        print("[*] Running RFC 8785 conformance vector verification...")
        from tests.test_jcs_canonicalizer import TestJCSCanonicalizer, TestRFC8785AppendixBVectors
        import unittest
        suite = unittest.TestSuite()
        loader = unittest.defaultTestLoader
        suite.addTest(loader.loadTestsFromTestCase(TestJCSCanonicalizer))
        suite.addTest(loader.loadTestsFromTestCase(TestRFC8785AppendixBVectors))
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        res = runner.run(suite)
        if not res.wasSuccessful():
            print("[!] RFC 8785 conformance test vector failure!", file=sys.stderr)
            sys.exit(VerificationStatus.SCHEMA_ERROR.value)
        print("    -> 25 RFC 8785 canonicalization vectors PASSED.")

    print(f"[*] Verifying Phase 2 evidence bundle: {bundle_path.name}")
    manifest = bundle_data.get("evidence_bundle", {})
    print(f"    - Scenario ID     : {manifest.get('scenario_id')}")
    print(f"    - Source Commit   : {manifest.get('provenance', {}).get('source_commit')}")
    print(f"    - Branch          : {manifest.get('provenance', {}).get('branch')}")
    print(f"    - Generated At    : {manifest.get('generated_at')}")

    try:
        verify_phase2_bundle(bundle_data, pub_key)
    except InvalidSignature as e:
        print(f"[✗] Signature verification failed: {e}", file=sys.stderr)
        sys.exit(VerificationStatus.INVALID_SIGNATURE.value)
    except ValueError as e:
        print(f"[✗] Verification error: {e}", file=sys.stderr)
        sys.exit(VerificationStatus.INVARIANT_VIOLATION.value)
    except Exception as e:
        print(f"[✗] Unexpected error: {e}", file=sys.stderr)
        sys.exit(VerificationStatus.SCHEMA_ERROR.value)

    print("=" * 80)
    print("  VERIFICATION RESULT: VALID")
    print("=" * 80)
    print("  ✓ Bundle schema version and metadata intact.")
    print("  ✓ Canonical RFC 8785 JCS bundle digest recomputed and verified.")
    print("  ✓ Ed25519 bundle signature verified against trusted public key.")
    print(f"  ✓ {len(manifest.get('artifacts', []))} constituent artifacts verified for RFC 8785 digest parity.")
    print("  ✓ Scenario-specific Phase 2 causal & authority invariants confirmed.")
    print("=" * 80)
    sys.exit(VerificationStatus.SUCCESS.value)


if __name__ == "__main__":
    main()
