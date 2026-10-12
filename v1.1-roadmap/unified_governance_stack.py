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
import re
import urllib.parse
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


# ============================================================================
# 5. 10-Signal Industry Convergence Primitives (v1.1 Prototype Extensions)
# ============================================================================

_RAW_SECRET_KEY_NAMES: Set[str] = {
    "authorization",
    "bearer",
    "api_key",
    "apikey",
    "secret",
    "secret_key",
    "password",
    "private_key",
    "access_token",
    "client_secret",
}

_RAW_SECRET_VALUE_RE = re.compile(
    r"(?i)(\bbearer\s+[a-z0-9\-._~+/]+=*|\bsk-[a-z0-9_\-]{8,}|\bghp_[a-z0-9]{8,}|\bak_[a-z0-9]{8,}|-----begin\s+[a-z\s]*private\s+key-----)"
)


class CredentialVaultGate:
    """Signal 1 (Tool Surface / GridEx & Pryxor prototype): Opaque credential_ref vault gate.

    Maps opaque `credential_ref` handles to vault-held target scopes without exposing
    raw credentials to the agent; rejects payloads containing raw secret or bearer
    patterns fail-closed (`GovernanceHaltError`).
    """

    def __init__(self, vault_bindings: Optional[Dict[str, str]] = None) -> None:
        self._vault_bindings: Dict[str, str] = dict(vault_bindings or {})

    def register_credential_ref(
        self, credential_ref: str, allowed_target_prefix: str
    ) -> None:
        """Bind an opaque credential_ref handle to an allowed target URI prefix."""
        if not credential_ref or not allowed_target_prefix:
            raise ValueError("credential_ref and allowed_target_prefix must be non-empty")
        self._vault_bindings[credential_ref] = allowed_target_prefix

    def inspect_payload_no_raw_secrets(self, payload: Any) -> None:
        """Recursively inspect a payload and halt fail-closed if raw secrets appear."""
        if isinstance(payload, dict):
            for k, v in payload.items():
                key_str = str(k)
                if (
                    key_str.lower() in _RAW_SECRET_KEY_NAMES
                    and key_str.lower() != "credential_ref"
                ):
                    raise GovernanceHaltError(
                        f"Raw secret key {key_str!r} forbidden in agent payload; use opaque credential_ref"
                    )
                self.inspect_payload_no_raw_secrets(v)
        elif isinstance(payload, (list, tuple)):
            for item in payload:
                self.inspect_payload_no_raw_secrets(item)
        elif isinstance(payload, str):
            if _RAW_SECRET_VALUE_RE.search(payload):
                raise GovernanceHaltError(
                    "Raw credential or bearer pattern detected in agent payload"
                )

    def resolve_scope(
        self,
        credential_ref: str,
        target_uri: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Validate payload purity and verify credential_ref maps to target_uri scope."""
        if payload is not None:
            self.inspect_payload_no_raw_secrets(payload)
        if _RAW_SECRET_VALUE_RE.search(credential_ref):
            raise GovernanceHaltError(
                "credential_ref contains raw secret pattern instead of opaque handle"
            )
        if credential_ref not in self._vault_bindings:
            raise GovernanceHaltError(
                f"Unknown or unmapped credential_ref: {credential_ref!r}"
            )
        allowed_scope = self._vault_bindings[credential_ref]
        if not target_uri.startswith(allowed_scope):
            raise GovernanceHaltError(
                f"credential_ref {credential_ref!r} scope {allowed_scope!r} does not permit target {target_uri!r}"
            )
        return allowed_scope


class ForkAndFlushContextBoundary:
    """Signals 2 & 4 (Fork-and-Flush Reasoning Isolation & Non-Explanatory Wire Interception).

    Strips ephemeral reasoning and prose fields (`_reasoning`, `chain_of_thought`,
    `rationale`, `explanation`) so only canonical wire mutation parameters enter
    RFC 8785 JCS `CAID` computation and boolean standing evaluation.
    """

    EPHEMERAL_REASONING_FIELDS: Tuple[str, ...] = (
        "_reasoning",
        "chain_of_thought",
        "rationale",
        "explanation",
    )

    def __init__(self, extra_ephemeral_fields: Optional[Set[str]] = None) -> None:
        self._ephemeral_fields: Set[str] = set(self.EPHEMERAL_REASONING_FIELDS)
        if extra_ephemeral_fields:
            self._ephemeral_fields.update(extra_ephemeral_fields)
        self.flushed_field_count: int = 0

    def flush_reasoning(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Strip all ephemeral reasoning/prose fields recursively from `raw_payload`."""
        cleaned = self._strip_node(raw_payload)
        if not isinstance(cleaned, dict):
            raise GovernanceHaltError("Expected dictionary payload at context boundary")
        return cleaned

    def _strip_node(self, node: Any) -> Any:
        if isinstance(node, dict):
            purified: Dict[str, Any] = {}
            for k, v in node.items():
                if k in self._ephemeral_fields:
                    self.flushed_field_count += 1
                    continue
                purified[k] = self._strip_node(v)
            return purified
        if isinstance(node, list):
            return [self._strip_node(item) for item in node]
        return node

    def compute_wire_caid(
        self, raw_payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        """Flush ephemeral reasoning and compute RFC 8785 JCS CAID over wire parameters only."""
        wire_payload = self.flush_reasoning(raw_payload)
        return wire_payload, compute_caid(wire_payload)

    def evaluate_boolean_standing(
        self,
        raw_payload: Dict[str, Any],
        standing_predicate: Callable[[Dict[str, Any]], bool],
    ) -> Tuple[bool, str]:
        """Evaluate boolean standing purely on flushed wire parameters; prose cannot influence verdict."""
        wire_payload, wire_caid = self.compute_wire_caid(raw_payload)
        if not standing_predicate(wire_payload):
            raise GovernanceHaltError(
                "Boolean standing evaluation rejected canonical wire parameters"
            )
        return True, wire_caid


class AntiSpecGamingReconciler:
    """Signal 3 (Specification Gaming `AI Finds A Way` prototype): Target-state reconciler.

    Evaluates an agent's self-reported outcome (`agent_self_report`) against target-side
    semantic state (`target_state`) under a bounded `probe_budget`. Even when
    `agent_self_report == "CONFIRMED"`, if `target_state` is `"NOT_FOUND"`,
    `"ROLLED_BACK"`, or `"TIMEOUT"`, returns `"REFUTED"` or `"EFFECT_INDETERMINATE"`
    and increments `spec_gaming_alerts`.
    """

    def __init__(self, probe_budget: int = 3) -> None:
        if probe_budget <= 0:
            raise ValueError("probe_budget must be a positive integer")
        self.probe_budget: int = probe_budget
        self.probes_consumed: int = 0
        self.spec_gaming_alerts: int = 0

    def reconcile(
        self,
        agent_self_report: str,
        target_state: str,
        probes_used: int = 1,
    ) -> str:
        """Reconcile agent self-report against observed target semantic state under probe budget."""
        if probes_used <= 0 or (self.probes_consumed + probes_used) > self.probe_budget:
            self.probes_consumed = min(
                self.probe_budget, self.probes_consumed + max(probes_used, 1)
            )
            if agent_self_report == "CONFIRMED":
                self.spec_gaming_alerts += 1
            return "EFFECT_INDETERMINATE"

        self.probes_consumed += probes_used

        if target_state in ("NOT_FOUND", "ROLLED_BACK"):
            if agent_self_report == "CONFIRMED":
                self.spec_gaming_alerts += 1
            return "REFUTED"

        if target_state == "TIMEOUT" or target_state != "CONFIRMED":
            if agent_self_report == "CONFIRMED":
                self.spec_gaming_alerts += 1
            return "EFFECT_INDETERMINATE"

        return "CONFIRMED"


class TemporalMemoryDigest:
    """Signal 5 (Memory Staleness `Cognitive Governance` prototype): Epoch-bound MemoryDigest.

    Computes a SHA-256 `MemoryDigest` over RFC 8785 JCS bytes bound to
    `(context_caid, source_epoch, policy_epoch)` and evaluates freshness against
    current `(active_source_epoch, active_policy_epoch)`. If either epoch advances,
    transitions status to `"STALE_DONT_TRUST_YET"` and raises `GovernanceHaltError`
    on dispatch.
    """

    def __init__(
        self,
        context_caid: str,
        source_epoch: int,
        policy_epoch: int,
    ) -> None:
        self.context_caid: str = context_caid
        self.source_epoch: int = int(source_epoch)
        self.policy_epoch: int = int(policy_epoch)
        statement = {
            "contextCaid": self.context_caid,
            "policyEpoch": self.policy_epoch,
            "sourceEpoch": self.source_epoch,
        }
        self.memory_digest_hex: str = hashlib.sha256(encode_jcs(statement)).hexdigest()
        self.status: str = "FRESH"

    @classmethod
    def from_context_payload(
        cls,
        context_payload: Dict[str, Any],
        source_epoch: int,
        policy_epoch: int,
    ) -> TemporalMemoryDigest:
        """Construct a TemporalMemoryDigest directly from a canonicalizable context payload."""
        return cls(
            context_caid=compute_caid(context_payload),
            source_epoch=source_epoch,
            policy_epoch=policy_epoch,
        )

    def evaluate_freshness(
        self, active_source_epoch: int, active_policy_epoch: int
    ) -> str:
        """Compare bound epochs against active epochs and update status."""
        if (
            int(active_source_epoch) != self.source_epoch
            or int(active_policy_epoch) != self.policy_epoch
        ):
            self.status = "STALE_DONT_TRUST_YET"
        else:
            self.status = "FRESH"
        return self.status

    def assert_fresh_for_dispatch(
        self, active_source_epoch: int, active_policy_epoch: int
    ) -> str:
        """Enforce freshness prior to dispatch; raise GovernanceHaltError if stale."""
        current_status = self.evaluate_freshness(
            active_source_epoch, active_policy_epoch
        )
        if current_status != "FRESH":
            raise GovernanceHaltError(
                f"MemoryDigest {self.memory_digest_hex[:16]} status is {current_status} "
                f"(bound=({self.source_epoch}, {self.policy_epoch}), "
                f"active=({active_source_epoch}, {active_policy_epoch}))"
            )
        return self.memory_digest_hex


class TypedOwaspPreDispatchGate:
    """Signal 7 (Typed Pre-Dispatch Gate `AI Goat 2.0` & `AnyJev` prototype).

    Deterministic typed pre-dispatch validator checking target URI scheme/host
    allowlist, path traversal (`..`), and numeric parameter bounds before ticket minting.
    """

    def __init__(
        self,
        allowed_hosts: Set[str],
        numeric_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
        allowed_schemes: Optional[Set[str]] = None,
    ) -> None:
        if not allowed_hosts:
            raise ValueError("allowed_hosts must contain at least one host")
        self.allowed_hosts: Set[str] = set(allowed_hosts)
        self.numeric_bounds: Dict[str, Tuple[float, float]] = dict(numeric_bounds or {})
        self.allowed_schemes: Set[str] = set(allowed_schemes or {"https"})

    def validate_pre_dispatch(
        self, target_uri: str, action_payload: Dict[str, Any]
    ) -> bool:
        """Deterministically validate URI scheme/host, path traversal, and numeric bounds."""
        unquoted_uri = urllib.parse.unquote(target_uri)
        if ".." in target_uri or ".." in unquoted_uri or "\\" in unquoted_uri or "\x00" in unquoted_uri:
            raise GovernanceHaltError(
                f"Path traversal or unsafe sequence detected in target_uri: {target_uri!r}"
            )

        parsed = urllib.parse.urlsplit(target_uri)
        if parsed.scheme not in self.allowed_schemes:
            raise GovernanceHaltError(
                f"Disallowed target URI scheme {parsed.scheme!r}; allowed: {sorted(self.allowed_schemes)}"
            )
        if not parsed.hostname or parsed.hostname not in self.allowed_hosts:
            raise GovernanceHaltError(
                f"Disallowed target URI host {parsed.hostname!r}; allowed: {sorted(self.allowed_hosts)}"
            )

        path_segments = [seg for seg in parsed.path.split("/") if seg]
        if any(seg in (".", "..") for seg in path_segments):
            raise GovernanceHaltError(
                f"Dot-segment path traversal detected in target_uri: {target_uri!r}"
            )

        self._check_payload_traversal(action_payload)

        for field_name, (min_val, max_val) in self.numeric_bounds.items():
            if field_name not in action_payload:
                raise GovernanceHaltError(
                    f"Required bounded numeric parameter {field_name!r} missing from payload"
                )
            raw_val = action_payload[field_name]
            if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)):
                raise GovernanceHaltError(
                    f"Parameter {field_name!r} failed strict type check: expected int/float, got {type(raw_val).__name__}"
                )
            if raw_val < min_val or raw_val > max_val:
                raise GovernanceHaltError(
                    f"Parameter {field_name!r}={raw_val} violates configured bounds [{min_val}, {max_val}]"
                )

        return True

    def _check_payload_traversal(self, node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                self._check_payload_traversal(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                self._check_payload_traversal(item)
        elif isinstance(node, str):
            unquoted = urllib.parse.unquote(node)
            if "../" in node or "..\\" in node or "../" in unquoted or "..\\" in unquoted:
                raise GovernanceHaltError(
                    "Path traversal sequence detected inside payload string parameter"
                )

    def validate_and_mint_ticket(
        self,
        issuer_private_key: Ed25519PrivateKey,
        ticket_id: str,
        action_payload: Dict[str, Any],
        target_uri: str,
        heartbeat_pulse_hash: str,
    ) -> ExecutionTicket:
        """Run deterministic pre-dispatch validation before minting an ExecutionTicket."""
        self.validate_pre_dispatch(target_uri=target_uri, action_payload=action_payload)
        return mint_execution_ticket(
            issuer_private_key=issuer_private_key,
            ticket_id=ticket_id,
            action_payload=action_payload,
            target_uri=target_uri,
            heartbeat_pulse_hash=heartbeat_pulse_hash,
        )


# ============================================================================
# SECTION 6: 11-Item Delivery Scope & 5 Moats Integration Primitives
# ============================================================================

import ast as _py_ast
import csv as _py_csv
import io as _py_io
import json as _py_json
import sqlite3 as _py_sqlite3


class CoWSubgraphSandbox:
    """Copy-on-Write (CoW) Subgraph Sandbox backed by SQLite overlay tables.

    Aligned with open-source `tursodatabase/agentfs` and `multikernel/branchfs`
    speculative branching patterns:
    - Isolates candidate state mutations inside an ephemeral overlay branch.
    - Promotes mutations into `committed_state` only when Station 2 reconciliation
      returns `CONFIRMED`.
    - Atomically discards all branch mutations if policy checks, circuit breakers,
      or transport ambiguity (`EFFECT_INDETERMINATE` / `HALTED`) trip.
    """

    def __init__(self) -> None:
        self._conn = _py_sqlite3.connect(":memory:")
        self._conn.execute(
            """
            CREATE TABLE committed_state (
                node_key TEXT PRIMARY KEY,
                canonical_json TEXT NOT NULL,
                value_caid TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE branch_overlay (
                branch_id TEXT NOT NULL,
                node_key TEXT NOT NULL,
                canonical_json TEXT NOT NULL,
                value_caid TEXT NOT NULL,
                PRIMARY KEY (branch_id, node_key)
            )
            """
        )
        self._active_branches: Set[str] = set()

    def seed_committed_node(self, node_key: str, value: Dict[str, Any]) -> str:
        """Write an initial baseline node into committed_state and return its CAID."""
        canonical = canonicalize_jcs(value)
        caid = compute_caid(value)
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO committed_state (node_key, canonical_json, value_caid)
                VALUES (?, ?, ?)
                """,
                (node_key, canonical, caid),
            )
        return caid

    def fork_branch(self, branch_id: str) -> str:
        """Create an isolated speculative Copy-on-Write branch."""
        if not branch_id or not branch_id.strip():
            raise GovernanceHaltError("CoW branch_id must be non-empty")
        if branch_id in self._active_branches:
            raise GovernanceHaltError(f"CoW branch {branch_id!r} is already active")
        self._active_branches.add(branch_id)
        return branch_id

    def stage_mutation(
        self, branch_id: str, node_key: str, candidate_value: Dict[str, Any]
    ) -> str:
        """Stage a candidate node mutation inside the ephemeral CoW overlay branch."""
        if branch_id not in self._active_branches:
            raise GovernanceHaltError(f"Unknown or closed CoW branch: {branch_id!r}")
        canonical = canonicalize_jcs(candidate_value)
        caid = compute_caid(candidate_value)
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO branch_overlay
                    (branch_id, node_key, canonical_json, value_caid)
                VALUES (?, ?, ?, ?)
                """,
                (branch_id, node_key, canonical, caid),
            )
        return caid

    def read_node(
        self, node_key: str, branch_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Read a node with Copy-on-Write resolution (overlay first, then committed_state)."""
        if branch_id is not None:
            if branch_id not in self._active_branches:
                raise GovernanceHaltError(f"Cannot read from inactive branch {branch_id!r}")
            cur = self._conn.execute(
                "SELECT canonical_json FROM branch_overlay WHERE branch_id = ? AND node_key = ?",
                (branch_id, node_key),
            )
            row = cur.fetchone()
            if row is not None:
                return _py_json.loads(row[0])

        cur = self._conn.execute(
            "SELECT canonical_json FROM committed_state WHERE node_key = ?",
            (node_key,),
        )
        row = cur.fetchone()
        return _py_json.loads(row[0]) if row is not None else None

    def finalize_branch(self, branch_id: str, disposition: str) -> Dict[str, Any]:
        """Promote overlay mutations on `CONFIRMED` or discard them fail-closed."""
        if branch_id not in self._active_branches:
            raise GovernanceHaltError(f"Unknown or already finalized branch: {branch_id!r}")

        cur = self._conn.execute(
            """
            SELECT node_key, canonical_json, value_caid
            FROM branch_overlay
            WHERE branch_id = ?
            ORDER BY node_key ASC
            """,
            (branch_id,),
        )
        staged_rows = cur.fetchall()
        self._active_branches.remove(branch_id)

        if disposition == "CONFIRMED":
            with self._conn:
                for node_key, canonical_json, value_caid in staged_rows:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO committed_state
                            (node_key, canonical_json, value_caid)
                        VALUES (?, ?, ?)
                        """,
                        (node_key, canonical_json, value_caid),
                    )
                self._conn.execute(
                    "DELETE FROM branch_overlay WHERE branch_id = ?", (branch_id,)
                )
            return {
                "branchId": branch_id,
                "disposition": "CONFIRMED",
                "outcome": "COMMITTED",
                "promotedNodeCount": len(staged_rows),
            }

        with self._conn:
            self._conn.execute(
                "DELETE FROM branch_overlay WHERE branch_id = ?", (branch_id,)
            )
        raise GovernanceHaltError(
            f"CoW branch {branch_id!r} discarded {len(staged_rows)} partial mutation(s) "
            f"due to non-confirmed disposition {disposition!r}"
        )


@dataclass(frozen=True)
class CompiledGovernanceArtifact:
    """Output of compiling a declarative `smaos.hcl` policy block."""

    policy_name: str
    bpf_security_map: Dict[str, Any]
    scitt_action_capsule_profile: Dict[str, Any]
    artifact_caid: str


class SmaosHclCompiler:
    """Declarative Governance DSL (`smaos.hcl`) Compiler.

    Compiles ontological policy constraints into:
    1. Structural BPF-LSM / XDP security map definitions (`bpf_security_map`).
       Note per AGENTS.md Section 5: eBPF map definitions are structural scaffolding
       unless loaded into a locked Linux kernel with an active BPF-LSM subsystem.
    2. IETF SCITT Action Capsule admissibility profiles (`scitt_action_capsule_profile`).
    """

    _BLOCK_RE = re.compile(
        r'policy\s+"([A-Za-z0-9_\-]+)"\s*\{([^}]*)\}', re.DOTALL
    )
    _ASSIGN_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)")

    @classmethod
    def compile_hcl(cls, hcl_source: str) -> CompiledGovernanceArtifact:
        """Parse a declarative `smaos.hcl` policy block and emit canonical artifacts."""
        match = cls._BLOCK_RE.search(hcl_source or "")
        if not match:
            raise GovernanceHaltError("Invalid smaos.hcl: missing `policy \"<name>\" { ... }` block")

        policy_name = match.group(1)
        body = match.group(2)
        parsed: Dict[str, Any] = {}

        for raw_line in body.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            assign = cls._ASSIGN_RE.match(line)
            if not assign:
                raise GovernanceHaltError(f"Invalid smaos.hcl statement: {line!r}")
            key, raw_val = assign.group(1), assign.group(2).strip().rstrip(",")
            try:
                parsed[key] = _py_json.loads(raw_val)
            except ValueError as exc:
                raise GovernanceHaltError(
                    f"Unsupported literal in smaos.hcl for {key!r}: {raw_val!r}"
                ) from exc

        allowed_tools = sorted(str(t) for t in parsed.get("allowed_tools", []))
        blocked_syscalls = sorted(str(s) for s in parsed.get("blocked_syscalls", []))
        allowed_cidrs = sorted(str(c) for c in parsed.get("allowed_egress_cidrs", []))
        max_amount = int(parsed.get("max_amount", 0))
        require_heartbeat = bool(parsed.get("require_heartbeat", True))

        if not allowed_tools:
            raise GovernanceHaltError("smaos.hcl policy must declare non-empty `allowed_tools`")

        bpf_map = {
            "allowedEgressCidrs": allowed_cidrs,
            "blockedSyscalls": blocked_syscalls,
            "enforcementHook": "bpf_lsm_and_xdp_structural_scaffold",
            "failClosedErrno": "EPERM",
            "policyName": policy_name,
            "scaffoldingNotice": (
                "Structural BPF policy map definition; requires a Linux CVM kernel "
                "with active BPF-LSM lockdown for live kernel syscall interception."
            ),
        }
        scitt_profile = {
            "allowedTools": allowed_tools,
            "maxAmount": max_amount,
            "policyName": policy_name,
            "requireHeartbeat": require_heartbeat,
            "scittProfileVersion": "draft-ietf-scitt-agent-profile-01",
            "transportAmbiguityDisposition": "EFFECT_INDETERMINATE",
        }
        combined = {
            "bpfSecurityMap": bpf_map,
            "scittActionCapsuleProfile": scitt_profile,
        }
        return CompiledGovernanceArtifact(
            policy_name=policy_name,
            bpf_security_map=bpf_map,
            scitt_action_capsule_profile=scitt_profile,
            artifact_caid=compute_caid(combined),
        )


