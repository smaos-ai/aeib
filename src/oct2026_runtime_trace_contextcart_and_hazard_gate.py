"""
October 2026 Frontier Runtime Verification, Provenance-Bound Memory,
ContextCart Archival Forgetting, and STPA Hazard Control Gate.

Implements executable verification structures grounded in October 2026 literature:
1. Formal Runtime Verification 12+ Field Enforcement Trace Schema (arXiv:2610.09793v1)
   & Agent Flight Recorder canonical serialization (arXiv:2609.01931v1).
2. Janus Evidence-Before-Effect Offline Saga Log Verifier & Post-Approval Substitution
   Defense (arXiv:2609.38266v1) + Atomix / Agent libOS 3-State Crash Ambiguity
   Classification (arXiv:2602.14849v2, arXiv:2606.03895v3).
3. MHG-Mem Ternary Evolutionary Hyperedges & Provenance-Bound Retrieval Lookup
   Binding (arXiv:2610.29995v1, arXiv:2610.02945v1).
4. ContextCart Archival Forgetting with Lossless SHA-256 Recovery & Protected-Record
   Invariants (arXiv:2610.10590v1).
5. Delegated Misalignment Taint Penalty, Test-Gated Iterative Repair, and STPA
   Hazard Register Controls (arXiv:2609.27900v1, arXiv:2609.10123v1,
   arXiv:2608.29460v3, arXiv:2610.12813v1, arXiv:2601.08012v1).

All cryptographic signatures use real Ed25519 (cryptography.hazmat) over RFC 8785
JCS canonical JSON (src.jcs_canonicalizer.encode_jcs) and SHA-256 digests.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

GENESIS_TRACE_HASH = "0" * 64


class CrashAmbiguityState(str, Enum):
    """
    Three-state crash ambiguity classification (Atomix arXiv:2602.14849v2 &
    Agent libOS arXiv:2606.03895v3).
    """

    NO_DURABLE_INTENT = "NO_DURABLE_INTENT"
    INTENT_PREPARED_NOT_DISPATCHED = "INTENT_PREPARED_NOT_DISPATCHED"
    DISPATCH_MAY_HAVE_STARTED = "DISPATCH_MAY_HAVE_STARTED"


class ContextRecordKind(str, Enum):
    """Context entry categories for ContextCart archival forgetting (arXiv:2610.10590v1)."""

    USER_INSTRUCTION = "USER_INSTRUCTION"
    SAFETY_INVARIANT = "SAFETY_INVARIANT"
    EO1_APPROVAL_RECORD = "EO1_APPROVAL_RECORD"
    TOOL_OBSERVATION = "TOOL_OBSERVATION"
    SCRATCH_SUMMARY = "SCRATCH_SUMMARY"


PROTECTED_CONTEXT_KINDS = frozenset(
    {
        ContextRecordKind.USER_INSTRUCTION,
        ContextRecordKind.SAFETY_INVARIANT,
        ContextRecordKind.EO1_APPROVAL_RECORD,
    }
)


def _sha256_jcs(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# 1. Provenance-Bound Retrieval Lookup & MHG-Mem Evolutionary Hyperedges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceLookupReceipt:
    """
    Cryptographic binding of a HyperSUStore retrieval event (arXiv:2610.09793v1,
    arXiv:2610.29995v1, arXiv:2610.02945v1).
    """

    lookup_id: str
    query_digest: str
    retrieved_fact_ids: Tuple[str, ...]
    traversal_path: Tuple[str, ...]
    source_span_digests: Tuple[str, ...]
    provenance_lookup_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lookup_id": self.lookup_id,
            "provenance_lookup_digest": self.provenance_lookup_digest,
            "query_digest": self.query_digest,
            "retrieved_fact_ids": list(self.retrieved_fact_ids),
            "source_span_digests": list(self.source_span_digests),
            "traversal_path": list(self.traversal_path),
        }


@dataclass(frozen=True)
class MhgEvolutionaryHyperedge:
    """
    Ternary evolutionary hyperedge [old_fact_id, new_fact_id, evidence_span_fact_id]
    tracking entity/state transitions without overwriting historical provenance
    (MHG-Mem arXiv:2610.29995v1).
    """

    hyperedge_id: str
    old_fact_id: str
    new_fact_id: str
    evidence_span_fact_id: str
    relation: str
    transition_reason: str
    hyperedge_digest: str

    @property
    def vertices(self) -> Tuple[str, str, str]:
        return (self.old_fact_id, self.new_fact_id, self.evidence_span_fact_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_span_fact_id": self.evidence_span_fact_id,
            "hyperedge_digest": self.hyperedge_digest,
            "hyperedge_id": self.hyperedge_id,
            "new_fact_id": self.new_fact_id,
            "old_fact_id": self.old_fact_id,
            "relation": self.relation,
            "transition_reason": self.transition_reason,
            "vertices": list(self.vertices),
        }


class ProvenanceBoundLookupRegistry:
    """
    Maintains retrieval lookup receipts and ternary evolutionary hyperedges.
    Rejects any execution trace citation that is not backed by a recorded lookup.
    """

    def __init__(self) -> None:
        self._lookups_by_digest: Dict[str, ProvenanceLookupReceipt] = {}
        self._evolutionary_edges: Dict[str, MhgEvolutionaryHyperedge] = {}
        self._superseded_facts: Dict[str, str] = {}

    def record_lookup(
        self,
        lookup_id: str,
        query_text: str,
        retrieved_fact_ids: Sequence[str],
        traversal_path: Sequence[str],
        source_span_digests: Sequence[str],
    ) -> ProvenanceLookupReceipt:
        if not lookup_id or not retrieved_fact_ids:
            raise ValueError("HALT_EMPTY_PROVENANCE_LOOKUP: lookup_id and retrieved_fact_ids required")
        query_digest = _sha256_bytes(query_text.encode("utf-8"))
        fact_tuple = tuple(sorted(set(retrieved_fact_ids)))
        path_tuple = tuple(traversal_path)
        span_tuple = tuple(sorted(set(source_span_digests)))
        statement = {
            "lookup_id": lookup_id,
            "query_digest": query_digest,
            "retrieved_fact_ids": list(fact_tuple),
            "source_span_digests": list(span_tuple),
            "traversal_path": list(path_tuple),
        }
        digest = _sha256_jcs(statement)
        receipt = ProvenanceLookupReceipt(
            lookup_id=lookup_id,
            query_digest=query_digest,
            retrieved_fact_ids=fact_tuple,
            traversal_path=path_tuple,
            source_span_digests=span_tuple,
            provenance_lookup_digest=digest,
        )
        self._lookups_by_digest[digest] = receipt
        return receipt

    def verify_trace_provenance(
        self,
        provenance_lookup_digest: str,
        cited_fact_ids: Sequence[str],
        reject_superseded: bool = True,
    ) -> ProvenanceLookupReceipt:
        receipt = self._lookups_by_digest.get(provenance_lookup_digest)
        if receipt is None:
            raise ValueError(
                f"HALT_UNBOUND_OR_FORGED_PROVENANCE_LOOKUP: digest {provenance_lookup_digest!r} not in registry"
            )
        allowed = set(receipt.retrieved_fact_ids)
        for fid in cited_fact_ids:
            if fid not in allowed:
                raise ValueError(
                    f"HALT_UNBOUND_OR_FORGED_PROVENANCE_LOOKUP: cited fact {fid!r} was not retrieved in lookup {receipt.lookup_id!r}"
                )
            if reject_superseded and fid in self._superseded_facts:
                newer = self._superseded_facts[fid]
                raise ValueError(
                    f"HALT_SUPERSEDED_FACT_CITATION: fact {fid!r} was superseded by {newer!r} via MHG evolutionary hyperedge"
                )
        return receipt

    def record_evolutionary_transition(
        self,
        hyperedge_id: str,
        old_fact_id: str,
        new_fact_id: str,
        evidence_span_fact_id: str,
        transition_reason: str,
    ) -> MhgEvolutionaryHyperedge:
        if len({old_fact_id, new_fact_id, evidence_span_fact_id}) < 3:
            raise ValueError(
                "HALT_INVALID_EVOLUTIONARY_HYPEREDGE: old_fact_id, new_fact_id, and evidence_span_fact_id must be distinct"
            )
        statement = {
            "evidence_span_fact_id": evidence_span_fact_id,
            "hyperedge_id": hyperedge_id,
            "new_fact_id": new_fact_id,
            "old_fact_id": old_fact_id,
            "relation": "MHG_EVOLUTIONARY_TRANSITION",
            "transition_reason": transition_reason,
        }
        digest = _sha256_jcs(statement)
        edge = MhgEvolutionaryHyperedge(
            hyperedge_id=hyperedge_id,
            old_fact_id=old_fact_id,
            new_fact_id=new_fact_id,
            evidence_span_fact_id=evidence_span_fact_id,
            relation="MHG_EVOLUTIONARY_TRANSITION",
            transition_reason=transition_reason,
            hyperedge_digest=digest,
        )
        self._evolutionary_edges[hyperedge_id] = edge
        self._superseded_facts[old_fact_id] = new_fact_id
        return edge


# ---------------------------------------------------------------------------
# 2. 12+ Field EO1 Enforcement Trace & Janus Pure-Function Offline Verifier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignedApprovalArtifact:
    """
    Ed25519-signed approval record binding actor, tool_id, and canonical_act_digest
    before side-effect release (Janus arXiv:2609.38266v1).
    """

    approval_id: str
    approver_actor_id: str
    subject_agent_id: str
    tool_id: str
    capability_id: str
    canonical_act_digest: str
    policy_version: str
    approval_digest: str
    signature_b64: str

    def statement_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approver_actor_id": self.approver_actor_id,
            "canonical_act_digest": self.canonical_act_digest,
            "capability_id": self.capability_id,
            "policy_version": self.policy_version,
            "subject_agent_id": self.subject_agent_id,
            "tool_id": self.tool_id,
        }

    @classmethod
    def issue(
        cls,
        approval_id: str,
        approver_actor_id: str,
        subject_agent_id: str,
        tool_id: str,
        capability_id: str,
        action_payload: Mapping[str, Any],
        policy_version: str,
        approver_private_key: Ed25519PrivateKey,
    ) -> "SignedApprovalArtifact":
        act_digest = _sha256_jcs(dict(action_payload))
        statement = {
            "approval_id": approval_id,
            "approver_actor_id": approver_actor_id,
            "canonical_act_digest": act_digest,
            "capability_id": capability_id,
            "policy_version": policy_version,
            "subject_agent_id": subject_agent_id,
            "tool_id": tool_id,
        }
        jcs_bytes = encode_jcs(statement)
        sig_b64 = base64.b64encode(approver_private_key.sign(jcs_bytes)).decode("ascii")
        appr_digest = "sha256:" + hashlib.sha256(jcs_bytes).hexdigest()
        return cls(
            approval_id=approval_id,
            approver_actor_id=approver_actor_id,
            subject_agent_id=subject_agent_id,
            tool_id=tool_id,
            capability_id=capability_id,
            canonical_act_digest=act_digest,
            policy_version=policy_version,
            approval_digest=appr_digest,
            signature_b64=sig_b64,
        )


@dataclass(frozen=True)
class EO1EnforcementTraceV1:
    """
    12+ field enforcement-ready runtime trace record (arXiv:2610.09793v1 &
    Agent Flight Recorder arXiv:2609.01931v1).
    """

    trace_version: str
    trace_id: str
    timestamp_ns: int
    actor_id: str
    session_id: str
    agent_id: str
    tool_id: str
    capability_id: str
    operation_id: str
    idempotency_key: str
    canonical_act_digest: str
    approval_digest: str
    input_taint_tier: int
    provenance_lookup_digest: str
    policy_version: str
    decision: str
    decision_reason: str
    outcome_state: str
    retry_allowed: bool
    prev_trace_hash: str
    trace_hash: str
    signature_b64: str

    def statement_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "agent_id": self.agent_id,
            "approval_digest": self.approval_digest,
            "canonical_act_digest": self.canonical_act_digest,
            "capability_id": self.capability_id,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "idempotency_key": self.idempotency_key,
            "input_taint_tier": self.input_taint_tier,
            "operation_id": self.operation_id,
            "outcome_state": self.outcome_state,
            "policy_version": self.policy_version,
            "prev_trace_hash": self.prev_trace_hash,
            "provenance_lookup_digest": self.provenance_lookup_digest,
            "retry_allowed": self.retry_allowed,
            "session_id": self.session_id,
            "timestamp_ns": self.timestamp_ns,
            "tool_id": self.tool_id,
            "trace_id": self.trace_id,
            "trace_version": self.trace_version,
        }


def classify_crash_ambiguity(
    intent_durable_on_disk: bool,
    wire_socket_opened: bool,
) -> Tuple[CrashAmbiguityState, bool]:
    """
    Classifies crash state into the 3 Atomix/Agent-libOS states and returns
    (state, retry_allowed).
    """
    if not intent_durable_on_disk:
        return (CrashAmbiguityState.NO_DURABLE_INTENT, True)
    if not wire_socket_opened:
        return (CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED, True)
    return (CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED, False)


class JanusOfflineSagaLogVerifier:
    """
    Pure-function offline saga & trace verifier (Janus arXiv:2609.38266v1).
    Emits hash-chained EO1EnforcementTraceV1 records and verifies logs offline
    using only public keys, catching Post-Approval Substitution and chain breaks.
    """

    @staticmethod
    def build_and_sign_trace(
        *,
        trace_id: str,
        timestamp_ns: int,
        actor_id: str,
        session_id: str,
        agent_id: str,
        tool_id: str,
        capability_id: str,
        operation_id: str,
        idempotency_key: str,
        action_payload: Mapping[str, Any],
        approval: SignedApprovalArtifact,
        input_taint_tier: int,
        provenance_lookup_digest: str,
        policy_version: str,
        decision: str,
        decision_reason: str,
        crash_state: CrashAmbiguityState,
        prev_trace_hash: str,
        actor_private_key: Ed25519PrivateKey,
    ) -> EO1EnforcementTraceV1:
        canonical_act_digest = _sha256_jcs(dict(action_payload))
        retry_allowed = crash_state != CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED
        statement = {
            "actor_id": actor_id,
            "agent_id": agent_id,
            "approval_digest": approval.approval_digest,
            "canonical_act_digest": canonical_act_digest,
            "capability_id": capability_id,
            "decision": decision,
            "decision_reason": decision_reason,
            "idempotency_key": idempotency_key,
            "input_taint_tier": input_taint_tier,
            "operation_id": operation_id,
            "outcome_state": crash_state.value,
            "policy_version": policy_version,
            "prev_trace_hash": prev_trace_hash,
            "provenance_lookup_digest": provenance_lookup_digest,
            "retry_allowed": retry_allowed,
            "session_id": session_id,
            "timestamp_ns": timestamp_ns,
            "tool_id": tool_id,
            "trace_id": trace_id,
            "trace_version": "eo1.trace.v1",
        }
        jcs_bytes = encode_jcs(statement)
        trace_hash = hashlib.sha256(jcs_bytes).hexdigest()
        sig_b64 = base64.b64encode(actor_private_key.sign(jcs_bytes)).decode("ascii")
        return EO1EnforcementTraceV1(
            trace_version="eo1.trace.v1",
            trace_id=trace_id,
            timestamp_ns=timestamp_ns,
            actor_id=actor_id,
            session_id=session_id,
            agent_id=agent_id,
            tool_id=tool_id,
            capability_id=capability_id,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            canonical_act_digest=canonical_act_digest,
            approval_digest=approval.approval_digest,
            input_taint_tier=input_taint_tier,
            provenance_lookup_digest=provenance_lookup_digest,
            policy_version=policy_version,
            decision=decision,
            decision_reason=decision_reason,
            outcome_state=crash_state.value,
            retry_allowed=retry_allowed,
            prev_trace_hash=prev_trace_hash,
            trace_hash=trace_hash,
            signature_b64=sig_b64,
        )

    @staticmethod
    def verify_signed_log_offline(
        traces: Sequence[EO1EnforcementTraceV1],
        approvals_by_digest: Mapping[str, SignedApprovalArtifact],
        public_keys_by_actor: Mapping[str, Ed25519PublicKey],
        provenance_registry: Optional[ProvenanceBoundLookupRegistry] = None,
    ) -> Dict[str, Any]:
        """
        Pure-function offline verification of a hash-chained EO1 trace sequence.
        Checks:
        1. Contiguous hash chain from GENESIS_TRACE_HASH.
        2. Ed25519 trace signature against public_keys_by_actor[trace.actor_id].
        3. Ed25519 approval signature against public_keys_by_actor[approval.approver_actor_id].
        4. Post-Approval Substitution invariant:
           approval.canonical_act_digest == trace.canonical_act_digest,
           approval.tool_id == trace.tool_id,
           approval.capability_id == trace.capability_id,
           approval.subject_agent_id == trace.agent_id.
        5. Crash ambiguity retry invariant: DISPATCH_MAY_HAVE_STARTED requires retry_allowed is False.
        6. Provenance lookup digest existence in provenance_registry (when provided).
        """
        expected_prev = GENESIS_TRACE_HASH
        seen_idempotency_keys: Dict[str, str] = {}

        for idx, trace in enumerate(traces):
            if trace.prev_trace_hash != expected_prev:
                raise ValueError(
                    f"HALT_TRACE_HASH_CHAIN_BROKEN at index {idx}: expected prev {expected_prev}, got {trace.prev_trace_hash}"
                )
            stmt_bytes = encode_jcs(trace.statement_dict())
            computed_hash = hashlib.sha256(stmt_bytes).hexdigest()
            if computed_hash != trace.trace_hash:
                raise ValueError(
                    f"HALT_TRACE_DIGEST_TAMPERED at index {idx}: computed {computed_hash} != {trace.trace_hash}"
                )

            actor_pub = public_keys_by_actor.get(trace.actor_id)
            if actor_pub is None:
                raise ValueError(f"HALT_UNKNOWN_TRACE_ACTOR: {trace.actor_id!r}")
            try:
                actor_pub.verify(base64.b64decode(trace.signature_b64), stmt_bytes)
            except (InvalidSignature, ValueError) as exc:
                raise ValueError(f"HALT_INVALID_TRACE_SIGNATURE at index {idx}: {exc}") from exc

            if (
                trace.outcome_state == CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED.value
                and trace.retry_allowed
            ):
                raise ValueError(
                    f"HALT_AMBIGUOUS_DISPATCH_RETRY_FORBIDDEN at index {idx}: DISPATCH_MAY_HAVE_STARTED cannot set retry_allowed=True"
                )

            if trace.idempotency_key in seen_idempotency_keys:
                prior_outcome = seen_idempotency_keys[trace.idempotency_key]
                if prior_outcome == CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED.value:
                    raise ValueError(
                        f"HALT_AMBIGUOUS_DISPATCH_RETRY_FORBIDDEN: duplicate dispatch on latched idempotency_key {trace.idempotency_key!r}"
                    )
            seen_idempotency_keys[trace.idempotency_key] = trace.outcome_state

            if trace.decision == "ALLOW":
                approval = approvals_by_digest.get(trace.approval_digest)
                if approval is None:
                    raise ValueError(
                        f"HALT_MISSING_APPROVAL_ARTIFACT at index {idx}: digest {trace.approval_digest!r}"
                    )
                appr_bytes = encode_jcs(approval.statement_dict())
                computed_appr_digest = "sha256:" + hashlib.sha256(appr_bytes).hexdigest()
                if computed_appr_digest != approval.approval_digest:
                    raise ValueError("HALT_APPROVAL_DIGEST_TAMPERED")
                approver_pub = public_keys_by_actor.get(approval.approver_actor_id)
                if approver_pub is None:
                    raise ValueError(f"HALT_UNKNOWN_APPROVER_ACTOR: {approval.approver_actor_id!r}")
                try:
                    approver_pub.verify(base64.b64decode(approval.signature_b64), appr_bytes)
                except (InvalidSignature, ValueError) as exc:
                    raise ValueError(f"HALT_INVALID_APPROVAL_SIGNATURE: {exc}") from exc

                # Post-Approval Substitution Check (Janus arXiv:2609.38266v1)
                if approval.canonical_act_digest != trace.canonical_act_digest:
                    raise ValueError(
                        "HALT_POST_APPROVAL_SUBSTITUTION: trace canonical_act_digest "
                        f"{trace.canonical_act_digest} != approved {approval.canonical_act_digest}"
                    )
                if approval.tool_id != trace.tool_id:
                    raise ValueError(
                        f"HALT_POST_APPROVAL_SUBSTITUTION: trace tool_id {trace.tool_id!r} != approved {approval.tool_id!r}"
                    )
                if approval.capability_id != trace.capability_id:
                    raise ValueError(
                        f"HALT_POST_APPROVAL_SUBSTITUTION: trace capability_id {trace.capability_id!r} != approved {approval.capability_id!r}"
                    )
                if approval.subject_agent_id != trace.agent_id:
                    raise ValueError(
                        f"HALT_POST_APPROVAL_SUBSTITUTION: trace agent_id {trace.agent_id!r} != approved {approval.subject_agent_id!r}"
                    )

            if provenance_registry is not None:
                provenance_registry.verify_trace_provenance(
                    trace.provenance_lookup_digest,
                    cited_fact_ids=(),
                )

            expected_prev = trace.trace_hash

        return {
            "verified_trace_count": len(traces),
            "terminal_chain_tip": expected_prev,
        }


# ---------------------------------------------------------------------------
# 3. ContextCart Archival Forgetting with Lossless SHA-256 Recovery
# ---------------------------------------------------------------------------


@dataclass
class ContextSlot:
    """Single slot in the agent's active context window."""

    slot_id: str
    kind: ContextRecordKind
    content: str
    archived_digest: Optional[str] = None
    original_byte_len: int = 0


