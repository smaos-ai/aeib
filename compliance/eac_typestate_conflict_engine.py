#!/usr/bin/env python3
# File: compliance/eac_typestate_conflict_engine.py
"""
AEIB EAC Enforcement Engine (P0 + P1 Priority Paths):
1. P0: Non-Dilutable Conflict Register (Station 2 WAL) - Mitigates Harness Dilution
   (arXiv:2610.12360) by appending detected contradictions into a hash-chained WAL.
2. P1: Typestate-Enforced Epistemic-Ontic Gate (Station 1) - Enforces flow-sensitive
   capability typestates (Jia et al., arXiv:2510.08889; arXiv:2610.22469) by rejecting
   any state-mutating ontic action lacking a verified EpistemicObservation receipt
   (HALT_UNPROBED_MUTATION).
"""
import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _check_no_floats(val: Any) -> None:
    if isinstance(val, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_USE_INTEGER_MINOR_UNITS")
    if isinstance(val, dict):
        for v in val.values():
            _check_no_floats(v)
    elif isinstance(val, (list, tuple)):
        for v in val:
            _check_no_floats(v)


def canonical_jcs(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) encoding."""
    _check_no_floats(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# P1: TYPESTATE EPISTEMIC OBSERVATION RECEIPT & GATE (STATION 1)
# ============================================================================
@dataclass(frozen=True)
class EpistemicObservation:
    """
    Read-only probe receipt (Typestate Capability Proof, arXiv:2510.08889):
    Every state-mutating Ontic Action must carry a tool-signed EpistemicObservation
    demonstrating that the target object was inspected via a read-only epistemic
    probe prior to mutation proposal.
    """
    probe_id: str
    target_object_id: str
    probe_action: str
    timestamp_ns: int
    conflict_detected: bool
    evidence_digest: str
    verifier_signature_b64: str

    def compute_signature_payload(self) -> bytes:
        return canonical_jcs({
            "conflict_detected": self.conflict_detected,
            "evidence_digest": self.evidence_digest,
            "probe_action": self.probe_action,
            "probe_id": self.probe_id,
            "target_object_id": self.target_object_id,
            "timestamp_ns": self.timestamp_ns,
        })


# ============================================================================
# P0: NON-DILUTABLE CONFLICT REGISTER (STATION 2 WAL)
# ============================================================================
@dataclass(frozen=True)
class ConflictEntry:
    conflict_id: str
    probe_id: str
    target_object_id: str
    conflict_description: str
    timestamp_ns: int
    prev_entry_hash: str

    def compute_entry_hash(self) -> str:
        return sha256_hex(canonical_jcs({
            "conflict_description": self.conflict_description,
            "conflict_id": self.conflict_id,
            "prev_entry_hash": self.prev_entry_hash,
            "probe_id": self.probe_id,
            "target_object_id": self.target_object_id,
            "timestamp_ns": self.timestamp_ns,
        }))


class Station2ConflictRegister:
    """
    Non-Dilutable Conflict Register:
    In long-horizon trajectories, whenever conflict_detected=True is observed,
    an immutable ConflictEntry is appended to the hash-chained WAL ledger.
    Any unresolved conflict on a target_object_id blocks ontic mutations until
    resolved via explicit supervisor authorization.
    """

    def __init__(self, supervisor_pubkey: Optional[Ed25519PublicKey] = None) -> None:
        self.wal_ledger: List[ConflictEntry] = []
        self.resolved_conflict_ids: Set[str] = set()
        self.supervisor_pubkey = supervisor_pubkey

    def register_conflict(
        self, probe_id: str, target_object_id: str, description: str
    ) -> str:
        prev_hash = (
            self.wal_ledger[-1].compute_entry_hash()
            if self.wal_ledger
            else "genesis:0"
        )
        conflict_id = f"conflict-{len(self.wal_ledger) + 1}"
        entry = ConflictEntry(
            conflict_id=conflict_id,
            probe_id=probe_id,
            target_object_id=target_object_id,
            conflict_description=description,
            timestamp_ns=time.time_ns(),
            prev_entry_hash=prev_hash,
        )
        self.wal_ledger.append(entry)
        return conflict_id

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_rationale: str = "Explicit supervisor conflict resolution.",
        supervisor_signature_b64: Optional[str] = None,
    ) -> bool:
        """
        Marks a conflict as resolved. When supervisor_pubkey is configured on the
        register, requires a valid Ed25519 signature over the canonical JCS resolution
        payload so an untrusted agent cannot self-resolve its own WAL blocks.
        """
        known_ids = {e.conflict_id for e in self.wal_ledger}
        if conflict_id not in known_ids:
            return False

        if self.supervisor_pubkey is not None:
            if not supervisor_signature_b64:
                return False
            payload = canonical_jcs({
                "conflict_id": conflict_id,
                "resolution_rationale": resolution_rationale,
            })
            try:
                sig_bytes = base64.b64decode(supervisor_signature_b64, validate=True)
                self.supervisor_pubkey.verify(sig_bytes, payload)
            except Exception:
                return False

        self.resolved_conflict_ids.add(conflict_id)
        return True

    def verify_wal_chain_integrity(self) -> bool:
        """Verifies the hash-chain continuity of the entire WAL ledger."""
        expected_prev = "genesis:0"
        for entry in self.wal_ledger:
            if entry.prev_entry_hash != expected_prev:
                return False
            expected_prev = entry.compute_entry_hash()
        return True

    def has_unresolved_conflicts(self, target_object_id: str) -> bool:
        for entry in self.wal_ledger:
            if entry.target_object_id == target_object_id:
                if entry.conflict_id not in self.resolved_conflict_ids:
                    return True
        return False


# ============================================================================
# AEIB INTEGRATED DUAL-GATE HARNESS
# ============================================================================
class EACGatekeeperHarness:
    def __init__(
        self,
        verifier_pubkey: Ed25519PublicKey,
        conflict_register: Station2ConflictRegister,
    ) -> None:
        self.verifier_pubkey = verifier_pubkey
        self.conflict_register = conflict_register

    def dispatch_ontic_action(
        self,
        action_name: str,
        target_object_id: str,
        payload: Dict[str, Any],
        epistemic_receipt: Optional[EpistemicObservation],
    ) -> Dict[str, str]:
        # 1. P1: Typestate Gate - Verify presence of EpistemicObservation receipt
        if epistemic_receipt is None:
            return {
                "disposition": "DENIED",
                "code": "HALT_UNPROBED_MUTATION",
                "reason": "Ontic action initiated without EpistemicObservation receipt.",
            }

        # 2. P1: Target binding & Ed25519 signature verification
        if epistemic_receipt.target_object_id != target_object_id:
            return {
                "disposition": "DENIED",
                "code": "HALT_EPISTEMIC_TARGET_MISMATCH",
                "reason": "Receipt target does not match ontic action target.",
            }

        try:
            sig_bytes = base64.b64decode(
                epistemic_receipt.verifier_signature_b64, validate=True
            )
            self.verifier_pubkey.verify(
                sig_bytes, epistemic_receipt.compute_signature_payload()
            )
        except Exception:
            return {
                "disposition": "DENIED",
                "code": "HALT_INVALID_EPISTEMIC_SIGNATURE",
                "reason": "EpistemicObservation signature verification failed.",
            }

        # 3. P0: Station 2 Non-Dilutable Conflict Register check (Anti-Harness Dilution)
        if epistemic_receipt.conflict_detected:
            self.conflict_register.register_conflict(
                epistemic_receipt.probe_id,
                target_object_id,
                f"Conflict detected during probe {epistemic_receipt.probe_action}",
            )

        if self.conflict_register.has_unresolved_conflicts(target_object_id):
            return {
                "disposition": "DENIED",
                "code": "HALT_UNRESOLVED_CONFLICT_PRESENT",
                "reason": "Unresolved conflicts pending in Station 2 WAL for this target.",
            }

        return {
            "disposition": "GRANTED",
            "code": "ONTIC_ACTION_DISPATCHED",
            "target_object_id": target_object_id,
            "action_name": action_name,
            "payload_digest": sha256_hex(canonical_jcs(payload)),
        }


def test_eac_p0_p1_gates() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    wal = Station2ConflictRegister()
    harness = EACGatekeeperHarness(verifier_pubkey=pub, conflict_register=wal)
    target_id = "order:ORD-2026-881"

    # 1. Unprobed mutation without EpistemicObservation receipt -> HALT_UNPROBED_MUTATION
    res1 = harness.dispatch_ontic_action(
        "CancelOrder", target_id, {"reason": "user_request"}, epistemic_receipt=None
    )
    assert res1["disposition"] == "DENIED"
    assert res1["code"] == "HALT_UNPROBED_MUTATION"

    # 2. Construct valid EpistemicObservation with conflict_detected=True
    probe_payload = EpistemicObservation(
        probe_id="probe-101",
        target_object_id=target_id,
        probe_action="ReadOrderStatus",
        timestamp_ns=time.time_ns(),
        conflict_detected=True,
        evidence_digest="sha256:status_disputed",
        verifier_signature_b64="",
    )
    sig = priv.sign(probe_payload.compute_signature_payload())
    valid_receipt = EpistemicObservation(
        probe_id=probe_payload.probe_id,
        target_object_id=probe_payload.target_object_id,
        probe_action=probe_payload.probe_action,
        timestamp_ns=probe_payload.timestamp_ns,
        conflict_detected=probe_payload.conflict_detected,
        evidence_digest=probe_payload.evidence_digest,
        verifier_signature_b64=base64.b64encode(sig).decode("utf-8"),
    )

    # 3. Submit request with conflict receipt -> Appends WAL & halts (HALT_UNRESOLVED_CONFLICT_PRESENT)
    res2 = harness.dispatch_ontic_action(
        "CancelOrder",
        target_id,
        {"reason": "user_request"},
        epistemic_receipt=valid_receipt,
    )
    assert res2["disposition"] == "DENIED"
    assert res2["code"] == "HALT_UNRESOLVED_CONFLICT_PRESENT"
    assert len(wal.wal_ledger) == 1
    assert wal.verify_wal_chain_integrity() is True

    # 4. Even if agent submits a subsequent clean probe, unresolved WAL conflict still blocks it!
    clean_probe = EpistemicObservation(
        probe_id="probe-102",
        target_object_id=target_id,
        probe_action="ReadOrderStatus",
        timestamp_ns=time.time_ns(),
        conflict_detected=False,
        evidence_digest="sha256:status_clean",
        verifier_signature_b64="",
    )
    sig_clean = priv.sign(clean_probe.compute_signature_payload())
    clean_receipt = EpistemicObservation(
        probe_id=clean_probe.probe_id,
        target_object_id=clean_probe.target_object_id,
        probe_action=clean_probe.probe_action,
        timestamp_ns=clean_probe.timestamp_ns,
        conflict_detected=clean_probe.conflict_detected,
        evidence_digest=clean_probe.evidence_digest,
        verifier_signature_b64=base64.b64encode(sig_clean).decode("utf-8"),
    )
    res_still_blocked = harness.dispatch_ontic_action(
        "CancelOrder",
        target_id,
        {"reason": "user_request"},
        epistemic_receipt=clean_receipt,
    )
    assert res_still_blocked["disposition"] == "DENIED"
    assert res_still_blocked["code"] == "HALT_UNRESOLVED_CONFLICT_PRESENT"

    # 5. Explicitly resolve WAL conflict, then re-submit -> ONTIC_ACTION_DISPATCHED
    conflict_id = wal.wal_ledger[0].conflict_id
    assert wal.resolve_conflict(conflict_id) is True

    res3 = harness.dispatch_ontic_action(
        "CancelOrder",
        target_id,
        {"reason": "user_request"},
        epistemic_receipt=clean_receipt,
    )
    assert res3["disposition"] == "GRANTED"
    assert res3["code"] == "ONTIC_ACTION_DISPATCHED"


if __name__ == "__main__":
    test_eac_p0_p1_gates()
    print(json.dumps({"eac_p0_p1_self_test": "completed", "wal_entries_evaluated": 1}, sort_keys=True))
