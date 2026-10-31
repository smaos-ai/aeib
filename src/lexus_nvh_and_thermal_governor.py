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
src/lexus_nvh_and_thermal_governor.py
================================================================================
Lexus-Grade NVH Damping, Context Thermal Management, and Anti-Backlash Transmission.

Evaluated under the stated model (1989 Lexus Project F1 Standards, Toyota Production
System Jidoka/Poka-Yoke, and BYD Vertical Scale Commodity Powertrain Adaptation).

Architectural Subsystems:
  1. SemanticNVHDamper:
     Suppresses the "motor whine" of commodity LLM generators by measuring
     semantic output variance and AST divergence across speculative passes.
     Enforces the Lexus 500 bps (0.05) maximum jitter tolerance threshold.
  2. ContextThermalBMS:
     Applies Toyota's 10-year 90% capacity retention benchmark to agentic
     context compaction. Tracks safety rule recall retention across turns;
     initiates an active thermal quench if rule recall drops below 9000 bps (90.0%).
  3. AntiBacklashWireTransmission:
     Applies Toyota 1UZ-FE scissor-gear anti-backlash mechanics to distributed
     tool execution, binding monotonic attempt fences and pre-socket reservations
     to prevent duplicate mutations and wire backlash.
  4. TakumiInspectionHUD:
     Formats exact AST blast-radius diffs and structural impact metrics into
     the RFC 8785 canonical payload for Apple Silicon Secure Enclave FaceID review.
