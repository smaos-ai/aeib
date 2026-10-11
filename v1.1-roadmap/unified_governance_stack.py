"""AEIB v1.1 / v1.2 Unified Governance Architectural Stack Prototype.

Implements executable, zero-mock primitives corresponding to the Four Core Mental Models:
1. Wire Control Gate (LICITRA-SENTRY & PAD-016 Heartbeat): Ed25519 Execution Tickets
   bound to RFC 8785 JCS CAIDs, burned on single use before wire access.
2. Write-Before-Execute (EO-1 Pre-Dispatch Receipt): Pre-execution ledger commitment
   as a strict prerequisite for wire I/O; ledger failures abort dispatch fail-closed.
3. Continuous Hashing & LICITRA-MMR Ledger: Real-time SHA-256 chain evaluation on
   every append/read cycle, O(log n) Merkle Mountain Range (MMR) inclusion proofs,
   and a Consistent Hash Ring for deterministic gateway partition routing.
4. NoSQL Merkle Anti-Entropy & v1.2 Witnessed Signed Tree Heads (STH): Fail-closed
   latching (EFFECT_INDETERMINATE) on replica divergence instead of Last-Write-Wins,
   plus dual-signed (Operator + Witness) tree heads for operator-independent verification.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


def canonicalize_jcs(obj: Any) -> str:
    """Return RFC 8785 JCS canonical UTF-8 string representation."""
    return encode_jcs(obj).decode("utf-8")


class GovernanceHaltError(RuntimeError):
    """Raised when the governance stack halts execution fail-closed."""


def compute_caid(action_payload: Dict[str, Any]) -> str:
    """Derive a 64-hex SHA-256 Content-Addressed Action Identifier over RFC 8785 JCS bytes."""
    return hashlib.sha256(encode_jcs(action_payload)).hexdigest()


def _hash_leaf(index: int, event_bytes: bytes) -> bytes:
    """Domain-separated SHA-256 leaf digest (0x00 prefix per RFC 6962 convention)."""
    h = hashlib.sha256()
    h.update(b"\x00")
    h.update(index.to_bytes(8, "big"))
    h.update(event_bytes)
    return h.digest()


def _hash_node(left: bytes, right: bytes) -> bytes:
    """Domain-separated SHA-256 interior node digest (0x01 prefix)."""
    h = hashlib.sha256()
    h.update(b"\x01")
    h.update(left)
    h.update(right)
    return h.digest()


# ============================================================================
# 1. PAD-016 Cryptographic Heartbeat & LICITRA-SENTRY Execution Ticket Gate
# ============================================================================


@dataclass(frozen=True)
class HeartbeatPulse:
    """Single pulse in a PAD-016 cryptographic renewal chain."""

    sequence: int
    previous_pulse_hash: str
    timestamp_utc: str
    signature_hex: str
    pulse_hash: str


class PAD016HeartbeatChain:
    """Untrusted-until-renewed cryptographic heartbeat chain (PAD-016 prototype)."""

    def __init__(self, authority_private_key: Ed25519PrivateKey) -> None:
        self._private_key = authority_private_key
        self.public_key: Ed25519PublicKey = authority_private_key.public_key()
        self._pulses: List[HeartbeatPulse] = []
        self._revoked: bool = False

    def emit_pulse(self, timestamp_utc: str) -> HeartbeatPulse:
        if self._revoked:
            raise GovernanceHaltError("PAD-016 authority is revoked; cannot emit pulse")
        seq = len(self._pulses) + 1
        prev_hash = self._pulses[-1].pulse_hash if self._pulses else "0" * 64
        statement = {
            "previousPulseHash": prev_hash,
            "sequence": seq,
            "timestampUtc": timestamp_utc,
        }
        canonical_bytes = encode_jcs(statement)
        sig_bytes = self._private_key.sign(canonical_bytes)
        pulse_hash = hashlib.sha256(canonical_bytes + sig_bytes).hexdigest()
        pulse = HeartbeatPulse(
            sequence=seq,
            previous_pulse_hash=prev_hash,
            timestamp_utc=timestamp_utc,
            signature_hex=sig_bytes.hex(),
            pulse_hash=pulse_hash,
        )
        self._pulses.append(pulse)
        return pulse

    def revoke(self) -> None:
        self._revoked = True

    def verify_active_pulse(self, expected_pulse_hash: str) -> bool:
        if self._revoked or not self._pulses:
            return False
        latest = self._pulses[-1]
        if latest.pulse_hash != expected_pulse_hash:
            return False
        statement = {
            "previousPulseHash": latest.previous_pulse_hash,
            "sequence": latest.sequence,
            "timestampUtc": latest.timestamp_utc,
        }
        try:
            self.public_key.verify(
                bytes.fromhex(latest.signature_hex),
                encode_jcs(statement),
            )
            return True
        except (InvalidSignature, ValueError):
            return False


@dataclass(frozen=True)
class ExecutionTicket:
    """Ed25519-signed execution ticket bound to a specific RFC 8785 CAID and heartbeat."""

    ticket_id: str
    action_caid: str
    target_uri: str
    heartbeat_pulse_hash: str
    signature_hex: str

    def to_statement_dict(self) -> Dict[str, Any]:
        return {
            "actionCaid": self.action_caid,
            "heartbeatPulseHash": self.heartbeat_pulse_hash,
            "targetUri": self.target_uri,
            "ticketId": self.ticket_id,
        }


def mint_execution_ticket(
    issuer_private_key: Ed25519PrivateKey,
    ticket_id: str,
    action_payload: Dict[str, Any],
    target_uri: str,
    heartbeat_pulse_hash: str,
) -> ExecutionTicket:
    """Mint an Ed25519 Execution Ticket bound to the canonical payload CAID."""
    caid = compute_caid(action_payload)
    statement = {
        "actionCaid": caid,
        "heartbeatPulseHash": heartbeat_pulse_hash,
        "targetUri": target_uri,
        "ticketId": ticket_id,
    }
    signature = issuer_private_key.sign(encode_jcs(statement)).hex()
    return ExecutionTicket(
        ticket_id=ticket_id,
        action_caid=caid,
        target_uri=target_uri,
        heartbeat_pulse_hash=heartbeat_pulse_hash,
        signature_hex=signature,
    )


# ============================================================================
# 2. Continuous Hashing & LICITRA-MMR Ledger + Consistent Hash Ring
# ============================================================================


@dataclass(frozen=True)
class MmrInclusionProofStep:
    """Single sibling hash step in an MMR Merkle branch."""

    sibling_hex: str
    is_left_sibling: bool


@dataclass(frozen=True)
class MmrInclusionProof:
    """O(log n) inclusion proof for an event in the LICITRA-MMR ledger."""

    leaf_index: int
    leaf_hash_hex: str
    peak_hash_hex: str
    branch: Tuple[MmrInclusionProofStep, ...]
    all_peaks_hex: Tuple[str, ...]
    bagged_root_hex: str


@dataclass(frozen=True)
class LedgerEntry:
    """Immutable entry in the continuous-hashing + MMR ledger."""

    sequence: int
    phase: str
    action_caid: str
    target_uri: str
    chain_tip_hex: str
    mmr_root_hex: str
    receipt_signature_hex: str
    canonical_event_json: str


class LicitraMmrLedger:
    """Continuous-hashing ledger with Merkle Mountain Range (MMR) O(log n) proofs."""

    def __init__(self, ledger_private_key: Ed25519PrivateKey) -> None:
        self._private_key = ledger_private_key
        self.public_key: Ed25519PublicKey = ledger_private_key.public_key()
        self._entries: List[LedgerEntry] = []
        self._leaf_hashes: List[bytes] = []
        self._chain_tip: bytes = b"\x00" * 32

    @property
    def chain_tip_hex(self) -> str:
        return self._chain_tip.hex()

    @property
    def size(self) -> int:
        return len(self._entries)

    def verify_continuous_integrity(self) -> bool:
        """Re-evaluate the entire continuous hash chain and Ed25519 signatures."""
        running_tip = b"\x00" * 32
        for idx, entry in enumerate(self._entries):
            event_bytes = entry.canonical_event_json.encode("utf-8")
            expected_tip = hashlib.sha256(running_tip + event_bytes).digest()
            if expected_tip.hex() != entry.chain_tip_hex:
                return False
            receipt_statement = {
                "actionCaid": entry.action_caid,
                "chainTip": entry.chain_tip_hex,
                "mmrRoot": entry.mmr_root_hex,
                "phase": entry.phase,
                "sequence": entry.sequence,
                "targetUri": entry.target_uri,
            }
            try:
                self.public_key.verify(
                    bytes.fromhex(entry.receipt_signature_hex),
                    encode_jcs(receipt_statement),
                )
            except (InvalidSignature, ValueError):
                return False
            if self._leaf_hashes[idx] != _hash_leaf(idx, event_bytes):
                return False
            running_tip = expected_tip
        return True

    def append_event(self, phase: str, action_caid: str, target_uri: str) -> LedgerEntry:
        """Continuously verify existing chain, append event, update MMR, and sign receipt."""
        if not self.verify_continuous_integrity():
            raise GovernanceHaltError(
                "Continuous hashing immune check failed prior to append"
            )
        seq = len(self._entries) + 1
        event_obj = {
            "actionCaid": action_caid,
            "phase": phase,
            "sequence": seq,
            "targetUri": target_uri,
        }
        canonical_json = canonicalize_jcs(event_obj)
        event_bytes = canonical_json.encode("utf-8")
        new_tip = hashlib.sha256(self._chain_tip + event_bytes).digest()

        leaf_idx = len(self._leaf_hashes)
        self._leaf_hashes.append(_hash_leaf(leaf_idx, event_bytes))
        mmr_root = self.current_mmr_root_hex()

        receipt_statement = {
            "actionCaid": action_caid,
            "chainTip": new_tip.hex(),
            "mmrRoot": mmr_root,
            "phase": phase,
            "sequence": seq,
            "targetUri": target_uri,
        }
        sig_hex = self._private_key.sign(encode_jcs(receipt_statement)).hex()

        entry = LedgerEntry(
            sequence=seq,
            phase=phase,
            action_caid=action_caid,
            target_uri=target_uri,
            chain_tip_hex=new_tip.hex(),
            mmr_root_hex=mmr_root,
            receipt_signature_hex=sig_hex,
            canonical_event_json=canonical_json,
        )
        self._entries.append(entry)
        self._chain_tip = new_tip
        return entry

    def _compute_peaks(self) -> List[Tuple[int, int, bytes]]:
        """Decompose [0, n) into power-of-two perfect binary subtrees (start, size, root)."""
        peaks: List[Tuple[int, int, bytes]] = []
        n = len(self._leaf_hashes)
        offset = 0
        bit = 1 << (n.bit_length())
        while bit > 0:
            if n & bit:
                root = self._subtree_root(offset, bit)
                peaks.append((offset, bit, root))
                offset += bit
            bit >>= 1
        return peaks

    def _subtree_root(self, start: int, size: int) -> bytes:
        if size == 1:
            return self._leaf_hashes[start]
        half = size // 2
        left = self._subtree_root(start, half)
        right = self._subtree_root(start + half, half)
        return _hash_node(left, right)

    @staticmethod
    def bag_peaks(peaks_hex: Tuple[str, ...]) -> str:
        """Bag MMR peaks right-to-left into a single 64-hex root digest."""
        if not peaks_hex:
            return ("0" * 64)
        acc = bytes.fromhex(peaks_hex[-1])
        for peak_hex in reversed(peaks_hex[:-1]):
            acc = _hash_node(bytes.fromhex(peak_hex), acc)
        return acc.hex()

    def current_mmr_root_hex(self) -> str:
        peaks = tuple(p[2].hex() for p in self._compute_peaks())
        return self.bag_peaks(peaks)

    def generate_inclusion_proof(self, leaf_index: int) -> MmrInclusionProof:
        """Generate an O(log n) inclusion proof for `leaf_index`."""
        if leaf_index < 0 or leaf_index >= len(self._leaf_hashes):
            raise IndexError(f"leaf_index {leaf_index} out of bounds")
        peaks = self._compute_peaks()
        all_peaks_hex = tuple(p[2].hex() for p in peaks)
        bagged_root = self.bag_peaks(all_peaks_hex)

        for start, size, peak_root in peaks:
            if start <= leaf_index < start + size:
                branch: List[MmrInclusionProofStep] = []
                self._build_branch(start, size, leaf_index, branch)
                return MmrInclusionProof(
                    leaf_index=leaf_index,
                    leaf_hash_hex=self._leaf_hashes[leaf_index].hex(),
                    peak_hash_hex=peak_root.hex(),
                    branch=tuple(branch),
                    all_peaks_hex=all_peaks_hex,
                    bagged_root_hex=bagged_root,
                )
        raise RuntimeError("Unreachable: leaf_index not covered by MMR peaks")

    def _build_branch(
        self,
        start: int,
        size: int,
        target: int,
        branch: List[MmrInclusionProofStep],
    ) -> None:
        if size == 1:
            return
        half = size // 2
        mid = start + half
        if target < mid:
            self._build_branch(start, half, target, branch)
            right_sibling = self._subtree_root(mid, half)
            branch.append(
                MmrInclusionProofStep(
                    sibling_hex=right_sibling.hex(),
                    is_left_sibling=False,
                )
            )
        else:
            self._build_branch(mid, half, target, branch)
            left_sibling = self._subtree_root(start, half)
            branch.append(
                MmrInclusionProofStep(
                    sibling_hex=left_sibling.hex(),
                    is_left_sibling=True,
                )
            )

    @staticmethod
    def verify_inclusion_proof(proof: MmrInclusionProof) -> bool:
        """Verify an O(log n) MMR inclusion proof without traversing the full ledger."""
        current = bytes.fromhex(proof.leaf_hash_hex)
        for step in proof.branch:
            sibling = bytes.fromhex(step.sibling_hex)
            if step.is_left_sibling:
                current = _hash_node(sibling, current)
            else:
                current = _hash_node(current, sibling)
        if current.hex() != proof.peak_hash_hex:
            return False
        if proof.peak_hash_hex not in proof.all_peaks_hex:
            return False
        return LicitraMmrLedger.bag_peaks(proof.all_peaks_hex) == proof.bagged_root_hex


class ConsistentHashRing:
    """Deterministic SHA-256 consistent hashing ring for gateway partition routing."""

    def __init__(self, nodes: List[str], virtual_nodes: int = 16) -> None:
        if not nodes:
            raise ValueError("ConsistentHashRing requires at least one node")
        self._ring: List[Tuple[int, str]] = []
        for node in sorted(set(nodes)):
            for v in range(virtual_nodes):
                key = f"{node}#vnode-{v}".encode("utf-8")
                point = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
                self._ring.append((point, node))
        self._ring.sort(key=lambda item: item[0])
        self._points = [item[0] for item in self._ring]

    def route_caid(self, action_caid: str) -> str:
        """Route a 64-hex CAID deterministically to its owning gateway partition node."""
        point = int.from_bytes(
            hashlib.sha256(action_caid.encode("utf-8")).digest()[:8], "big"
        )
        idx = bisect.bisect_left(self._points, point)
        if idx == len(self._ring):
            idx = 0
        return self._ring[idx][1]


# ============================================================================
# 3. LICITRA-SENTRY Wire Control Gate & Write-Before-Execute Interlock
# ============================================================================


class LicitraSentryProxyGate:
    """Default-closed wire control proxy gate enforcing Write-Before-Execute (EO-1)."""

    def __init__(
        self,
        ticket_issuer_public_key: Ed25519PublicKey,
        heartbeat_chain: PAD016HeartbeatChain,
        ledger: LicitraMmrLedger,
    ) -> None:
        self._issuer_public_key = ticket_issuer_public_key
        self._heartbeat_chain = heartbeat_chain
        self._ledger = ledger
        self._burned_tickets: Set[str] = set()

    def execute_through_gate(
        self,
        ticket: ExecutionTicket,
        action_payload: Dict[str, Any],
        target_uri: str,
        wire_callable: Callable[[Dict[str, Any], str], Dict[str, Any]],
    ) -> Tuple[LedgerEntry, Dict[str, Any], LedgerEntry]:
        """Verify ticket + heartbeat, commit pre-dispatch receipt (Write-Before-Execute), then execute."""
        # 1. Single-use ticket burn check
        if ticket.ticket_id in self._burned_tickets:
            raise GovernanceHaltError(
                f"ExecutionTicket {ticket.ticket_id} already burned (replay blocked)"
            )

        # 2. PAD-016 cryptographic heartbeat liveness check
        if not self._heartbeat_chain.verify_active_pulse(ticket.heartbeat_pulse_hash):
            raise GovernanceHaltError(
                "PAD-016 Heartbeat pulse expired, mismatched, or revoked"
            )

        # 3. Payload CAID & target URI binding check (prevents parameter substitution)
        observed_caid = compute_caid(action_payload)
        if observed_caid != ticket.action_caid or target_uri != ticket.target_uri:
            raise GovernanceHaltError(
                "Payload CAID or target URI mismatch against ExecutionTicket"
            )

        # 4. Ed25519 signature verification over RFC 8785 JCS ticket statement
        try:
            self._issuer_public_key.verify(
                bytes.fromhex(ticket.signature_hex),
                encode_jcs(ticket.to_statement_dict()),
            )
        except (InvalidSignature, ValueError) as exc:
            raise GovernanceHaltError(
                "Invalid Ed25519 signature on ExecutionTicket"
            ) from exc

        # Burn ticket before any I/O
        self._burned_tickets.add(ticket.ticket_id)

        # 5. Write-Before-Execute (EO-1): Commit pre-dispatch receipt BEFORE wire I/O
        pre_dispatch_entry = self._ledger.append_event(
            phase="PRE_DISPATCH_COMMITTED",
            action_caid=observed_caid,
            target_uri=target_uri,
        )

        # 6. Execute target wire call only after pre-dispatch ledger write succeeds
        wire_response = wire_callable(action_payload, target_uri)

        # 7. Append reconciled post-dispatch event
        disposition = str(wire_response.get("disposition", "CONFIRMED"))
        post_dispatch_entry = self._ledger.append_event(
            phase=f"RECONCILED_{disposition}",
            action_caid=observed_caid,
            target_uri=target_uri,
        )
        return pre_dispatch_entry, wire_response, post_dispatch_entry


# ============================================================================
# 4. NoSQL Merkle Anti-Entropy & v1.2 Witnessed Signed Tree Heads (STH)
# ============================================================================


@dataclass(frozen=True)
class AntiEntropyVerdict:
    """Result of comparing MMR roots across gateway replicas."""

    disposition: str
    halted: bool
    primary_mmr_root: str
    replica_mmr_root: str


class MerkleAntiEntropyReconciler:
    """Fail-closed anti-entropy reconciler (never performs Last-Write-Wins)."""

    def __init__(self) -> None:
        self.latched_disposition: Optional[str] = None

    def compare_replica_ledgers(
        self, primary: LicitraMmrLedger, replica: LicitraMmrLedger
    ) -> AntiEntropyVerdict:
        primary_ok = primary.verify_continuous_integrity()
        replica_ok = replica.verify_continuous_integrity()
        p_root = primary.current_mmr_root_hex()
        r_root = replica.current_mmr_root_hex()

        if not primary_ok or not replica_ok or primary.size != replica.size or p_root != r_root:
            self.latched_disposition = "EFFECT_INDETERMINATE"
            return AntiEntropyVerdict(
                disposition="EFFECT_INDETERMINATE",
                halted=True,
                primary_mmr_root=p_root,
                replica_mmr_root=r_root,
            )

        return AntiEntropyVerdict(
            disposition="CONFIRMED",
            halted=False,
            primary_mmr_root=p_root,
            replica_mmr_root=r_root,
        )


@dataclass(frozen=True)
class WitnessedSignedTreeHead:
    """v1.2 CT-style Signed Tree Head co-signed by Operator and Independent Witness."""

    tree_size: int
    mmr_root_hex: str
    chain_tip_hex: str
    timestamp_utc: str
    operator_signature_hex: str
    witness_signature_hex: str

    def to_statement_dict(self) -> Dict[str, Any]:
        return {
            "chainTip": self.chain_tip_hex,
            "mmrRoot": self.mmr_root_hex,
            "timestampUtc": self.timestamp_utc,
            "treeSize": self.tree_size,
        }


def mint_witnessed_sth(
    ledger: LicitraMmrLedger,
    operator_private_key: Ed25519PrivateKey,
    witness_private_key: Ed25519PrivateKey,
    timestamp_utc: str,
) -> WitnessedSignedTreeHead:
    """Mint a dual-signed CT-style Signed Tree Head (Operator + Independent Witness)."""
    if not ledger.verify_continuous_integrity():
        raise GovernanceHaltError("Cannot mint STH on tampered ledger")
    statement = {
        "chainTip": ledger.chain_tip_hex,
        "mmrRoot": ledger.current_mmr_root_hex(),
        "timestampUtc": timestamp_utc,
        "treeSize": ledger.size,
    }
    canonical = encode_jcs(statement)
    op_sig = operator_private_key.sign(canonical).hex()
    wit_sig = witness_private_key.sign(canonical).hex()
    return WitnessedSignedTreeHead(
        tree_size=ledger.size,
        mmr_root_hex=statement["mmrRoot"],
        chain_tip_hex=statement["chainTip"],
        timestamp_utc=timestamp_utc,
        operator_signature_hex=op_sig,
        witness_signature_hex=wit_sig,
    )


def verify_witnessed_sth(
    sth: WitnessedSignedTreeHead,
    operator_public_key: Ed25519PublicKey,
    witness_public_key: Ed25519PublicKey,
) -> bool:
    """Verify both Operator and Witness Ed25519 signatures over the canonical STH."""
    canonical = encode_jcs(sth.to_statement_dict())
    try:
        operator_public_key.verify(bytes.fromhex(sth.operator_signature_hex), canonical)
        witness_public_key.verify(bytes.fromhex(sth.witness_signature_hex), canonical)
        return True
    except (InvalidSignature, ValueError):
        return False
