#!/usr/bin/env python3
# File: src/epistemic_core.py
"""
epistemic-core (aeib-kernel): Bose-Einstein Cognitive Synthesizer & Phase Transition Scheduler.

Models multi-agent epistemic discovery ("Bose Engine") and ontic execution adjudication
("Einstein Judge") via absorbing-state phase transitions (Zheng et al., arXiv:2609.38327)
and budgeted multi-agent synergy thresholds (Liu et al., arXiv:2601.17311).

Core Axiom: Models propose. Governance decides. Evidence survives.

Hardened Invariants (fixing naive wrapper blind spots):
1. All integer basis-point arithmetic (0 floats) for deterministic cross-platform JCS hashing.
2. Complete Witness Registry: Both non-conflict Bose calculations and conflict witnesses are
   cryptographically verified and indexed; fabricated or omitted witness IDs fail closed
   (HALT_MISSING_BOSE_EPISTEMIC_WITNESS / HALT_UNVERIFIED_OR_FABRICATED_WITNESS).
3. Provenance Entropy Filter: Witnesses tagged AI_GENERATED_UNVERIFIED are barred from
   authorizing ontic state mutations (HALT_SYNTHETIC_OVERLOAD_UNVERIFIED_PROVENANCE).
4. Critical Cognitive Density Phase Transition (rho >= rho_c): Automatically collapses
   high-entropy multi-agent exploration into HALT_ONTIC_EXECUTION until supervisor-signed
   mitigations condense the state into CONDENSED_LOCKED.
5. Disjoint Write-Set Enforcement: Concurrent ontic proposals with overlapping target
   resources fail closed (HALT_DISJOINT_WRITESET_COLLISION).
"""
import base64
import enum
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