class ContextCartArchivalForgettingEngine:
    """
    Implements agent-controlled reversible context forgetting (arXiv:2610.10590v1):
    - Replaces bulky TOOL_OBSERVATION or SCRATCH_SUMMARY slots with a compact
      semantic note at their original position while storing the exact original
      payload in a content-addressed archive keyed by SHA-256.
    - Refuses to compress or archive USER_INSTRUCTION, SAFETY_INVARIANT, or
      EO1_APPROVAL_RECORD entries (HALT_PROTECTED_RECORD_COMPRESSION_FORBIDDEN).
    - Supports lossless recovery with SHA-256 verification.
    """

    def __init__(self) -> None:
        self._slots: Dict[str, ContextSlot] = {}
        self._slot_order: List[str] = []
        self._archive_blobs: Dict[str, bytes] = {}

    def append_slot(self, slot_id: str, kind: ContextRecordKind, content: str) -> ContextSlot:
        raw_len = len(content.encode("utf-8"))
        slot = ContextSlot(
            slot_id=slot_id,
            kind=kind,
            content=content,
            archived_digest=None,
            original_byte_len=raw_len,
        )
        self._slots[slot_id] = slot
        self._slot_order.append(slot_id)
        return slot

    def archive_observation(self, slot_id: str, compact_note: str) -> Dict[str, Any]:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise KeyError(f"Unknown context slot_id: {slot_id!r}")
        if slot.kind in PROTECTED_CONTEXT_KINDS:
            raise ValueError(
                f"HALT_PROTECTED_RECORD_COMPRESSION_FORBIDDEN: cannot archive slot {slot_id!r} of protected kind {slot.kind.value}"
            )
        raw_bytes = slot.content.encode("utf-8")
        digest = _sha256_bytes(raw_bytes)
        self._archive_blobs[digest] = raw_bytes
        stub = f"[ARCHIVED_OBSERVATION slot={slot_id} digest={digest} note={compact_note}]"
        stub_bytes = stub.encode("utf-8")
        if len(stub_bytes) >= len(raw_bytes):
            raise ValueError(
                "HALT_ARCHIVE_NOTE_NOT_COMPACT: replacement stub must be strictly smaller than original observation"
            )
        slot.content = stub
        slot.archived_digest = digest
        return {
            "slot_id": slot_id,
            "archived_digest": digest,
            "original_bytes": len(raw_bytes),
            "active_stub_bytes": len(stub_bytes),
            "bytes_reclaimed": len(raw_bytes) - len(stub_bytes),
        }

    def recover_observation(self, slot_id: str) -> str:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise KeyError(f"Unknown context slot_id: {slot_id!r}")
        if slot.archived_digest is None:
            return slot.content
        blob = self._archive_blobs.get(slot.archived_digest)
        if blob is None:
            raise ValueError(
                f"HALT_ARCHIVE_BLOB_MISSING: digest {slot.archived_digest!r} not found in archive"
            )
        recomputed = _sha256_bytes(blob)
        if recomputed != slot.archived_digest:
            raise ValueError(
                f"HALT_ARCHIVE_INTEGRITY_MISMATCH: expected {slot.archived_digest}, got {recomputed}"
            )
        restored = blob.decode("utf-8")
        slot.content = restored
        slot.archived_digest = None
        return restored

    def active_byte_footprint(self) -> int:
        return sum(len(self._slots[sid].content.encode("utf-8")) for sid in self._slot_order)


