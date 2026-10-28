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
tests/test_sovereign_moat_upgrades.py
================================================================================
Falsification Suite for Sovereign Moat Upgrades.
Evaluates geopolitical export control routing and model weight manifest binding.
"""

from __future__ import annotations

import pytest
from src.sovereign_moat_upgrades import (
    Jurisdiction,
    ModelManifest,
    ProofStatus,
    SovereignMoMRouter,
    SovereignPCCVerifier,
    SovereignProofArtifact,
    SovereignRoutingRequest,
)


def test_geopolitical_taint_routing_block() -> None:
    """Sensitive finance task routed to a restricted jurisdiction MUST HALT."""
    req = SovereignRoutingRequest(
        task_id="fin-wire-01",
        contains_pii_or_finance=True,
        required_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    restricted_model = ModelManifest(
        model_id="qwen-foreign-node",
        weight_snapshot_digest="sha256:weights_v1",
        hosting_jurisdiction=Jurisdiction.RESTRICTED_EXPORT,
    )

    with pytest.raises(ValueError, match="HALT_GEOPOLITICAL_TAINT_VIOLATION"):
        SovereignMoMRouter.dispatch_sovereign_route(req, restricted_model)


def test_sovereign_routing_success_domestic() -> None:
    """Domestic compliant route succeeds and returns model routing string."""
    req = SovereignRoutingRequest(
        task_id="fin-wire-02",
        contains_pii_or_finance=True,
        required_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    domestic_model = ModelManifest(
        model_id="claude-opus-domestic",
        weight_snapshot_digest="sha256:weights_domestic_v1",
        hosting_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    route = SovereignMoMRouter.dispatch_sovereign_route(req, domestic_model)
    assert route == "OK_ROUTED_TO_SOVEREIGN_MODEL:claude-opus-domestic"


def test_sovereign_routing_non_sensitive_to_restricted_allowed() -> None:
    """Non-sensitive public task can route without geopolitical halt."""
    req = SovereignRoutingRequest(
        task_id="pub-task-01",
        contains_pii_or_finance=False,
        required_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    model = ModelManifest(
        model_id="qwen-foreign-node",
        weight_snapshot_digest="sha256:weights_v1",
        hosting_jurisdiction=Jurisdiction.RESTRICTED_EXPORT,
    )
    route = SovereignMoMRouter.dispatch_sovereign_route(req, model)
    assert route == "OK_ROUTED_TO_SOVEREIGN_MODEL:qwen-foreign-node"


def test_model_weight_update_invalidates_proof_t3() -> None:
    """If vendor silently updates model weights, PCC verification MUST fail on T3."""
    original_digest = "sha256:opus_weights_v1"
    silently_updated_digest = "sha256:opus_weights_v2_stealth_update"

    artifact = SovereignProofArtifact(
        task_id="t3-auth-01",
        risk_tier="T3",
        model_manifest_digest=original_digest,
        formal_proof_script="theorem safe : True := by trivial",
        proof_status=ProofStatus.VERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(
        artifact, silently_updated_digest
    )
    assert status == ProofStatus.FAILED


def test_model_weight_update_invalidates_proof_t2() -> None:
    """If vendor silently updates model weights, PCC verification MUST fail on T2."""
    original_digest = "sha256:argon_weights_v1"
    silently_updated_digest = "sha256:argon_weights_v2_stealth_update"

    artifact = SovereignProofArtifact(
        task_id="t2-auth-01",
        risk_tier="T2",
        model_manifest_digest=original_digest,
        formal_proof_script="theorem safe_t2 : True := by trivial",
        proof_status=ProofStatus.VERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(
        artifact, silently_updated_digest
    )
    assert status == ProofStatus.FAILED


def test_matching_model_manifest_verifies_t3() -> None:
    """When model manifest digest matches and proof script has theorem, proof succeeds."""
    pinned_digest = "sha256:opus_weights_v1"

    artifact = SovereignProofArtifact(
        task_id="t3-auth-02",
        risk_tier="T3",
        model_manifest_digest=pinned_digest,
        formal_proof_script="theorem verified_math : True := by trivial",
        proof_status=ProofStatus.VERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(artifact, pinned_digest)
    assert status == ProofStatus.VERIFIED


def test_t0_t1_bypasses_model_manifest_check() -> None:
    """T0 and T1 tasks bypass model manifest equality check but still require theorem."""
    original_digest = "sha256:flash_weights_v1"
    new_digest = "sha256:flash_weights_v2"

    artifact = SovereignProofArtifact(
        task_id="t1-task-01",
        risk_tier="T1",
        model_manifest_digest=original_digest,
        formal_proof_script="theorem trivial_t1 : True := by trivial",
        proof_status=ProofStatus.VERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(artifact, new_digest)
    assert status == ProofStatus.VERIFIED


def test_proof_without_theorem_keyword_fails() -> None:
    """Proof script lacking theorem keyword fails closed."""
    digest = "sha256:weights_v1"
    artifact = SovereignProofArtifact(
        task_id="t3-auth-03",
        risk_tier="T3",
        model_manifest_digest=digest,
        formal_proof_script="def foo := 42",
        proof_status=ProofStatus.VERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(artifact, digest)
    assert status == ProofStatus.FAILED


def test_unverified_proof_status_fails() -> None:
    """Proof artifact with unverified status fails closed."""
    digest = "sha256:weights_v1"
    artifact = SovereignProofArtifact(
        task_id="t3-auth-04",
        risk_tier="T3",
        model_manifest_digest=digest,
        formal_proof_script="theorem safe : True := by trivial",
        proof_status=ProofStatus.UNVERIFIED,
    )

    status = SovereignPCCVerifier.verify_artifact_manifest(artifact, digest)
    assert status == ProofStatus.FAILED


def test_dataclasses_frozen_immutability() -> None:
    """Verifies that all sovereign data transfer structures are strictly immutable."""
    import dataclasses

    manifest = ModelManifest(
        model_id="test-model",
        weight_snapshot_digest="sha256:weights",
        hosting_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.model_id = "mutated"  # type: ignore

    req = SovereignRoutingRequest(
        task_id="req-1",
        contains_pii_or_finance=True,
        required_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.task_id = "mutated"  # type: ignore

    artifact = SovereignProofArtifact(
        task_id="art-1",
        risk_tier="T3",
        model_manifest_digest="sha256:d",
        formal_proof_script="theorem safe : True",
        proof_status=ProofStatus.VERIFIED,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.task_id = "mutated"  # type: ignore