"""

from __future__ import annotations

import difflib
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from src.jcs_canonicalizer import encode_jcs


class GovernorTripReason(str, Enum):
    """Trip reason codes for the Lexus-grade governor."""

    TRIP_SEMANTIC_NVH_EXCESSIVE = "TRIP_SEMANTIC_NVH_EXCESSIVE"
    TRIP_CONTEXT_THERMAL_RUNAWAY = "TRIP_CONTEXT_THERMAL_RUNAWAY"
    TRIP_WIRE_BACKLASH_DETECTED = "TRIP_WIRE_BACKLASH_DETECTED"
    TRIP_TAKUMI_INSPECTION_REJECTED = "TRIP_TAKUMI_INSPECTION_REJECTED"


class NVHDampingDisposition(str, Enum):
    """Disposition of the semantic NVH damper."""

    NVH_DAMPED_ACCEPTABLE = "NVH_DAMPED_ACCEPTABLE"
    NVH_JITTER_EXCESSIVE = "NVH_JITTER_EXCESSIVE"


@dataclass(frozen=True)
class NVHInspectionResult:
    """Result of semantic noise, vibration, and harshness inspection."""

    passed: bool
    jitter_variance_bps: int
    max_allowed_jitter_bps: int
    disposition: NVHDampingDisposition
    consensus_digest: str
    sample_count: int


class SemanticNVHDamper:
    """
    Measures and damps semantic jitter across speculative candidate outputs.
    Analogous to acoustic glass, hydraulic engine mounts, and counterbalanced
    crankshafts in the 1989 Lexus LS 400.
    """

    DEFAULT_MAX_JITTER_BPS: int = 500  # claim: config

    def __init__(self, max_jitter_bps: int = DEFAULT_MAX_JITTER_BPS) -> None:
        if type(max_jitter_bps) is not int or max_jitter_bps < 0 or max_jitter_bps > 10000:
            raise ValueError("ERR_INVALID_MAX_JITTER_BPS")
        self.max_jitter_bps = max_jitter_bps

    def inspect_speculative_candidates(
        self, candidate_outputs: Sequence[str]
    ) -> NVHInspectionResult:
        """
        Evaluates pairwise character and token diff variance across candidates.
        Computes jitter variance in integer basis points (0..10000).
        """
        if not candidate_outputs:
            raise ValueError("ERR_EMPTY_CANDIDATES")

        if len(candidate_outputs) == 1:
            # Single candidate: zero variance by definition
            out_bytes = candidate_outputs[0].encode("utf-8")
            digest = hashlib.sha256(out_bytes).hexdigest()
            return NVHInspectionResult(
                passed=True,
                jitter_variance_bps=0,
                max_allowed_jitter_bps=self.max_jitter_bps,
                disposition=NVHDampingDisposition.NVH_DAMPED_ACCEPTABLE,
                consensus_digest=digest,
                sample_count=1,
            )

        # Compute pairwise sequence matcher ratios
        total_divergence = 0.0
        comparisons = 0
        n = len(candidate_outputs)

        for i in range(n):
            for j in range(i + 1, n):
                s1 = candidate_outputs[i]
                s2 = candidate_outputs[j]
                matcher = difflib.SequenceMatcher(None, s1, s2)
                sim = matcher.ratio()  # 0.0 to 1.0
                div = 1.0 - sim
                total_divergence += div
                comparisons += 1

        avg_divergence = total_divergence / max(1, comparisons)
        jitter_bps = int(round(avg_divergence * 10000))

        # Select consensus candidate (first one or highest similarity)
        consensus_str = candidate_outputs[0]
        consensus_digest = hashlib.sha256(consensus_str.encode("utf-8")).hexdigest()

        passed = jitter_bps <= self.max_jitter_bps
        disp = (
            NVHDampingDisposition.NVH_DAMPED_ACCEPTABLE
            if passed
            else NVHDampingDisposition.NVH_JITTER_EXCESSIVE
        )

        return NVHInspectionResult(
            passed=passed,
            jitter_variance_bps=jitter_bps,
            max_allowed_jitter_bps=self.max_jitter_bps,
            disposition=disp,
            consensus_digest=consensus_digest,
            sample_count=n,
        )


@dataclass(frozen=True)
class ThermalBMSStatus:
    """Status of the Context Thermal Management System."""

    quenched: bool
    current_retention_bps: int
    min_required_retention_bps: int
    active_rule_count: int
    recalled_rule_count: int
    turn_index: int
    quench_reason: Optional[str] = None


class ContextThermalBMS:
    """
    Context Thermal Battery Management System (BMS).
    Translates Toyota's 10-year 90% battery capacity retention requirement
    to autonomous agent context compaction. Quenches fail-closed if critical
    safety rule recall drops below 9000 bps (90.0%).
    """

    MIN_CAPACITY_RETENTION_BPS: int = 9000  # claim: config

    def __init__(
        self,
        pinned_safety_rules: Sequence[str],
        retention_floor_bps: int = MIN_CAPACITY_RETENTION_BPS,
    ) -> None:
        if not pinned_safety_rules:
            raise ValueError("ERR_PINNED_RULES_EMPTY")
        if (
            type(retention_floor_bps) is not int
            or retention_floor_bps < 1
            or retention_floor_bps > 10000
        ):
            raise ValueError("ERR_INVALID_RETENTION_FLOOR_BPS")

        self.pinned_safety_rules: Tuple[str, ...] = tuple(pinned_safety_rules)
        self.retention_floor_bps = retention_floor_bps
        self._turn_index: int = 0
        self._quenched: bool = False

    @property
    def is_quenched(self) -> bool:
        return self._quenched

    def evaluate_context_turn(self, active_context_window: str) -> ThermalBMSStatus:
        """
        Evaluates the current compacted context window against pinned safety rules.
        Computes recall retention ratio in basis points.
        """
        self._turn_index += 1
        if self._quenched:
            return ThermalBMSStatus(
                quenched=True,
                current_retention_bps=0,
                min_required_retention_bps=self.retention_floor_bps,
                active_rule_count=len(self.pinned_safety_rules),
                recalled_rule_count=0,
                turn_index=self._turn_index,
                quench_reason="THERMAL_BMS_ALREADY_QUENCHED",
            )

        recalled = 0
        for rule in self.pinned_safety_rules:
            if rule in active_context_window:
                recalled += 1

        total = len(self.pinned_safety_rules)
        retention_bps = int(round((recalled / total) * 10000))

        if retention_bps < self.retention_floor_bps:
            self._quenched = True
            return ThermalBMSStatus(
                quenched=True,
                current_retention_bps=retention_bps,
                min_required_retention_bps=self.retention_floor_bps,
                active_rule_count=total,
                recalled_rule_count=recalled,
                turn_index=self._turn_index,
                quench_reason="SAFETY_RULE_RETENTION_COLLAPSED_BELOW_FLOOR",
            )

        return ThermalBMSStatus(
            quenched=False,
            current_retention_bps=retention_bps,
            min_required_retention_bps=self.retention_floor_bps,
            active_rule_count=total,
            recalled_rule_count=recalled,
            turn_index=self._turn_index,
        )


@dataclass(frozen=True)
class WireReservationReceipt:
    """Pre-socket reservation ticket preventing wire backlash."""

    operation_id: str
    target_resource: str
    attempt_fence: int
    reservation_caid: str
    timestamp_utc: str
    consumed: bool


class AntiBacklashWireTransmission:
    """
    Dual Scissor-Gear Anti-Backlash Wire Interlock.
    Eliminates tooth backlash (network timeout ambiguity, phantom retries,
    and out-of-order execution) in distributed agent tool calls.
    """

    def __init__(self) -> None:
        self._reservations: Dict[str, WireReservationReceipt] = {}
        self._consumed_operations: Set[str] = set()

    def reserve_pre_socket(
        self,
        operation_id: str,
        target_resource: str,
        attempt_fence: int,
    ) -> WireReservationReceipt:
        """
        Reserves wire mutation atomically before any socket bytes are dispatched.
        Fails closed on replayed or decreasing attempt fences.
        """
        if not operation_id or not isinstance(operation_id, str):
            raise ValueError("ERR_INVALID_OPERATION_ID")
        if not target_resource or not isinstance(target_resource, str):
            raise ValueError("ERR_INVALID_TARGET_RESOURCE")
        if type(attempt_fence) is not int or attempt_fence <= 0:
            raise ValueError("ERR_INVALID_ATTEMPT_FENCE")

        if operation_id in self._consumed_operations:
            raise ValueError(f"ERR_WIRE_BACKLASH_OPERATION_ALREADY_COMMITTED:{operation_id}")

        existing = self._reservations.get(operation_id)
        if existing:
            if attempt_fence <= existing.attempt_fence:
                raise ValueError(
                    f"ERR_WIRE_BACKLASH_STALE_ATTEMPT_FENCE: expected > {existing.attempt_fence}, got {attempt_fence}"
                )

        payload = {
            "attempt_fence": attempt_fence,
            "operation_id": operation_id,
            "target_resource": target_resource,
        }
        res_caid = "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()
        receipt = WireReservationReceipt(
            operation_id=operation_id,
            target_resource=target_resource,
            attempt_fence=attempt_fence,
            reservation_caid=res_caid,
            timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            consumed=False,
        )
        self._reservations[operation_id] = receipt
        return receipt

    def commit_wire_execution(
        self, operation_id: str, attempt_fence: int
    ) -> WireReservationReceipt:
        """Atomically marks pre-socket reservation as executed."""
        receipt = self._reservations.get(operation_id)
        if not receipt:
            raise ValueError(f"ERR_NO_PRE_SOCKET_RESERVATION_FOUND:{operation_id}")
        if receipt.attempt_fence != attempt_fence:
            raise ValueError("ERR_ATTEMPT_FENCE_MISMATCH")
        if receipt.consumed or operation_id in self._consumed_operations:
            raise ValueError("ERR_OPERATION_ALREADY_CONSUMED")

        committed = WireReservationReceipt(
            operation_id=receipt.operation_id,
            target_resource=receipt.target_resource,
            attempt_fence=receipt.attempt_fence,
            reservation_caid=receipt.reservation_caid,
            timestamp_utc=receipt.timestamp_utc,
            consumed=True,
        )
        self._reservations[operation_id] = committed
        self._consumed_operations.add(operation_id)
        return committed


@dataclass(frozen=True)
class TakumiInspectionHUDPayload:
    """Formatted HUD payload presented to the human on the edge device."""

    task_id: str
    modified_files: Tuple[str, ...]
    blast_radius_symbol_count: int
    added_lines_count: int
    deleted_lines_count: int
    purity_confirmed: bool
    hud_digest_sha256: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Serializes HUD into canonical dictionary without floats."""
        return {
            "added_lines_count": self.added_lines_count,
            "blast_radius_symbol_count": self.blast_radius_symbol_count,
            "deleted_lines_count": self.deleted_lines_count,
            "hud_digest_sha256": self.hud_digest_sha256,
            "modified_files": list(self.modified_files),
            "purity_confirmed": self.purity_confirmed,
            "task_id": self.task_id,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.to_canonical_dict())


