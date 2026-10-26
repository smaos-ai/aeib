#!/usr/bin/env python3
"""
src/behavioral_assurance_gate.py — Organizational Behavioral Assurance, Derivative-Aware
Trajectory No-Op Gate, and Gandalf/AKV SSD Wear-Bounded KV Offload Guard (prototype).

Grounded in verified primary sources:
1. Alan Turing Institute CETaS (Hennessy & Ashurst, 2026, "Behavioural Assurance of Agentic AI
   for Sensitive and High-Stakes Organisations") + NLAH (Tsinghua SIGS & HIT, arXiv:2603.25723)
   + post-approval substitution binding (arXiv:2609.38266v1):
   `BehavioralAssuranceGate` enforces Ed25519 human warrant verification over RFC 8785 JCS
   action digests, goal-displacement detection against the signed initial scope, and
   cumulative organizational policy limits (preventing policy-invisible smurfing/autonomy drift).
2. Discrete Trajectory Total Variation & ACID-Agent (Sun, Wang, Li — Tsinghua, arXiv:2608.13900):
   `DerivativeNoOpGate` checks not only endpoint state convergence (`final_digest == initial_digest`),
   but also the discrete path derivative (total variation across state transitions) and
   non-compensable intermediate excursions (rejecting covert dirty-and-revert trajectories).
3. Gandalf (arXiv:2610.30791, "Flash Shall Not Die! Increasing Flash Storage Lifetime for KV
   Cache Offloading in LLM Serving") + AKV Cache Compaction:
   `KVStorageGuard` filters KV cache blocks by attention type and memory tier, coalesces admitted
   blocks into 4096-byte page-aligned sequential flushes, and enforces a daily Drive Writes Per Day
   (DWPD) wear budget before allowing NVMe offload.

Epistemic notice: prototype, evaluated under the stated model. No outbound network calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs

BPS_SCALE = 10000
NVME_PAGE_BYTES = 4096
HIGH_VALUE_ATTENTION_TYPES = ("full_attention", "mla_pinned_prefix")
HIGH_VALUE_MEMORY_TIERS = ("CONSTRAINT_C", "PROCEDURE_P")


def jcs_sha256(payload: object) -> str:
    """Computes sha256:-prefixed digest over RFC 8785 JCS canonical bytes."""
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


# ==============================================================================
# 1. Organizational Behavioral Assurance Gate (CETaS + NLAH arXiv:2603.25723)
# ==============================================================================


@dataclass(frozen=True)
class OrganizationalPolicy:
    policy_id: str
    nlah_harness_digest: str
    allowed_capabilities: Tuple[str, ...]
    high_stakes_capabilities: Tuple[str, ...]
    max_single_action_minor: int
    max_epoch_cumulative_minor: int
    max_unattended_steps: int


@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    subject_agent_id: str
    tool_id: str
    capability_id: str
    amount_minor: int
    unattended_steps: int
    nlah_harness_digest: str
    warrant_signature_hex: str = ""


@dataclass(frozen=True)
class BehavioralVerdict:
    allowed: bool
    reason: str
    canonical_act_digest: str
    cumulative_epoch_minor: int


class BehavioralAssuranceGate:
    """
    Evaluates agent actions against organizational risk appetite, NLAH harness digest pinning,
    goal-displacement boundaries, and Ed25519 human warrant binding (arXiv:2609.38266v1).
    """

    def __init__(self, policy: OrganizationalPolicy, human_authority_pub: Ed25519PublicKey) -> None:
        if (
            policy.max_single_action_minor < 0
            or policy.max_epoch_cumulative_minor < 0
            or policy.max_unattended_steps < 1
        ):
            raise ValueError("ERR_INVALID_ORG_POLICY_LIMITS")
        self.policy = policy
        self.human_authority_pub = human_authority_pub
        self.cumulative_epoch_minor: int = 0

    @staticmethod
    def canonical_warrant_payload(proposal: ActionProposal, policy_id: str) -> Dict[str, object]:
        return {
            "action_id": proposal.action_id,
            "amount_minor": proposal.amount_minor,
            "capability_id": proposal.capability_id,
            "nlah_harness_digest": proposal.nlah_harness_digest,
            "policy_id": policy_id,
            "subject_agent_id": proposal.subject_agent_id,
            "tool_id": proposal.tool_id,
        }

    def evaluate(self, proposal: ActionProposal) -> BehavioralVerdict:
        if proposal.amount_minor < 0 or proposal.unattended_steps < 0:
            raise ValueError("ERR_NEGATIVE_ACTION_PARAMETERS")

        payload = self.canonical_warrant_payload(proposal, self.policy.policy_id)
        act_digest = jcs_sha256(payload)

        if proposal.nlah_harness_digest != self.policy.nlah_harness_digest:
            return BehavioralVerdict(
                False, "HALT_NLAH_HARNESS_DIGEST_DRIFT", act_digest, self.cumulative_epoch_minor
            )

        if proposal.capability_id not in self.policy.allowed_capabilities:
            return BehavioralVerdict(
                False, "HALT_GOAL_DISPLACEMENT_OUT_OF_SCOPE", act_digest, self.cumulative_epoch_minor
            )

        if proposal.unattended_steps > self.policy.max_unattended_steps:
            return BehavioralVerdict(
                False, "HALT_ROGUE_AUTONOMY_STEP_LIMIT", act_digest, self.cumulative_epoch_minor
            )

        if proposal.amount_minor > self.policy.max_single_action_minor:
            return BehavioralVerdict(
                False, "HALT_SINGLE_ACTION_LIMIT_EXCEEDED", act_digest, self.cumulative_epoch_minor
            )

        projected_minor = self.cumulative_epoch_minor + proposal.amount_minor
        if projected_minor > self.policy.max_epoch_cumulative_minor:
            return BehavioralVerdict(
                False,
                "HALT_POLICY_INVISIBLE_CUMULATIVE_EXCEEDED",
                act_digest,
                self.cumulative_epoch_minor,
            )

        if proposal.capability_id in self.policy.high_stakes_capabilities:
            if not proposal.warrant_signature_hex:
                return BehavioralVerdict(
                    False,
                    "HALT_ROGUE_AGENT_UNATTESTED_HIGH_STAKES",
                    act_digest,
                    self.cumulative_epoch_minor,
                )
            try:
                sig_bytes = bytes.fromhex(proposal.warrant_signature_hex)
                self.human_authority_pub.verify(sig_bytes, encode_jcs(payload))
            except (ValueError, InvalidSignature):
                return BehavioralVerdict(
                    False,
                    "HALT_INVALID_HUMAN_WARRANT_SIGNATURE",
                    act_digest,
                    self.cumulative_epoch_minor,
                )

        self.cumulative_epoch_minor = projected_minor
        return BehavioralVerdict(
            True, "ALLOW_BEHAVIORAL_POLICY_SATISFIED", act_digest, self.cumulative_epoch_minor
        )


# ==============================================================================
# 2. Derivative-Aware Trajectory No-Op Gate (Staircase / ACID-Agent arXiv:2608.13900)
# ==============================================================================


@dataclass(frozen=True)
class TrajectoryStep:
    step_index: int
    tool_id: str
    state_digest_after: str
    compensable: bool = True


@dataclass(frozen=True)
class DerivativeNoOpVerdict:
    is_valid_noop: bool
    reason: str
    endpoint_converged: bool
    total_variation: int
    non_compensable_steps: int


class DerivativeNoOpGate:
    """
    Verifies both endpoint convergence (`final_digest == initial_digest`) and discrete
    trajectory total variation. Rejects covert dirty-and-revert loops or non-compensable
    intermediate excursions even when the final state digest matches the initial state.
    """

    def __init__(self, max_allowed_noop_variation: int = 0) -> None:
        if max_allowed_noop_variation < 0:
            raise ValueError("ERR_NEGATIVE_VARIATION_BOUND")
        self.max_allowed_noop_variation = max_allowed_noop_variation

    def evaluate_trajectory(
        self, initial_state_digest: str, steps: Sequence[TrajectoryStep]
    ) -> DerivativeNoOpVerdict:
        if not initial_state_digest:
            raise ValueError("ERR_EMPTY_INITIAL_DIGEST")

        prev_digest = initial_state_digest
        total_variation = 0
        non_compensable = 0

        for step in steps:
            if step.state_digest_after != prev_digest:
                total_variation += 1
            if not step.compensable:
                non_compensable += 1
            prev_digest = step.state_digest_after

        endpoint_converged = prev_digest == initial_state_digest
        if not endpoint_converged:
            return DerivativeNoOpVerdict(
                False,
                "REJECT_ENDPOINT_STATE_MUTATED",
                False,
                total_variation,
                non_compensable,
            )

        if non_compensable > 0:
            return DerivativeNoOpVerdict(
                False,
                "HALT_COVERT_NON_COMPENSABLE_EXCURSION",
                True,
                total_variation,
                non_compensable,
            )

        if total_variation > self.max_allowed_noop_variation:
            return DerivativeNoOpVerdict(
                False,
                "HALT_STAIRCASE_DERIVATIVE_DIVERGENCE",
                True,
                total_variation,
                non_compensable,
            )

        return DerivativeNoOpVerdict(
            True, "HALT_VERIFIED_ZERO_VARIATION_NOOP", True, total_variation, non_compensable
        )


# ==============================================================================
# 3. Gandalf SSD Lifetime-Aware KV Offload Guard (arXiv:2610.30791 + AKV)
# ==============================================================================


@dataclass(frozen=True)
class KVBlockCandidate:
    block_id: str
    attention_type: str
    memory_tier: str
    payload_bytes: int
    reuse_priority_bps: int


@dataclass(frozen=True)
class KVOffloadDecision:
    admitted: bool
    flushed_to_ssd: bool
    reason: str
    coalesced_buffer_bytes: int
    flushed_page_aligned_bytes: int
    daily_written_bytes: int


class KVStorageGuard:
    """
    Prevents SSD wear-out from indiscriminate KV cache offloading (Gandalf, arXiv:2610.30791):
    1. Attention-type & memory-tier admission filter: admits only high-reuse full-attention /
       pinned-prefix or [C]/[P] constraint/procedure KV blocks meeting `min_priority_bps`.
    2. Sequential write coalescing: buffers admitted blocks in RAM until reaching
       `flush_threshold_bytes`, padding flushes to 4096-byte NVMe page boundaries.
    3. Daily DWPD wear-budget circuit breaker: halts SSD writes when `daily_written_bytes`
       would exceed `daily_wear_budget_bytes`.
    """

    def __init__(
        self,
        daily_wear_budget_bytes: int,
        flush_threshold_bytes: int = NVME_PAGE_BYTES,
        min_priority_bps: int = 5000,
    ) -> None:
        if (
            daily_wear_budget_bytes < NVME_PAGE_BYTES
            or flush_threshold_bytes < NVME_PAGE_BYTES
            or not 0 <= min_priority_bps <= BPS_SCALE
        ):
            raise ValueError("ERR_INVALID_KV_GUARD_PARAMS")
        self.daily_wear_budget_bytes = daily_wear_budget_bytes
        self.flush_threshold_bytes = flush_threshold_bytes
        self.min_priority_bps = min_priority_bps
        self.coalesced_buffer_bytes: int = 0
        self.daily_written_bytes: int = 0

    @staticmethod
    def _align_to_nvme_page(raw_bytes: int) -> int:
        rem = raw_bytes % NVME_PAGE_BYTES
        return raw_bytes if rem == 0 else raw_bytes + (NVME_PAGE_BYTES - rem)

    def evaluate_offload(self, block: KVBlockCandidate) -> KVOffloadDecision:
        if block.payload_bytes <= 0 or not 0 <= block.reuse_priority_bps <= BPS_SCALE:
            raise ValueError("ERR_INVALID_KV_BLOCK")

        high_value_type = (
            block.attention_type in HIGH_VALUE_ATTENTION_TYPES
            or block.memory_tier in HIGH_VALUE_MEMORY_TIERS
        )
        if not high_value_type or block.reuse_priority_bps < self.min_priority_bps:
            return KVOffloadDecision(
                False,
                False,
                "SKIPPED_LOW_REUSE_KV_BLOCK",
                self.coalesced_buffer_bytes,
                0,
                self.daily_written_bytes,
            )

        candidate_buffer = self.coalesced_buffer_bytes + block.payload_bytes
        if candidate_buffer < self.flush_threshold_bytes:
            self.coalesced_buffer_bytes = candidate_buffer
            return KVOffloadDecision(
                True,
                False,
                "BUFFERED_IN_RAM_AWAITING_SEQUENTIAL_BATCH",
                self.coalesced_buffer_bytes,
                0,
                self.daily_written_bytes,
            )

        aligned_write = self._align_to_nvme_page(candidate_buffer)
        if self.daily_written_bytes + aligned_write > self.daily_wear_budget_bytes:
            return KVOffloadDecision(
                False,
                False,
                "HALT_SSD_DWPD_WEAR_BUDGET_EXCEEDED",
                self.coalesced_buffer_bytes,
                0,
                self.daily_written_bytes,
            )

        self.coalesced_buffer_bytes = 0
        self.daily_written_bytes += aligned_write
        return KVOffloadDecision(
            True,
            True,
            "FLUSHED_SEQUENTIAL_NVME_BATCH",
            0,
            aligned_write,
            self.daily_written_bytes,
        )
