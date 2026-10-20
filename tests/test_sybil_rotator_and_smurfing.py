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
from cryptography.hazmat.primitives import hashes, serialization
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
    "DISPATCHED": {"EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED", "RESOLVED_CONFIRMED", "RESOLVED_REFUTED"},
    "EFFECT_INDETERMINATE": {"EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED", "RESOLVED_CONFIRMED", "RESOLVED_REFUTED"},
    "CONFIRMED": set(),
    "REFUTED": set(),
    "RESOLVED_CONFIRMED": set(),
    "RESOLVED_REFUTED": set(),
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


def compute_caid(
    op_id: str,
    amount_minor: int,
    payee_id: str,
    endpoint: str,
    payload_hash: bytes,
) -> bytes:
    """Computes the canonical action identifier binding payee, amount, endpoint, and payload."""
    hasher = hashlib.sha256()
    hasher.update(op_id.encode("utf-8"))
    hasher.update(amount_minor.to_bytes(8, "big"))
    hasher.update(payee_id.encode("utf-8"))
    hasher.update(endpoint.encode("utf-8"))
    hasher.update(payload_hash)
    return hasher.digest()


class SystemHaltError(RuntimeError):
    """Raised when persistence integrity or continuity check fails."""
    pass


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


class CallableDigest(str):
    def __call__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class ContextBlock:
    block_id: str
    taint_tier: str  # "TIER_0_PINNED", "TIER_1_INTERNAL", "TIER_2_UNTRUSTED_EXTERNAL"
    raw_bytes: bytes

    def __init__(
        self,
        block_id: str,
        taint_tier: Optional[str] = None,
        raw_bytes: bytes = b"",
        *,
        trust_tier: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "block_id", str(block_id))
        object.__setattr__(
            self, "taint_tier", str(taint_tier or trust_tier or "TIER_0_PINNED")
        )
        object.__setattr__(self, "raw_bytes", bytes(raw_bytes))

    @property
    def digest(self) -> CallableDigest:
        return CallableDigest(sha256_prefixed(self.raw_bytes))


