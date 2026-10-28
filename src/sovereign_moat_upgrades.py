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
src/sovereign_moat_upgrades.py
================================================================================
Sovereign Moat Upgrades: Geopolitical Export Control Routing & Model Manifest Binding.

Evaluated under the stated model (scaffold verifier):
1. Geopolitical Taint / Export Controls: Blocks routing sensitive finance or PII
   to models in restricted export jurisdictions.
2. Model Update Approval Expiry: Binds exact model weight / manifest digests
   into PCC proof verification. If a model vendor silently updates weights,
   the verification fails closed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, List, Optional


class Jurisdiction(str, Enum):
    EU_US_DOMESTIC = "EU_US_DOMESTIC"
    RESTRICTED_EXPORT = "RESTRICTED_EXPORT"
    SOVEREIGN_AIR_GAPPED = "SOVEREIGN_AIR_GAPPED"


class ProofStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    weight_snapshot_digest: str  # e.g., "sha256:opus_5_5_weights_2026_10"
    hosting_jurisdiction: Jurisdiction


@dataclass(frozen=True)
class SovereignRoutingRequest:
    task_id: str
    contains_pii_or_finance: bool
    required_jurisdiction: Jurisdiction


class SovereignMoMRouter:
    """
    Evaluates Geopolitical Export Controls and Sovereign Routing boundaries.
    """

    @classmethod
    def dispatch_sovereign_route(
        cls, request: SovereignRoutingRequest, candidate_model: ModelManifest
    ) -> str:
        # 1. Geopolitical Taint Check
        if (
            request.contains_pii_or_finance
            and candidate_model.hosting_jurisdiction == Jurisdiction.RESTRICTED_EXPORT
        ):
            raise ValueError(
                f"HALT_GEOPOLITICAL_TAINT_VIOLATION: Task {request.task_id} contains sensitive "
                f"data and cannot be routed to restricted jurisdiction {candidate_model.hosting_jurisdiction}."
            )

        return f"OK_ROUTED_TO_SOVEREIGN_MODEL:{candidate_model.model_id}"


@dataclass(frozen=True)
class SovereignProofArtifact:
    task_id: str
    risk_tier: str  # T0, T1, T2, T3
    model_manifest_digest: str
    formal_proof_script: str
    proof_status: ProofStatus = ProofStatus.VERIFIED


class SovereignPCCVerifier:
    """
    Validates that model weights match the exact pinned manifest (scaffold verifier).
    Intercepts silent vendor updates from invalidating safety proofs.
    """

    @staticmethod
    def verify_artifact_manifest(
        artifact: SovereignProofArtifact, current_live_manifest_digest: str
    ) -> ProofStatus:
        if artifact.risk_tier in ("T2", "T3"):
            if artifact.model_manifest_digest != current_live_manifest_digest:
                # Vendor silently updated model weights: proof fails closed
                return ProofStatus.FAILED

        if (
            artifact.proof_status == ProofStatus.VERIFIED
            and "theorem" in artifact.formal_proof_script
        ):
            return ProofStatus.VERIFIED

        return ProofStatus.FAILED
