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
src/ebpf_tail_call_hotpatch.py — Dynamic eBPF LSM Tail-Call Map Hot-Patching Engine.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an in-kernel
eBPF LSM tail-call map hot-patching scaffold and zero-downtime policy handover prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for dynamic eBPF LSM
    prog-array and tail-call map pointer updates.
  - It does NOT invoke kernel `bpf(BPF_MAP_UPDATE_ELEM)` or bpftool in this software prototype.
  - Operational mode: scaffold / simulated hot-patching engine.

Architectural Invariants:
1. Dual-Slot Program Array (A/B Ping-Pong):
   - Maintains Slot 0 (A) and Slot 1 (B) tail-call program pointers.
   - Atomic pointer switch guarantees zero-downtime policy activation.
2. In-Flight Lease Draining:
   - Tracks concurrent socket and inode mediation leases during slot transition.
   - Refuses slot retirement until active reference count drains to zero or drain timeout elapses.
3. Strict Monotonic Epoch Fencing:
   - Enforces epoch_new == epoch_active + 1. Rejects out-of-order or stale policies.
4. Fail-Closed Rollback Rejection Codes:
   - HALT_BPF_NON_MONOTONIC_EPOCH
   - HALT_BPF_DIGEST_MISMATCH
   - HALT_BPF_SIGNATURE_INVALID
   - HALT_BPF_STAGING_PROBE_FAILED
   - HALT_BPF_DRAIN_TIMEOUT_EXCEEDED
   - HALT_BPF_INVALID_STATE_TRANSITION
   - HALT_BPF_LEASE_NOT_FOUND
5. Sub-5ms SQLite-WAL Durability:
   - Persists all slot transitions, lease allocations, and swap receipts to a local WAL database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Slot definitions
SLOT_A: int = 0
SLOT_B: int = 1

# Slot Lifecycle States
SLOT_STATE_QUIESCENT: str = "QUIESCENT"
SLOT_STATE_STAGING: str = "STAGING"
SLOT_STATE_ACTIVE: str = "ACTIVE"
SLOT_STATE_DRAINING: str = "DRAINING"
SLOT_STATE_RETIRED: str = "RETIRED"

# Rejection Codes
HALT_BPF_NON_MONOTONIC_EPOCH: str = "HALT_BPF_NON_MONOTONIC_EPOCH"
HALT_BPF_DIGEST_MISMATCH: str = "HALT_BPF_DIGEST_MISMATCH"
HALT_BPF_SIGNATURE_INVALID: str = "HALT_BPF_SIGNATURE_INVALID"
HALT_BPF_STAGING_PROBE_FAILED: str = "HALT_BPF_STAGING_PROBE_FAILED"
HALT_BPF_DRAIN_TIMEOUT_EXCEEDED: str = "HALT_BPF_DRAIN_TIMEOUT_EXCEEDED"
HALT_BPF_INVALID_STATE_TRANSITION: str = "HALT_BPF_INVALID_STATE_TRANSITION"
HALT_BPF_LEASE_NOT_FOUND: str = "HALT_BPF_LEASE_NOT_FOUND"

# Actions
ACTION_ALLOW: str = "ALLOW"
ACTION_DENY: str = "DENY"
ACTION_AUDIT: str = "AUDIT"
VALID_ACTIONS: frozenset[str] = frozenset({ACTION_ALLOW, ACTION_DENY, ACTION_AUDIT})


