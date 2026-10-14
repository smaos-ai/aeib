"""
v1.1-roadmap/external_checkpoint_anchor.py — External Witness Checkpoint Anchor Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 3.3 Core Delivery Contract:
Periodically aggregates continuous ledger hash-chain entries into Merkle trees,
computing cryptographically anchored Merkle checkpoint roots:
  1. Merkle tree computation over SHA-256 leaf hashes (RFC 6962 alignment).
  2. Checkpoint commitment:
     (checkpoint_seq, start_seq, end_seq, merkle_root, previous_checkpoint_root, timestamp_utc)
     canonicalized via RFC 8785 JCS and signed using an external witness Ed25519 key.
  3. Outage window lifecycle management:
     - State machine: ANCHOR_STATE_ACTIVE vs ANCHOR_STATE_OUTAGE.
     - When the witness is unreachable: records DISPATCH_UNANCHORED_LOCAL_ONLY status,
       buffers unanchored checkpoints, and tracks outage elapsed time.
     - Safety interlock: trips CheckpointOutageCeilingExceededError if max_outage_seconds
       or max_unanchored_batches is exceeded.
  4. Outage recovery and burst reconciliation (RECONCILE_OUTAGE_BURST):
     - Bursts queued checkpoints in strict chronological order upon reconnect.
     - Verifies cumulative hash-chain continuity across the outage gap.
     - Emits a signed OutageReconciliationReceipt and transitions back to ANCHOR_STATE_ACTIVE.

Operates under the stated model: Fails closed on any sequence or hash continuity violation.
"""

from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class CheckpointAnchorError(Exception):
    """Base exception for external checkpoint anchor errors."""


class CheckpointOutageCeilingExceededError(CheckpointAnchorError):
    """Raised when outage duration or unanchored batch count exceeds configured ceiling."""


class CheckpointContinuityError(CheckpointAnchorError):
    """Raised when sequence or hash-chain continuity across an outage gap is violated."""


class InvalidCheckpointSignatureError(CheckpointAnchorError):
    """Raised when an anchored checkpoint signature verification fails."""


# Lifecycle state constants
ANCHOR_STATE_ACTIVE = "ANCHOR_STATE_ACTIVE"
ANCHOR_STATE_OUTAGE = "ANCHOR_STATE_OUTAGE"

# Dispatch disposition during witness outage
DISPATCH_UNANCHORED_LOCAL_ONLY = "DISPATCH_UNANCHORED_LOCAL_ONLY"

# Burst reconciliation phase
RECONCILE_OUTAGE_BURST = "RECONCILE_OUTAGE_BURST"

# Normal anchored status
STATUS_ANCHORED = "ANCHORED"


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """
    Computes binary SHA-256 Merkle root from an ordered list of leaf hex hashes.
    RFC 6962 alignment: if layer length is odd, duplicate last element.
    """
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()

    # Validate and convert leaf hashes to bytes
    layer: List[bytes] = []
    for idx, h in enumerate(leaf_hashes):
        cleaned = h.strip().lower()
        if len(cleaned) != 64:
            raise ValueError(f"Leaf hash at index {idx} has invalid length {len(cleaned)} (expected 64)")
        try:
            layer.append(bytes.fromhex(cleaned))
        except ValueError as exc:
            raise ValueError(f"Leaf hash at index {idx} is not valid hex: {exc}") from exc

    if len(layer) == 1:
        return layer[0].hex()

    while len(layer) > 1:
        next_layer: List[bytes] = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if (i + 1 < len(layer)) else left
            combined = hashlib.sha256(left + right).digest()
            next_layer.append(combined)
        layer = next_layer

    return layer[0].hex()


@dataclass(frozen=True)
class CheckpointCommitment:
    """Canonical checkpoint commitment structure."""

    checkpoint_seq: int
    start_seq: int
    end_seq: int
    merkle_root: str
    previous_checkpoint_root: str
    timestamp_utc: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "checkpointSeq": self.checkpoint_seq,
            "endSeq": self.end_seq,
            "merkleRoot": self.merkle_root,
            "previousCheckpointRoot": self.previous_checkpoint_root,
            "startSeq": self.start_seq,
            "timestampUtc": self.timestamp_utc,
        }

    def compute_digest(self) -> str:
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass(frozen=True)
class AnchoredCheckpoint:
    """Individual checkpoint with witness signature and state status."""

    commitment: CheckpointCommitment
    witness_public_key_hex: str
    signature_hex: str
    status: str

    def verify_signature(self, witness_public_key: Optional[Ed25519PublicKey] = None) -> bool:
        """Verifies the Ed25519 signature over canonical RFC 8785 JCS bytes."""
        if self.status != STATUS_ANCHORED or not self.signature_hex:
            return False

        pub = witness_public_key
        if pub is None:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.witness_public_key_hex))

        canonical_bytes = encode_jcs(self.commitment.to_canonical_dict())
        try:
            pub.verify(bytes.fromhex(self.signature_hex), canonical_bytes)
            return True
        except InvalidSignature:
            return False


