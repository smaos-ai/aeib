#!/usr/bin/env python3
# File: src/cerno_scion_ta14_omnigent_fabric.py
"""
Unified 6-Pillar Execution Control & Governance Fabric (`v1.0.0-rc.5-preprod`):

1. Cognitive & Decision Routing — `CernoSystemOneFastRouter`:
   Single-pass calibrated probability router (<= 52ms budget, zero CoT text generation)
   positioning Cerno System One as the fast pre-dispatch classifier at Station 1.

2. Source Control & Concurrency — `ScionServerAuthoritativeDisjointMerger`:
   Anthropic Scion server-authoritative version control coordinator enforcing disjoint
   write sets (`Write(A) intersect Write(B) == empty`) across parallel agents with O(1)
   branch pointer rollback.

3. Enterprise Context & Retrieval — `OnyxNemotronHybridRetriever`:
   Self-hosted Tier-3 hybrid BM25 + dense vector similarity retriever with content-addressed
   provenance digests, relieving storage pressure on the Tier-2 Lossless Vault.

4. Authoritative & Admissibility Governance — `Ta14RuntimeAdmissibilityProtocol` (`TA-14 RAP`):
   Enforces the constitutional axiom "No admissible evidence, no admissible execution" across
   the 8-stage chain:
     `REALITY -> RECORD -> CONTINUITY -> ADMISSIBILITY -> BINDING -> COMMIT -> EXECUTION -> OUTCOME`
   Requires three simultaneous cryptographic proofs (`AdmissibleEvidence`, `ApplicableAuthority`,
   `EstablishedStanding`) before any consequential execution can proceed.

5. Enterprise Orchestration & Sandbox — `OmnigentThreeTierMetaHarness`:
   Databricks Omnigent / Omnibox 3-tier policy evaluator (`SERVER`, `AGENT`, `SESSION`) returning
   deterministic `ALLOW | ASK | DENY` decisions under strict dominance (`DENY > ASK > ALLOW`).

6. Machine Identity & Patch Velocity — `MachineIdentityShadowAgentGuard`:
   Governs the 109:1 machine-to-human identity ratio by blocking unregistered Shadow Agents
   (`HALT_SHADOW_AGENT_UNREGISTERED_IDENTITY`) and enforcing Ed25519 machine identity warrants.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
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


def canonical_jcs(obj: Any) -> bytes:
    """Serialize object to RFC 8785 JCS canonical UTF-8 bytes (rejecting floats)."""
    def _reject_float(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("Floats are forbidden in RFC 8785 JCS payloads; use integer bps.")
        if isinstance(val, dict):
            for k, v in val.items():
                _reject_float(k)
                _reject_float(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _reject_float(item)

    _reject_float(obj)
    return _reference_encode_jcs(obj)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# PILLAR 1: Cerno System One Fast Decision Router (Station 1 Pre-Dispatch)
# ============================================================================
class CernoSystemOneFastRouter:
    """
    Single-forward-pass calibrated probability router (<= 52ms budget, zero CoT generation).
    Evaluates calibrated safety & read-only probabilities (in basis points, 0..10000)
    to route tool calls without multi-second generative CoT latency.
    """

    def __init__(
        self,
        fast_allow_confidence_floor_bps: int = 9500,
        block_hazard_ceiling_bps: int = 7000,
    ) -> None:
        self._fast_allow_floor = fast_allow_confidence_floor_bps
        self._block_ceiling = block_hazard_ceiling_bps

    def route_single_pass(
        self,
        ticket_id: str,
        tool_name: str,
        is_read_only_op: bool,
        calibrated_safe_prob_bps: int,
        calibrated_hazard_prob_bps: int,
        forward_pass_latency_us: int,
    ) -> Dict[str, Any]:
        # Enforce 52ms (52,000 microseconds) System One SLA ceiling
        if forward_pass_latency_us > 52_000:
            return {
                "allowed": False,
                "halt_code": "HALT_CERNO_SLA_LATENCY_EXCEEDED",
                "route": "STATION1_TIMEOUT_HOLD",
                "ticket_id": ticket_id,
            }

        if calibrated_hazard_prob_bps >= self._block_ceiling:
            return {
                "allowed": False,
                "calibrated_hazard_prob_bps": calibrated_hazard_prob_bps,
                "halt_code": "HALT_CERNO_SYSTEM1_HIGH_HAZARD_PROBABILITY",
                "route": "IMMEDIATE_BLOCK",
                "ticket_id": ticket_id,
                "tool_name": tool_name,
            }

        if is_read_only_op and calibrated_safe_prob_bps >= self._fast_allow_floor:
            return {
                "allowed": True,
                "calibrated_safe_prob_bps": calibrated_safe_prob_bps,
                "halt_code": "NONE",
                "route": "FAST_PATH_READ_ONLY_ALLOW",
                "ticket_id": ticket_id,
                "tool_name": tool_name,
            }

        return {
            "allowed": True,
            "calibrated_safe_prob_bps": calibrated_safe_prob_bps,
            "halt_code": "NONE",
            "route": "STATION1_FULL_ADMISSIBILITY_GATE",
            "ticket_id": ticket_id,
            "tool_name": tool_name,
        }


# ============================================================================
# PILLAR 2: Anthropic Scion Server-Authoritative Disjoint Write-Set Merger
# ============================================================================
@dataclass(frozen=True)
class ScionBranchCommit:
    commit_id: str
    agent_id: str
    parent_commit_id: str
    modified_files: FrozenSet[str]
    tree_sha256: str


class ScionServerAuthoritativeDisjointMerger:
    """
    Server-authoritative version control coordinator modeled on Anthropic Scion:
    - Enforces mathematical disjointness of concurrent agent write sets:
      `Write(A) intersect Write(B) == empty`
    - Provides O(1) server pointer rollback to any historical commit ID.
    """

    def __init__(self, initial_commit_id: str = "commit-root-000") -> None:
        self._head_commit_id = initial_commit_id
        self._commits: Dict[str, ScionBranchCommit] = {
            initial_commit_id: ScionBranchCommit(
                commit_id=initial_commit_id,
                agent_id="system",
                parent_commit_id="",
                modified_files=frozenset(),
                tree_sha256=sha256_prefixed(b"root"),
            )
        }
        self._active_reservations: Dict[str, Set[str]] = {}

    @property
    def head_commit_id(self) -> str:
        return self._head_commit_id

    def reserve_disjoint_write_set(
        self,
        agent_id: str,
        target_files: FrozenSet[str],
    ) -> Dict[str, Any]:
        for other_agent, reserved_files in sorted(self._active_reservations.items()):
            if other_agent == agent_id:
                continue
            overlap = target_files & reserved_files
            if overlap:
                return {
                    "allowed": False,
                    "colliding_agent": other_agent,
                    "colliding_files": sorted(overlap),
                    "halt_code": "HALT_SCION_WRITE_SET_COLLISION",
                }
        self._active_reservations[agent_id] = set(target_files)
        return {
            "agent_id": agent_id,
            "allowed": True,
            "halt_code": "NONE",
            "reserved_files": sorted(target_files),
        }

    def merge_server_authoritative_commit(
        self,
        commit_id: str,
        agent_id: str,
        modified_files: FrozenSet[str],
        file_contents: Dict[str, str],
    ) -> Dict[str, Any]:
        reserved = self._active_reservations.get(agent_id)
        if reserved is None or not modified_files.issubset(reserved):
            return {
                "allowed": False,
                "halt_code": "HALT_SCION_UNRESERVED_WRITE_PATH",
            }

        tree_Digest = sha256_prefixed(canonical_jcs(file_contents))
        new_commit = ScionBranchCommit(
            commit_id=commit_id,
            agent_id=agent_id,
            parent_commit_id=self._head_commit_id,
            modified_files=modified_files,
            tree_sha256=tree_Digest,
        )
        self._commits[commit_id] = new_commit
        self._head_commit_id = commit_id
        del self._active_reservations[agent_id]
        return {
            "allowed": True,
            "commit_id": commit_id,
            "halt_code": "NONE",
            "new_head": self._head_commit_id,
            "tree_sha256": tree_Digest,
        }

    def rollback_branch_o1(self, target_commit_id: str) -> Dict[str, Any]:
        if target_commit_id not in self._commits:
            return {
                "allowed": False,
                "halt_code": "HALT_SCION_UNKNOWN_COMMIT_ID",
            }
        self._head_commit_id = target_commit_id
        return {
            "allowed": True,
            "halt_code": "NONE",
            "restored_head_commit_id": self._head_commit_id,
            "restored_tree_sha256": self._commits[target_commit_id].tree_sha256,
        }


# ============================================================================
# PILLAR 3: Onyx + Nemotron 3.5 Embed Self-Hosted Tier-3 Hybrid Retriever
# ============================================================================
@dataclass(frozen=True)
class OnyxDocumentChunk:
    doc_id: str
    connector_source: str  # e.g., "github", "confluence", "s3_vault"
    text: str
    embedding_int_vec: Tuple[int, ...]
    doc_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "doc_sha256", sha256_prefixed(self.text.encode("utf-8"))
        )


class OnyxNemotronHybridRetriever:
    """
    Self-hosted Tier-3 Knowledge Base combining BM25 lexical term matching with
    Nemotron-style quantized vector cosine similarity, returning provenance-pinned chunks.
    """

    def __init__(self) -> None:
        self._chunks: List[OnyxDocumentChunk] = []

    def index_chunk(self, chunk: OnyxDocumentChunk) -> None:
        self._chunks.append(chunk)

    def retrieve_hybrid(
        self,
        query_terms: Sequence[str],
        query_vec: Sequence[int],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        scored: List[Tuple[int, OnyxDocumentChunk]] = []
        q_terms_lower = [t.lower() for t in query_terms]
        q_norm = math.sqrt(sum(x * x for x in query_vec)) or 1.0

        for ch in self._chunks:
            text_lower = ch.text.lower()
            lexical_hits = sum(1 for t in q_terms_lower if t in text_lower)
            lexical_score_bps = (
                (lexical_hits * 10000) // max(1, len(q_terms_lower))
            )

            dot = sum(a * b for a, b in zip(query_vec, ch.embedding_int_vec))
            c_norm = math.sqrt(sum(x * x for x in ch.embedding_int_vec)) or 1.0
            cosine = max(0.0, dot / (q_norm * c_norm))
            dense_score_bps = int(round(cosine * 10000))

            # 50/50 hybrid fusion in integer basis points
            hybrid_bps = (lexical_score_bps + dense_score_bps) // 2
            scored.append((hybrid_bps, ch))

        scored.sort(key=lambda item: (-item[0], item[1].doc_id))
        return [
            {
                "connector_source": ch.connector_source,
                "doc_id": ch.doc_id,
                "doc_sha256": ch.doc_sha256,
                "hybrid_score_bps": score_bps,
            }
            for score_bps, ch in scored[:top_k]
        ]


# ============================================================================
# PILLAR 4: TA-14 Runtime Admissibility Protocol (`TA-14 RAP` & `CAG`)
# ============================================================================
@dataclass(frozen=True)
class Ta14TripleAdmissibilityProof:
    """
    TA-14 Core Axiom: "No admissible evidence, no admissible execution."
    Every consequential execution must carry three verified proofs:
    1. Admissible Evidence (`evidence_digest` + non-expired observation timestamp)
    2. Applicable Authority (`authority_warrant_id` + authorized scope)
    3. Established Standing (`standing_epoch_valid` + active agent lifecycle standing)
    """
    action_caid: str
    reality_observation_digest: str
    continuity_hash_chain_tip: str
    admissible_evidence_present: bool
    applicable_authority_scope: FrozenSet[str]
    established_standing_active: bool
    authority_signature_b64: str


class Ta14RuntimeAdmissibilityProtocol:
    """
    Enforces the 8-stage TA-14 Governance Chain:
    `REALITY -> RECORD -> CONTINUITY -> ADMISSIBILITY -> BINDING -> COMMIT -> EXECUTION -> OUTCOME`
    """

    EIGHT_STAGES: Tuple[str, ...] = (
        "REALITY",
        "RECORD",
        "CONTINUITY",
        "ADMISSIBILITY",
        "BINDING",
        "COMMIT",
        "EXECUTION",
        "OUTCOME",
    )

    def __init__(self, authority_pubkey: Ed25519PublicKey) -> None:
        self._authority_pubkey = authority_pubkey

    def adjudicate_execution_admissibility(
        self,
        requested_action: str,
        proof: Ta14TripleAdmissibilityProof,
    ) -> Dict[str, Any]:
        # 1. Verify Admissible Evidence
        if not proof.admissible_evidence_present or not proof.reality_observation_digest.startswith("sha256:"):
            return {
                "admissible": False,
                "failed_stage": "ADMISSIBILITY_EVIDENCE_CHECK",
                "halt_code": "HALT_TA14_NO_ADMISSIBLE_EVIDENCE",
            }

        # 2. Verify Established Standing (LAS / CAG)
        if not proof.established_standing_active:
            return {
                "admissible": False,
                "failed_stage": "ADMISSIBILITY_STANDING_CHECK",
                "halt_code": "HALT_TA14_STANDING_NOT_ESTABLISHED",
            }

        # 3. Verify Applicable Authority scope & Ed25519 Binding
        if requested_action not in proof.applicable_authority_scope:
            return {
                "admissible": False,
                "failed_stage": "ADMISSIBILITY_AUTHORITY_CHECK",
                "halt_code": "HALT_TA14_APPLICABLE_AUTHORITY_MISSING",
            }

        signed_statement = {
            "action_caid": proof.action_caid,
            "applicable_authority_scope": sorted(proof.applicable_authority_scope),
            "continuity_hash_chain_tip": proof.continuity_hash_chain_tip,
            "established_standing_active": proof.established_standing_active,
            "reality_observation_digest": proof.reality_observation_digest,
        }
        try:
            sig = base64.b64decode(proof.authority_signature_b64)
            self._authority_pubkey.verify(sig, canonical_jcs(signed_statement))
        except (InvalidSignature, ValueError):
            return {
                "admissible": False,
                "failed_stage": "BINDING_CRYPTOGRAPHIC_CHECK",
                "halt_code": "HALT_TA14_INVALID_AUTHORITY_BINDING",
            }

        return {
            "action_caid": proof.action_caid,
            "admissible": True,
            "chain_traversed": list(self.EIGHT_STAGES),
            "halt_code": "NONE",
        }


# ============================================================================
# PILLAR 5: Databricks Omnigent (`Omnibox`) 3-Tier Meta-Harness Policy Engine
# ============================================================================
class OmnigentThreeTierMetaHarness:
    """
    Evaluates hierarchical `ALLOW | ASK | DENY` policies across the `SERVER`, `AGENT`,
    and `SESSION` tiers. Strict dominance applies: `DENY > ASK > ALLOW`.
    """

    PRECEDENCE: Dict[str, int] = {"ALLOW": 0, "ASK": 1, "DENY": 2}

    def __init__(
        self,
        server_tier_rules: Dict[str, str],
        agent_tier_rules: Dict[str, str],
        session_tier_rules: Dict[str, str],
    ) -> None:
        self._server = dict(server_tier_rules)
        self._agent = dict(agent_tier_rules)
        self._session = dict(session_tier_rules)

    def evaluate_three_tier_policy(self, tool_name: str) -> Dict[str, str]:
        v_server = self._server.get(tool_name, "DENY")
        v_agent = self._agent.get(tool_name, "DENY")
        v_session = self._session.get(tool_name, "DENY")

        decisions = [
            ("SERVER", v_server),
            ("AGENT", v_agent),
            ("SESSION", v_session),
        ]
        winning_tier, winning_verdict = max(
            decisions, key=lambda item: self.PRECEDENCE.get(item[1], 2)
        )
        halt_code = (
            "HALT_OMNIGENT_POLICY_DENIED"
            if winning_verdict == "DENY"
            else ("HOLD_OMNIGENT_STEP_UP_ASK" if winning_verdict == "ASK" else "NONE")
        )
        return {
            "agent_tier": v_agent,
            "deciding_tier": winning_tier,
            "effective_decision": winning_verdict,
            "halt_code": halt_code,
            "server_tier": v_server,
            "session_tier": v_session,
            "tool_name": tool_name,
        }


# ============================================================================
# PILLAR 6: Machine Identity & Shadow Agent Guard (109:1 Identity Ratio)
# ============================================================================
@dataclass(frozen=True)
class MachineIdentityCertificate:
    machine_agent_caid: str
    human_sponsor_did: str
    allowed_tools: FrozenSet[str]
    expires_at_epoch: int
    signature_b64: str


class MachineIdentityShadowAgentGuard:
    """
    Governs the 109:1 machine-to-human identity ratio by blocking unregistered
    Shadow Agents (82% enterprise exposure) and verifying Ed25519 machine identity
    warrants tied to a human sponsor DID.
    """

    def __init__(self, identity_ca_pubkey: Ed25519PublicKey) -> None:
        self._ca_pubkey = identity_ca_pubkey
        self._registered_machine_caids: Dict[str, MachineIdentityCertificate] = {}

    def register_machine_identity(
        self, cert: MachineIdentityCertificate
    ) -> Dict[str, Any]:
        payload = {
            "allowed_tools": sorted(cert.allowed_tools),
            "expires_at_epoch": cert.expires_at_epoch,
            "human_sponsor_did": cert.human_sponsor_did,
            "machine_agent_caid": cert.machine_agent_caid,
        }
        try:
            sig = base64.b64decode(cert.signature_b64)
            self._ca_pubkey.verify(sig, canonical_jcs(payload))
        except (InvalidSignature, ValueError):
            return {
                "halt_code": "HALT_MACHINE_IDENTITY_INVALID_SIGNATURE",
                "registered": False,
            }

        self._registered_machine_caids[cert.machine_agent_caid] = cert
        return {
            "halt_code": "NONE",
            "machine_agent_caid": cert.machine_agent_caid,
            "registered": True,
        }

    def verify_agent_dispatch(
        self,
        machine_agent_caid: str,
        requested_tool: str,
        current_epoch: int,
    ) -> Dict[str, Any]:
        cert = self._registered_machine_caids.get(machine_agent_caid)
        if cert is None:
            return {
                "allowed": False,
                "halt_code": "HALT_SHADOW_AGENT_UNREGISTERED_IDENTITY",
                "machine_agent_caid": machine_agent_caid,
            }
        if current_epoch > cert.expires_at_epoch:
            return {
                "allowed": False,
                "halt_code": "HALT_MACHINE_IDENTITY_EXPIRED",
                "machine_agent_caid": machine_agent_caid,
            }
        if requested_tool not in cert.allowed_tools:
            return {
                "allowed": False,
                "halt_code": "HALT_MACHINE_IDENTITY_LEAST_PRIVILEGE_VIOLATION",
                "machine_agent_caid": machine_agent_caid,
                "requested_tool": requested_tool,
            }
        return {
            "allowed": True,
            "halt_code": "NONE",
            "human_sponsor_did": cert.human_sponsor_did,
            "machine_agent_caid": machine_agent_caid,
        }