@dataclass(frozen=True)
class RedactablePassport:
    """Ed25519-signed W3C Data Integrity selective-disclosure passport prototype."""

    receipt_id: str
    field_commitments: Dict[str, str]
    revealed_fields: Dict[str, str]
    revealed_salts: Dict[str, str]
    redacted_keys: List[str]
    root_signature_hex: str

    def to_root_statement(self) -> Dict[str, Any]:
        return {
            "fieldCommitments": dict(sorted(self.field_commitments.items())),
            "receiptId": self.receipt_id,
            "schema": "w3c-vc-di-bbs-selective-disclosure-v1",
        }


class Ed25519BbsSelectiveRedactor:
    """Selective redaction engine resolving EU AI Act Art. 12 vs. GDPR Art. 17.

    Aligned with W3C Data Integrity (`w3c/vc-di-bbs`) and `docknetwork/crypto`:
    - Binds each attribute $(k, v_k)$ to a salted SHA-256 commitment $C_k$.
    - Signs the canonical commitment map with `Ed25519PrivateKey` over RFC 8785 JCS.
    - Allows post-issuance redaction of PII fields (e.g., `iban`, `customer_email`)
      by stripping their cleartext values and salts while preserving root signature
      verification and mathematical commitment checks on all remaining attributes.
    """

    @staticmethod
    def _compute_field_commitment(field_name: str, field_value: str, salt_hex: str) -> str:
        commitment_obj = {
            "field": field_name,
            "salt": salt_hex,
            "value": field_value,
        }
        return hashlib.sha256(encode_jcs(commitment_obj)).hexdigest()

    @classmethod
    def mint_passport(
        cls,
        issuer_private_key: Ed25519PrivateKey,
        receipt_id: str,
        fields: Dict[str, str],
        salt_seed: str,
    ) -> RedactablePassport:
        """Mint an unredacted passport with salted field commitments and Ed25519 root signature."""
        if not fields:
            raise GovernanceHaltError("Passport fields must be non-empty")
        commitments: Dict[str, str] = {}
        salts: Dict[str, str] = {}
        for k in sorted(fields.keys()):
            salt_hex = hashlib.sha256(
                f"{salt_seed}:{receipt_id}:{k}".encode("utf-8")
            ).hexdigest()[:32]
            salts[k] = salt_hex
            commitments[k] = cls._compute_field_commitment(k, str(fields[k]), salt_hex)

        temp_passport = RedactablePassport(
            receipt_id=receipt_id,
            field_commitments=commitments,
            revealed_fields=dict(fields),
            revealed_salts=salts,
            redacted_keys=[],
            root_signature_hex="",
        )
        root_bytes = encode_jcs(temp_passport.to_root_statement())
        sig_hex = issuer_private_key.sign(root_bytes).hex()
        return RedactablePassport(
            receipt_id=receipt_id,
            field_commitments=commitments,
            revealed_fields=dict(fields),
            revealed_salts=salts,
            redacted_keys=[],
            root_signature_hex=sig_hex,
        )

    @staticmethod
    def redact_pii_fields(
        passport: RedactablePassport, pii_keys_to_redact: List[str]
    ) -> RedactablePassport:
        """Erase PII cleartext values and salts (GDPR Art. 17) while keeping commitments intact."""
        redact_set = set(pii_keys_to_redact)
        new_revealed = {
            k: v for k, v in passport.revealed_fields.items() if k not in redact_set
        }
        new_salts = {
            k: s for k, s in passport.revealed_salts.items() if k not in redact_set
        }
        combined_redacted = sorted(set(passport.redacted_keys) | redact_set)
        return RedactablePassport(
            receipt_id=passport.receipt_id,
            field_commitments=dict(passport.field_commitments),
            revealed_fields=new_revealed,
            revealed_salts=new_salts,
            redacted_keys=combined_redacted,
            root_signature_hex=passport.root_signature_hex,
        )

    @classmethod
    def verify_passport(
        cls,
        passport: RedactablePassport,
        issuer_public_key: Ed25519PublicKey,
    ) -> bool:
        """Verify Ed25519 root signature and all unredacted attribute commitments."""
        root_bytes = encode_jcs(passport.to_root_statement())
        try:
            issuer_public_key.verify(
                bytes.fromhex(passport.root_signature_hex), root_bytes
            )
        except (InvalidSignature, ValueError):
            return False

        expected_keys = set(passport.field_commitments.keys())
        revealed_keys = set(passport.revealed_fields.keys())
        redacted_keys = set(passport.redacted_keys)

        if revealed_keys | redacted_keys != expected_keys:
            return False
        if revealed_keys & redacted_keys:
            return False

        for k in revealed_keys:
            salt_hex = passport.revealed_salts.get(k)
            if not salt_hex:
                return False
            recomputed = cls._compute_field_commitment(
                k, passport.revealed_fields[k], salt_hex
            )
            if recomputed != passport.field_commitments.get(k):
                return False

        return True