def _check_no_floats(val: Any) -> None:
    if isinstance(val, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_USE_INTEGER_BASIS_POINTS")
    if isinstance(val, dict):
        for v in val.values():
            _check_no_floats(v)
    elif isinstance(val, (list, tuple)):
        for v in val:
            _check_no_floats(v)


def canonical_jcs(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) encoding with integer-only enforcement."""
    _check_no_floats(obj)
    return _reference_encode_jcs(obj)


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class PhaseState(enum.Enum):
    EXPLORATION = "ERGODIC_EXPLORATION"        # High-entropy parallel probing (T > Tc)
    PHASE_TRANSITION = "CRITICAL_COLLAPSE"     # Intermediate unresolved conflict state (0 < rho < rho_c)
    CONDENSED_LOCKED = "CONDENSED_LOCKED"      # Zero-entropy condensed execution state (rho == 0, T < Tc)
    HALTED = "HALT_ONTIC_EXECUTION"            # Absorbing halt state when conflict density rho >= rho_c


ALLOWED_PROVENANCE_TAGS = frozenset({
    "DETERMINISTIC_PROBE",
    "HUMAN_VERIFIED",
    "FORMAL_COUNTEREXAMPLE_CHECK",
})


@dataclass(frozen=True)
class EpistemicWitness:
    """
    Immutable epistemic observation receipt produced by the Bose Engine.
    Uses integer basis points (0..10000) for severity_bp to avoid IEEE 754 float drift.
    """
    witness_id: str
    agent_id: str
    action_type: str  # "PRIOR_ART_SEARCH" | "HYPOTHESIS_DROP_PROBE" | "FORMAL_VERIFICATION"
    target_resource: str
    evidence_payload_hash: str
    provenance_tag: str  # "DETERMINISTIC_PROBE" | "HUMAN_VERIFIED" | "AI_GENERATED_UNVERIFIED"
    is_conflict: bool
    severity_bp: int  # Basis points: 10000 = 1.0000
    signature_b64: str = ""

    def canonical_signing_bytes(self) -> bytes:
        if self.severity_bp < 0 or self.severity_bp > 10000:
            raise ValueError("ERR_SEVERITY_BP_OUT_OF_RANGE")
        return canonical_jcs({
            "action_type": self.action_type,
            "agent_id": self.agent_id,
            "evidence_payload_hash": self.evidence_payload_hash,
            "is_conflict": self.is_conflict,
            "provenance_tag": self.provenance_tag,
            "severity_bp": self.severity_bp,
            "target_resource": self.target_resource,
            "witness_id": self.witness_id,
        })


@dataclass(frozen=True)
class OnticActionProposal:
    """
    Macroscopic state-mutating action proposal evaluated by the Einstein Judge.
    Must bind explicit Bose EpistemicWitness IDs and declare its write-set resources.
    """
    operation_id: str
    proposer_agent_id: str
    action_class: str
    target_resource: str
    write_set_resources: Tuple[str, ...]
    amount_minor: int
    required_witness_ids: Tuple[str, ...]


class NonDilutableConflictRegister:
    """
    Append-only register storing all verified Bose EpistemicWitnesses and tracking
    unresolved conflicts against an active token/probe budget denominator.
    """

    def __init__(
        self,
        probe_signing_pubkey: Optional[Ed25519PublicKey] = None,
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> None:
        self._all_witnesses: Dict[str, EpistemicWitness] = {}
        self._conflicts: Dict[str, EpistemicWitness] = {}
        self._resolved: Dict[str, str] = {}  # witness_id -> resolution_digest
        self.probe_signing_pubkey = probe_signing_pubkey
        self.supervisor_pubkey = supervisor_pubkey

    def ingest(self, witness: EpistemicWitness) -> Tuple[bool, str]:
        if witness.severity_bp < 0 or witness.severity_bp > 10000:
            return False, "ERR_INVALID_SEVERITY_BP"

        if self.probe_signing_pubkey is not None:
            if not witness.signature_b64:
                return False, "HALT_UNSIGNED_BOSE_WITNESS"
            try:
                sig = base64.b64decode(witness.signature_b64, validate=True)
                self.probe_signing_pubkey.verify(sig, witness.canonical_signing_bytes())
            except Exception:
                return False, "HALT_INVALID_BOSE_WITNESS_SIGNATURE"

        self._all_witnesses[witness.witness_id] = witness
        if witness.is_conflict:
            self._conflicts[witness.witness_id] = witness
        return True, "WITNESS_INGESTED"

    def resolve(
        self,
        witness_id: str,
        resolution_proof: str,
        supervisor_sig_b64: Optional[str] = None,
    ) -> bool:
        if witness_id not in self._conflicts:
            return False
        if len(resolution_proof.strip()) < 10:
            return False

        payload = canonical_jcs({
            "resolution_proof": resolution_proof.strip(),
            "witness_id": witness_id,
        })
        if self.supervisor_pubkey is not None:
            if not supervisor_sig_b64:
                return False
            try:
                sig = base64.b64decode(supervisor_sig_b64, validate=True)
                self.supervisor_pubkey.verify(sig, payload)
            except Exception:
                return False

        self._resolved[witness_id] = sha256_hex(payload)
        return True

    def get_witness(self, witness_id: str) -> Optional[EpistemicWitness]:
        return self._all_witnesses.get(witness_id)

    def is_conflict_unresolved(self, witness_id: str) -> bool:
        return witness_id in self._conflicts and witness_id not in self._resolved

    @property
    def unresolved_severity_bp(self) -> int:
        return sum(
            w.severity_bp
            for w_id, w in self._conflicts.items()
            if w_id not in self._resolved
        )

    @property
    def unresolved_count(self) -> int:
        return sum(1 for w_id in self._conflicts if w_id not in self._resolved)

    @property
    def total_witness_count(self) -> int:
        return len(self._all_witnesses)


class BoseEinsteinCognitiveSynthesizer:
    """
    BEC Cognitive Synthesizer:
    Governs the phase transition from high-entropy multi-agent exploration (T > Tc)
    to low-entropy condensed execution (T < Tc), enforcing Bose-Einstein provenance
    attribution and disjoint write-sets.
    """

    def __init__(
        self,
        conflict_density_threshold_bp: int = 7500,  # 0.7500 in basis points
        probe_signing_pubkey: Optional[Ed25519PublicKey] = None,
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> None:
        self.register = NonDilutableConflictRegister(
            probe_signing_pubkey=probe_signing_pubkey,
            supervisor_pubkey=supervisor_pubkey,
        )
        self.threshold_bp = conflict_density_threshold_bp
        self.state = PhaseState.EXPLORATION
        self.active_locked_resources: Set[str] = set()
        self.committed_operations: List[Dict[str, Any]] = []

    def evaluate_phase_transition(self) -> PhaseState:
        unresolved_bp = self.register.unresolved_severity_bp
        if unresolved_bp >= self.threshold_bp:
            self.state = PhaseState.HALTED
        elif unresolved_bp > 0:
            self.state = PhaseState.PHASE_TRANSITION
        elif self.register.total_witness_count > 0:
            self.state = PhaseState.CONDENSED_LOCKED
        else:
            self.state = PhaseState.EXPLORATION
        return self.state

    def adjudicate_ontic_proposal(
        self, proposal: OnticActionProposal
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Einstein Judge Adjudication:
        1. Evaluates macroscopic phase state (blocks if HALTED or PHASE_TRANSITION).
        2. Requires >= 1 explicit Bose EpistemicWitness ID.
        3. Verifies every witness exists, is resolved, and has verified provenance.
        4. Enforces disjoint write-set isolation across concurrent proposals.
        """
        current_state = self.evaluate_phase_transition()

        if current_state == PhaseState.HALTED:
            return (
                False,
                "HALT_UNRESOLVED_COGNITIVE_CONFLICTS_PRESENT",
                {"phase_state": current_state.value, "unresolved_bp": self.register.unresolved_severity_bp},
            )

        if not proposal.required_witness_ids:
            return (
                False,
                "HALT_MISSING_BOSE_EPISTEMIC_WITNESS",
                {"phase_state": current_state.value},
            )

        verified_witness_digests: List[str] = []
        for w_id in proposal.required_witness_ids:
            witness = self.register.get_witness(w_id)
            if witness is None:
                return (
                    False,
                    f"HALT_UNVERIFIED_OR_FABRICATED_WITNESS:{w_id}",
                    {"phase_state": current_state.value},
                )
            if self.register.is_conflict_unresolved(w_id):
                return (
                    False,
                    f"HALT_WITNESS_{w_id}_REMAINS_UNRESOLVED",
                    {"phase_state": current_state.value},
                )
            if witness.provenance_tag not in ALLOWED_PROVENANCE_TAGS:
                return (
                    False,
                    "HALT_SYNTHETIC_OVERLOAD_UNVERIFIED_PROVENANCE",
                    {"witness_id": w_id, "provenance_tag": witness.provenance_tag},
                )
            verified_witness_digests.append(witness.evidence_payload_hash)

        if current_state == PhaseState.PHASE_TRANSITION:
            return (
                False,
                "HALT_GLOBAL_PHASE_TRANSITION_UNRESOLVED_CONFLICTS",
                {"phase_state": current_state.value, "unresolved_bp": self.register.unresolved_severity_bp},
            )

        # Disjoint write-set check: Write(A_i) intersect Write(A_j) == empty
        write_set = set(proposal.write_set_resources) | {proposal.target_resource}
        overlap = self.active_locked_resources.intersection(write_set)
        if overlap:
            return (
                False,
                "HALT_DISJOINT_WRITESET_COLLISION",
                {"overlapping_resources": sorted(overlap)},
            )

        self.active_locked_resources.update(write_set)
        attribution_receipt = {
            "operation_id": proposal.operation_id,
            "proposer_agent_id": proposal.proposer_agent_id,
            "bose_witness_ids": list(proposal.required_witness_ids),
            "bose_evidence_digests": verified_witness_digests,
            "phase_state": PhaseState.CONDENSED_LOCKED.value,
            "write_set": sorted(write_set),
            "amount_minor": proposal.amount_minor,
        }
        attribution_receipt["attribution_digest"] = sha256_hex(
            canonical_jcs(attribution_receipt)
        )
        self.committed_operations.append(attribution_receipt)
        return True, "ONTIC_EXECUTION_AUTHORIZED_CONDENSED_STATE", attribution_receipt


def simulate_1000_agent_phase_transition(num_agents: int = 1000) -> Dict[str, Any]:
    """
    Deterministic simulation of 1,000 autonomous agents executing parallel Bose
    epistemic probes and Einstein ontic proposals:
    - Phase 1: 1,000 agents emit read-only probes; 15 agents uncover hypothesis-drop
      or prior-art conflicts (each 1,000 bp = 0.10 severity, total 15,000 bp >= 7,500 bp threshold).
    - Phase 2: Synthesizer undergoes an absorbing-state phase transition into HALT_ONTIC_EXECUTION,
      blocking premature ontic mutations across the swarm.
    - Phase 3: Supervisor signs Ed25519 conflict resolutions for the 15 conflicts.
    - Phase 4: Swarm condenses into CONDENSED_LOCKED; disjoint write-sets allow non-overlapping
      proposals while blocking overlapping resource collisions.
    """
    probe_priv = Ed25519PrivateKey.generate()
    sup_priv = Ed25519PrivateKey.generate()

    synthesizer = BoseEinsteinCognitiveSynthesizer(
        conflict_density_threshold_bp=7500,
        probe_signing_pubkey=probe_priv.public_key(),
        supervisor_pubkey=sup_priv.public_key(),
    )

    conflict_ids: List[str] = []
    for i in range(num_agents):
        is_conflict = (i % 67 == 0)  # 15 conflict witnesses across 1,000 agents
        severity_bp = 1000 if is_conflict else 0
        w_id = f"bose-witness-{i:04d}"
        unsigned = EpistemicWitness(
            witness_id=w_id,
            agent_id=f"agent-{i:04d}",
            action_type="HYPOTHESIS_DROP_PROBE" if is_conflict else "FORMAL_VERIFICATION",
            target_resource=f"resource://shard-{i:04d}",
            evidence_payload_hash=sha256_hex(canonical_jcs({"agent": i, "conflict": is_conflict})),
            provenance_tag="DETERMINISTIC_PROBE",
            is_conflict=is_conflict,
            severity_bp=severity_bp,
        )
        sig_b64 = base64.b64encode(
            probe_priv.sign(unsigned.canonical_signing_bytes())
        ).decode("ascii")
        signed_w = EpistemicWitness(
            witness_id=unsigned.witness_id,
            agent_id=unsigned.agent_id,
            action_type=unsigned.action_type,
            target_resource=unsigned.target_resource,
            evidence_payload_hash=unsigned.evidence_payload_hash,
            provenance_tag=unsigned.provenance_tag,
            is_conflict=unsigned.is_conflict,
            severity_bp=unsigned.severity_bp,
            signature_b64=sig_b64,
        )
        ok, code = synthesizer.register.ingest(signed_w)
        assert ok is True, f"Failed ingest: {code}"
        if is_conflict:
            conflict_ids.append(w_id)

    # Check phase collapse into HALTED due to critical conflict density (15,000 bp >= 7,500 bp)
    state_during_conflicts = synthesizer.evaluate_phase_transition()
    assert state_during_conflicts == PhaseState.HALTED

    # Any ontic proposal during HALTED state is immediately rejected
    early_proposal = OnticActionProposal(
        operation_id="op-early-0001",
        proposer_agent_id="agent-0001",
        action_class="MUTATE_SHARD",
        target_resource="resource://shard-0001",
        write_set_resources=("resource://shard-0001",),
        amount_minor=500_00,
        required_witness_ids=("bose-witness-0001",),
    )
    allowed_early, reason_early, _ = synthesizer.adjudicate_ontic_proposal(early_proposal)
    assert allowed_early is False
    assert reason_early == "HALT_UNRESOLVED_COGNITIVE_CONFLICTS_PRESENT"

    # Supervisor resolves all 15 conflicts with Ed25519 signatures
    for c_id in conflict_ids:
        proof_text = f"Mitigated conflict {c_id} via deterministic TCC latch."
        sig = base64.b64encode(
            sup_priv.sign(canonical_jcs({"resolution_proof": proof_text, "witness_id": c_id}))
        ).decode("ascii")
        resolved_ok = synthesizer.register.resolve(c_id, proof_text, sig)
        assert resolved_ok is True

    # Phase state now condenses into CONDENSED_LOCKED (0 unresolved conflicts)
    state_after_resolution = synthesizer.evaluate_phase_transition()
    assert state_after_resolution == PhaseState.CONDENSED_LOCKED

    # Now early_proposal succeeds in condensed state
    allowed_post, reason_post, receipt = synthesizer.adjudicate_ontic_proposal(early_proposal)
    assert allowed_post is True
    assert reason_post == "ONTIC_EXECUTION_AUTHORIZED_CONDENSED_STATE"

    # Overlapping write-set proposal from another agent fails closed
    colliding_proposal = OnticActionProposal(
        operation_id="op-collide-0002",
        proposer_agent_id="agent-0002",
        action_class="MUTATE_SHARD",
        target_resource="resource://shard-0001",  # Overlaps with agent-0001!
        write_set_resources=("resource://shard-0001",),
        amount_minor=200_00,
        required_witness_ids=("bose-witness-0002",),
    )
    allowed_col, reason_col, _ = synthesizer.adjudicate_ontic_proposal(colliding_proposal)
    assert allowed_col is False
    assert reason_col == "HALT_DISJOINT_WRITESET_COLLISION"

    return {
        "total_agents_simulated": num_agents,
        "total_bose_witnesses_ingested": synthesizer.register.total_witness_count,
        "conflicts_detected_and_halted": len(conflict_ids),
        "phase_state_under_conflict": state_during_conflicts.value,
        "phase_state_after_condensation": state_after_resolution.value,
        "committed_ontic_operations": len(synthesizer.committed_operations),
        "sample_attribution_digest": receipt["attribution_digest"],
    }


if __name__ == "__main__":
    summary = simulate_1000_agent_phase_transition(1000)
    print(json.dumps(summary, indent=2, sort_keys=True))