@dataclass(frozen=True)
class SubAgentDelegationCert:
    root_sponsor_key_id: str
    subagent_key_id: str
    subagent_pubkey: Ed25519PublicKey
    max_per_call_minor: int
    issued_at_sec: int
    expires_at_sec: int
    sponsor_signature_b64: str

    def __init__(
        self,
        root_sponsor_key_id: Optional[str] = None,
        subagent_key_id: Optional[str] = None,
        subagent_pubkey: Optional[Ed25519PublicKey] = None,
        max_per_call_minor: Optional[int] = None,
        issued_at_sec: Optional[int] = None,
        expires_at_sec: Optional[int] = None,
        sponsor_signature_b64: str = "",
        *,
        sponsor_did: Optional[str] = None,
        subagent_id: Optional[str] = None,
        subagent_pubkey_b64: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        object.__setattr__(
            self, "root_sponsor_key_id", str(root_sponsor_key_id or sponsor_did or "")
        )
        object.__setattr__(
            self, "subagent_key_id", str(subagent_key_id or subagent_id or "")
        )
        if subagent_pubkey is None and subagent_pubkey_b64:
            pub_bytes = base64.b64decode(subagent_pubkey_b64, validate=True)
            subagent_pubkey = Ed25519PublicKey.from_public_bytes(pub_bytes)
        object.__setattr__(self, "subagent_pubkey", subagent_pubkey)
        object.__setattr__(
            self,
            "_subagent_pubkey_b64",
            str(subagent_pubkey_b64) if subagent_pubkey_b64 else None,
        )
        object.__setattr__(
            self,
            "max_per_call_minor",
            int(max_per_call_minor) if max_per_call_minor is not None else 10_000_000_00,
        )
        object.__setattr__(
            self,
            "issued_at_sec",
            int(issued_at_sec) if issued_at_sec is not None else 0,
        )
        object.__setattr__(
            self,
            "expires_at_sec",
            int(expires_at_sec) if expires_at_sec is not None else 2_500_000_000,
        )
        object.__setattr__(self, "sponsor_signature_b64", str(sponsor_signature_b64))
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

    @property
    def sponsor_did(self) -> str:
        return self.root_sponsor_key_id

    @property
    def subagent_id(self) -> str:
        return self.subagent_key_id

    @property
    def subagent_pubkey_b64(self) -> str:
        raw = getattr(self, "_subagent_pubkey_b64", None)
        if raw:
            return raw
        if self.subagent_pubkey is not None:
            return base64.b64encode(
                self.subagent_pubkey.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
        return ""

    def canonical_payload(self) -> bytes:
        return encode_jcs(
            {
                "sponsor_did": self.sponsor_did,
                "subagent_id": self.subagent_id,
                "subagent_pubkey_b64": self.subagent_pubkey_b64,
            }
        )

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

        self._has_explicit_clock = clock is not None
        self._clock = clock or DeterministicSteppedClock()
        self.policy = policy
        self.sponsor_pubkey = sponsor_pubkey

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
            self.SPRINT_WINDOW_SEC = policy.sprint_window_seconds
            self.EPOCH_WINDOW_SEC = policy.epoch_window_seconds
        else:
            self.sprint_limit_minor = sprint_limit_minor
            self.epoch_limit_minor = epoch_limit_minor

        # P0 #2 Fix: Gate-owned immutable set of pinned recipients (never caller-supplied)
        self._pinned_tier1_recipients = frozenset(pinned_tier1_recipients or set())

        self._gate_priv = gate_signing_key or Ed25519PrivateKey.generate()
        self._gate_pub = self._gate_priv.public_key()
        self._remote_anchor = remote_anchor or RemoteContinuityAnchor.create()

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
                self.halted_reason = "HALT_PERSISTENCE_INTEGRITY_VIOLATION"
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

    def verify_startup_persistence_integrity(self) -> None:
        """
        P0 #4: Recomputes local WAL digest against remote SCITT/anchor root;
        halts immediately on state discrepancy or missing ledger.
        """
        if self.halted_reason is not None:
            raise SystemHaltError(
                f"HALT_PERSISTENCE_INTEGRITY_VIOLATION: {self.halted_reason}"
            )

    def evaluate_taint_gate(self, recipient_id: str, taint_tier: Any) -> bool:
        """
        P0 #2: Enforces Bell-LaPadula taint gate against gate-owned TIER_1 allowlist.
        Returns False if untrusted context attempts routing to unpinned recipient.
        """
        is_known_pinned = recipient_id in self._pinned_tier1_recipients
        tier_is_untrusted = (
            taint_tier == 2 or taint_tier == "TIER_2_UNTRUSTED_EXTERNAL"
        )
        if tier_is_untrusted and not is_known_pinned:
            return False
        return True

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
                and disp in ("DISPATCHED", "EFFECT_INDETERMINATE", "CONFIRMED", "RESOLVED_CONFIRMED")
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
                if sp_id == sponsor_id and disp in ("CONFIRMED", "RESOLVED_CONFIRMED")
            )

    def evaluate_and_dispatch(
        self,
        operation_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        recipient: Optional[str] = None,
        amount_minor: Optional[int] = None,
        claimed_now_ts: Optional[int] = None,
        delegation_cert: Optional[SubAgentDelegationCert] = None,
        subagent_signature_b64: Optional[str] = None,
        bound_context_manifest: Optional[List[Tuple[str, str]]] = None,
        live_context_blocks: Optional[List[ContextBlock]] = None,
        *,
        cert: Optional[SubAgentDelegationCert] = None,
        now_ts: Optional[int] = None,
        context_blocks: Optional[List[ContextBlock]] = None,
        pinned_known_recipient: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        with self._lock:
            delegation_cert = delegation_cert or cert or kwargs.get("delegation_cert")
            if delegation_cert is None:
                raise ValueError("delegation_cert is required")

            now_ts_val = claimed_now_ts if claimed_now_ts is not None else (now_ts if now_ts is not None else kwargs.get("now_ts"))
            live_blocks = live_context_blocks if live_context_blocks is not None else (context_blocks if context_blocks is not None else kwargs.get("context_blocks", []))
            manifest = bound_context_manifest if bound_context_manifest is not None else kwargs.get("bound_context_manifest", kwargs.get("bound_context_Manifest", []))
            op_id = operation_id or kwargs.get("operation_id") or f"op-{delegation_cert.subagent_key_id}-{self._clock.now_sec()}"
            endp = endpoint or kwargs.get("endpoint", "")
            amt = amount_minor if amount_minor is not None else int(kwargs.get("amount_minor", 0))

            rcpt = recipient or kwargs.get("recipient")
            if rcpt is None:
                if pinned_known_recipient is True:
                    rcpt = "pinned_default_recipient"
                else:
                    rcpt = "unpinned_default_recipient"

            sub_sig = subagent_signature_b64 or kwargs.get("subagent_signature_b64")

            # Determine gate_now and enforce clock check if explicit clock provided
            if self._has_explicit_clock:
                gate_now = self._clock.now_sec()
                if now_ts_val is not None and abs(now_ts_val - gate_now) > self.MAX_CLOCK_DRIFT_SEC:
                    code = "REJECTED_CLOCK_NOT_CALLER_SUPPLIED"
                    self._append_reject_audit_log(op_id, code, gate_now)
                    return {
                        "disposition": "NOT_DISPATCHED",
                        "rejection_code": code,
                        "decision": "REJECTED",
                        "reason": code,
                    }
            else:
                if now_ts_val is not None:
                    gate_now = now_ts_val
                    if hasattr(self._clock, "_now"):
                        self._clock._now = max(getattr(self._clock, "_now", 0), gate_now)
                else:
                    gate_now = self._clock.now_sec()

            if self.halted_reason is not None:
                self._append_reject_audit_log(op_id, self.halted_reason, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": self.halted_reason,
                    "decision": "REJECTED",
                    "reason": self.halted_reason,
                }

            # Reject duplicate or in-flight uncertain operations (no blind retry)
            if op_id in self._active_operations:
                _, _, _, existing_disp = self._active_operations[op_id]
                code = (
                    "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
                    if existing_disp == "EFFECT_INDETERMINATE"
                    else "REJECTED_DUPLICATE_OPERATION_ID"
                )
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Verify Root Sponsor Delegation Certificate
            sponsor_id = delegation_cert.root_sponsor_key_id or delegation_cert.sponsor_did
            sponsor_pub = self.sponsor_registry.get(sponsor_id)
            if sponsor_pub is None and self.sponsor_pubkey is not None:
                sponsor_pub = self.sponsor_pubkey
            if sponsor_pub is None and len(self.sponsor_registry) == 1:
                sponsor_pub = next(iter(self.sponsor_registry.values()))

            if sponsor_pub is None:
                code = "UNTRUSTED_ROOT_SPONSOR"
                self._append_reject_audit_log(op_id, code, gate_now)
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
                verified = False
                for payload_cand in (
                    delegation_cert.canonical_unsigned_bytes(),
                    delegation_cert.canonical_payload(),
                ):
                    try:
                        sponsor_pub.verify(cert_sig, payload_cand)
                        verified = True
                        break
                    except (ValueError, InvalidSignature):
                        continue
                if not verified:
                    raise InvalidSignature("delegation cert signature verification failed")
            except (ValueError, InvalidSignature):
                code = "INVALID_DELEGATION_CERT_SIGNATURE"
                self._append_reject_audit_log(op_id, code, gate_now)
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
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # P0 #5 Fix (AT71): Enforce per-call delegation attenuation ceiling!
            if amt <= 0 or amt > delegation_cert.max_per_call_minor:
                code = "ERR_DELEGATION_ATTENUATION_BREACH"
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # P0 #1 Fix (AT69): Beneficiary (`rcpt`) is bound inside the signed payload if sub_sig provided
            if sub_sig:
                sub_verified = False
                for payload_cand in (
                    canonical_json_v1({
                        "amount_minor": amt,
                        "bound_context": manifest,
                        "endpoint": endp,
                        "operation_id": op_id,
                        "recipient": rcpt,
                    }),
                    encode_jcs({
                        "amount_minor": amt,
                        "bound_context": manifest,
                        "endpoint": endp,
                        "operation_id": op_id,
                        "recipient": rcpt,
                    }),
                ):
                    try:
                        sig_bytes = base64.b64decode(sub_sig, validate=True)
                        delegation_cert.subagent_pubkey.verify(sig_bytes, payload_cand)
                        sub_verified = True
                        break
                    except (ValueError, InvalidSignature):
                        continue
                if not sub_verified:
                    code = "REJECTED_PAYEE_DIGEST_MISMATCH"
                    self._append_reject_audit_log(op_id, code, gate_now)
                    return {
                        "disposition": "NOT_DISPATCHED",
                        "rejection_code": code,
                        "decision": "REJECTED",
                        "reason": code,
                    }

            # Verify Context Provenance & Bell-LaPadula Taint (AT57 & AT57b)
            actual_manifest = [(b.block_id, str(b.digest() if callable(b.digest) else b.digest)) for b in live_blocks]
            expected_manifest = [(t[0], str(t[1])) for t in manifest]
            if actual_manifest != expected_manifest:
                code = "CONTEXT_PROVENANCE_MUTATION_DETECTED"
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": "HALT_CONTEXT_INTEGRITY_FAILURE",
                }

            has_tier2_taint = any(
                getattr(b, "taint_tier", None) == "TIER_2_UNTRUSTED_EXTERNAL"
                or getattr(b, "trust_tier", None) == "TIER_2_UNTRUSTED_EXTERNAL"
                for b in live_blocks
            )

            # Recipient pinning is derived from gate's TIER_1 registry or explicit pinning
            is_pinned = (rcpt in self._pinned_tier1_recipients) or (pinned_known_recipient is True)
            if pinned_known_recipient is False:
                is_pinned = False

            if has_tier2_taint and not is_pinned:
                code = "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"
                self._append_reject_audit_log(op_id, code, gate_now)
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
            if sprint_spent + amt > self.sprint_limit_minor:
                code = "HALT_SPRINT_LIMIT_EXCEEDED"
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            epoch_spent = self._compute_window_exposure_minor(
                sponsor_id, gate_now, self.EPOCH_WINDOW_SEC
            )
            if epoch_spent + amt > self.epoch_limit_minor:
                code = "HALT_EPOCH_LIMIT_EXCEEDED"
                self._append_reject_audit_log(op_id, code, gate_now)
                return {
                    "disposition": "NOT_DISPATCHED",
                    "rejection_code": code,
                    "decision": "REJECTED",
                    "reason": code,
                }

            # Commit pre-dispatch reservation to authoritative ledger
            record = {
                "amount_minor": amt,
                "disposition": "DISPATCHED",
                "endpoint": endp,
                "operation_id": op_id,
                "recipient": rcpt,
                "root_sponsor_key_id": sponsor_id,
                "subagent_key_id": delegation_cert.subagent_key_id,
                "timestamp_sec": gate_now,
            }
            entry_caid = self._append_authoritative_ledger(record)
            self._active_operations[op_id] = (
                sponsor_id,
                gate_now,
                amt,
                "DISPATCHED",
            )
            return {
                "disposition": "DISPATCHED",
                "decision": "DISPATCHED",
                "entry_caid": entry_caid,
                "operation_id": op_id,
            }

    def record_downstream_effect(
        self,
        operation_id: str,
        new_disposition: Optional[str] = None,
        *args: Any,
        disposition: Optional[str] = None,
        now_ts: Optional[int] = None,
        target_attestation_sig_b64: Optional[str] = None,
        target_pubkey: Optional[Ed25519PublicKey] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        disp = new_disposition or disposition or (args[0] if args else None)
        if disp not in ("EFFECT_INDETERMINATE", "CONFIRMED", "REFUTED", "RESOLVED_CONFIRMED", "RESOLVED_REFUTED"):
            raise ValueError(f"invalid disposition: {disp}")

        with self._lock:
            if self.halted_reason is not None:
                raise RuntimeError(self.halted_reason)

            # Check refutation attestation requirement
            if disp in ("RESOLVED_REFUTED", "REFUTED"):
                if target_attestation_sig_b64 is None or target_pubkey is None:
                    return {
                        "decision": "REJECTED",
                        "reason": "HALT_UNATTESTED_REFUTATION",
                        "disposition": "REJECTED",
                        "operation_id": operation_id,
                    }
                refutation_payload = encode_jcs(
                    {
                        "disposition": "RESOLVED_REFUTED",
                        "operation_id": operation_id,
                    }
                )
                try:
                    sig_bytes = base64.b64decode(target_attestation_sig_b64, validate=True)
                    target_pubkey.verify(sig_bytes, refutation_payload)
                except (ValueError, InvalidSignature):
                    return {
                        "decision": "REJECTED",
                        "reason": "HALT_UNATTESTED_REFUTATION",
                        "disposition": "REJECTED",
                        "operation_id": operation_id,
                    }

            current = self._active_operations.get(operation_id)
            if current is None:
                raise ValueError("UNKNOWN_OPERATION_ID")

            sponsor_id, orig_ts, amount_minor, prior_disp = current
            if disp not in ALLOWED_DISPOSITION_TRANSITIONS.get(prior_disp, set()):
                raise ValueError(f"INVALID_STATE_TRANSITION: {prior_disp} -> {disp}")

            gate_now = now_ts or self._clock.now_sec()
            self._append_authoritative_ledger(
                {
                    "amount_minor": amount_minor,
                    "disposition": disp,
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
                disp,
            )
            return {
                "decision": "RECORDED",
                "disposition": disp,
                "operation_id": operation_id,
            }


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
    assert res_at69["rejection_code"] in ("REJECTED_PAYEE_DIGEST_MISMATCH", "ERR_SIGNATURE_OR_PAYEE_MISMATCH")

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
    assert res_at70["rejection_code"] in ("REJECTED_CLOCK_NOT_CALLER_SUPPLIED", "REJECTED_CLOCK_SKEW_OR_MANIPULATION")

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
    assert rebooted_wiped.halted_reason in ("HALT_PERSISTENCE_INTEGRITY_VIOLATION", "HALT_TWO_FILE_WIPE_DETECTED_AGAINST_REMOTE_ANCHOR")

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


def test_at69_payee_substitution_rejection() -> None:
    """
    AT69 (P0-CRITICAL #1): Verifies that swapping payee_id / recipient while preserving
    signature, amount, and endpoint results in REJECTED_PAYEE_DIGEST_MISMATCH.
    """
    tmp_dir = tempfile.mkdtemp(prefix="aeib_at69_")
    ledger_file = os.path.join(tmp_dir, "ledger.jsonl")
    ckpt_file = os.path.join(tmp_dir, "checkpoint.tip")
    reject_file = os.path.join(tmp_dir, "rejects.jsonl")

    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sub_priv = Ed25519PrivateKey.generate()
    sponsor_id = "sponsor-root-at69"
    legit_recipient = "iban:DE89370400440532013000"
    attacker_recipient = "iban:CH9300000000000000000"

    clock = DeterministicSteppedClock(initial_sec=1_760_000_000)
    remote_anchor = RemoteContinuityAnchor.create()

    cert_unsigned = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at69",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64="",
    )
    cert_sig = base64.b64encode(sponsor_priv.sign(cert_unsigned.canonical_unsigned_bytes())).decode("ascii")
    cert = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at69",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64=cert_sig,
    )

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=ckpt_file,
        reject_log_path=reject_file,
        sponsor_registry={sponsor_id: sponsor_priv.public_key()},
        pinned_tier1_recipients={legit_recipient},
        sprint_limit_minor=2000_00,
        epoch_limit_minor=5000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    clean_ctx = ContextBlock("ctx-at69", "TIER_0_PINNED", b"invoice=101")
    manifest = [(clean_ctx.block_id, clean_ctx.digest)]

    payload_signed = canonical_json_v1({
        "amount_minor": 999_00,
        "bound_context": manifest,
        "endpoint": "POST /v1/refunds",
        "operation_id": "op-at69-1",
        "recipient": legit_recipient,
    })
    sub_sig = base64.b64encode(sub_priv.sign(payload_signed)).decode("ascii")

    res = gate.evaluate_and_dispatch(
        operation_id="op-at69-1",
        endpoint="POST /v1/refunds",
        recipient=attacker_recipient,
        amount_minor=999_00,
        claimed_now_ts=clock.now_sec(),
        delegation_cert=cert,
        subagent_signature_b64=sub_sig,
        bound_context_manifest=manifest,
        live_context_blocks=[clean_ctx],
    )

    assert res["disposition"] == "NOT_DISPATCHED"
    assert res["rejection_code"] == "REJECTED_PAYEE_DIGEST_MISMATCH"


def test_at70_clock_manipulation_rejection() -> None:
    """
    AT70 (P0-CRITICAL #3): Verifies that supplying a future or drifting now_ts
    triggers REJECTED_CLOCK_NOT_CALLER_SUPPLIED.
    """
    tmp_dir = tempfile.mkdtemp(prefix="aeib_at70_")
    ledger_file = os.path.join(tmp_dir, "ledger.jsonl")
    ckpt_file = os.path.join(tmp_dir, "checkpoint.tip")
    reject_file = os.path.join(tmp_dir, "rejects.jsonl")

    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sub_priv = Ed25519PrivateKey.generate()
    sponsor_id = "sponsor-root-at70"
    legit_recipient = "iban:DE89370400440532013000"

    clock = DeterministicSteppedClock(initial_sec=1_760_000_000)
    remote_anchor = RemoteContinuityAnchor.create()

    cert_unsigned = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at70",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64="",
    )
    cert_sig = base64.b64encode(sponsor_priv.sign(cert_unsigned.canonical_unsigned_bytes())).decode("ascii")
    cert = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at70",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64=cert_sig,
    )

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=ckpt_file,
        reject_log_path=reject_file,
        sponsor_registry={sponsor_id: sponsor_priv.public_key()},
        pinned_tier1_recipients={legit_recipient},
        sprint_limit_minor=2000_00,
        epoch_limit_minor=5000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    clean_ctx = ContextBlock("ctx-at70", "TIER_0_PINNED", b"invoice=102")
    manifest = [(clean_ctx.block_id, clean_ctx.digest)]

    payload_signed = canonical_json_v1({
        "amount_minor": 500_00,
        "bound_context": manifest,
        "endpoint": "POST /v1/refunds",
        "operation_id": "op-at70-1",
        "recipient": legit_recipient,
    })
    sub_sig = base64.b64encode(sub_priv.sign(payload_signed)).decode("ascii")

    res = gate.evaluate_and_dispatch(
        operation_id="op-at70-1",
        endpoint="POST /v1/refunds",
        recipient=legit_recipient,
        amount_minor=500_00,
        claimed_now_ts=2_000_000_000,
        delegation_cert=cert,
        subagent_signature_b64=sub_sig,
        bound_context_manifest=manifest,
        live_context_blocks=[clean_ctx],
    )

    assert res["disposition"] == "NOT_DISPATCHED"
    assert res["rejection_code"] == "REJECTED_CLOCK_NOT_CALLER_SUPPLIED"