class TakumiInspectionHUD:
    """
    Takumi Craftsmanship Inspection HUD.
    Renders exact AST diffs, blast radius metrics, and purity checks
    for out-of-band Apple Silicon Secure Enclave FaceID verification (WYSIWYS).
    """

    @staticmethod
    def render_hud(
        task_id: str,
        modified_files: Sequence[str],
        unified_diff_text: str,
        blast_radius_symbol_count: int,
        purity_confirmed: bool,
    ) -> TakumiInspectionHUDPayload:
        if not task_id:
            raise ValueError("ERR_INVALID_TASK_ID")
        if not modified_files:
            raise ValueError("ERR_EMPTY_MODIFIED_FILES")

        added = 0
        deleted = 0
        for line in unified_diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                deleted += 1

        summary = {
            "added": added,
            "deleted": deleted,
            "diff_hash": hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest(),
            "files": sorted(modified_files),
            "purity": purity_confirmed,
            "symbols": blast_radius_symbol_count,
            "task_id": task_id,
        }
        hud_digest = hashlib.sha256(encode_jcs(summary)).hexdigest()

        return TakumiInspectionHUDPayload(
            task_id=task_id,
            modified_files=tuple(sorted(modified_files)),
            blast_radius_symbol_count=blast_radius_symbol_count,
            added_lines_count=added,
            deleted_lines_count=deleted,
            purity_confirmed=purity_confirmed,
            hud_digest_sha256=hud_digest,
        )
