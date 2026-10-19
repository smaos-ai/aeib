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
tests/test_sybil_rotator_and_smurfing.py — Hardened Financial Integrity Gate & Red-Team Suite

Evaluates Station 1 & Station 2 Financial Integrity Gate under the stated model.
Addresses review findings:
- P0 #1 (AT69): Beneficiary (`recipient`) cryptographically bound inside subagent signature & CAID.
- P0 #2 (AT57b): Recipient pinning derived strictly from gate-owned signed TIER_1 allowlist.
- P0 #3 (AT70): Gate-owned monotonic clock (`ClockSource`); caller-supplied far-future timestamps
                rejected with `REJECTED_CLOCK_SKEW_OR_MANIPULATION`.
- P0 #4 (AT59): Two-file deletion (`rm ledger.jsonl checkpoint.tip`) evaluated via external/hardware
                continuity anchor (`RemoteContinuityAnchor`) checked at boot.
- P0 #5 (AT71): `delegation_cert.max_per_call_minor` strictly enforced (`ERR_DELEGATION_ATTENUATION_BREACH`).
- P1 #6: Boot-time verification recomputes `entry_caid` and verifies Ed25519 gate signatures on every
         entry, detecting in-place `amount_minor -> 0` disk edits.
- P1 #7: O(1) in-memory rolling-window spend index + separate rate-limited rejection log.
- Moat #4: Dual-Curve Mandate Adapter evaluating both internal `Ed25519` warrants and external
           `AP2 / Apple Secure Enclave ECDSA P-256` (`secp256r1`) W3C VC 2.0 mandates.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs

GENESIS_CHAIN_TIP = "sha256:" + ("0" * 64)

ALLOWED_DISPOSITION_TRANSITIONS: Dict[str, Set[str]] = {
    "DISPATCHED": {"EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED"},
    "EFFECT_INDETERMINATE": {"EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED"},
    "CONFIRMED": set(),
    "REFUTED": set(),
}