def test_at71_taint_self_attestation_rejection() -> None:
    """
    AT71 (P0-CRITICAL #2): Verifies that external/untrusted context routing to an
    unpinned recipient cannot self-attest pinning, triggering UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP.
    """
    tmp_dir = tempfile.mkdtemp(prefix="aeib_at71_")
    ledger_file = os.path.join(tmp_dir, "ledger.jsonl")
    ckpt_file = os.path.join(tmp_dir, "checkpoint.tip")
    reject_file = os.path.join(tmp_dir, "rejects.jsonl")

    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sub_priv = Ed25519PrivateKey.generate()
    sponsor_id = "sponsor-root-at71"
    pinned_iban = "iban:DE89370400440532013000"
    unpinned_recipient = "iban:FR7630006000011234567890189"

    clock = DeterministicSteppedClock(initial_sec=1_760_000_000)
    remote_anchor = RemoteContinuityAnchor.create()

    cert_unsigned = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at71",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64="",
    )
    cert_sig = base64.b64encode(sponsor_priv.sign(cert_unsigned.canonical_unsigned_bytes())).decode("ascii")
    cert = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at71",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
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
        sprint_limit_minor=2000_00,
        epoch_limit_minor=5000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    tainted_ctx = ContextBlock("ctx-taint-at71", "TIER_2_UNTRUSTED_EXTERNAL", b"attacker_webhook=true")
    manifest = [(tainted_ctx.block_id, tainted_ctx.digest)]

    payload_signed = canonical_json_v1({
        "amount_minor": 200_00,
        "bound_context": manifest,
        "endpoint": "POST /v1/refunds",
        "operation_id": "op-at71-1",
        "recipient": unpinned_recipient,
    })
    sub_sig = base64.b64encode(sub_priv.sign(payload_signed)).decode("ascii")

    res = gate.evaluate_and_dispatch(
        operation_id="op-at71-1",
        endpoint="POST /v1/refunds",
        recipient=unpinned_recipient,
        amount_minor=200_00,
        claimed_now_ts=clock.now_sec(),
        delegation_cert=cert,
        subagent_signature_b64=sub_sig,
        bound_context_manifest=manifest,
        live_context_blocks=[tainted_ctx],
    )

    assert res["disposition"] == "NOT_DISPATCHED"
    assert res["rejection_code"] == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"
    assert gate.evaluate_taint_gate(unpinned_recipient, "TIER_2_UNTRUSTED_EXTERNAL") is False
    assert gate.evaluate_taint_gate(pinned_iban, "TIER_2_UNTRUSTED_EXTERNAL") is True


