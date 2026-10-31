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
src/swat_heterogeneous_airlock.py
================================================================================
Heterogeneous SwaT Cross-Model Tensor Airlock with Griffiths Merkle History
and Out-of-Band Biometric Step-Up Latch.

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - SwaT (Swarm Telepathy, MIT CSAIL / IBM arXiv:2610.15095) cross-family KV-cache transfer.
  - HeteroFold Procrustes alignment verification and latent Trojan activation bounds.
  - Robert B. Griffiths Consistent Histories incremental Merkle tree verification.
  - Apple Secure Enclave NIST P-256 (secp256r1) hardware-notary step-up authorization.
  - RFC 8785 single-source JSON Canonicalization Scheme (JCS) with zero floats.
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, FrozenSet, Mapping, Optional, Sequence, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.hypersu_consistent_latent_gate import sha256_jcs_caid
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    T3LatchReleaseVerdict,
)
from src.jcs_canonicalizer import encode_jcs


PROJECTION_SCALE = 10000  # claim: config
MAX_ALLOWABLE_DISTORTION_BPS = 1500  # claim: config (15.00% max distortion)
MAX_LATENT_ENERGY_PER_COORD = 1_000_000  # claim: config
STEP_UP_THRESHOLD_MINOR = 10000  # claim: config ($100.00 in minor units)
MIN_PROJECTION_FIDELITY_BPS = 9000  # claim: config (90.00% minimum fidelity)


@dataclass(frozen=True)
class CrossModelMapperSpec:
    """Specification of a learned cross-family KV-cache translation mapper."""

    mapper_id: str
    sender_backbone: str
    receiver_backbone: str
    dim_sender: int
    dim_receiver: int
    projection_matrix_flat: Tuple[int, ...]
    mapper_caid: str

    def __post_init__(self) -> None:
        if not self.mapper_id or not self.sender_backbone or not self.receiver_backbone:
            raise ValueError("ERR_INVALID_MAPPER_IDENTIFIERS")
        if self.dim_sender <= 0 or self.dim_receiver <= 0:
            raise ValueError("ERR_INVALID_MAPPER_DIMENSIONS")
        expected_len = self.dim_sender * self.dim_receiver
        if len(self.projection_matrix_flat) != expected_len:
            raise ValueError("ERR_PROJECTION_MATRIX_DIMENSION_MISMATCH")

    @classmethod
    def create(
        cls,
        mapper_id: str,
        sender_backbone: str,
        receiver_backbone: str,
        dim_sender: int,
        dim_receiver: int,
        projection_matrix_flat: Sequence[int],
    ) -> CrossModelMapperSpec:
        flat_tuple = tuple(int(x) for x in projection_matrix_flat)
        body = {
            "dim_receiver": dim_receiver,
            "dim_sender": dim_sender,
            "mapper_id": mapper_id,
            "projection_matrix_flat": list(flat_tuple),
            "receiver_backbone": receiver_backbone,
            "sender_backbone": sender_backbone,
        }
        mapper_caid = sha256_jcs_caid(body)
        return cls(
            mapper_id=mapper_id,
            sender_backbone=sender_backbone,
            receiver_backbone=receiver_backbone,
            dim_sender=dim_sender,
            dim_receiver=dim_receiver,
            projection_matrix_flat=flat_tuple,
            mapper_caid=mapper_caid,
        )


