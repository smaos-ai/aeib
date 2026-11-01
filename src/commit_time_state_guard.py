# Copyright 2026 SovereignNexus Project
#
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
src/commit_time_state_guard.py — Commit-Time Consistency Guard (BSC-R).

Implements Boundary-State Control for tool-using agents under state drift
(Wesley Shu, arXiv:2609.37475; IETF draft-das-agent-execution-finality-00).

Eliminates the 'proposal-to-commit gap' by evaluating whether the semantic
projection of authorization state has drifted between proposal time and commit time.
Fails closed if budget, epoch, taint tier, or destination state has drifted.
"""

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class AuthorizationStateProjection:
    """Immutable snapshot of authorization-relevant state dimensions."""
    tenant_id: str
    policy_epoch: int
    available_balance_minor: int
    max_single_spend_minor: int
    context_taint_tier: int  # 0=Clean, 1=Tainted, 2=Suspicious, 3=Quarantined
    target_uri_digest: str
    timestamp_ns: int

    def compute_digest(self) -> str:
        canonical = encode_jcs({
            "available_balance_minor": self.available_balance_minor,
            "context_taint_tier": self.context_taint_tier,
            "max_single_spend_minor": self.max_single_spend_minor,
            "policy_epoch": self.policy_epoch,
            "target_uri_digest": self.target_uri_digest,
            "tenant_id": self.tenant_id,
        })
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class CandidateAct:
    """A proposed action awaiting commit-time authorization verification."""
    caid: str
    tenant_id: str
    action_type: str
    amount_minor: int
    target_uri: str
    proposal_projection: AuthorizationStateProjection


@dataclass(frozen=True)
class CommitValidationResult:
    """Result of commit-time evaluation."""
    permitted: bool
    reason: str
    drift_detected: bool
    commit_token: Optional[str] = None


class CommitTimeStateGuard:
    """
    Evaluates candidate acts at the exact moment of wire dispatch.
    Enforces atomic commit-time consistency against the live system state.
    """

    @staticmethod
    def evaluate_commit(
        candidate: CandidateAct,
        current_state: AuthorizationStateProjection,
    ) -> CommitValidationResult:
        proposal = candidate.proposal_projection

        # 1. Tenant boundary check
        if candidate.tenant_id != current_state.tenant_id or proposal.tenant_id != current_state.tenant_id:
            return CommitValidationResult(
                permitted=False,
                reason="TENANT_MISMATCH: candidate act tenant does not match live state",
                drift_detected=True,
            )

        # 2. Policy epoch consistency
        if proposal.policy_epoch != current_state.policy_epoch:
            return CommitValidationResult(
                permitted=False,
                reason=f"POLICY_EPOCH_DRIFT: proposal epoch {proposal.policy_epoch} != live {current_state.policy_epoch}",
                drift_detected=True,
            )

        # 3. Context taint elevation check
        if current_state.context_taint_tier > proposal.context_taint_tier:
            return CommitValidationResult(
                permitted=False,
                reason=f"TAINT_ELEVATION_DRIFT: taint tier escalated from {proposal.context_taint_tier} to {current_state.context_taint_tier}",
                drift_detected=True,
            )

        # 4. Target endpoint integrity check
        expected_target_digest = hashlib.sha256(candidate.target_uri.encode("utf-8")).hexdigest()
        if expected_target_digest != current_state.target_uri_digest:
            return CommitValidationResult(
                permitted=False,
                reason="TARGET_URI_DRIFT: candidate target does not match authorized target digest",
                drift_detected=True,
            )

        # 5. Live solvency check (detects concurrent spend between proposal and commit)
        if current_state.available_balance_minor < candidate.amount_minor:
            return CommitValidationResult(
                permitted=False,
                reason=f"SOLVENCY_DRIFT: live balance {current_state.available_balance_minor} < requested {candidate.amount_minor}",
                drift_detected=True,
            )

        # 6. Single spend ceiling check
        if candidate.amount_minor > current_state.max_single_spend_minor:
            return CommitValidationResult(
                permitted=False,
                reason=f"CEILING_BREACH: requested {candidate.amount_minor} > ceiling {current_state.max_single_spend_minor}",
                drift_detected=False,
            )

        # All checks passed: compute commit token binding act CAID and live state digest
        binding_payload = encode_jcs({
            "caid": candidate.caid,
            "live_state_digest": current_state.compute_digest(),
            "status": "AUTHORIZATION_LOCKED",
        })
        commit_token = f"commit:{hashlib.sha256(binding_payload).hexdigest()}"

        return CommitValidationResult(
            permitted=True,
            reason="COMMIT_AUTHORIZED: state projection consistent; single-use token issued",
            drift_detected=False,
            commit_token=commit_token,
        )