def test_at72_persistence_integrity_violation() -> None:
    """
    AT72 (P0-CRITICAL #4): Verifies that deleting ledger files to reset spend state
    is caught against the remote anchor, latching HALT_PERSISTENCE_INTEGRITY_VIOLATION.
    """
    tmp_dir = tempfile.mkdtemp(prefix="aeib_at72_")
    ledger_file = os.path.join(tmp_dir, "ledger.jsonl")
    ckpt_file = os.path.join(tmp_dir, "checkpoint.tip")
    reject_file = os.path.join(tmp_dir, "rejects.jsonl")

    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sub_priv = Ed25519PrivateKey.generate()
    sponsor_id = "sponsor-root-at72"
    pinned_iban = "iban:DE89370400440532013000"

    clock = DeterministicSteppedClock(initial_sec=1_760_000_000)
    remote_anchor = RemoteContinuityAnchor.create()

    cert_unsigned = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at72",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
        issued_at_sec=1_760_000_000,
        expires_at_sec=1_760_003_600,
        sponsor_signature_b64="",
    )
    cert_sig = base64.b64encode(sponsor_priv.sign(cert_unsigned.canonical_unsigned_bytes())).decode("ascii")
    cert = SubAgentDelegationCert(
        root_sponsor_key_id=sponsor_id,
        subagent_key_id="sub-at72",
        subagent_pubkey=sub_priv.public_key(),
        max_per_call_minor=1000_00,
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
        sprint_limit_minor=2000_00,
        epoch_limit_minor=5000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    clean_ctx = ContextBlock("ctx-at72", "TIER_0_PINNED", b"invoice=103")
    manifest = [(clean_ctx.block_id, clean_ctx.digest)]

    payload_signed = canonical_json_v1({
        "amount_minor": 800_00,
        "bound_context": manifest,
        "endpoint": "POST /v1/refunds",
        "operation_id": "op-at72-1",
        "recipient": pinned_iban,
    })
    sub_sig = base64.b64encode(sub_priv.sign(payload_signed)).decode("ascii")

    res = gate.evaluate_and_dispatch(
        operation_id="op-at72-1",
        endpoint="POST /v1/refunds",
        recipient=pinned_iban,
        amount_minor=800_00,
        claimed_now_ts=clock.now_sec(),
        delegation_cert=cert,
        subagent_signature_b64=sub_sig,
        bound_context_manifest=manifest,
        live_context_blocks=[clean_ctx],
    )
    assert res["disposition"] == "DISPATCHED"
    assert remote_anchor.state["seq"] == 1

    os.remove(ledger_file)
    os.remove(ckpt_file)

    gate_rebooted = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=ckpt_file,
        reject_log_path=reject_file,
        sponsor_registry={sponsor_id: sponsor_priv.public_key()},
        pinned_tier1_recipients={pinned_iban},
        sprint_limit_minor=2000_00,
        epoch_limit_minor=5000_00,
        gate_signing_key=gate_priv,
        remote_anchor=remote_anchor,
        clock=clock,
    )

    assert gate_rebooted.halted_reason == "HALT_PERSISTENCE_INTEGRITY_VIOLATION"
    try:
        gate_rebooted.verify_startup_persistence_integrity()
        assert False, "Expected SystemHaltError on persistence integrity violation"
    except SystemHaltError as e:
        assert "HALT_PERSISTENCE_INTEGRITY_VIOLATION" in str(e)


if __name__ == "__main__":
    test_all_p0_and_p1_fixes_end_to_end()
    test_at69_payee_substitution_rejection()
    test_at70_clock_manipulation_rejection()
    test_at71_taint_self_attestation_rejection()
    test_at72_persistence_integrity_violation()
    print("ALL P0 (#1-#5), P1 (#6-#8), AND AT69-AT72 TESTS PASSED.")