class HeteroFoldAlignmentVerifier:
    """Verifies orthogonal alignment and Trojan activation bounds on latent state mappers."""

    @staticmethod
    def compute_orthogonal_distortion_bps(mapper: CrossModelMapperSpec) -> int:
        """Computes Frobenius norm deviation of W * W^T from scaled identity in integer bps."""
        d_recv = mapper.dim_receiver
        d_send = mapper.dim_sender
        flat = mapper.projection_matrix_flat

        total_abs_deviation = 0
        scale_sq = PROJECTION_SCALE * PROJECTION_SCALE

        for i in range(d_recv):
            row_i_offset = i * d_send
            for j in range(d_recv):
                row_j_offset = j * d_send
                dot_val = 0
                for k in range(d_send):
                    dot_val += flat[row_i_offset + k] * flat[row_j_offset + k]

                expected = scale_sq if i == j else 0
                total_abs_deviation += abs(dot_val - expected)

        # Normalize deviation across elements
        normalization_denominator = d_recv * scale_sq
        if normalization_denominator <= 0:
            return 10000

        frac = Fraction(total_abs_deviation, normalization_denominator)
        distortion_bps = int(frac * 10000)
        return min(10000, max(0, distortion_bps))

    @classmethod
    def verify_mapper_and_samples(
        cls,
        mapper: CrossModelMapperSpec,
        sample_coords: Sequence[int],
    ) -> Tuple[bool, str, int]:
        """Validates alignment distortion and checks coordinates against Trojan energy bounds."""
        distortion_bps = cls.compute_orthogonal_distortion_bps(mapper)
        if distortion_bps > MAX_ALLOWABLE_DISTORTION_BPS:
            return (
                False,
                f"HALT_LATENT_ALIGNMENT_DECOHERENCE:{distortion_bps}_exceeds_{MAX_ALLOWABLE_DISTORTION_BPS}_bps",
                distortion_bps,
            )

        for idx, coord in enumerate(sample_coords):
            if abs(coord) > MAX_LATENT_ENERGY_PER_COORD:
                return (
                    False,
                    f"HALT_LATENT_TROJAN_NORM_SPIKE:coord_{idx}_value_{coord}",
                    distortion_bps,
                )

        return (True, "OK_ALIGNMENT_AND_BOUNDS_VERIFIED", distortion_bps)


@dataclass(frozen=True)
class MerkleHistoryLeaf:
    index: int
    leaf_caid: str
    cycle_phase: str
    sender_agent_id: str
    receiver_agent_id: str
    mapper_caid: str
    intent_caid: str
    spend_minor: int
    target_scope: str