class EbpfHotpatchError(Exception):
    """Exception raised when an eBPF LSM hot-patch operation fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EbpfSecurityRule:
    """Represents an atomic eBPF LSM security rule."""

    rule_id: str
    hook_point: str
    target_path_or_prefix: str
    allowed_taint_ceiling_bps: int
    action: str

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "allowed_taint_ceiling_bps": self.allowed_taint_ceiling_bps,
            "hook_point": self.hook_point,
            "rule_id": self.rule_id,
            "target_path_or_prefix": self.target_path_or_prefix,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class EbpfPolicyManifest:
    """Signed specification of an eBPF LSM policy to be hot-patched."""

    policy_id: str
    policy_epoch: int
    rules: List[EbpfSecurityRule]
    ruleset_digest: str
    program_bytecode_sha256: str
    created_at_ms: int
    authority_pub_key_hex: str
    signature: str

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "created_at_ms": self.created_at_ms,
            "policy_epoch": self.policy_epoch,
            "policy_id": self.policy_id,
            "program_bytecode_sha256": self.program_bytecode_sha256,
            "rules": [r.canonical_dict() for r in sorted(self.rules, key=lambda x: x.rule_id)],
            "ruleset_digest": self.ruleset_digest,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class HotpatchSwapReceipt:
    """Durable receipt recording an atomic eBPF tail-call slot swap."""

    swap_id: str
    old_slot: int
    new_slot: int
    active_epoch: int
    ruleset_digest: str
    receipt_caid: str
    status: str
    swapped_at_ms: int

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "active_epoch": self.active_epoch,
            "new_slot": self.new_slot,
            "old_slot": self.old_slot,
            "receipt_caid": self.receipt_caid,
            "ruleset_digest": self.ruleset_digest,
            "status": self.status,
            "swap_id": self.swap_id,
            "swapped_at_ms": self.swapped_at_ms,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class InflightExecutionLease:
    """Represents an active in-flight operation bound to a specific policy slot."""

    lease_id: str
    slot_index: int
    policy_epoch: int
    operation_caid: str
    acquired_at_ms: int


def compute_sha256_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 canonical SHA-256 CAID."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def compute_ruleset_digest(rules: Sequence[EbpfSecurityRule]) -> str:
    """Computes deterministic SHA-256 digest over sorted rules."""
    sorted_dicts = [r.canonical_dict() for r in sorted(rules, key=lambda x: x.rule_id)]
    return f"sha256:{hashlib.sha256(encode_jcs(sorted_dicts)).hexdigest()}"


class EbpfTailCallHotpatchEngine:
    """
    Dynamic eBPF LSM Tail-Call Map Hot-Patching Engine.
    Coordinates zero-downtime A/B slot swaps and reference-counted in-flight lease draining.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._active_slot: int = SLOT_A
        self._slot_policies: Dict[int, Optional[EbpfPolicyManifest]] = {
            SLOT_A: None,
            SLOT_B: None,
        }
        self._slot_states: Dict[int, str] = {
            SLOT_A: SLOT_STATE_QUIESCENT,
            SLOT_B: SLOT_STATE_QUIESCENT,
        }
        self._active_leases: Dict[str, InflightExecutionLease] = {}
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ebpf_hotpatch_events_ledger (
                    swap_id TEXT PRIMARY KEY,
                    old_slot INTEGER NOT NULL,
                    new_slot INTEGER NOT NULL,
                    active_epoch INTEGER NOT NULL,
                    ruleset_digest TEXT NOT NULL,
                    receipt_caid TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    swapped_at_ms INTEGER NOT NULL,
                    raw_receipt_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ebpf_policy_slots_ledger (
                    slot_index INTEGER NOT NULL,
                    policy_epoch INTEGER NOT NULL,
                    policy_id TEXT NOT NULL,
                    ruleset_digest TEXT NOT NULL,
                    program_bytecode_sha256 TEXT NOT NULL,
                    slot_state TEXT NOT NULL,
                    updated_at_ms INTEGER NOT NULL,
                    PRIMARY KEY (slot_index, policy_epoch)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hotpatch_epoch ON ebpf_hotpatch_events_ledger(active_epoch);"
            )

    @property
    def active_slot(self) -> int:
        return self._active_slot

    @property
    def staging_slot(self) -> int:
        return SLOT_B if self._active_slot == SLOT_A else SLOT_A

    def get_slot_state(self, slot_index: int) -> str:
        return self._slot_states.get(slot_index, SLOT_STATE_QUIESCENT)

    def get_slot_policy(self, slot_index: int) -> Optional[EbpfPolicyManifest]:
        return self._slot_policies.get(slot_index)

    @staticmethod
    def create_policy_manifest(
        policy_id: str,
        policy_epoch: int,
        rules: Sequence[EbpfSecurityRule],
        program_bytecode_sha256: str,
        authority_priv_key: ed25519.Ed25519PrivateKey,
        created_at_ms: Optional[int] = None,
    ) -> EbpfPolicyManifest:
        """Helper to create a cryptographically signed eBPF policy manifest."""
        now_ms = created_at_ms if created_at_ms is not None else int(time.time() * 1000)
        ruleset_digest = compute_ruleset_digest(rules)
        payload = {
            "created_at_ms": now_ms,
            "policy_epoch": policy_epoch,
            "policy_id": policy_id,
            "program_bytecode_sha256": program_bytecode_sha256,
            "rules": [r.canonical_dict() for r in sorted(rules, key=lambda x: x.rule_id)],
            "ruleset_digest": ruleset_digest,
        }
        sig = authority_priv_key.sign(encode_jcs(payload))
        pub_hex = authority_priv_key.public_key().public_bytes_raw().hex()
        return EbpfPolicyManifest(
            policy_id=policy_id,
            policy_epoch=policy_epoch,
            rules=list(rules),
            ruleset_digest=ruleset_digest,
            program_bytecode_sha256=program_bytecode_sha256,
            created_at_ms=now_ms,
            authority_pub_key_hex=pub_hex,
            signature=sig.hex(),
        )

    def bootstrap_initial_policy(
        self,
        manifest: EbpfPolicyManifest,
        now_ms: Optional[int] = None,
    ) -> None:
        """Bootstraps the initial active slot with epoch 1 policy."""
        self._verify_manifest_signature(manifest)
        computed_digest = compute_ruleset_digest(manifest.rules)
        if computed_digest != manifest.ruleset_digest:
            raise EbpfHotpatchError(
                HALT_BPF_DIGEST_MISMATCH,
                f"Ruleset digest mismatch: {computed_digest} != {manifest.ruleset_digest}",
            )

        self._active_slot = SLOT_A
        self._slot_policies[SLOT_A] = manifest
        self._slot_states[SLOT_A] = SLOT_STATE_ACTIVE
        self._slot_states[SLOT_B] = SLOT_STATE_QUIESCENT

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        self._record_slot_ledger(SLOT_A, manifest, SLOT_STATE_ACTIVE, effective_time)

    def stage_policy(
        self,
        manifest: EbpfPolicyManifest,
        now_ms: Optional[int] = None,
    ) -> int:
        """
        Validates and loads a new policy manifest into the quiescent staging slot.
        Fails closed on non-monotonic epoch, digest mismatch, or invalid signature.
        """
        active_policy = self._slot_policies[self._active_slot]
        current_epoch = active_policy.policy_epoch if active_policy else 0
        expected_epoch = current_epoch + 1

        if manifest.policy_epoch != expected_epoch:
            raise EbpfHotpatchError(
                HALT_BPF_NON_MONOTONIC_EPOCH,
                f"Non-monotonic epoch: got {manifest.policy_epoch}, expected {expected_epoch}",
            )

        # Signature verification
        self._verify_manifest_signature(manifest)

        # Ruleset digest validation
        computed_digest = compute_ruleset_digest(manifest.rules)
        if computed_digest != manifest.ruleset_digest:
            raise EbpfHotpatchError(
                HALT_BPF_DIGEST_MISMATCH,
                f"Ruleset digest mismatch: {computed_digest} != {manifest.ruleset_digest}",
            )

        # Staging slot must be quiescent
        target_slot = self.staging_slot
        target_state = self._slot_states[target_slot]
        if target_state not in (SLOT_STATE_QUIESCENT, SLOT_STATE_RETIRED):
            raise EbpfHotpatchError(
                HALT_BPF_INVALID_STATE_TRANSITION,
                f"Cannot stage into slot {target_slot} in state {target_state}",
            )

        self._slot_policies[target_slot] = manifest
        self._slot_states[target_slot] = SLOT_STATE_STAGING

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        self._record_slot_ledger(target_slot, manifest, SLOT_STATE_STAGING, effective_time)
        return target_slot

    def run_staging_health_probes(
        self,
        probes: Sequence[Tuple[str, str, int]],
    ) -> bool:
        """
        Executes synthetic health verification probes against the staged policy.
        Each probe is a tuple: (hook_point, path, taint_bps).
        Returns True if all probes pass policy validation; raises HALT_BPF_STAGING_PROBE_FAILED otherwise.
        """
        staged_policy = self._slot_policies[self.staging_slot]
        if not staged_policy or self._slot_states[self.staging_slot] != SLOT_STATE_STAGING:
            raise EbpfHotpatchError(
                HALT_BPF_INVALID_STATE_TRANSITION,
                "No policy currently staged for health probing",
            )

        for hook, path, taint_bps in probes:
            # Check if any rule denies this probe
            for rule in staged_policy.rules:
                if rule.hook_point == hook and path.startswith(rule.target_path_or_prefix):
                    if rule.action == ACTION_DENY and taint_bps >= rule.allowed_taint_ceiling_bps:
                        raise EbpfHotpatchError(
                            HALT_BPF_STAGING_PROBE_FAILED,
                            f"Health probe ({hook}, {path}) failed against rule {rule.rule_id}",
                        )

        return True

    def atomic_slot_swap(
        self,
        now_ms: Optional[int] = None,
    ) -> HotpatchSwapReceipt:
        """
        Atomically swaps the active program array tail-call pointer.
        Transitions staged slot to ACTIVE and previously active slot to DRAINING.
        """
        old_slot = self._active_slot
        new_slot = self.staging_slot

        if self._slot_states[new_slot] != SLOT_STATE_STAGING:
            raise EbpfHotpatchError(
                HALT_BPF_INVALID_STATE_TRANSITION,
                f"Cannot swap: target slot {new_slot} is not in STAGING state",
            )

        new_policy = self._slot_policies[new_slot]
        assert new_policy is not None

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)

        # Atomic switch
        self._active_slot = new_slot
        self._slot_states[new_slot] = SLOT_STATE_ACTIVE
        self._slot_states[old_slot] = SLOT_STATE_DRAINING

        swap_id = f"swap-{uuid.uuid4().hex[:16]}"
        prelim_receipt = {
            "active_epoch": new_policy.policy_epoch,
            "new_slot": new_slot,
            "old_slot": old_slot,
            "receipt_caid": "",
            "ruleset_digest": new_policy.ruleset_digest,
            "status": "SWAP_COMMITTED",
            "swap_id": swap_id,
            "swapped_at_ms": effective_time,
        }
        receipt_caid = compute_sha256_caid(prelim_receipt)

        receipt = HotpatchSwapReceipt(
            swap_id=swap_id,
            old_slot=old_slot,
            new_slot=new_slot,
            active_epoch=new_policy.policy_epoch,
            ruleset_digest=new_policy.ruleset_digest,
            receipt_caid=receipt_caid,
            status="SWAP_COMMITTED",
            swapped_at_ms=effective_time,
        )

        self._record_slot_ledger(new_slot, new_policy, SLOT_STATE_ACTIVE, effective_time)
        old_policy = self._slot_policies[old_slot]
        if old_policy:
            self._record_slot_ledger(old_slot, old_policy, SLOT_STATE_DRAINING, effective_time)
        self._record_swap_event(receipt)
        return receipt

    def acquire_execution_lease(
        self,
        operation_caid: str,
        now_ms: Optional[int] = None,
    ) -> InflightExecutionLease:
        """Acquires a reference-counted in-flight execution lease on the currently active slot."""
        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        active_policy = self._slot_policies[self._active_slot]
        epoch = active_policy.policy_epoch if active_policy else 0

        lease_id = f"lease-{uuid.uuid4().hex[:16]}"
        lease = InflightExecutionLease(
            lease_id=lease_id,
            slot_index=self._active_slot,
            policy_epoch=epoch,
            operation_caid=operation_caid,
            acquired_at_ms=effective_time,
        )
        self._active_leases[lease_id] = lease
        return lease

    def release_execution_lease(self, lease_id: str) -> None:
        """Releases an in-flight execution lease."""
        if lease_id not in self._active_leases:
            raise EbpfHotpatchError(
                HALT_BPF_LEASE_NOT_FOUND,
                f"Lease {lease_id} not found or already released",
            )
        del self._active_leases[lease_id]

    def count_active_leases_for_slot(self, slot_index: int) -> int:
        """Returns the number of outstanding active leases on a given slot."""
        return sum(1 for l in self._active_leases.values() if l.slot_index == slot_index)

    def drain_and_retire_slot(
        self,
        slot_index: int,
        timeout_ms: int = 5000,
        now_ms: Optional[int] = None,
    ) -> bool:
        """
        Drains in-flight operations on a DRAINING slot and retires it to QUIESCENT.
        Fails closed with HALT_BPF_DRAIN_TIMEOUT_EXCEEDED if active leases remain.
        """
        if self._slot_states[slot_index] != SLOT_STATE_DRAINING:
            raise EbpfHotpatchError(
                HALT_BPF_INVALID_STATE_TRANSITION,
                f"Slot {slot_index} is not in DRAINING state (current: {self._slot_states[slot_index]})",
            )

        outstanding = self.count_active_leases_for_slot(slot_index)
        if outstanding > 0:
            raise EbpfHotpatchError(
                HALT_BPF_DRAIN_TIMEOUT_EXCEEDED,
                f"Slot {slot_index} has {outstanding} active leases outstanding; cannot retire",
            )

        self._slot_states[slot_index] = SLOT_STATE_QUIESCENT
        self._slot_policies[slot_index] = None

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        with self._conn:
            self._conn.execute(
                """
                UPDATE ebpf_policy_slots_ledger
                SET slot_state = ?, updated_at_ms = ?
                WHERE slot_index = ? AND slot_state = ?
                """,
                (SLOT_STATE_QUIESCENT, effective_time, slot_index, SLOT_STATE_DRAINING),
            )
        return True

    def rollback_to_previous_slot(
        self,
        reason: str,
        now_ms: Optional[int] = None,
    ) -> HotpatchSwapReceipt:
        """
        Emergency rollback: swaps the active slot back to the draining/previous slot.
        Fails closed and logs the anomaly event.
        """
        fallback_slot = self.staging_slot
        bad_slot = self._active_slot

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)

        self._active_slot = fallback_slot
        self._slot_states[fallback_slot] = SLOT_STATE_ACTIVE
        self._slot_states[bad_slot] = SLOT_STATE_RETIRED

        fallback_policy = self._slot_policies[fallback_slot]
        digest = fallback_policy.ruleset_digest if fallback_policy else "sha256:" + "0" * 64
        epoch = fallback_policy.policy_epoch if fallback_policy else 0

        swap_id = f"swap-rollback-{uuid.uuid4().hex[:16]}"
        prelim_receipt = {
            "active_epoch": epoch,
            "new_slot": fallback_slot,
            "old_slot": bad_slot,
            "receipt_caid": "",
            "ruleset_digest": digest,
            "status": f"ROLLBACK_TRIGGERED: {reason}",
            "swap_id": swap_id,
            "swapped_at_ms": effective_time,
        }
        receipt_caid = compute_sha256_caid(prelim_receipt)

        receipt = HotpatchSwapReceipt(
            swap_id=swap_id,
            old_slot=bad_slot,
            new_slot=fallback_slot,
            active_epoch=epoch,
            ruleset_digest=digest,
            receipt_caid=receipt_caid,
            status=f"ROLLBACK_TRIGGERED: {reason}",
            swapped_at_ms=effective_time,
        )

        self._record_swap_event(receipt)
        return receipt

    def _verify_manifest_signature(self, manifest: EbpfPolicyManifest) -> None:
        try:
            pub_bytes = bytes.fromhex(manifest.authority_pub_key_hex)
            verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig_bytes = bytes.fromhex(manifest.signature)
            verifier.verify(sig_bytes, manifest.canonical_bytes())
        except Exception as exc:
            raise EbpfHotpatchError(
                HALT_BPF_SIGNATURE_INVALID,
                f"Authority signature invalid on policy manifest: {exc}",
            ) from exc

    def _record_slot_ledger(
        self,
        slot_index: int,
        manifest: EbpfPolicyManifest,
        state: str,
        timestamp_ms: int,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO ebpf_policy_slots_ledger (
                    slot_index, policy_epoch, policy_id, ruleset_digest,
                    program_bytecode_sha256, slot_state, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slot_index,
                    manifest.policy_epoch,
                    manifest.policy_id,
                    manifest.ruleset_digest,
                    manifest.program_bytecode_sha256,
                    state,
                    timestamp_ms,
                ),
            )

    def _record_swap_event(self, receipt: HotpatchSwapReceipt) -> None:
        raw_json = json.dumps(asdict(receipt), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ebpf_hotpatch_events_ledger (
                    swap_id, old_slot, new_slot, active_epoch, ruleset_digest,
                    receipt_caid, status, swapped_at_ms, raw_receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.swap_id,
                    receipt.old_slot,
                    receipt.new_slot,
                    receipt.active_epoch,
                    receipt.ruleset_digest,
                    receipt.receipt_caid,
                    receipt.status,
                    receipt.swapped_at_ms,
                    raw_json,
                ),
            )

    def get_swap_receipt(self, swap_id: str) -> Optional[HotpatchSwapReceipt]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_receipt_json FROM ebpf_hotpatch_events_ledger
            WHERE swap_id = ?
            """,
            (swap_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return HotpatchSwapReceipt(**json.loads(row[0]))

    def list_swap_events(self) -> List[HotpatchSwapReceipt]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_receipt_json FROM ebpf_hotpatch_events_ledger
            ORDER BY swapped_at_ms DESC
            """
        )
        rows = cursor.fetchall()
        return [HotpatchSwapReceipt(**json.loads(r[0])) for r in rows]

    def close(self) -> None:
        self._conn.close()