class DoraXbrlCsvPackageBuilder:
    """DORA Register of Information (`RT.01.01–RT.01.03`) xBRL-CSV Exporter (EBA DPM 4.0).

    Aligned with open-source `Arelle/Arelle` xBRL-CSV package conventions and
    `FiorLab/dora-article-28-ict-third-party-register`:
    Generates deterministic CSV tables (`RT.01.01.csv`, `RT.01.02.csv`, `RT.01.03.csv`,
    `parameters.csv`) and `META-INF/reports.json` bound by an Ed25519 package receipt.
    """

    @staticmethod
    def _render_csv(headers: List[str], rows: List[List[str]]) -> str:
        buf = _py_io.StringIO()
        writer = _py_csv.writer(buf, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return buf.getvalue()

    @classmethod
    def build_package(
        cls,
        signing_key: Ed25519PrivateKey,
        entity_lei: str,
        entity_name: str,
        reporting_period: str,
        containment_arrangements: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Build an EBA DPM 4.0 xBRL-CSV Register of Information package from agent records."""
        if not entity_lei or len(entity_lei) != 20:
            raise GovernanceHaltError("DORA xBRL-CSV requires a 20-character LEI identifier")
        if not containment_arrangements:
            raise GovernanceHaltError(
                "DORA xBRL-CSV requires at least one ICT containment arrangement"
            )

        reports_json = canonicalize_jcs(
            {
                "documentInfo": {
                    "documentType": "https://xbrl.org/2021/xbrl-csv",
                    "extends": [
                        "http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/dora/4.0/mod/dora.json"
                    ],
                }
            }
        )
        parameters_csv = cls._render_csv(
            ["name", "value"],
            [
                ["entityID", f"lei:{entity_lei}"],
                ["refPeriod", reporting_period],
                ["baseCurrency", "iso4217:EUR"],
                ["decimalsInteger", "0"],
            ],
        )
        rt_01_01_csv = cls._render_csv(
            ["c0010", "c0020", "c0030", "c0040"],
            [[entity_lei, entity_name, "EU", reporting_period]],
        )

        rt_01_02_rows: List[List[str]] = []
        rt_01_03_rows: List[List[str]] = []
        for idx, arr in enumerate(containment_arrangements, start=1):
            contract_ref = arr.get("contract_ref", f"CTR-{idx:04d}")
            provider_id = arr.get("provider_lei", f"PRV-{idx:04d}")
            provider_name = arr.get("provider_name", "SovereignRuntimeBoundary")
            function_id = arr.get("function_id", "ICT-AGENT-EXECUTION-BOUNDARY")
            receipt_caid = arr.get("receipt_caid", "")
            if not receipt_caid:
                raise GovernanceHaltError(
                    f"Arrangement {contract_ref!r} missing verified receipt_caid"
                )
            rt_01_02_rows.append(
                [contract_ref, entity_lei, function_id, "CRITICAL", receipt_caid]
            )
            rt_01_03_rows.append(
                [contract_ref, provider_id, provider_name, "SHA256_ED25519_BOUND"]
            )

        rt_01_02_csv = cls._render_csv(
            ["c0010", "c0020", "c0030", "c0040", "c0050"], rt_01_02_rows
        )
        rt_01_03_csv = cls._render_csv(
            ["c0010", "c0020", "c0030", "c0040"], rt_01_03_rows
        )

        files = {
            "META-INF/reports.json": reports_json,
            "reports/parameters.csv": parameters_csv,
            "reports/RT.01.01.csv": rt_01_01_csv,
            "reports/RT.01.02.csv": rt_01_02_csv,
            "reports/RT.01.03.csv": rt_01_03_csv,
        }
        file_digests = {
            path: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for path, content in sorted(files.items())
        }
        manifest_statement = {
            "ebaDpmVersion": "4.0",
            "entityLei": entity_lei,
            "fileDigests": file_digests,
            "reportingPeriod": reporting_period,
        }
        manifest_bytes = encode_jcs(manifest_statement)
        sig_hex = signing_key.sign(manifest_bytes).hex()

        return {
            "files": files,
            "manifestStatement": manifest_statement,
            "packageCaid": hashlib.sha256(manifest_bytes).hexdigest(),
            "signatureHex": sig_hex,
        }


@dataclass(frozen=True)
class StarBaselineReceipt:
    """Ed25519-signed STAR Protocol AST Merkle-DAG baseline receipt."""

    baseline_id: str
    module_ast_digests: Dict[str, str]
    merkle_root_hex: str
    signature_hex: str

    def to_statement_dict(self) -> Dict[str, Any]:
        return {
            "baselineId": self.baseline_id,
            "merkleRoot": self.merkle_root_hex,
            "moduleAstDigests": dict(sorted(self.module_ast_digests.items())),
        }


class StarAstMerkleDagBaseline:
    """STAR Protocol CLI & AST Baseline (Ed25519-signed Merkle-DAG over normalized ASTs).

    Computes deterministic SHA-256 digests over normalized Python AST structures
    (`ast.dump(tree, annotate_fields=True, include_attributes=False)`) so whitespace
    or comment edits do not alter the digest, while any structural AST mutation changes
    the Merkle root and triggers a fail-closed baseline verification error in $O(1)$
    root-comparison time.
    """

    @staticmethod
    def compute_normalized_ast_digest(module_name: str, python_source: str) -> str:
        try:
            tree = _py_ast.parse(python_source, filename=module_name)
        except SyntaxError as exc:
            raise GovernanceHaltError(
                f"STAR AST parse failure in {module_name!r}: {exc}"
            ) from exc
        normalized_dump = _py_ast.dump(
            tree, annotate_fields=True, include_attributes=False
        )
        h = hashlib.sha256()
        h.update(b"\x00")
        h.update(module_name.encode("utf-8"))
        h.update(b"\x00")
        h.update(normalized_dump.encode("utf-8"))
        return h.hexdigest()

    @classmethod
    def compute_merkle_root(cls, module_digests: Dict[str, str]) -> str:
        if not module_digests:
            raise GovernanceHaltError("STAR AST baseline requires at least one module")
        level = [
            bytes.fromhex(module_digests[k]) for k in sorted(module_digests.keys())
        ]
        while len(level) > 1:
            next_level: List[bytes] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    next_level.append(_hash_node(level[i], level[i + 1]))
                else:
                    next_level.append(level[i])
            level = next_level
        return level[0].hex()

    @classmethod
    def freeze_baseline(
        cls,
        baseline_id: str,
        module_sources: Dict[str, str],
        signing_key: Ed25519PrivateKey,
    ) -> StarBaselineReceipt:
        """Freeze a set of Python modules into an Ed25519-signed AST Merkle-DAG baseline."""
        digests = {
            mod: cls.compute_normalized_ast_digest(mod, src)
            for mod, src in sorted(module_sources.items())
        }
        merkle_root = cls.compute_merkle_root(digests)
        temp = StarBaselineReceipt(
            baseline_id=baseline_id,
            module_ast_digests=digests,
            merkle_root_hex=merkle_root,
            signature_hex="",
        )
        canonical = encode_jcs(temp.to_statement_dict())
        sig_hex = signing_key.sign(canonical).hex()
        return StarBaselineReceipt(
            baseline_id=baseline_id,
            module_ast_digests=digests,
            merkle_root_hex=merkle_root,
            signature_hex=sig_hex,
        )

    @classmethod
    def verify_o1_root_and_sources(
        cls,
        receipt: StarBaselineReceipt,
        candidate_sources: Dict[str, str],
        public_key: Ed25519PublicKey,
    ) -> bool:
        """Verify the Ed25519 baseline receipt and confirm $O(1)$ Merkle root equality."""
        canonical = encode_jcs(receipt.to_statement_dict())
        try:
            public_key.verify(bytes.fromhex(receipt.signature_hex), canonical)
        except (InvalidSignature, ValueError):
            return False

        candidate_digests = {
            mod: cls.compute_normalized_ast_digest(mod, src)
            for mod, src in sorted(candidate_sources.items())
        }
        if candidate_digests.keys() != receipt.module_ast_digests.keys():
            return False
        candidate_root = cls.compute_merkle_root(candidate_digests)
        return candidate_root == receipt.merkle_root_hex


@dataclass(frozen=True)
class ZeroOverclaimProof:
    """Blinded commitment compliance proof attesting to a 0% overclaim rate."""

    batch_id: str
    total_episodes: int
    overclaim_count: int
    overclaim_rate_bps: int
    blinded_episode_commitments: List[str]
    commitment_merkle_root: str
    signature_hex: str

    def to_public_journal(self) -> Dict[str, Any]:
        return {
            "batchId": self.batch_id,
            "blindedEpisodeCommitments": list(self.blinded_episode_commitments),
            "commitmentMerkleRoot": self.commitment_merkle_root,
            "overclaimCount": self.overclaim_count,
            "overclaimRateBps": self.overclaim_rate_bps,
            "totalEpisodes": self.total_episodes,
        }


class ZeroOverclaimComplianceProver:
    """Blinded-commitment compliance prover attesting `overclaim_count == 0`.

    Aligned with open-source zkVM public-journal commitment patterns (`succinctlabs/sp1`,
    `risc0/risc0`):
    - Evaluates each episode's boolean invariant:
      `overclaim = claimed_safe and (not verified_safe)`
    - Blinds raw enterprise payloads behind salted SHA-256 commitments so no raw
      payload strings or account numbers leave the proving boundary.
    - Signs the canonical public journal with `Ed25519PrivateKey` only when
      `overclaim_count == 0`.
    """

    @staticmethod
    def prove_zero_overclaim_batch(
        batch_id: str,
        episodes: List[Dict[str, Any]],
        blinding_seed: str,
        prover_private_key: Ed25519PrivateKey,
    ) -> ZeroOverclaimProof:
        if not episodes:
            raise GovernanceHaltError("Compliance proof requires at least one episode")

        commitments: List[str] = []
        overclaim_count = 0

        for idx, ep in enumerate(episodes):
            ep_id = str(ep.get("episode_id", f"ep-{idx}"))
            raw_payload = ep.get("raw_payload", {})
            claimed_safe = bool(ep.get("claimed_safe", False))
            verified_safe = bool(ep.get("verified_safe", False))

            if claimed_safe and not verified_safe:
                overclaim_count += 1

            blinding_nonce = hashlib.sha256(
                f"{blinding_seed}:{batch_id}:{ep_id}".encode("utf-8")
            ).hexdigest()
            blinded_record = {
                "blindingNonce": blinding_nonce,
                "claimedSafe": claimed_safe,
                "episodeId": ep_id,
                "payloadCaid": compute_caid(raw_payload),
                "verifiedSafe": verified_safe,
            }
            commitments.append(hashlib.sha256(encode_jcs(blinded_record)).hexdigest())

        if overclaim_count > 0:
            raise GovernanceHaltError(
                f"Zero-overclaim proof aborted: observed {overclaim_count} overclaim(s) in batch {batch_id!r}"
            )

        level = [bytes.fromhex(c) for c in commitments]
        while len(level) > 1:
            next_level: List[bytes] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    next_level.append(_hash_node(level[i], level[i + 1]))
                else:
                    next_level.append(level[i])
            level = next_level
        merkle_root = level[0].hex()

        temp = ZeroOverclaimProof(
            batch_id=batch_id,
            total_episodes=len(episodes),
            overclaim_count=0,
            overclaim_rate_bps=0,
            blinded_episode_commitments=commitments,
            commitment_merkle_root=merkle_root,
            signature_hex="",
        )
        journal_bytes = encode_jcs(temp.to_public_journal())
        sig_hex = prover_private_key.sign(journal_bytes).hex()

        return ZeroOverclaimProof(
            batch_id=batch_id,
            total_episodes=len(episodes),
            overclaim_count=0,
            overclaim_rate_bps=0,
            blinded_episode_commitments=commitments,
            commitment_merkle_root=merkle_root,
            signature_hex=sig_hex,
        )

    @staticmethod
    def verify_zero_overclaim_proof(
        proof: ZeroOverclaimProof,
        prover_public_key: Ed25519PublicKey,
    ) -> bool:
        """Verify the Ed25519 signature, Merkle root, and zero-overclaim invariants."""
        if proof.overclaim_count != 0 or proof.overclaim_rate_bps != 0:
            return False
        if proof.total_episodes <= 0 or len(proof.blinded_episode_commitments) != proof.total_episodes:
            return False

        level = [bytes.fromhex(c) for c in proof.blinded_episode_commitments]
        while len(level) > 1:
            next_level: List[bytes] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    next_level.append(_hash_node(level[i], level[i + 1]))
                else:
                    next_level.append(level[i])
            level = next_level
        if level[0].hex() != proof.commitment_merkle_root:
            return False

        journal_bytes = encode_jcs(proof.to_public_journal())
        try:
            prover_public_key.verify(bytes.fromhex(proof.signature_hex), journal_bytes)
            return True
        except (InvalidSignature, ValueError):
            return False


# ============================================================================
# SECTION 7: Open-Source Primitive Composition Glue & v1.1 Backlog Primitives
# ============================================================================

import zipfile as _py_zipfile


class TetragonTracingPolicyCompiler:
    """Dual-emission compiler translating `smaos.hcl` into Cilium Tetragon `TracingPolicy`.

    Emits:
    1. Cilium Tetragon `cilium.io/v1alpha1` `TracingPolicy` specification (`sys_execve`
       and `sys_connect` kprobes with `Sigkill` action on un-cleared socket/process access).
    2. Structural BPF-LSM map + IETF SCITT Action Capsule profile via `SmaosHclCompiler`.

    Epistemic Boundary (AGENTS.md Section 5):
    Emitted Tetragon / BPF-LSM definitions are structural scaffolding unless applied to
    a Linux kernel running Cilium Tetragon / BPF-LSM.
    """

    @classmethod
    def compile_dual_emission(cls, hcl_source: str) -> Dict[str, Any]:
        base = SmaosHclCompiler.compile_hcl(hcl_source)
        allowed_cidrs = base.bpf_security_map["allowedEgressCidrs"]
        blocked_syscalls = base.bpf_security_map["blockedSyscalls"]

        kprobes: List[Dict[str, Any]] = [
            {
                "call": "sys_connect",
                "syscall": True,
                "args": [{"index": 0, "type": "int"}, {"index": 1, "type": "sockaddr"}],
                "selectors": [
                    {
                        "matchArgs": [
                            {
                                "index": 1,
                                "operator": "NotDAddr",
                                "values": allowed_cidrs or ["127.0.0.1/32"],
                            }
                        ],
                        "matchActions": [{"action": "Sigkill"}],
                    }
                ],
            }
        ]
        for syscall_name in blocked_syscalls:
            kprobes.append(
                {
                    "call": syscall_name,
                    "syscall": True,
                    "selectors": [{"matchActions": [{"action": "Sigkill"}]}],
                }
            )

        tracing_policy = {
            "apiVersion": "cilium.io/v1alpha1",
            "kind": "TracingPolicy",
            "metadata": {
                "name": f"smaos-{base.policy_name.replace('_', '-')}",
                "annotations": {
                    "smaos.io/scaffolding-notice": (
                        "Structural TracingPolicy specification; requires a Linux kernel "
                        "running Cilium Tetragon for live kprobe SIGKILL enforcement."
                    )
                },
            },
            "spec": {"kprobes": kprobes},
        }
        dual_bundle = {
            "bpfSecurityMap": base.bpf_security_map,
            "scittActionCapsuleProfile": base.scitt_action_capsule_profile,
            "tetragonTracingPolicy": tracing_policy,
        }
        return {
            "bundle": dual_bundle,
            "bundleCaid": compute_caid(dual_bundle),
        }


class DoraIts2024ZipExporter:
    """Direct auto-mapper from pinned agent/MCP manifests into EBA DPM 4.0 xBRL-CSV ZIP packages.

    Complies with EBA DPM 4.0 ITS 2024/2956 (`dora.json`) directory layout:
    - `<package_name>/META-INF/reports.json`
    - `<package_name>/reports/parameters.csv`
    - `<package_name>/reports/RT.01.01.csv`
    - `<package_name>/reports/RT.01.02.csv`
    - `<package_name>/reports/RT.01.03.csv`
    """

    @classmethod
    def build_xbrl_csv_zip_bytes(
        cls,
        signing_key: Ed25519PrivateKey,
        entity_lei: str,
        entity_name: str,
        reporting_period: str,
        pinned_mcp_manifests: List[Dict[str, str]],
        package_prefix: str = "dora_roi_eba_dpm_4_0",
    ) -> Tuple[bytes, Dict[str, Any]]:
        pkg = DoraXbrlCsvPackageBuilder.build_package(
            signing_key=signing_key,
            entity_lei=entity_lei,
            entity_name=entity_name,
            reporting_period=reporting_period,
            containment_arrangements=pinned_mcp_manifests,
        )
        buf = _py_io.BytesIO()
        fixed_dt = (2026, 1, 1, 0, 0, 0)
        with _py_zipfile.ZipFile(buf, mode="w", compression=_py_zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in sorted(pkg["files"].items()):
                info = _py_zipfile.ZipInfo(
                    filename=f"{package_prefix}/{rel_path}", date_time=fixed_dt
                )
                info.compress_type = _py_zipfile.ZIP_DEFLATED
                zf.writestr(info, content.encode("utf-8"))
        zip_bytes = buf.getvalue()
        pkg["zipSha256"] = hashlib.sha256(zip_bytes).hexdigest()
        return zip_bytes, pkg


class GhostAtrDiagnosticScanner:
    """Diagnostic scanner evaluating `agent-threat-rules` (`ATR-2026-01932`) and CISO GII.

    Audits local developer configuration objects (`.claude`, `cursor.json`, `mcp.json`)
    and computes a deterministic CISO Governance Intensity Index (`GII`, `0–100`)
    signed with Ed25519.
    """

    RULE_ID = "ATR-2026-01932"

    @classmethod
    def evaluate_environment(
        cls,
        config_snapshot: Dict[str, Any],
        signing_key: Ed25519PrivateKey,
    ) -> Dict[str, Any]:
        findings: List[Dict[str, str]] = []
        penalty = 0

        mcp_servers = config_snapshot.get("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}

        for srv_name in sorted(mcp_servers.keys()):
            srv = mcp_servers[srv_name] or {}
            if not srv.get("sha256_pin"):
                findings.append(
                    {
                        "ruleId": f"{cls.RULE_ID}:UNPINNED_MCP_MANIFEST",
                        "server": srv_name,
                        "severity": "HIGH",
                    }
                )
                penalty += 25

            capabilities = set(srv.get("capabilities", []))
            if {"shell_exec", "network_egress"}.issubset(capabilities):
                findings.append(
                    {
                        "ruleId": f"{cls.RULE_ID}:TOXIC_SHELL_EGRESS_CHAIN",
                        "server": srv_name,
                        "severity": "CRITICAL",
                    }
                )
                penalty += 35

            env_map = srv.get("env", {}) or {}
            for env_key, env_val in sorted(env_map.items()):
                if isinstance(env_val, str) and (
                    env_val.startswith("sk-") or "SECRET" in env_key.upper()
                ) and not env_val.startswith("vault://"):
                    findings.append(
                        {
                            "ruleId": f"{cls.RULE_ID}:PLAINTEXT_CREDENTIAL_EXPOSURE",
                            "server": f"{srv_name}:{env_key}",
                            "severity": "HIGH",
                        }
                    )
                    penalty += 25

        if not config_snapshot.get("station1_wire_interlock_enabled", False):
            findings.append(
                {
                    "ruleId": f"{cls.RULE_ID}:MISSING_STATION1_WIRE_INTERLOCK",
                    "server": "runtime_boundary",
                    "severity": "MEDIUM",
                }
            )
            penalty += 15

        gii_score = max(0, 100 - penalty)
        statement = {
            "atrRuleBaseline": cls.RULE_ID,
            "findingCount": len(findings),
            "findings": findings,
            "governanceIntensityIndex": gii_score,
        }
        jcs_bytes = encode_jcs(statement)
        return {
            "report": statement,
            "reportCaid": hashlib.sha256(jcs_bytes).hexdigest(),
            "signatureHex": signing_key.sign(jcs_bytes).hex(),
        }


class Station1AuthorizationAdmissibilityGate:
    """Station 1 Zero-I/O 5-Term Boolean Standing Interlock.

    Evaluates:
      AuthorizationAdmissibility =
          GrantValid
          ∧ PolicyEpochFresh
          ∧ SourceEpochFresh
          ∧ ControlHealthy
          ∧ RiskProfileWithinGrantLimits
    """

    @staticmethod
    def evaluate_standing(
        *,
        grant_valid: bool,
        bound_policy_epoch: int,
        active_policy_epoch: int,
        bound_source_epoch: int,
        active_source_epoch: int,
        control_healthy: bool,
        action_risk_score: int,
        grant_max_risk_score: int,
    ) -> Dict[str, Any]:
        policy_epoch_fresh = bool(bound_policy_epoch == active_policy_epoch)
        source_epoch_fresh = bool(bound_source_epoch == active_source_epoch)
        risk_within_limits = bool(0 <= action_risk_score <= grant_max_risk_score)

        admissible = bool(
            grant_valid
            and policy_epoch_fresh
            and source_epoch_fresh
            and control_healthy
            and risk_within_limits
        )
        return {
            "admissible": admissible,
            "terms": {
                "ControlHealthy": bool(control_healthy),
                "GrantValid": bool(grant_valid),
                "PolicyEpochFresh": policy_epoch_fresh,
                "RiskProfileWithinGrantLimits": risk_within_limits,
                "SourceEpochFresh": source_epoch_fresh,
            },
        }


class TripartiteKvBlockAdmissibilityGate:
    """Post-v1.0 Roadmap (`v1.1` Item 1): Tripartite Memory Admissibility at ~16k-Token KV Block Unit.

    Enforces:
      MemoryAdmissible =
          BlockIntegrityValid ∧ ProvenanceValid ∧ EpochFresh ∧ GrantScopeValid

    Binds state restoration at the <= 16,384-token KV block granularity rather than
    whole-conversation granularity.
    """

    MAX_KV_BLOCK_TOKENS = 16384

    @classmethod
    def evaluate_kv_block(
        cls,
        *,
        kv_block_bytes: bytes,
        expected_block_sha256: str,
        token_count: int,
        source_provenance_caid: str,
        pinned_provenance_caids: Set[str],
        block_policy_epoch: int,
        active_policy_epoch: int,
        block_source_epoch: int,
        active_source_epoch: int,
        requested_tool_scope: str,
        granted_tool_scopes: Set[str],
    ) -> Dict[str, Any]:
        observed_sha256 = hashlib.sha256(kv_block_bytes).hexdigest()
        block_integrity_valid = bool(
            0 < token_count <= cls.MAX_KV_BLOCK_TOKENS
            and observed_sha256 == expected_block_sha256
        )
        provenance_valid = bool(
            source_provenance_caid and source_provenance_caid in pinned_provenance_caids
        )
        epoch_fresh = bool(
            block_policy_epoch == active_policy_epoch
            and block_source_epoch == active_source_epoch
        )
        grant_scope_valid = bool(
            requested_tool_scope and requested_tool_scope in granted_tool_scopes
        )

        memory_admissible = bool(
            block_integrity_valid
            and provenance_valid
            and epoch_fresh
            and grant_scope_valid
        )
        return {
            "blockSha256": observed_sha256,
            "memoryAdmissible": memory_admissible,
            "status": "FRESH" if memory_admissible else "STALE_DONT_TRUST_YET",
            "terms": {
                "BlockIntegrityValid": block_integrity_valid,
                "EpochFresh": epoch_fresh,
                "GrantScopeValid": grant_scope_valid,
                "ProvenanceValid": provenance_valid,
            },
            "tokenCount": token_count,
        }


class ScittOtelActionCapsuleCorrelator:
    """Post-v1.0 Roadmap (`v1.1` Item 2): OpenTelemetry SCITT Action Capsule Correlation.

    Maps `draft-palanisamy-scitt-aac-otel-00` (`org.agentactioncapsule.otel`) into
    an RFC 8785 JCS canonicalized, Ed25519-signed `ContinuityReceipt` envelope for
    distributed trace alignment.
    """

    _HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
    _HEX16_RE = re.compile(r"^[0-9a-f]{16}$")

    @classmethod
    def mint_otel_correlated_receipt(
        cls,
        *,
        signing_key: Ed25519PrivateKey,
        receipt_id: str,
        prev_chain_tip_hex: str,
        action_payload: Dict[str, Any],
        disposition: str,
        trace_id_hex: str,
        span_id_hex: str,
        trace_flags_hex: str = "01",
    ) -> Dict[str, Any]:
        trace_id = trace_id_hex.lower()
        span_id = span_id_hex.lower()
        if not cls._HEX32_RE.match(trace_id) or trace_id == "0" * 32:
            raise GovernanceHaltError("Invalid OpenTelemetry 128-bit trace_id")
        if not cls._HEX16_RE.match(span_id) or span_id == "0" * 16:
            raise GovernanceHaltError("Invalid OpenTelemetry 64-bit span_id")

        caid = compute_caid(action_payload)
        otel_extension = {
            "scittDraft": "draft-palanisamy-scitt-aac-otel-00",
            "spanId": span_id,
            "traceFlags": trace_flags_hex,
            "traceId": trace_id,
            "traceparent": f"00-{trace_id}-{span_id}-{trace_flags_hex}",
        }
        statement = {
            "caid": caid,
            "disposition": disposition,
            "org.agentactioncapsule.otel": otel_extension,
            "prevChainTip": prev_chain_tip_hex,
            "receiptId": receipt_id,
        }
        jcs_bytes = encode_jcs(statement)
        chain_tip = hashlib.sha256(
            bytes.fromhex(prev_chain_tip_hex) + jcs_bytes
        ).hexdigest()
        envelope = {
            "chainTip": chain_tip,
            "statement": statement,
        }
        envelope_bytes = encode_jcs(envelope)
        sig_hex = signing_key.sign(envelope_bytes).hex()
        return {
            "envelope": envelope,
            "signatureHex": sig_hex,
        }

    @staticmethod
    def verify_otel_correlated_receipt(
        receipt_bundle: Dict[str, Any], public_key: Ed25519PublicKey
    ) -> bool:
        envelope = receipt_bundle.get("envelope", {})
        sig_hex = receipt_bundle.get("signatureHex", "")
        statement = envelope.get("statement", {})
        prev_tip = statement.get("prevChainTip", "")
        try:
            expected_tip = hashlib.sha256(
                bytes.fromhex(prev_tip) + encode_jcs(statement)
            ).hexdigest()
            if expected_tip != envelope.get("chainTip"):
                return False
            public_key.verify(bytes.fromhex(sig_hex), encode_jcs(envelope))
            return True
        except (InvalidSignature, ValueError):
            return False


class HardwareAttestationReceiptBinder:
    """Post-v1.0 Roadmap (`v1.1` Item 3): Hardware Attestation Binding in `ContinuityReceipt`.

    Embeds Intel TDX / AMD SEV-SNP enclave quote claims (verified by a Tinfoil/VirTEE
    verifier key) directly into the `ContinuityReceipt` statement, binding `reportDataCaid`
    to the receipt's RFC 8785 `CAID`.

    Epistemic Boundary (AGENTS.md Section 5):
    This cryptographic quote-binding layer is structural scaffolding unless executed
    inside physical Intel TDX or AMD SEV-SNP CVM hardware.
    """

    SUPPORTED_TEES = {"INTEL_TDX", "AMD_SEV_SNP"}

    @classmethod
    def mint_attested_continuity_receipt(
        cls,
        *,
        ledger_signing_key: Ed25519PrivateKey,
        tinfoil_verifier_key: Ed25519PrivateKey,
        receipt_id: str,
        action_payload: Dict[str, Any],
        tee_type: str,
        measurement_mrtd_hex: str,
    ) -> Dict[str, Any]:
        if tee_type not in cls.SUPPORTED_TEES:
            raise GovernanceHaltError(f"Unsupported TEE architecture: {tee_type!r}")
        caid = compute_caid(action_payload)
        quote_claims = {
            "measurementHex": measurement_mrtd_hex,
            "reportDataCaid": caid,
            "scaffoldingNotice": (
                "Structural CVM quote binding; requires physical Intel TDX or "
                "AMD SEV-SNP hardware for live silicon attestation."
            ),
            "teeType": tee_type,
            "verifierProfile": "tinfoil-virtee-rats-v1",
        }
        quote_sig_hex = tinfoil_verifier_key.sign(encode_jcs(quote_claims)).hex()
        receipt_statement = {
            "caid": caid,
            "hardwareAttestationQuote": {
                "claims": quote_claims,
                "verifierSignatureHex": quote_sig_hex,
            },
            "receiptId": receipt_id,
        }
        receipt_sig_hex = ledger_signing_key.sign(encode_jcs(receipt_statement)).hex()
        return {
            "receiptSignatureHex": receipt_sig_hex,
            "statement": receipt_statement,
        }

    @classmethod
    def verify_attested_continuity_receipt(
        cls,
        attested_receipt: Dict[str, Any],
        ledger_public_key: Ed25519PublicKey,
        tinfoil_verifier_public_key: Ed25519PublicKey,
    ) -> bool:
        statement = attested_receipt.get("statement", {})
        receipt_sig = attested_receipt.get("receiptSignatureHex", "")
        hw_quote = statement.get("hardwareAttestationQuote", {})
        claims = hw_quote.get("claims", {})
        quote_sig = hw_quote.get("verifierSignatureHex", "")

        if claims.get("reportDataCaid") != statement.get("caid"):
            return False
        if claims.get("teeType") not in cls.SUPPORTED_TEES:
            return False

        try:
            tinfoil_verifier_public_key.verify(
                bytes.fromhex(quote_sig), encode_jcs(claims)
            )
            ledger_public_key.verify(
                bytes.fromhex(receipt_sig), encode_jcs(statement)
            )
            return True
        except (InvalidSignature, ValueError):
            return False


class R1csZeroOverclaimCircuit:
    """Post-v1.0 Roadmap (`v1.1` Item 4): R1CS Finite-Field Circuit for 0% Overclaim Proofs.

    Evaluates Rank-1 Constraint System (R1CS) equations over prime field
    $\\mathbb{F}_p$ ($p = 2^{255} - 19$) for each episode witness
    $w_i = (1, c_i, v_i, o_i)$ where $c_i = \\text{claimed\\_safe}_i$,
    $v_i = \\text{verified\\_safe}_i$, and $o_i = \\text{overclaim}_i$:
      1. Booleanity of $c_i$: $c_i \\cdot (1 - c_i) \\equiv 0 \\pmod p$
      2. Booleanity of $v_i$: $v_i \\cdot (1 - v_i) \\equiv 0 \\pmod p$
      3. Overclaim gate:      $c_i \\cdot (1 - v_i) \\equiv o_i \\pmod p$
      4. Zero-overclaim wire: $1 \\cdot o_i \\equiv 0 \\pmod p$
    """

    FIELD_PRIME = (1 << 255) - 19

    @classmethod
    def verify_episode_witness_r1cs(
        cls, claimed_safe: int, verified_safe: int
    ) -> Dict[str, Any]:
        p = cls.FIELD_PRIME
        c = claimed_safe % p
        v = verified_safe % p
        o = (c * ((1 - v) % p)) % p

        # 4 R1CS constraints (A_k . w) * (B_k . w) == (C_k . w) mod p
        c1_lhs = (c * ((1 - c) % p)) % p
        c1_rhs = 0

        c2_lhs = (v * ((1 - v) % p)) % p
        c2_rhs = 0

        c3_lhs = (c * ((1 - v) % p)) % p
        c3_rhs = o

        c4_lhs = (1 * o) % p
        c4_rhs = 0

        satisfied = (
            c1_lhs == c1_rhs
            and c2_lhs == c2_rhs
            and c3_lhs == c3_rhs
            and c4_lhs == c4_rhs
        )
        return {
            "overclaimWire": o,
            "r1csSatisfied": satisfied,
            "witnessVector": [1, c, v, o],
        }


class Ed25519WycheproofZip215Validator:
    r"""Tier 2 (Action 20): Ed25519 Strictness & Wycheproof / ZIP-215 Vector Validator.

    Enforces strict canonical checks before invoking Ed25519 signature verification:
      1. Signature must be exactly 64 bytes and public key exactly 32 bytes.
      2. Scalar $S$ (upper 32 bytes, little-endian) must satisfy $0 \le S < L$, where
         $L = 2^{252} + 27742317777372353535851937790883648493$ (rejects malleable $S + L$).
      3. Neither public key $A$ nor commitment $R$ (lower 32 bytes) may be one of the
         8 known small-order torsion points on Curve25519.
    """

    ED25519_ORDER_L = (1 << 252) + 27742317777372353535851937790883648493

    # 8 small-order torsion point encodings (32-byte hex) on Ed25519
    SMALL_ORDER_POINTS_HEX = {
        "01" + "00" * 31,  # Identity (0, 1)
        "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",  # (0, -1)
        "00" * 32,  # Order 4 point
        "00" * 31 + "80",  # Order 4 point with sign bit
        "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
        "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
        "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
        "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
    }

    @classmethod
    def verify_strict(
        cls,
        public_key_bytes: bytes,
        signature_bytes: bytes,
        message_bytes: bytes,
    ) -> Dict[str, Any]:
        if len(public_key_bytes) != 32:
            return {"valid": False, "reason": "INVALID_PUBKEY_LENGTH"}
        if len(signature_bytes) != 64:
            return {"valid": False, "reason": "INVALID_SIGNATURE_LENGTH"}

        r_bytes = signature_bytes[:32]
        s_bytes = signature_bytes[32:]
        s_int = int.from_bytes(s_bytes, "little")

        if s_int >= cls.ED25519_ORDER_L:
            return {"valid": False, "reason": "NON_CANONICAL_SCALAR_S_GE_L"}

        if public_key_bytes.hex() in cls.SMALL_ORDER_POINTS_HEX:
            return {"valid": False, "reason": "SMALL_ORDER_PUBLIC_KEY"}

        if r_bytes.hex() in cls.SMALL_ORDER_POINTS_HEX:
            return {"valid": False, "reason": "SMALL_ORDER_COMMITMENT_R"}

        try:
            pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            pub.verify(signature_bytes, message_bytes)
            return {"valid": True, "reason": "VALID_CANONICAL_ED25519"}
        except (InvalidSignature, ValueError):
            return {"valid": False, "reason": "INVALID_SIGNATURE"}


class CyberphoneJcsVectorSuite:
    """Tier 2 (Action 21): Cyberphone RFC 8785 JCS Vector Validator & No-Float Contract Guard.

    Enforces:
      - UTF-16 code-unit sorting across BMP (`\\u20ac`) and supplementary planes (`\\ud83d\\ude00` vs `\\uffff`).
      - Rejection of floating-point values (`float`) and out-of-range I-JSON integers ($|n| > 2^{53} - 1$)
        in signed payload contracts to eliminate IEEE 754 cross-language serialization drift.
    """

    MAX_SAFE_IJSON_INT = (1 << 53) - 1

    @classmethod
    def validate_no_float_contract(cls, node: Any) -> None:
        if isinstance(node, float):
            raise GovernanceHaltError(
                "Floating-point numbers are disallowed in signed payload contracts; use integer minor units or string decimals"
            )
        if isinstance(node, int) and not isinstance(node, bool):
            if abs(node) > cls.MAX_SAFE_IJSON_INT:
                raise GovernanceHaltError(
                    f"Integer {node} exceeds RFC 7493 I-JSON safe range +/- (2^53 - 1)"
                )
        elif isinstance(node, dict):
            for k, v in node.items():
                if not isinstance(k, str):
                    raise GovernanceHaltError("JSON object keys must be strings")
                cls.validate_no_float_contract(v)
        elif isinstance(node, list):
            for item in node:
                cls.validate_no_float_contract(item)

    @classmethod
    def run_cyberphone_utf16_sorting_vector(cls) -> Dict[str, Any]:
        # U+20AC (0x20AC), U+1F600 (surrogate pair 0xD83D 0xDE00), U+FFFF (0xFFFF)
        # In UTF-16 code unit order: 0x20AC < 0xD83D < 0xFFFF
        # (Whereas in UTF-8 / Unicode code point order, U+FFFF < U+1F600!)
        test_obj = {
            "\uffff": "bmp_high",
            "\U0001f600": "astral_surrogate",
            "\u20ac": "euro_sign",
        }
        canonical_bytes = encode_jcs(test_obj)
        canonical_str = canonical_bytes.decode("utf-8")
        expected_str = '{"\u20ac":"euro_sign","\U0001f600":"astral_surrogate","\uffff":"bmp_high"}'
        return {
            "canonicalString": canonical_str,
            "matchesRfc8785Utf16Order": canonical_str == expected_str,
        }


class Rfc3161TimestampAuthorityAnchor:
    """Tier 2 (Action 23): RFC 3161 Time Stamping Authority (TSA) Receipt Anchor.

    Binds a ledger `chainTip` to an external TSA signature over
    `(chainTipHex, genTimeIso, policyOid, serialNumber, tsaEpoch)` to mitigate
    operator key compromise or log-tail truncation.
    """

    @staticmethod
    def mint_timestamp_token(
        *,
        tsa_private_key: Ed25519PrivateKey,
        chain_tip_hex: str,
        policy_oid: str,
        serial_number: int,
        tsa_epoch: int,
        gen_time_iso: str,
    ) -> Dict[str, Any]:
        tst_info = {
            "chainTipHex": chain_tip_hex.lower(),
            "genTimeIso": gen_time_iso,
            "hashAlgorithm": "SHA-256",
            "policyOid": policy_oid,
            "serialNumber": serial_number,
            "tsaEpoch": tsa_epoch,
        }
        sig_hex = tsa_private_key.sign(encode_jcs(tst_info)).hex()
        return {
            "tsaSignatureHex": sig_hex,
            "tstInfo": tst_info,
        }

    @staticmethod
    def verify_timestamp_token(
        token: Dict[str, Any],
        expected_chain_tip_hex: str,
        tsa_public_key: Ed25519PublicKey,
    ) -> bool:
        tst_info = token.get("tstInfo", {})
        sig_hex = token.get("tsaSignatureHex", "")
        if tst_info.get("chainTipHex") != expected_chain_tip_hex.lower():
            return False
        try:
            tsa_public_key.verify(bytes.fromhex(sig_hex), encode_jcs(tst_info))
            return True
        except (InvalidSignature, ValueError):
            return False


class McpOAuth21ResourceAudienceGate:
    """Gap 4: MCP 2025-11-25 OAuth 2.1 Resource Server Audience Binding & No-Token-Passthrough Gate.

    Enforces:
      1. RFC 8707 `resource` audience binding (`token_claims["aud"] == expected_resource_uri`).
      2. Mandatory identity claims (`sub`, `client_id`, `scope`).
      3. Strict prohibition of OAuth/Bearer token passthrough in outbound tool arguments
         (prevents Confused Deputy attacks).
    """

    _PASSTHROUGH_PATTERNS = (
        re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    )

    @classmethod
    def evaluate_mcp_dispatch(
        cls,
        *,
        token_claims: Dict[str, Any],
        expected_resource_uri: str,
        required_scope: str,
        outbound_tool_arguments: Dict[str, Any],
        inbound_raw_access_token: str = "",
    ) -> Dict[str, Any]:
        aud = str(token_claims.get("aud", ""))
        sub = str(token_claims.get("sub", ""))
        client_id = str(token_claims.get("client_id", ""))
        scopes = set(str(token_claims.get("scope", "")).split())

        if not aud or aud != expected_resource_uri:
            raise GovernanceHaltError(
                f"RFC 8707 resource audience mismatch: expected {expected_resource_uri!r}, got {aud!r}"
            )
        if not sub or not client_id:
            raise GovernanceHaltError("Missing required OAuth 2.1 principal claims (sub, client_id)")
        if required_scope not in scopes:
            raise GovernanceHaltError(f"Missing required OAuth 2.1 scope: {required_scope!r}")

        serialized_args = encode_jcs(outbound_tool_arguments).decode("utf-8")
        if inbound_raw_access_token and inbound_raw_access_token in serialized_args:
            raise GovernanceHaltError(
                "MCP 2025-11-25 violation: inbound access token passthrough detected in tool arguments"
            )
        for pat in cls._PASSTHROUGH_PATTERNS:
            if pat.search(serialized_args):
                raise GovernanceHaltError(
                    "MCP 2025-11-25 violation: Bearer/JWT token passthrough detected in tool arguments"
                )

        return {
            "identityBinding": {
                "aud": aud,
                "clientId": client_id,
                "scope": required_scope,
                "sub": sub,
            },
            "tokenPassthroughDetected": False,
        }


class IndeterminateResolutionReceiptProtocol:
    """Tier 3 (Action 25): Signed `EFFECT_INDETERMINATE` -> `RESOLUTION_RECEIPT` Saga Protocol.

    Demonstrates eventual-consistency resolution (per `AGENTS.md` §5):
      1. Mints an `EFFECT_INDETERMINATE` receipt (`retrySafe=False`) when the transport severs post-dispatch.
      2. After out-of-band target state reconciliation, mints a signed `RESOLUTION_RECEIPT`
         cryptographically chained via `prevChainTip == indeterminateReceipt.chainTip` and
         bound to the same `operationId` and `caid`.
    """

    @staticmethod
    def mint_indeterminate_receipt(
        *,
        signing_key: Ed25519PrivateKey,
        operation_id: str,
        action_payload: Dict[str, Any],
        prev_chain_tip_hex: str,
        epoch: int,
    ) -> Dict[str, Any]:
        caid = compute_caid(action_payload)
        statement = {
            "caid": caid,
            "disposition": "EFFECT_INDETERMINATE",
            "epoch": epoch,
            "operationId": operation_id,
            "prevChainTip": prev_chain_tip_hex,
            "receiptType": "DISPATCH_OUTCOME_RECEIPT",
            "retrySafe": False,
        }
        chain_tip = hashlib.sha256(
            bytes.fromhex(prev_chain_tip_hex) + encode_jcs(statement)
        ).hexdigest()
        envelope = {"chainTip": chain_tip, "statement": statement}
        sig_hex = signing_key.sign(encode_jcs(envelope)).hex()
        return {"envelope": envelope, "signatureHex": sig_hex}

    @staticmethod
    def mint_resolution_receipt(
        *,
        signing_key: Ed25519PrivateKey,
        indeterminate_receipt: Dict[str, Any],
        reconciled_disposition: str,
        target_proof_hash_hex: str,
        epoch: int,
    ) -> Dict[str, Any]:
        if reconciled_disposition not in {"CONFIRMED", "REFUTED", "CONFLICT"}:
            raise GovernanceHaltError(
                f"Invalid terminal resolution disposition: {reconciled_disposition!r}"
            )
        ind_env = indeterminate_receipt["envelope"]
        ind_stmt = ind_env["statement"]
        if ind_stmt.get("disposition") != "EFFECT_INDETERMINATE":
            raise GovernanceHaltError("Resolution receipt requires an EFFECT_INDETERMINATE predecessor")

        statement = {
            "caid": ind_stmt["caid"],
            "consistencyModel": "EVENTUAL_CONSISTENCY_SAGA_PROBE",
            "epoch": epoch,
            "operationId": ind_stmt["operationId"],
            "prevChainTip": ind_env["chainTip"],
            "receiptType": "RESOLUTION_RECEIPT",
            "reconciledDisposition": reconciled_disposition,
            "retrySafe": reconciled_disposition == "REFUTED",
            "targetProofHashHex": target_proof_hash_hex,
        }
        chain_tip = hashlib.sha256(
            bytes.fromhex(ind_env["chainTip"]) + encode_jcs(statement)
        ).hexdigest()
        envelope = {"chainTip": chain_tip, "statement": statement}
        sig_hex = signing_key.sign(encode_jcs(envelope)).hex()
        return {"envelope": envelope, "signatureHex": sig_hex}

    @staticmethod
    def verify_resolution_pair(
        indeterminate_receipt: Dict[str, Any],
        resolution_receipt: Dict[str, Any],
        public_key: Ed25519PublicKey,
    ) -> bool:
        try:
            ind_env = indeterminate_receipt["envelope"]
            res_env = resolution_receipt["envelope"]
            public_key.verify(
                bytes.fromhex(indeterminate_receipt["signatureHex"]),
                encode_jcs(ind_env),
            )
            public_key.verify(
                bytes.fromhex(resolution_receipt["signatureHex"]),
                encode_jcs(res_env),
            )
            ind_stmt = ind_env["statement"]
            res_stmt = res_env["statement"]
            if res_stmt.get("prevChainTip") != ind_env.get("chainTip"):
                return False
            if res_stmt.get("caid") != ind_stmt.get("caid"):
                return False
            if res_stmt.get("operationId") != ind_stmt.get("operationId"):
                return False
            expected_res_tip = hashlib.sha256(
                bytes.fromhex(ind_env["chainTip"]) + encode_jcs(res_stmt)
            ).hexdigest()
            return expected_res_tip == res_env.get("chainTip")
        except (InvalidSignature, ValueError, KeyError):
            return False


class LuMayGovernanceLayerMapper:
    """Category E: LuMay AI Framework 8-Layer Governance Taxonomy Mapper.

    Maps AEIB runtime artifacts strictly to the narrow subset of layers where
    AEIB produces machine-verifiable evidence (Layer 6: Controls & Guardrails,
    and Layer 7: Monitoring & Audit), while explicitly marking Layers 1-5 and
    Layer 8 as external organizational or model-plane responsibilities
    (including EU AI Act Article 4 AI Literacy human-side governance).
    """

    TAXONOMY_LAYERS: Tuple[Dict[str, str], ...] = (
        {
            "layerId": "L1_STRATEGY_AND_POLICY",
            "aeibCoverage": "OUT_OF_SCOPE_ORGANIZATIONAL",
            "boundaryNote": "Human sovereignty defines risk appetite and grant policies.",
        },
        {
            "layerId": "L2_REGULATORY_AND_COMPLIANCE",
            "aeibCoverage": "EVIDENCE_INPUT_ONLY",
            "boundaryNote": "AEIB emits DORA RT.01.01-RT.01.03 xBRL-CSV and EU AI Act Art. 12 logs; legal filing remains deployer responsibility.",
        },
        {
            "layerId": "L3_DATA_AND_KNOWLEDGE",
            "aeibCoverage": "EPOCH_FRESHNESS_METADATA_ONLY",
            "boundaryNote": "TemporalMemoryDigest checks epoch freshness; does not verify semantic truth of upstream corpora.",
        },
        {
            "layerId": "L4_MODELS_AND_PROMPTS",
            "aeibCoverage": "NOT_COVERED_MODEL_PLANE",
            "boundaryNote": "AEIB operates outside the model plane and does not inspect model weights or prompt text (OWASP ASI01).",
        },
        {
            "layerId": "L5_AGENTS_AND_ORCHESTRATION",
            "aeibCoverage": "BOUNDARY_INTERFACE_ONLY",
            "boundaryNote": "Agents propose candidate actions; orchestration does not hold raw target credentials.",
        },
        {
            "layerId": "L6_CONTROLS_AND_GUARDRAILS",
            "aeibCoverage": "COVERED_WIRE_INTERLOCK",
            "boundaryNote": "Station0AdmissionGate, Station1DispatchInterlock, and Station2EffectReconciler enforce pre-dispatch standing and EFFECT_INDETERMINATE latching.",
        },
        {
            "layerId": "L7_MONITORING_AND_AUDIT",
            "aeibCoverage": "COVERED_SIGNED_RECEIPT_LEDGER",
            "boundaryNote": "Station3ContinuousLedger emits RFC 8785 JCS + Ed25519 ContinuityReceipt hash chains verified offline by Java 21 and Python verifiers.",
        },
        {
            "layerId": "L8_HUMAN_OVERSIGHT_AND_AI_LITERACY",
            "aeibCoverage": "COMPLEMENTARY_HUMAN_OBLIGATION",
            "boundaryNote": "EU AI Act Art. 4 (AI Literacy, in force since 2 Feb 2025) and Art. 14 human review govern operator decisions when AEIB latches EFFECT_INDETERMINATE.",
        },
    )

    @classmethod
    def evaluate_taxonomy_coverage(cls, receipt_disposition: str) -> Dict[str, Any]:
        if receipt_disposition not in {
            "CONFIRMED",
            "REFUTED",
            "EFFECT_INDETERMINATE",
            "CONFLICT",
            "REJECTED",
        }:
            raise GovernanceHaltError(
                f"Unknown receipt disposition for taxonomy mapping: {receipt_disposition!r}"
            )
        covered = [
            layer["layerId"]
            for layer in cls.TAXONOMY_LAYERS
            if layer["aeibCoverage"].startswith("COVERED_")
        ]
        non_covered = [
            layer["layerId"]
            for layer in cls.TAXONOMY_LAYERS
            if not layer["aeibCoverage"].startswith("COVERED_")
        ]
        return {
            "coveredLayers": covered,
            "humanLiteracyRequiredOnIndeterminate": receipt_disposition
            in {"EFFECT_INDETERMINATE", "CONFLICT"},
            "nonCoveredOrExternalLayers": non_covered,
            "receiptDisposition": receipt_disposition,
            "totalLayers": len(cls.TAXONOMY_LAYERS),
        }


class ContextModeScriptInterfaceSandbox:
    """Category E: Clean-Room Apache-2.0 Script-as-Interface Bulk Data Isolation Boundary.

    Architectural reference pattern: decouples the agent's reasoning context window
    from bulk tool output payloads by reducing raw records inside an isolated
    deterministic filter boundary and returning only:
      1. A bounded, typed summary (`boundedSummary`) below `max_context_bytes`, and
      2. A cryptographic SHA-256 `rawPayloadCaid` over the RFC 8785 JCS bulk payload
         for audit traceability without polluting the model context window.

    License & Clean-Room Note: External 'Context Mode' tooling uses the non-OSI
    Elastic License 2.0 (ELv2). This class is a 100% clean-room Apache-2.0
    implementation of the general script-as-interface architectural pattern using
    only Python standard library and AEIB's RFC 8785 JCS canonicalizer.
    """

    LICENSE_SPDX = "Apache-2.0"
    CLEAN_ROOM_SEPARATION = "ARCHITECTURAL_PATTERN_ONLY_NO_ELV2_CODE"

    @classmethod
    def isolate_bulk_tool_output(
        cls,
        *,
        raw_records: List[Dict[str, Any]],
        filter_key: str,
        filter_value: Any,
        projected_fields: Tuple[str, ...],
        max_context_bytes: int = 2048,
    ) -> Dict[str, Any]:
        if max_context_bytes <= 0:
            raise GovernanceHaltError("max_context_bytes must be positive")

        raw_envelope = {"recordCount": len(raw_records), "records": raw_records}
        raw_bytes = encode_jcs(raw_envelope)
        raw_caid = hashlib.sha256(raw_bytes).hexdigest()

        matched_projections: List[Dict[str, Any]] = []
        for rec in raw_records:
            if rec.get(filter_key) == filter_value:
                projected = {k: rec[k] for k in projected_fields if k in rec}
                matched_projections.append(projected)

        summary_payload = {
            "cleanRoomLicense": cls.LICENSE_SPDX,
            "filterApplied": {filter_key: filter_value},
            "matchedCount": len(matched_projections),
            "matchedProjections": matched_projections,
            "rawPayloadByteLength": len(raw_bytes),
            "rawPayloadCaid": raw_caid,
            "totalInputRecords": len(raw_records),
        }
        summary_bytes = encode_jcs(summary_payload)
        if len(summary_bytes) > max_context_bytes:
            raise GovernanceHaltError(
                f"Projected summary ({len(summary_bytes)} B) exceeds context budget ({max_context_bytes} B)"
            )

        return {
            "boundedSummary": summary_payload,
            "contextBytesReturned": len(summary_bytes),
            "rawBytesIsolated": len(raw_bytes),
            "rawPayloadCaid": raw_caid,
        }