@dataclass(frozen=True)
class OutageReconciliationReceipt:
    """Notarized receipt certifying batch reconciliation across an outage window."""

    receipt_id: str
    action_phase: str
    start_checkpoint_seq: int
    end_checkpoint_seq: int
    reconciled_batch_count: int
    prior_anchored_root: str
    latest_anchored_root: str
    outage_duration_seconds: float
    timestamp_utc: str
    witness_public_key_hex: str
    signature_hex: str

    def to_canonical_statement(self) -> Dict[str, Any]:
        return {
            "actionPhase": self.action_phase,
            "endCheckpointSeq": self.end_checkpoint_seq,
            "latestAnchoredRoot": self.latest_anchored_root,
            "outageDurationSeconds": round(self.outage_duration_seconds, 6),
            "priorAnchoredRoot": self.prior_anchored_root,
            "receiptId": self.receipt_id,
            "reconciledBatchCount": self.reconciled_batch_count,
            "startCheckpointSeq": self.start_checkpoint_seq,
            "timestampUtc": self.timestamp_utc,
            "witnessPublicKeyHex": self.witness_public_key_hex,
        }

    def verify_signature(self, witness_public_key: Optional[Ed25519PublicKey] = None) -> bool:
        """Verifies receipt Ed25519 signature over canonical RFC 8785 JCS bytes."""
        if not self.signature_hex:
            return False

        pub = witness_public_key
        if pub is None:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.witness_public_key_hex))

        canonical_bytes = encode_jcs(self.to_canonical_statement())
        try:
            pub.verify(bytes.fromhex(self.signature_hex), canonical_bytes)
            return True
        except InvalidSignature:
            return False