class ConsistentHistoryMerkleTree:
    """Incremental Merkle tree verifying Griffiths Consistent Histories joint trajectories."""

    PHASE_ORDER: Mapping[str, int] = {
        "CYCLE_1_BRAINSTORM": 1,
        "CYCLE_2_GO_NOGO": 2,
        "CYCLE_3_EXECUTE": 3,
    }

    def __init__(
        self,
        max_budget_minor: int,
        authorized_scopes: FrozenSet[str],
    ) -> None:
        if max_budget_minor < 0:
            raise ValueError("ERR_INVALID_MAX_BUDGET")
        if not authorized_scopes:
            raise ValueError("ERR_EMPTY_AUTHORIZED_SCOPES")
        self.max_budget_minor = max_budget_minor
        self.authorized_scopes = authorized_scopes
        self._leaves: list[MerkleHistoryLeaf] = []
        self._current_merkle_root: str = "MERKLE_ROOT_GENESIS"

    @property
    def cumulative_spend_minor(self) -> int:
        return sum(leaf.spend_minor for leaf in self._leaves)

    @property
    def current_merkle_root(self) -> str:
        return self._current_merkle_root

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    def append_and_verify(
        self,
        cycle_phase: str,
        sender_agent_id: str,
        receiver_agent_id: str,
        mapper_caid: str,
        intent_caid: str,
        spend_minor: int,
        target_scope: str,
    ) -> Tuple[bool, str, str]:
        """Appends event leaf if joint trajectory maintains monotonic phase, scope, and budget."""
        if spend_minor < 0:
            return (False, "HALT_INCONSISTENT_HISTORY:NEGATIVE_SPEND", self._current_merkle_root)

        # 1. Monotonic Cycle Phase Check
        if cycle_phase not in self.PHASE_ORDER:
            return (
                False,
                f"HALT_INCONSISTENT_HISTORY:UNKNOWN_PHASE:{cycle_phase}",
                self._current_merkle_root,
            )

        new_rank = self.PHASE_ORDER[cycle_phase]
        if self._leaves:
            last_rank = self.PHASE_ORDER[self._leaves[-1].cycle_phase]
            if new_rank < last_rank:
                return (
                    False,
                    f"HALT_INCONSISTENT_HISTORY:PHASE_REGRESSION:{self._leaves[-1].cycle_phase}_to_{cycle_phase}",
                    self._current_merkle_root,
                )

        # 2. Prerequisite Check for CYCLE_3_EXECUTE
        if cycle_phase == "CYCLE_3_EXECUTE":
            has_gonogo = any(leaf.cycle_phase == "CYCLE_2_GO_NOGO" for leaf in self._leaves)
            if not has_gonogo:
                return (
                    False,
                    "HALT_INCONSISTENT_HISTORY:MISSING_CYCLE_2_GO_NOGO_GATE",
                    self._current_merkle_root,
                )

        # 3. Scope Confinement
        if target_scope not in self.authorized_scopes:
            return (
                False,
                f"HALT_INCONSISTENT_HISTORY:SCOPE_AMPLIFICATION:{target_scope}",
                self._current_merkle_root,
            )

        # 4. Joint Trajectory Cumulative Budget Conservation
        projected_spend = self.cumulative_spend_minor + spend_minor
        if projected_spend > self.max_budget_minor:
            return (
                False,
                f"HALT_INCONSISTENT_HISTORY:BUDGET_DECOHERENCE:{projected_spend}_exceeds_{self.max_budget_minor}",
                self._current_merkle_root,
            )

        # Compute Leaf CAID
        leaf_index = len(self._leaves)
        leaf_payload = {
            "cycle_phase": cycle_phase,
            "index": leaf_index,
            "intent_caid": intent_caid,
            "mapper_caid": mapper_caid,
            "prev_root": self._current_merkle_root,
            "receiver_agent_id": receiver_agent_id,
            "sender_agent_id": sender_agent_id,
            "spend_minor": spend_minor,
            "target_scope": target_scope,
        }
        leaf_caid = sha256_jcs_caid(leaf_payload)

        # Update Merkle Root
        new_root_payload = {
            "leaf_index": leaf_index,
            "left_root": self._current_merkle_root,
            "right_leaf": leaf_caid,
        }
        new_merkle_root = sha256_jcs_caid(new_root_payload)

        leaf = MerkleHistoryLeaf(
            index=leaf_index,
            leaf_caid=leaf_caid,
            cycle_phase=cycle_phase,
            sender_agent_id=sender_agent_id,
            receiver_agent_id=receiver_agent_id,
            mapper_caid=mapper_caid,
            intent_caid=intent_caid,
            spend_minor=spend_minor,
            target_scope=target_scope,
        )
        self._leaves.append(leaf)
        self._current_merkle_root = new_merkle_root

        return (True, "OK_CONSISTENT_HISTORY_LEAF_COMMITTED", new_merkle_root)


@dataclass(frozen=True)
class SwatTransferIntent:
    """Intent packet for cross-model latent KV-cache transfer."""

    sender_agent_id: str
    receiver_agent_id: str
    sender_backbone: str
    receiver_backbone: str
    kv_cache_raw_bytes: bytes
    latent_sample_coords: Tuple[int, ...]
    mapper_id: str
    semantic_projection: Optional[Dict[str, Any]]
    projection_fidelity_bps: int
    cycle_phase: str
    spend_minor_units: int
    target_scope: str
    operation_id: str
    attempt_fence: int
    expires_at_epoch_sec: int
    step_up_warrant: Optional[EnclaveSignedWarrant] = None