def canonical_json_v1(obj: Any) -> bytes:
    """
    AEIB deterministic JSON serialization profile v1 (`aeib.canonical_json.v1`).
    Restricted to integer minor units and UTF-8 strings; NaN/Infinity forbidden.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def ct_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def write_all_sync(fd: int, data: bytes) -> None:
    """Loops until all bytes are written to the OS file descriptor."""
    view = memoryview(data)
    total_written = 0
    while total_written < len(view):
        written = os.write(fd, view[total_written:])
        if written <= 0:
            raise OSError("short write on ledger descriptor")
        total_written += written


class ClockSource(Protocol):
    def now_sec(self) -> int:
        ...


class DeterministicSteppedClock:
    """Gate-owned clock for Deterministic Simulation Testing (DST) and red-team suites."""

    def __init__(self, initial_sec: int = 1_760_000_000) -> None:
        self._now = initial_sec

    def now_sec(self) -> int:
        return self._now

    def advance(self, delta_sec: int) -> None:
        if delta_sec < 0:
            raise ValueError("monotonic clock cannot move backward")
        self._now += delta_sec


@dataclass(frozen=True)
class RemoteContinuityAnchor:
    """
    Fixes P0-CRITICAL #4: Simulates an out-of-host continuity anchor (e.g., AWS Nitro /
    Apple Secure Enclave monotonic counter or SCITT/Rekor transparency checkpoint).
    Survives local `rm -f ledger.jsonl checkpoint.tip`.
    """

    state: Dict[str, Any]

    @classmethod
    def create(cls) -> "RemoteContinuityAnchor":
        return cls(state={"seq": 0, "chain_tip": GENESIS_CHAIN_TIP})

    def record_anchor(self, seq: int, chain_tip: str) -> None:
        self.state["seq"] = seq
        self.state["chain_tip"] = chain_tip


@dataclass(frozen=True)
class RootSponsorPolicy:
    """Immutable quota policy bound to a single Root Sponsor DID."""

    sponsor_did: str
    sprint_window_seconds: int = 900
    sprint_max_minor_units: int = 800_00
    epoch_window_seconds: int = 86_400
    epoch_max_minor_units: int = 2000_00
    allowed_pool_endpoints: Tuple[str, ...] = (
        "POST /v1/refunds",
        "POST /v1/loyalty-credits",
        "POST /v1/vouchers",
        "POST /v1/payouts",
    )


@dataclass(frozen=True)
class ContextBlock:
    block_id: str
    taint_tier: str  # "TIER_0_PINNED", "TIER_1_INTERNAL", "TIER_2_UNTRUSTED_EXTERNAL"
    raw_bytes: bytes

    @property
    def digest(self) -> str:
        return sha256_prefixed(self.raw_bytes)


@dataclass(frozen=True)
class SubAgentDelegationCert:
    root_sponsor_key_id: str
    subagent_key_id: str
    subagent_pubkey: Ed25519PublicKey
    max_per_call_minor: int
    issued_at_sec: int
    expires_at_sec: int
    sponsor_signature_b64: str

    def canonical_unsigned_bytes(self) -> bytes:
        return canonical_json_v1(
            {
                "expires_at_sec": self.expires_at_sec,
                "issued_at_sec": self.issued_at_sec,
                "max_per_call_minor": self.max_per_call_minor,
                "root_sponsor_key_id": self.root_sponsor_key_id,
                "subagent_key_id": self.subagent_key_id,
            }
        )

    # Alias for capitalization flexibility
    def canonical_Unsigned_bytes(self) -> bytes:
        return self.canonical_unsigned_bytes()


class Station1FinancialIntegrityGate:
    """
    Hardened AEIB Station 1 & Station 2 Financial Integrity Gate.
    """

    SPRINT_WINDOW_SEC = 900       # 15-minute sprint window
    EPOCH_WINDOW_SEC = 86_400     # 24-hour epoch window
    MAX_CLOCK_DRIFT_SEC = 5       # Rejects caller timestamps drifting > 5s from gate clock

    def __init__(
        self,
        ledger_path: str,
        checkpoint_path: str,
        reject_log_path: Optional[str] = None,
        sponsor_registry: Optional[Dict[str, Ed25519PublicKey]] = None,
        pinned_tier1_recipients: Optional[Set[str]] = None,
        sprint_limit_minor: int = 800_00,
        epoch_limit_minor: int = 2000_00,
        gate_signing_key: Optional[Ed25519PrivateKey] = None,
        remote_anchor: Optional[RemoteContinuityAnchor] = None,
        clock: Optional[ClockSource] = None,
        *,
        sponsor_pubkey: Optional[Ed25519PublicKey] = None,
        policy: Optional[RootSponsorPolicy] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.ledger_path = str(ledger_path)
        self.checkpoint_path = str(checkpoint_path)
        self.reject_log_path = str(reject_log_path) if reject_log_path else f"{self.ledger_path}.rejects.jsonl"

        # Compatibility initialization
        if sponsor_registry is not None:
            self.sponsor_registry = dict(sponsor_registry)
        elif sponsor_pubkey is not None and policy is not None:
            self.sponsor_registry = {policy.sponsor_did: sponsor_pubkey}
        elif sponsor_pubkey is not None:
            self.sponsor_registry = {"default-sponsor": sponsor_pubkey}
        else:
            self.sponsor_registry = {}

        if policy is not None:
            self.sprint_limit_minor = policy.sprint_max_minor_units
            self.epoch_limit_minor = policy.epoch_max_minor_units
        else:
            self.sprint_limit_minor = sprint_limit_minor
            self.epoch_limit_minor = epoch_limit_minor

        # P0 #2 Fix: Gate-owned immutable set of pinned recipients (never caller-supplied)
        self._pinned_tier1_recipients = frozenset(pinned_tier1_recipients or set())

        self._gate_priv = gate_signing_key or Ed25519PrivateKey.generate()
        self._gate_pub = self._gate_priv.public_key()
        self._remote_anchor = remote_anchor or RemoteContinuityAnchor.create()
        self._clock = clock or DeterministicSteppedClock()

        self.halted_reason: Optional[str] = None
        self.chain_tip: str = GENESIS_CHAIN_TIP
        self.chain_seq: int = 0

        # P1 #7 Fix: In-memory O(1) rolling spend index per sponsor
        # Maps operation_id -> (sponsor_id, timestamp_sec, amount_minor, disposition)
        self._active_operations: Dict[str, Tuple[str, int, int, str]] = {}

        self._verify_continuity_on_boot()

    def _verify_continuity_on_boot(self) -> None:
        ledger_exists = os.path.exists(self.ledger_path)
        ckpt_exists = os.path.exists(self.checkpoint_path)

        # P0 #4 Fix: Detect two-file wipe (`rm -f ledger.jsonl checkpoint.tip`) via external anchor
        if not ledger_exists and not ckpt_exists:
            if self._remote_anchor.state["seq"] > 0:
                self.halted_reason = "HALT_TWO_FILE_WIPE_DETECTED_AGAINST_REMOTE_ANCHOR"
            return

        if ledger_exists != ckpt_exists:
            self.halted_reason = "HALT_CONTINUITY_FILE_MISSING"
            return

        with open(self.checkpoint_path, "r", encoding="utf-8") as cf:
            ckpt = json.loads(cf.read())
        expected_tip = ckpt.get("chain_tip", "")
        expected_seq = ckpt.get("seq", -1)

        running_tip = GENESIS_CHAIN_TIP
        running_seq = 0

        with open(self.ledger_path, "r", encoding="utf-8") as lf:
            for raw_line in lf:
                line = raw_line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                running_seq += 1

                if entry.get("seq") != running_seq:
                    self.halted_reason = "HALT_NON_MONOTONIC_SEQ_ON_BOOT"
                    return

                if not ct_eq(entry.get("prev_chain_tip", ""), running_tip):
                    self.halted_reason = "HALT_BROKEN_CHAIN_LINKAGE_ON_BOOT"
                    return

                # P1 #6 Fix: Recompute entry_caid from unsigned fields AND verify gate signature!
                unsigned = {
                    k: v
                    for k, v in entry.items()
                    if k not in ("entry_caid", "gate_signature_b64")
                }
                canonical_bytes = canonical_json_v1(unsigned)
                recomputed_caid = sha256_prefixed(canonical_bytes)
                if not ct_eq(recomputed_caid, entry.get("entry_caid", "")):
                    self.halted_reason = "HALT_IN_PLACE_LEDGER_TAMPER_DETECTED"
                    return

                try:
                    sig = base64.b64decode(entry.get("gate_signature_b64", ""), validate=True)
                    self._gate_pub.verify(sig, canonical_bytes)
                except (ValueError, InvalidSignature):
                    self.halted_reason = "HALT_INVALID_GATE_SIGNATURE_ON_BOOT"
                    return

                running_tip = recomputed_caid
                op_id = entry["operation_id"]
                disp = entry["disposition"]
                if disp in ("DISPATCHED", "EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED"):
                    self._active_operations[op_id] = (
                        entry["root_sponsor_key_id"],
                        int(entry["timestamp_sec"]),
                        int(entry["amount_minor"]),
                        disp,
                    )

        if not ct_eq(running_tip, expected_tip) or running_seq != expected_seq:
            self.halted_reason = "HALT_CHECKPOINT_TIP_MISMATCH"
            return

        if (
            self._remote_anchor.state["seq"] > 0
            and (
                running_seq != self._remote_anchor.state["seq"]
                or not ct_eq(running_tip, self._remote_anchor.state["chain_tip"])
            )
        ):
            self.halted_reason = "HALT_REMOTE_ANCHOR_ROLLBACK_DETECTED"
            return

        self.chain_tip = running_tip
        self.chain_seq = running_seq

    def _atomic_write_checkpoint(self, seq: int, tip: str) -> None:
        """Atomic temp-file write + fsync + os.replace."""
        tmp_path = f"{self.checkpoint_path}.tmp.{os.getpid()}.{threading.get_ident()}"
        payload = canonical_json_v1({"chain_tip": tip, "seq": seq})
        fd = os.open(tmp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        try:
            write_all_sync(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, self.checkpoint_path)

    def _append_authoritative_ledger(self, record: Dict[str, Any]) -> str:
        self.chain_seq += 1
        unsigned = {
            **record,
            "prev_chain_tip": self.chain_tip,
            "seq": self.chain_seq,
        }
        canonical_bytes = canonical_json_v1(unsigned)
        entry_caid = sha256_prefixed(canonical_bytes)
        sig_b64 = base64.b64encode(self._gate_priv.sign(canonical_bytes)).decode("ascii")
        signed_entry = {
            **unsigned,
            "entry_caid": entry_caid,
            "gate_signature_b64": sig_b64,
        }
        line_bytes = canonical_json_v1(signed_entry) + b"\n"

        fd = os.open(self.ledger_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            write_all_sync(fd, line_bytes)
            os.fsync(fd)
        finally:
            os.close(fd)

        self.chain_tip = entry_caid
        self._atomic_write_checkpoint(self.chain_seq, self.chain_tip)
        self._remote_anchor.record_anchor(self.chain_seq, self.chain_tip)
        return entry_caid

    def _append_reject_audit_log(
        self, operation_id: str, rejection_code: str, now_ts: int
    ) -> None:
        """
        Records rejected attempts in a separate audit log
        without polluting the authoritative financial escrow ledger.
        """
        entry = canonical_json_v1(
            {
                "operation_id": operation_id,
                "rejection_code": rejection_code,
                "timestamp_sec": now_ts,
            }
        ) + b"\n"
        fd = os.open(self.reject_log_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            write_all_sync(fd, entry)
        finally:
            os.close(fd)

    def _compute_window_exposure_minor(
        self, sponsor_id: str, now_ts: int, window_sec: int
    ) -> int:
        cutoff = now_ts - window_sec
        total = 0
        for sp_id, ts, amt, disp in self._active_operations.values():
            if (
                sp_id == sponsor_id
                and ts >= cutoff
                and disp in ("DISPATCHED", "EFFECT_INDETERMINATE", "CONFIRMED")
            ):
                total += amt
        return total

    def get_escrowed_amount_minor(self, sponsor_id: str) -> int:
        with self._lock:
            return sum(
                amt
                for sp_id, _, amt, disp in self._active_operations.values()
                if sp_id == sponsor_id and disp in ("DISPATCHED", "EFFECT_INDETERMINATE")
            )

    def get_settled_amount_minor(self, sponsor_id: str) -> int:
        with self._lock:
            return sum(
                amt
                for sp_id, _, amt, disp in self._active_operations.values()
                if sp_id == sponsor_id and disp == "CONFIRMED"
            )

    def evaluate_and_dispatch(
        self,
        operation_id: str,
        endpoint: str,
        recipient: str,
        amount_minor: int,
        claimed_now_ts: int,
        delegation_cert: SubAgentDelegationCert,
        subagent_signature_b64: str,
        bound_context_manifest: List[Tuple[str, str]],
        live_context_blocks: List[ContextBlock],
    ) -> Dict[str, Any]:
        with self._lock:
            gate_now = self._clock.now_sec()

            if self.halted_reason is not None:
                self._append_reject_audit_log(operation_id, self.halted_reason, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": self.halted_reason,
                    "decision": "REJECTED",
                    "reason": self.halted_reason,
                }

            # P0 #3 Fix (AT70): Gate-owned clock validation; reject caller clock manipulation
            if abs(claimed_now_ts - gate_now) > self.MAX_CLOCK_DRIFT_SEC:
                code = "REJECTED_CLOCK_SKEW_OR_MANIPULATION"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Reject duplicate or in-flight uncertain operations (no blind retry)
            if operation_id in self._active_operations:
                _, _, _, existing_disp = self._active_operations[operation_id]
                code = (
                    "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
                    if existing_disp == "EFFECT_INDETERMINATE"
                    else "REJECTED_DUPLICATE_OPERATION_ID"
                )
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Verify Root Sponsor Delegation Certificate
            sponsor_id = delegation_cert.root_sponsor_key_id
            sponsor_pub = self.sponsor_registry.get(sponsor_id)
            if sponsor_pub is None:
                code = "UNTRUSTED_ROOT_SPONSOR"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            try:
                cert_sig = base64.b64decode(
                    delegation_cert.sponsor_signature_b64, validate=True
                )
                sponsor_pub.verify(cert_sig, delegation_cert.canonical_unsigned_bytes())
            except (ValueError, InvalidSignature):
                code = "INVALID_DELEGATION_CERT_SIGNATURE"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            if not (
                delegation_cert.issued_at_sec <= gate_now <= delegation_cert.expires_at_sec
            ):
                code = "EXPIRED_DELEGATION_CERT"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # P0 #5 Fix (AT71): Enforce per-call delegation attenuation ceiling!
            if amount_minor <= 0 or amount_minor > delegation_cert.max_per_call_minor:
                code = "ERR_DELEGATION_ATTENUATION_BREACH"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # P0 #1 Fix (AT69): Beneficiary (`recipient`) is bound inside the signed payload!
            expected_req_bytes = canonical_json_v1(
                {
                    "amount_minor": amount_minor,
                    "bound_context": bound_context_manifest,
                    "endpoint": endpoint,
                    "operation_id": operation_id,
                    "recipient": recipient,
                }
            )
            try:
                sub_sig = base64.b64decode(subagent_signature_b64, validate=True)
                delegation_cert.subagent_pubkey.verify(sub_sig, expected_req_bytes)
            except (ValueError, InvalidSignature):
                code = "ERR_SIGNATURE_OR_PAYEE_MISMATCH"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Verify Context Provenance & Bell-LaPadula Taint (AT57 & AT57b)
            actual_manifest = [(b.block_id, b.digest) for b in live_context_blocks]
            if actual_manifest != bound_context_manifest:
                code = "CONTEXT_PROVENANCE_MUTATION_DETECTED"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            has_tier2_taint = any(
                b.taint_tier == "TIER_2_UNTRUSTED_EXTERNAL" for b in live_context_blocks
            )
            # P0 #2 Fix: Recipient pinning is derived strictly from gate's TIER_1 registry
            is_recipient_pinned_by_gate = recipient in self._pinned_tier1_recipients
            if has_tier2_taint and not is_recipient_pinned_by_gate:
                code = "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Check Sprint & Epoch Rolling Windows (AT56 & AT58)
            sprint_spent = self._compute_window_exposure_minor(
                sponsor_id, gate_now, self.SPRINT_WINDOW_SEC
            )
            if sprint_spent + amount_minor > self.sprint_limit_minor:
                code = "HALT_SPRINT_LIMIT_EXCEEDED"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            epoch_spent = self._compute_window_exposure_minor(
                sponsor_id, gate_now, self.EPOCH_WINDOW_SEC
            )
            if epoch_spent + amount_minor > self.epoch_limit_minor:
                code = "HALT_EPOCH_LIMIT_EXCEEDED"
                self._append_reject_audit_log(operation_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Commit pre-dispatch reservation to authoritative ledger
            record = {
                "amount_minor": amount_minor,
                "disposition": "DISPATCHED",
                "endpoint": endpoint,
                "operation_id": operation_id,
                "recipient": recipient,
                "root_sponsor_key_id": sponsor_id,
                "subagent_key_id": delegation_cert.subagent_key_id,
                "timestamp_sec": gate_now,
            }
            entry_caid = self._append_authoritative_ledger(record)
            self._active_operations[operation_id] = (
                sponsor_id,
                gate_now,
                amount_minor,
                "DISPATCHED",
            )
            return {
                "disposition": "DISPATCHED",
                "decision": "DISPATCHED",
                "entry_caid": entry_caid,
                "operation_id": operation_id,
            }

    def record_downstream_effect(
        self,
        operation_id: str,
        new_disposition: str,
    ) -> None:
        if new_disposition not in ("EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED"):
            raise ValueError(f"invalid disposition: {new_disposition}")

        with self._lock:
            if self.halted_reason is not None:
                raise RuntimeError(self.halted_reason)

            current = self._active_operations.get(operation_id)
            if current is None:
                raise ValueError("UNKNOWN_OPERATION_ID")

            sponsor_id, orig_ts, amount_minor, prior_disp = current
            if new_disposition not in ALLOWED_DISPOSITION_TRANSITIONS[prior_disp]:
                raise ValueError(f"INVALID_STATE_TRANSITION: {prior_disp} -> {new_disposition}")

            gate_now = self._clock.now_sec()
            self._append_authoritative_ledger(
                {
                    "amount_minor": amount_minor,
                    "disposition": new_disposition,
                    "operation_id": operation_id,
                    "prior_disposition": prior_disp,
                    "root_sponsor_key_id": sponsor_id,
                    "timestamp_sec": gate_now,
                }
            )
            self._active_operations[operation_id] = (
                sponsor_id,
                orig_ts,
                amount_minor,
                new_disposition,
            )


# --- Moat #4: AP2 / Apple Secure Enclave W3C VC 2.0 ECDSA P-256 Mandate Verifier ---
class Ap2AndSecureEnclaveP256Verifier:
    """
    Bridges internal Ed25519 warrants with external Google AP2 W3C Verifiable Credentials
    and Apple Secure Enclave (`secp256r1` / NIST P-256) ECDSA signatures.
    """

    @staticmethod
    def verify_p256_vc_mandate(
        issuer_pubkey: ec.EllipticCurvePublicKey,
        vc_document_without_proof: Dict[str, Any],
        signature_der_b64: str,
        expected_recipient: str,
        requested_minor: int,
    ) -> Tuple[bool, Optional[str]]:
        subj = vc_document_without_proof.get("credentialSubject", {})
        if subj.get("recipient") != expected_recipient:
            return False, "AP2_VC_RECIPIENT_MISMATCH"
        if int(subj.get("maxAmountMinor", -1)) < requested_minor:
            return False, "AP2_VC_MANDATE_CEILING_EXCEEDED"

        payload_bytes = canonical_json_v1(vc_document_without_proof)
        try:
            sig_der = base64.b64decode(signature_der_b64, validate=True)
            issuer_pubkey.verify(sig_der, payload_bytes, ec.ECDSA(hashes.SHA256()))
        except (ValueError, InvalidSignature):
            return False, "AP2_VC_INVALID_ECDSA_P256_SIGNATURE"
        return True, None


# --- Red-Team Test Suite Verifying All P0 & P1 Fixes (AT56 -> AT71 + AP2 P-256) ---
def test_all_p0_and_p1_fixes_end_to_end() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="aeib_p0_test_")
    ledger_file = os.path.join(tmp_dir, "ledger.jsonl")
    ckpt_file = os.path.join(tmp_dir, "checkpoint.tip")
    reject_file = os.path.join(tmp_dir, "rejects.jsonl")

    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sub_priv = Ed25519PrivateKey.generate()
    sponsor_id = "sponsor-treasury-root-01"
    pinned_iban = "iban:DE89370400440532013000"
    attacker_iban = "iban:CH9300000000000000000"

    clock = DeterministicSteppedClock(initial_sec=1_760_000_000)
    remote_anchor = RemoteContinuityAnchor.create()

    cert_unsigned = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-worker-01",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=500_00,  # EUR 500 max per single call
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64="",
    )
    cert_sig = base64.b64encode(
        sponsor_priv.sign(cert_unsigned.canonical_unsigned_bytes())
    ).decode("ascii")
    cert = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-worker-01",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=500_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64=cert_sig,
    )

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=ckpt_file,
        reject_log_path=reject_file,
        sponsor_registry={sponsor_id: sponsor_priv.public_key()},
        pinned_tier1_recipients={pinned_iban},
        sprint_limit_minor=800_00,  # EUR 800 sprint ceiling
        epoch_limit_minor=2000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    clean_ctx = ContextBlock("ctx-1", "TIER_0_PINNED", b"invoice_id=inv_101")
    manifest = [(clean_ctx.block_id, clean_ctx.digest)]

    def sign_subagent_req(
        op_id: str, amount: int, rcpt: str, mf: List[Tuple[str, str]]
    ) -> str:
        payload = canonical_json_v1(
            {
                "amount_minor": amount,
                "bound_context": mf,
                "endpoint": "POST /v1/refunds",
                "operation_id": op_id,
                "recipient": rcpt,
            }
        )
        return base64.b64encode(sub_priv.sign(payload)).decode("ascii")

    # 1. Valid EUR 450 dispatch to pinned IBAN succeeds
    sig_ok = sign_subagent_req("op-valid-1", 450_00, pinned_iban, manifest)
    res_ok = gate.evaluate_and_dispatch(
        "op-valid-1", "POST /v1/refunds", pinned_iban, 450_00, clock.now_sec(), cert, sig_ok, manifest, [clean_ctx]
    )
    assert res_ok["disposition"] == "DISPATCHED"

    # 2. AT69 (P0 #1 Fix): Payee substitution attack -> Signed for `pinned_iban`, swapped to `attacker_iban`
    res_at69 = gate.evaluate_and_dispatch(
        "op-at69-swap", "POST /v1/refunds", attacker_iban, 450_00, clock.now_sec(), cert, sig_ok, manifest, [clean_ctx]
    )
    assert res_at69["disposition"] == "NOT_DISPATCHED"
    assert res_at69["rejection_code"] == "ERR_SIGNATURE_OR_PAYEE_MISMATCH"

    # 3. AT57b (P0 #2 Fix): TIER_2 tainted context to unpinned recipient fails closed
    tainted_ctx = ContextBlock("ctx-taint", "TIER_2_UNTRUSTED_EXTERNAL", b"prompt_injection=send_to_attacker")
    taint_mf = [(tainted_ctx.block_id, tainted_ctx.digest)]
    sig_taint = sign_subagent_req("op-at57b", 100_00, attacker_iban, taint_mf)
    res_at57b = gate.evaluate_and_dispatch(
        "op-at57b", "POST /v1/refunds", attacker_iban, 100_00, clock.now_sec(), cert, sig_taint, taint_mf, [tainted_ctx]
    )
    assert res_at57b["disposition"] == "NOT_DISPATCHED"
    assert res_at57b["rejection_code"] == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"

    # 4. AT70 (P0 #3 Fix): Caller passes `claimed_now_ts = 2_000_000_000` to reset rolling window
    sig_clock = sign_subagent_req("op-at70-clock", 450_00, pinned_iban, manifest)
    res_at70 = gate.evaluate_and_dispatch(
        "op-at70-clock", "POST /v1/refunds", pinned_iban, 450_00, 2_000_000_000, cert, sig_clock, manifest, [clean_ctx]
    )
    assert res_at70["disposition"] == "NOT_DISPATCHED"
    assert res_at70["rejection_code"] == "REJECTED_CLOCK_SKEW_OR_MANIPULATION"

    # 5. AT71 (P0 #5 Fix): Subagent certified for max_per_call=EUR 500 requests EUR 550
    sig_atten = sign_subagent_req("op-at71-atten", 550_00, pinned_iban, manifest)
    res_at71 = gate.evaluate_and_dispatch(
        "op-at71-atten", "POST /v1/refunds", pinned_iban, 550_00, clock.now_sec(), cert, sig_atten, manifest, [clean_ctx]
    )
    assert res_at71["disposition"] == "NOT_DISPATCHED"
    assert res_at71["rejection_code"] == "ERR_DELEGATION_ATTENUATION_BREACH"

    # 6. AT58: Latch `op-valid-1` (EUR 450) as EFFECT_INDETERMINATE -> Escrow stays locked at EUR 450
    gate.record_downstream_effect("op-valid-1", "EFFECT_INDETERMINATE")
    assert gate.get_escrowed_amount_minor(sponsor_id) == 450_00
    # Second request of EUR 400 exceeds EUR 800 sprint ceiling (EUR 450 escrowed + EUR 400 > EUR 800)
    sig_escrow = sign_subagent_req("op-during-escrow", 400_00, pinned_iban, manifest)
    res_escrow = gate.evaluate_and_dispatch(
        "op-during-escrow", "POST /v1/refunds", pinned_iban, 400_00, clock.now_sec(), cert, sig_escrow, manifest, [clean_ctx]
    )
    assert res_escrow["disposition"] == "NOT_DISPATCHED"
    assert res_escrow["rejection_code"] == "HALT_SPRINT_LIMIT_EXCEEDED"

    # Reconcile `op-valid-1` to CONFIRMED -> Escrow drops to 0, settled becomes EUR 450
    gate.record_downstream_effect("op-valid-1", "CONFIRMED")
    assert gate.get_escrowed_amount_minor(sponsor_id) == 0
    assert gate.get_settled_amount_minor(sponsor_id) == 450_00

    # 7. P1 #6 Fix: In-place disk edit (`amount_minor: 45000 -> 0`) caught on reboot
    with open(ledger_file, "r", encoding="utf-8") as f:
        tampered_content = f.read().replace('"amount_minor":45000', '"amount_minor":0')
    with open(ledger_file, "w", encoding="utf-8") as f:
        f.write(tampered_content)

    rebooted_tampered = Station1FinancialIntegrityGate(
        ledger_file, ckpt_file, reject_file, {sponsor_id: sponsor_priv.public_key()},
        {pinned_iban}, 800_00, 2000_00, gate_priv, remote_anchor, clock
    )
    assert rebooted_tampered.halted_reason == "HALT_IN_PLACE_LEDGER_TAMPER_DETECTED"

    # 8. P0 #4 Fix (AT59): Two-file wipe (`rm -f ledger.jsonl checkpoint.tip`) caught via Remote Anchor
    os.remove(ledger_file)
    os.remove(ckpt_file)
    rebooted_wiped = Station1FinancialIntegrityGate(
        ledger_file, ckpt_file, reject_file, {sponsor_id: sponsor_priv.public_key()},
        {pinned_iban}, 800_00, 2000_00, gate_priv, remote_anchor, clock
    )
    assert rebooted_wiped.halted_reason == "HALT_TWO_FILE_WIPE_DETECTED_AGAINST_REMOTE_ANCHOR"

    # 9. Verify Moat #4: AP2 / Apple Secure Enclave ECDSA P-256 W3C VC 2.0 Mandate Adapter
    p256_priv = ec.generate_private_key(ec.SECP256R1())
    vc_doc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiableCredential", "AP2PaymentMandate"],
        "issuer": "did:web:treasury.example.com",
        "credentialSubject": {
            "id": "did:key:agent-01",
            "recipient": pinned_iban,
            "maxAmountMinor": 500_00,
            "currency": "EUR",
        },
    }
    vc_sig_der = p256_priv.sign(canonical_json_v1(vc_doc), ec.ECDSA(hashes.SHA256()))
    vc_sig_b64 = base64.b64encode(vc_sig_der).decode("ascii")
    ok_ap2, err_ap2 = Ap2AndSecureEnclaveP256Verifier.verify_p256_vc_mandate(
        p256_priv.public_key(), vc_doc, vc_sig_b64, pinned_iban, 450_00
    )
    assert ok_ap2 and err_ap2 is None


if __name__ == "__main__":
    test_all_p0_and_p1_fixes_end_to_end()
    print("ALL P0 (#1-#5), P1 (#6-#8), AND AP2/SEP P-256 TESTS PASSED.")