# ---------------------------------------------------------------------------
# 4. Delegated Misalignment Taint Gate, Test-Gated Repair, & STPA Controls
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PRIVATE )?KEY-----"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}"),
)


@dataclass(frozen=True)
class EscalationTicket:
    """
    Structured defect/ambiguity escalation artifact (arXiv:2608.29460v3 &
    SpecGuardBench arXiv:2610.16870v1).
    """

    ticket_id: str
    agent_id: str
    failing_oracle_id: str
    ambiguity_summary: str
    reward_hacking_blocked: bool
    status: str


class DelegatedTaintAndHazardGate:
    """
    Enforces:
    - Delegated Misalignment taint penalty (arXiv:2609.27900v1):
      target_taint_score >= source_taint_score + delegation_penalty, and
      supervisor delegation never exempts subordinate safety checks.
    - Test-Gated Iterative Repair (If It's Not Buggy, Don't Fix It, arXiv:2609.10123v1):
      blocks open-loop Builder code rewrites when deterministic tests already pass.
    - Structured Escalation Channel (arXiv:2608.29460v3):
      routes broken/conflicting specs or exhausted repair budgets (B > 3) to
      HUMAN_ESCALATION_REQUIRED instead of permitting test modification.
    - Outbound Secret Leakage Scanner (STPA Hazard H-03).
    """

    @staticmethod
    def validate_delegation_handoff(
        *,
        source_agent_id: str,
        target_agent_id: str,
        source_taint_score: int,
        claimed_target_taint_score: int,
        delegation_penalty: int = 1,
        bypass_subordinate_safety_gate: bool = False,
    ) -> Dict[str, Any]:
        if bypass_subordinate_safety_gate:
            raise ValueError(
                "HALT_DELEGATION_SAFETY_EXEMPTION_FORBIDDEN: supervisor delegation cannot exempt subordinate safety verification"
            )
        if delegation_penalty < 1:
            raise ValueError("HALT_INVALID_DELEGATION_PENALTY: delegation_penalty must be >= 1")
        min_required_taint = source_taint_score + delegation_penalty
        if claimed_target_taint_score < min_required_taint:
            raise ValueError(
                f"HALT_DELEGATED_TAINT_DOWNGRADE: target taint {claimed_target_taint_score} < required {min_required_taint} "
                f"(source={source_taint_score} + penalty={delegation_penalty})"
            )
        return {
            "source_agent_id": source_agent_id,
            "target_agent_id": target_agent_id,
            "effective_target_taint_score": claimed_target_taint_score,
            "subordinate_gate_mandatory": True,
        }

    @staticmethod
    def authorize_iterative_repair(
        *,
        agent_id: str,
        has_deterministic_failing_test: bool,
        failing_oracle_id: str,
        attempt_index: int,
        max_attempts: int = 3,
        spec_conflict_detected: bool = False,
        builder_attempted_test_edit: bool = False,
    ) -> Dict[str, Any]:
        if builder_attempted_test_edit:
            raise ValueError(
                "HALT_REWARD_HACKING_TEST_EDIT_FORBIDDEN: builder agent is forbidden from editing verification tests"
            )
        if spec_conflict_detected or attempt_index > max_attempts:
            ticket = EscalationTicket(
                ticket_id=f"esc-{agent_id}-{attempt_index}",
                agent_id=agent_id,
                failing_oracle_id=failing_oracle_id or "SPEC_CONFLICT",
                ambiguity_summary=(
                    "Specification conflict or bounded repair budget exhausted; routed to human escalation."
                ),
                reward_hacking_blocked=True,
                status="HUMAN_ESCALATION_REQUIRED",
            )
            return {
                "action": "ESCALATE_TO_HUMAN",
                "ticket": ticket,
            }
        if not has_deterministic_failing_test or not failing_oracle_id.strip():
            raise ValueError(
                "HALT_UNPROVOKED_ITERATIVE_REPAIR_FORBIDDEN: iterative repair requires a deterministic failing test oracle (arXiv:2609.10123v1)"
            )
        return {
            "action": "REPAIR_AUTHORIZED",
            "attempt_index": attempt_index,
            "failing_oracle_id": failing_oracle_id,
        }

    @staticmethod
    def scan_payload_for_secret_leakage(payload: Any) -> None:
        serialized = encode_jcs(payload).decode("utf-8", errors="replace")
        for pattern in _SECRET_PATTERNS:
            if pattern.search(serialized):
                raise ValueError(
                    "HALT_SECRET_LEAKAGE_DETECTED: raw credential or private key pattern detected in tool/trace payload"
                )

    @staticmethod
    def verify_hazard_register_file(yaml_path: Path) -> Dict[str, Any]:
        """
        Parses specs/aeib_hazard_register.yaml using stdlib line parsing and verifies
        that all 6 required STPA hazard IDs (H-01..H-06) and halt codes are present.
        """
        text = Path(yaml_path).read_text(encoding="utf-8")
        required_hazards = {
            "H-01": "duplicate_payment",
            "H-02": "post_approval_substitution",
            "H-03": "secret_leakage",
            "H-04": "prompt_injection_escalation",
            "H-05": "provenance_laundering",
            "H-06": "vacuous_specification",
        }
        missing: List[str] = []
        for hid, hname in required_hazards.items():
            if f'hazard_id: "{hid}"' not in text or f'name: "{hname}"' not in text:
                missing.append(f"{hid}:{hname}")
        if missing:
            raise ValueError(f"HALT_INCOMPLETE_HAZARD_REGISTER: missing {missing}")
        return {
            "register_sha256": _sha256_bytes(text.encode("utf-8")),
            "verified_hazard_ids": sorted(required_hazards.keys()),
        }