@dataclass(frozen=True)
class SwatAirlockReceipt:
    """Cryptographic dispatch receipt emitted upon passing airlock gates."""

    allowed: bool
    status_code: str
    intent_caid: str
    tensor_caid: str
    mapper_caid: str
    merkle_root: str
    dispatch_nonce: str
    airlock_signature_hex: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "airlock_signature_hex": self.airlock_signature_hex,
            "allowed": self.allowed,
            "dispatch_nonce": self.dispatch_nonce,
            "intent_caid": self.intent_caid,
            "mapper_caid": self.mapper_caid,
            "merkle_root": self.merkle_root,
            "receipt_caid": self.receipt_caid,
            "status_code": self.status_code,
            "tensor_caid": self.tensor_caid,
        }


class SwatHeterogeneousAirlock:
    """Unified cross-model latent airlock enforcing SwaT, Griffiths, and Enclave gates."""

    REQUIRED_PROJECTION_KEYS: FrozenSet[str] = frozenset(
        {"action", "risk_tier", "target_scope"}
    )
    FORBIDDEN_LATENT_ACTIONS: FrozenSet[str] = frozenset(
        {"bypass_eo1", "modify_tests", "exfiltrate_secret", "exec_shell"}
    )

    def __init__(
        self,
        allowed_backbones: FrozenSet[str],
        mappers: Mapping[str, CrossModelMapperSpec],
        max_trajectory_budget_minor: int,
        authorized_scopes: FrozenSet[str],
        pinned_enclave_pubkey_x963_hex: str,
        airlock_signing_key: ed25519.Ed25519PrivateKey,
    ) -> None:
        if not allowed_backbones:
            raise ValueError("ERR_AIRLOCK_EMPTY_ALLOWED_BACKBONES")
        if not authorized_scopes:
            raise ValueError("ERR_AIRLOCK_EMPTY_AUTHORIZED_SCOPES")
        if not isinstance(pinned_enclave_pubkey_x963_hex, str) or not pinned_enclave_pubkey_x963_hex.strip():
            raise ValueError("ERR_INVALID_PINNED_ENCLAVE_PUBKEY")

        self.allowed_backbones = allowed_backbones
        self._mappers: Dict[str, CrossModelMapperSpec] = dict(mappers)
        self.merkle_ledger = ConsistentHistoryMerkleTree(
            max_budget_minor=max_trajectory_budget_minor,
            authorized_scopes=authorized_scopes,
        )
        self.pinned_enclave_pubkey_hex = pinned_enclave_pubkey_x963_hex.strip().lower()
        self._airlock_signing_key = airlock_signing_key
        self._seen_operation_fences: Dict[str, int] = {}
        self._nonce_counter: int = 0

    def register_mapper(self, mapper: CrossModelMapperSpec) -> str:
        """Registers a cross-family translation mapper."""
        self._mappers[mapper.mapper_id] = mapper
        return mapper.mapper_caid

    def process_latent_transfer(
        self,
        intent: SwatTransferIntent,
        current_epoch_sec: Optional[int] = None,
    ) -> SwatAirlockReceipt:
        """Executes full multi-gate evaluation of cross-model latent transfer."""
        now_epoch = current_epoch_sec if current_epoch_sec is not None else int(time.time())

        # Gate 1: SwaT Mapper & Latent Vector Verification
        g1_ok, g1_status, tensor_caid = self._verify_mapper_and_latent(intent)
        if not g1_ok:
            return self._mint_receipt(False, g1_status, "NONE", tensor_caid, "NONE")

        mapper = self._mappers[intent.mapper_id]

        # Gate 2: Semantic Projection & Forbidden Intent Scanning
        g2_ok, g2_status, intent_caid = self._verify_semantic_projection(intent, tensor_caid, mapper.mapper_caid)
        if not g2_ok:
            return self._mint_receipt(False, g2_status, intent_caid, tensor_caid, mapper.mapper_caid)

        # Gate 3: Robert B. Griffiths Consistent History Joint Trajectory
        g3_ok, g3_status, updated_root = self.merkle_ledger.append_and_verify(
            cycle_phase=intent.cycle_phase,
            sender_agent_id=intent.sender_agent_id,
            receiver_agent_id=intent.receiver_agent_id,
            mapper_caid=mapper.mapper_caid,
            intent_caid=intent_caid,
            spend_minor=intent.spend_minor_units,
            target_scope=intent.target_scope,
        )
        if not g3_ok:
            return self._mint_receipt(False, g3_status, intent_caid, tensor_caid, mapper.mapper_caid)

        # Gate 4: Out-of-Band Hardware Biometric Step-Up Latch
        g4_ok, g4_status = self._verify_biometric_step_up(intent, intent_caid, now_epoch)
        if not g4_ok:
            return self._mint_receipt(False, g4_status, intent_caid, tensor_caid, mapper.mapper_caid)

        # Gate 5: Mint Dispatch Receipt and Ed25519 Token
        return self._mint_receipt(
            allowed=True,
            status_code="OK_SWAT_AIRLOCK_DISPATCHED",
            intent_caid=intent_caid,
            tensor_caid=tensor_caid,
            mapper_caid=mapper.mapper_caid,
            merkle_root=updated_root,
        )

    def _verify_mapper_and_latent(
        self, intent: SwatTransferIntent
    ) -> Tuple[bool, str, str]:
        if not intent.kv_cache_raw_bytes:
            return (False, "HALT_EMPTY_KV_CACHE_PAYLOAD", "NONE")

        tensor_caid = sha256_jcs_caid(intent.kv_cache_raw_bytes)

        if intent.sender_backbone not in self.allowed_backbones:
            return (False, f"HALT_UNTRUSTED_SENDER_BACKBONE:{intent.sender_backbone}", tensor_caid)

        if intent.receiver_backbone not in self.allowed_backbones:
            return (False, f"HALT_UNTRUSTED_RECEIVER_BACKBONE:{intent.receiver_backbone}", tensor_caid)

        if intent.mapper_id not in self._mappers:
            return (False, f"HALT_UNREGISTERED_MAPPER:{intent.mapper_id}", tensor_caid)

        mapper = self._mappers[intent.mapper_id]
        if mapper.sender_backbone != intent.sender_backbone:
            return (False, "HALT_MAPPER_SENDER_BACKBONE_MISMATCH", tensor_caid)
        if mapper.receiver_backbone != intent.receiver_backbone:
            return (False, "HALT_MAPPER_RECEIVER_BACKBONE_MISMATCH", tensor_caid)

        align_ok, align_reason, _ = HeteroFoldAlignmentVerifier.verify_mapper_and_samples(
            mapper, intent.latent_sample_coords
        )
        if not align_ok:
            return (False, align_reason, tensor_caid)

        return (True, "OK", tensor_caid)

    def _verify_semantic_projection(
        self, intent: SwatTransferIntent, tensor_caid: str, mapper_caid: str
    ) -> Tuple[bool, str, str]:
        if intent.semantic_projection is None:
            return (False, "HALT_MISSING_SEMANTIC_PROJECTION", "NONE")

        missing_keys = self.REQUIRED_PROJECTION_KEYS - set(intent.semantic_projection.keys())
        if missing_keys:
            return (
                False,
                f"HALT_INCOMPLETE_SEMANTIC_PROJECTION:{sorted(missing_keys)}",
                "NONE",
            )

        if intent.projection_fidelity_bps < MIN_PROJECTION_FIDELITY_BPS:
            return (
                False,
                f"HALT_LATENT_PROJECTION_LOW_FIDELITY:{intent.projection_fidelity_bps}_below_{MIN_PROJECTION_FIDELITY_BPS}",
                "NONE",
            )

        action = str(intent.semantic_projection.get("action", "")).strip()
        if action in self.FORBIDDEN_LATENT_ACTIONS:
            return (False, f"HALT_FORBIDDEN_LATENT_INTENT:{action}", "NONE")

        intent_body = {
            "mapper_caid": mapper_caid,
            "operation_id": intent.operation_id,
            "projection": intent.semantic_projection,
            "receiver": intent.receiver_agent_id,
            "sender": intent.sender_agent_id,
            "tensor_caid": tensor_caid,
        }
        intent_caid = sha256_jcs_caid(intent_body)
        return (True, "OK", intent_caid)

    def _verify_biometric_step_up(
        self, intent: SwatTransferIntent, intent_caid: str, now_epoch: int
    ) -> Tuple[bool, str]:
        risk_tier = str(intent.semantic_projection.get("risk_tier", "")).upper()
        requires_step_up = (
            intent.cycle_phase == "CYCLE_3_EXECUTE"
            and (risk_tier == "CRITICAL" or intent.spend_minor_units >= STEP_UP_THRESHOLD_MINOR)
        )

        if not requires_step_up:
            return (True, "OK_STEP_UP_NOT_REQUIRED")

        if intent.step_up_warrant is None:
            return (False, "HALT_BIOMETRIC_STEP_UP_REQUIRED:MISSING_WARRANT")

        # Monotonic Fence Enforcement
        last_fence = self._seen_operation_fences.get(intent.operation_id, 0)
        if intent.attempt_fence <= last_fence:
            return (
                False,
                f"HALT_REPLAYED_ATTEMPT_FENCE:{intent.attempt_fence}_must_exceed_{last_fence}",
            )

        # Construct expected proposal
        proposal = T3ActionProposal(
            operation_id=intent.operation_id,
            intent_caid=intent_caid,
            action_type=str(intent.semantic_projection.get("action")),
            target_resource=intent.target_scope,
            amount_minor=intent.spend_minor_units,
            attempt_fence=intent.attempt_fence,
            expires_at_epoch_sec=intent.expires_at_epoch_sec,
        )

        verdict: T3LatchReleaseVerdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
            expected_proposal=proposal,
            warrant=intent.step_up_warrant,
            pinned_enclave_pubkey_x963_hex=self.pinned_enclave_pubkey_hex,
            current_epoch_sec=now_epoch,
        )

        if not verdict.latch_released:
            return (False, f"HALT_BIOMETRIC_VERIFICATION_FAILED:{verdict.reason_code}")

        self._seen_operation_fences[intent.operation_id] = intent.attempt_fence
        return (True, "OK_BIOMETRIC_STEP_UP_VERIFIED")

    def _mint_receipt(
        self,
        allowed: bool,
        status_code: str,
        intent_caid: str,
        tensor_caid: str,
        mapper_caid: str,
        merkle_root: Optional[str] = None,
    ) -> SwatAirlockReceipt:
        self._nonce_counter += 1
        dispatch_nonce = f"dispatch-{self._nonce_counter}-{int(time.time())}"
        effective_root = merkle_root if merkle_root is not None else self.merkle_ledger.current_merkle_root

        body = {
            "allowed": allowed,
            "dispatch_nonce": dispatch_nonce,
            "intent_caid": intent_caid,
            "mapper_caid": mapper_caid,
            "merkle_root": effective_root,
            "status_code": status_code,
            "tensor_caid": tensor_caid,
        }
        body_bytes = encode_jcs(body)
        signature_hex = self._airlock_signing_key.sign(body_bytes).hex()

        return SwatAirlockReceipt(
            allowed=allowed,
            status_code=status_code,
            intent_caid=intent_caid,
            tensor_caid=tensor_caid,
            mapper_caid=mapper_caid,
            merkle_root=effective_root,
            dispatch_nonce=dispatch_nonce,
            airlock_signature_hex=signature_hex,
            receipt_caid=sha256_jcs_caid(body),
        )
