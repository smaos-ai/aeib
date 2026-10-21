#!/usr/bin/env python3
# File: tests/test_eac_typestate_conflict_engine.py
"""
Pytest suite for compliance/eac_typestate_conflict_engine.py (P0 + P1 Priority Paths).

Verifies:
1. P1 Typestate Gate: Unprobed ontic mutations fail closed with HALT_UNPROBED_MUTATION.
2. P1 Target Binding & Ed25519 Signature Verification: Mismatched target or forged signature fails closed.
3. P0 Non-Dilutable Conflict Register (Station 2 WAL): Conflict receipts append to hash-chained WAL
   and block subsequent ontic mutations until explicit supervisor resolution.
4. Cryptographic Supervisor Resolution Warrant: When supervisor_pubkey is configured, unsigned
   or forged resolution attempts fail closed.
5. Cleanroom banned-word scan.
"""
import base64
import re
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from compliance.eac_typestate_conflict_engine import (
    EACGatekeeperHarness,
    EpistemicObservation,
    Station2ConflictRegister,
    canonical_jcs,
    test_eac_p0_p1_gates,
)


def test_end_to_end_p0_p1_gates() -> None:
    test_eac_p0_p1_gates()


def test_typestate_target_mismatch_and_invalid_signature() -> None:
    priv = Ed25519PrivateKey.generate()
    wrong_priv = Ed25519PrivateKey.generate()
    wal = Station2ConflictRegister()
    harness = EACGatekeeperHarness(verifier_pubkey=priv.public_key(), conflict_register=wal)

    # 1. Target mismatch -> HALT_EPISTEMIC_TARGET_MISMATCH
    obs_wrong_target = EpistemicObservation(
        probe_id="probe-201",
        target_object_id="order:ORD-OTHER",
        probe_action="ReadOrder",
        timestamp_ns=time.time_ns(),
        conflict_detected=False,
        evidence_digest="sha256:clean",
        verifier_signature_b64="",
    )
    sig = priv.sign(obs_wrong_target.compute_signature_payload())
    signed_wrong_target = EpistemicObservation(
        probe_id=obs_wrong_target.probe_id,
        target_object_id=obs_wrong_target.target_object_id,
        probe_action=obs_wrong_target.probe_action,
        timestamp_ns=obs_wrong_target.timestamp_ns,
        conflict_detected=obs_wrong_target.conflict_detected,
        evidence_digest=obs_wrong_target.evidence_digest,
        verifier_signature_b64=base64.b64encode(sig).decode("ascii"),
    )
    res_mismatch = harness.dispatch_ontic_action(
        "CancelOrder",
        "order:ORD-ACTUAL",
        {"reason": "cancel"},
        epistemic_receipt=signed_wrong_target,
    )
    assert res_mismatch["disposition"] == "DENIED"
    assert res_mismatch["code"] == "HALT_EPISTEMIC_TARGET_MISMATCH"

    # 2. Invalid signature -> HALT_INVALID_EPISTEMIC_SIGNATURE
    obs_bad_sig = EpistemicObservation(
        probe_id="probe-202",
        target_object_id="order:ORD-ACTUAL",
        probe_action="ReadOrder",
        timestamp_ns=time.time_ns(),
        conflict_detected=False,
        evidence_digest="sha256:clean",
        verifier_signature_b64=base64.b64encode(
            wrong_priv.sign(obs_wrong_target.compute_signature_payload())
        ).decode("ascii"),
    )
    res_bad_sig = harness.dispatch_ontic_action(
        "CancelOrder",
        "order:ORD-ACTUAL",
        {"reason": "cancel"},
        epistemic_receipt=obs_bad_sig,
    )
    assert res_bad_sig["disposition"] == "DENIED"
    assert res_bad_sig["code"] == "HALT_INVALID_EPISTEMIC_SIGNATURE"


def test_cryptographic_supervisor_conflict_resolution() -> None:
    sup_priv = Ed25519PrivateKey.generate()
    rogue_priv = Ed25519PrivateKey.generate()
    wal = Station2ConflictRegister(supervisor_pubkey=sup_priv.public_key())

    c_id = wal.register_conflict("probe-301", "order:ORD-900", "Disputed chargeback active")
    assert wal.has_unresolved_conflicts("order:ORD-900") is True

    # 1. Attempt to resolve without signature when supervisor_pubkey is configured -> False
    assert wal.resolve_conflict(c_id) is False
    assert wal.has_unresolved_conflicts("order:ORD-900") is True

    # 2. Attempt with rogue signature -> False
    rationale = "Approved override after secondary document review."
    rogue_sig = base64.b64encode(
        rogue_priv.sign(canonical_jcs({"conflict_id": c_id, "resolution_rationale": rationale}))
    ).decode("ascii")
    assert wal.resolve_conflict(c_id, rationale, rogue_sig) is False

    # 3. Valid supervisor signature -> True
    valid_sig = base64.b64encode(
        sup_priv.sign(canonical_jcs({"conflict_id": c_id, "resolution_rationale": rationale}))
    ).decode("ascii")
    assert wal.resolve_conflict(c_id, rationale, valid_sig) is True
    assert wal.has_unresolved_conflicts("order:ORD-900") is False


def test_banned_words_absence() -> None:
    forbidden_tokens = [
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
        "proven universal" + "ly",
    ]
    pattern = re.compile("|".join(re.escape(t) for t in forbidden_tokens), re.IGNORECASE)

    for p in [Path("compliance/eac_typestate_conflict_engine.py"), Path(__file__)]:
        content = p.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        assert not matches, f"Banned tokens {matches} found in {p}"