class ExternalWitnessCheckpointAnchor:
    """
    Manages ledger checkpoint aggregation into Merkle roots and anchors them with
    an external Ed25519 witness. Manages outage buffering and burst reconciliation.
    """

    def __init__(
        self,
        witness_private_key: Ed25519PrivateKey,
        max_outage_seconds: float = 300.0,
        max_unanchored_batches: int = 10,
        genesis_root: Optional[str] = None,
    ) -> None:
        self.witness_private_key = witness_private_key
        self.witness_public_key = witness_private_key.public_key()
        self.witness_public_key_hex = self.witness_public_key.public_bytes_raw().hex()

        self.max_outage_seconds = float(max_outage_seconds)
        self.max_unanchored_batches = int(max_unanchored_batches)

        self.state = ANCHOR_STATE_ACTIVE
        self.last_anchored_root = genesis_root or ("00" * 32)
        self.last_checkpoint_seq = 0
        self.last_end_seq = 0

        self.outage_start_timestamp: Optional[float] = None
        self.unanchored_buffer: List[AnchoredCheckpoint] = []
        self.anchored_history: List[AnchoredCheckpoint] = []
        self._witness_available: bool = True

    def set_witness_availability(
        self,
        available: bool,
        current_time_epoch: Optional[float] = None,
    ) -> None:
        """Configures simulated witness connectivity."""
        self._witness_available = available
        if not available and self.state == ANCHOR_STATE_ACTIVE:
            self.state = ANCHOR_STATE_OUTAGE
            self.outage_start_timestamp = current_time_epoch or time.time()

    def create_checkpoint(
        self,
        leaf_hashes: List[str],
        timestamp_utc: Optional[str] = None,
        witness_available: Optional[bool] = None,
        current_time_epoch: Optional[float] = None,
    ) -> AnchoredCheckpoint:
        """
        Creates an aggregate Merkle checkpoint.
        If witness is reachable and active, computes Ed25519 witness signature.
        If witness is unreachable, buffers checkpoint under DISPATCH_UNANCHORED_LOCAL_ONLY
        and evaluates outage duration and batch count ceilings.
        """
        now_epoch = current_time_epoch or time.time()
        effective_available = (
            self._witness_available if witness_available is None else witness_available
        )

        ts = timestamp_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch))
        merkle_root = compute_merkle_root(leaf_hashes)
        batch_size = max(1, len(leaf_hashes))

        # Check outage condition
        if not effective_available or self.state == ANCHOR_STATE_OUTAGE:
            if self.state == ANCHOR_STATE_ACTIVE:
                self.state = ANCHOR_STATE_OUTAGE
                self.outage_start_timestamp = now_epoch

            outage_elapsed = now_epoch - (self.outage_start_timestamp or now_epoch)
            if outage_elapsed > self.max_outage_seconds:
                raise CheckpointOutageCeilingExceededError(
                    f"Outage duration {outage_elapsed:.2f}s exceeded configured ceiling {self.max_outage_seconds}s"
                )

            if len(self.unanchored_buffer) >= self.max_unanchored_batches:
                raise CheckpointOutageCeilingExceededError(
                    f"Unanchored batch count {len(self.unanchored_buffer)} reached configured ceiling {self.max_unanchored_batches}"
                )

            # Determine sequence continuity
            if not self.unanchored_buffer:
                prev_root = self.last_anchored_root
                start_seq = self.last_end_seq + 1
                checkpoint_seq = self.last_checkpoint_seq + 1
            else:
                last_unanchored = self.unanchored_buffer[-1]
                prev_root = last_unanchored.commitment.merkle_root
                start_seq = last_unanchored.commitment.end_seq + 1
                checkpoint_seq = last_unanchored.commitment.checkpoint_seq + 1

            end_seq = start_seq + batch_size - 1

            commitment = CheckpointCommitment(
                checkpoint_seq=checkpoint_seq,
                start_seq=start_seq,
                end_seq=end_seq,
                merkle_root=merkle_root,
                previous_checkpoint_root=prev_root,
                timestamp_utc=ts,
            )

            unanchored_cp = AnchoredCheckpoint(
                commitment=commitment,
                witness_public_key_hex=self.witness_public_key_hex,
                signature_hex="",
                status=DISPATCH_UNANCHORED_LOCAL_ONLY,
            )
            self.unanchored_buffer.append(unanchored_cp)
            return unanchored_cp

        # Normal active path: witness reachable
        checkpoint_seq = self.last_checkpoint_seq + 1
        start_seq = self.last_end_seq + 1
        end_seq = start_seq + batch_size - 1

        commitment = CheckpointCommitment(
            checkpoint_seq=checkpoint_seq,
            start_seq=start_seq,
            end_seq=end_seq,
            merkle_root=merkle_root,
            previous_checkpoint_root=self.last_anchored_root,
            timestamp_utc=ts,
        )

        canonical_bytes = encode_jcs(commitment.to_canonical_dict())
        sig_hex = self.witness_private_key.sign(canonical_bytes).hex()

        anchored_cp = AnchoredCheckpoint(
            commitment=commitment,
            witness_public_key_hex=self.witness_public_key_hex,
            signature_hex=sig_hex,
            status=STATUS_ANCHORED,
        )

        self.last_anchored_root = merkle_root
        self.last_checkpoint_seq = checkpoint_seq
        self.last_end_seq = end_seq
        self.anchored_history.append(anchored_cp)

        return anchored_cp

    def reconcile_outage_burst(
        self,
        current_time_epoch: Optional[float] = None,
    ) -> OutageReconciliationReceipt:
        """
        Reconciles all buffered unanchored checkpoints across an outage window.
        Verifies strict topological sequence and hash-chain continuity.
        Signs checkpoints in burst and returns a signed OutageReconciliationReceipt.
        """
        now_epoch = current_time_epoch or time.time()

        if not self.unanchored_buffer:
            # Nothing buffered: restore state to active
            self.state = ANCHOR_STATE_ACTIVE
            self.outage_start_timestamp = None
            self._witness_available = True
            empty_receipt = OutageReconciliationReceipt(
                receipt_id=f"rcpt-outage-noop-{int(now_epoch)}",
                action_phase=RECONCILE_OUTAGE_BURST,
                start_checkpoint_seq=self.last_checkpoint_seq,
                end_checkpoint_seq=self.last_checkpoint_seq,
                reconciled_batch_count=0,
                prior_anchored_root=self.last_anchored_root,
                latest_anchored_root=self.last_anchored_root,
                outage_duration_seconds=0.0,
                timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch)),
                witness_public_key_hex=self.witness_public_key_hex,
                signature_hex="",
            )
            canonical_bytes = encode_jcs(empty_receipt.to_canonical_statement())
            signed_empty = OutageReconciliationReceipt(
                **{
                    **empty_receipt.__dict__,
                    "signature_hex": self.witness_private_key.sign(canonical_bytes).hex(),
                }
            )
            return signed_empty

        # Sort buffer strictly in chronological order
        sorted_buffer = sorted(self.unanchored_buffer, key=lambda cp: cp.commitment.checkpoint_seq)

        # Verify cumulative hash-chain continuity across the outage gap
        expected_prev_root = self.last_anchored_root
        expected_start_seq = self.last_end_seq + 1
        expected_chk_seq = self.last_checkpoint_seq + 1

        for cp in sorted_buffer:
            if cp.commitment.checkpoint_seq != expected_chk_seq:
                raise CheckpointContinuityError(
                    f"Checkpoint sequence mismatch: expected {expected_chk_seq}, observed {cp.commitment.checkpoint_seq}"
                )
            if cp.commitment.previous_checkpoint_root != expected_prev_root:
                raise CheckpointContinuityError(
                    f"Hash-chain discontinuity at seq {expected_chk_seq}: expected prior root {expected_prev_root}, observed {cp.commitment.previous_checkpoint_root}"
                )
            if cp.commitment.start_seq != expected_start_seq:
                raise CheckpointContinuityError(
                    f"Entry sequence mismatch at seq {expected_chk_seq}: expected start {expected_start_seq}, observed {cp.commitment.start_seq}"
                )

            expected_prev_root = cp.commitment.merkle_root
            expected_start_seq = cp.commitment.end_seq + 1
            expected_chk_seq += 1

        # Continuity observed: sign buffered checkpoints in burst
        for cp in sorted_buffer:
            canonical_bytes = encode_jcs(cp.commitment.to_canonical_dict())
            sig_hex = self.witness_private_key.sign(canonical_bytes).hex()
            anchored_cp = AnchoredCheckpoint(
                commitment=cp.commitment,
                witness_public_key_hex=self.witness_public_key_hex,
                signature_hex=sig_hex,
                status=STATUS_ANCHORED,
            )
            self.anchored_history.append(anchored_cp)

        # Compute reconciliation bounds
        outage_start = self.outage_start_timestamp or now_epoch
        duration = max(0.0, now_epoch - outage_start)
        prior_root = self.last_anchored_root
        latest_root = expected_prev_root
        start_cp_seq = sorted_buffer[0].commitment.checkpoint_seq
        end_cp_seq = sorted_buffer[-1].commitment.checkpoint_seq
        batch_count = len(sorted_buffer)

        # Update anchor state
        self.last_anchored_root = latest_root
        self.last_checkpoint_seq = end_cp_seq
        self.last_end_seq = expected_start_seq - 1

        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch))
        receipt_id = f"rcpt-outage-{start_cp_seq:04d}-{end_cp_seq:04d}"

        draft_receipt = OutageReconciliationReceipt(
            receipt_id=receipt_id,
            action_phase=RECONCILE_OUTAGE_BURST,
            start_checkpoint_seq=start_cp_seq,
            end_checkpoint_seq=end_cp_seq,
            reconciled_batch_count=batch_count,
            prior_anchored_root=prior_root,
            latest_anchored_root=latest_root,
            outage_duration_seconds=duration,
            timestamp_utc=ts,
            witness_public_key_hex=self.witness_public_key_hex,
            signature_hex="",
        )

        receipt_canonical_bytes = encode_jcs(draft_receipt.to_canonical_statement())
        receipt_sig_hex = self.witness_private_key.sign(receipt_canonical_bytes).hex()

        signed_receipt = OutageReconciliationReceipt(
            receipt_id=receipt_id,
            action_phase=RECONCILE_OUTAGE_BURST,
            start_checkpoint_seq=start_cp_seq,
            end_checkpoint_seq=end_cp_seq,
            reconciled_batch_count=batch_count,
            prior_anchored_root=prior_root,
            latest_anchored_root=latest_root,
            outage_duration_seconds=duration,
            timestamp_utc=ts,
            witness_public_key_hex=self.witness_public_key_hex,
            signature_hex=receipt_sig_hex,
        )

        # Clear buffer and reset state
        self.unanchored_buffer.clear()
        self.outage_start_timestamp = None
        self.state = ANCHOR_STATE_ACTIVE
        self._witness_available = True

        return signed_receipt
