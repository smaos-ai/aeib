#!/usr/bin/env python3
"""
src/opencode_and_mcp_codemode_engine.py

AEIB OpenCode 2.0 & MCP Code Mode Execution Boundary Engine
Addresses runtime bypass vectors identified in late-2026 agent frameworks:
- AT67: MCP Code Mode Composite Script Interlock (High-Water-Mark Taint & Cumulative Spend).
- AT68: Mid-Session Self-Authored Hot-Reload Plugin Rejection (Pre-session registry freeze).
- AT69: Zero-Token System-1 Decision Governance + 4-Dimension Governance Accountability Binding
  (Ownership, Decision-Making, Challenge & Assurance, Practical Implementation).

Evaluated under the stated model. Uses RFC 8785 JCS and real Ed25519 asymmetric signatures.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

TIER_RANK = {
    "TIER_0_PINNED": 0,
    "TIER_1_INTERNAL_DB": 1,
    "TIER_2_UNTRUSTED_EXTERNAL": 2,
}


def sha256_prefixed(data: bytes) -> str:
    """Computes a sha256:-prefixed lowercase hexadecimal digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class SignedPluginManifest:
    """Cryptographically pinned plugin manifest signed by an offline human publisher."""

    plugin_id: str
    code_sha256: str
    registered_at_ns: int
    signer_key_id: str
    signature_b64: str


@dataclass(frozen=True)
class FourDimensionGovernanceRecord:
    """
    Binds the 4 core dimensions of AI operational governance:
    1. Ownership: Accountable human supervisor / role sponsor.
    2. Decision-Making: Authority artifact / policy delegation certificate.
    3. Challenge & Assurance: SCITT inclusion proof / cryptographic receipt hash.
    4. Practical Implementation: Observable runtime boundary verdict.
    """

    ownership_sponsor_id: str
    decision_authority_cert_id: str
    assurance_scitt_receipt_hash: str
    implementation_gate_verdict: str

    def to_canonical_dict(self) -> Dict[str, str]:
        return {
            "assurance_scitt_receipt_hash": self.assurance_scitt_receipt_hash,
            "decision_authority_cert_id": self.decision_authority_cert_id,
            "implementation_gate_verdict": self.implementation_gate_verdict,
            "ownership_sponsor_id": self.ownership_sponsor_id,
        }


class CodeModeAndHotReloadGate:
    """
    AEIB Out-of-process Station 1 Execution Boundary:
    - Defends against MCP Code Mode composite script taint propagation (AT67).
    - Defends against mid-session self-written hot-reloaded plugins (AT68).
    - Defends against zero-token System-1 classification actions (AT69).
    """

    def __init__(
        self,
        session_start_ns: int,
        human_publisher_pubkey: Ed25519PublicKey,
        human_publisher_key_id: str,
        sprint_limit_minor: int = 1000_00,
    ) -> None:
        self.session_start_ns = session_start_ns
        self.human_publisher_pubkey = human_publisher_pubkey
        self.human_publisher_key_id = human_publisher_key_id
        self.sprint_limit_minor = sprint_limit_minor
        self._pinned_plugins: Dict[str, SignedPluginManifest] = {}
        self.session_high_water_taint: str = "TIER_0_PINNED"
        self.session_spent_minor: int = 0
        self.blocked_mutation_count: int = 0
        self.dispatched_mutation_count: int = 0

    def register_plugin(
        self, manifest: SignedPluginManifest, live_code_bytes: bytes
    ) -> Tuple[bool, Optional[str]]:
        """
        AT68: Enforces pre-session freeze and offline human publisher signature.
        Rejects any plugin registered after session_start_ns or signed by the agent itself.
        """
        if manifest.registered_at_ns > self.session_start_ns:
            return False, "HALT_MID_SESSION_HOT_RELOAD_FORBIDDEN"

        if manifest.signer_key_id != self.human_publisher_key_id:
            return False, "HALT_SELF_AUTHORED_AGENT_PLUGIN_FORBIDDEN"

        actual_sha = sha256_prefixed(live_code_bytes)
        if actual_sha != manifest.code_sha256:
            return False, "HALT_PLUGIN_CODE_HASH_MISMATCH"

        payload = encode_jcs(
            {
                "code_sha256": manifest.code_sha256,
                "plugin_id": manifest.plugin_id,
                "registered_at_ns": manifest.registered_at_ns,
                "signer_key_id": manifest.signer_key_id,
            }
        )
        try:
            self.human_publisher_pubkey.verify(
                base64.b64decode(manifest.signature_b64), payload
            )
        except (InvalidSignature, ValueError):
            return False, "HALT_INVALID_PUBLISHER_SIGNATURE"

        self._pinned_plugins[manifest.plugin_id] = manifest
        return True, None

    def execute_mcp_codemode_step(
        self,
        plugin_id: str,
        step_type: str,
        data_tier: str,
        amount_minor: int = 0,
        pinned_known_recipient: bool = True,
    ) -> Dict[str, Any]:
        """
        AT67: Evaluates an atomic tool step inside a composite MCP Code Mode script.
        Propagates high-water-mark taint across the entire script lifecycle.
        """
        if plugin_id not in self._pinned_plugins:
            self.blocked_mutation_count += 1
            return {
                "disposition": "NOT_DISPATCHED",
                "rejection_code": "HALT_UNREGISTERED_OR_HOT_RELOADED_PLUGIN",
            }

        if TIER_RANK[data_tier] > TIER_RANK[self.session_high_water_taint]:
            self.session_high_water_taint = data_tier

        if step_type == "READ":
            return {
                "disposition": "READ_OBSERVED",
                "session_taint": self.session_high_water_taint,
            }

        if (
            self.session_high_water_taint == "TIER_2_UNTRUSTED_EXTERNAL"
            and not pinned_known_recipient
        ):
            self.blocked_mutation_count += 1
            return {
                "disposition": "NOT_DISPATCHED",
                "rejection_code": "HALT_CODEMODE_SCRIPT_TAINT_PROPAGATED",
            }

        if (self.session_spent_minor + amount_minor) > self.sprint_limit_minor:
            self.blocked_mutation_count += 1
            return {
                "disposition": "NOT_DISPATCHED",
                "rejection_code": "HALT_CODEMODE_CUMULATIVE_SPRINT_EXCEEDED",
            }

        self.session_spent_minor += amount_minor
        self.dispatched_mutation_count += 1
        return {
            "disposition": "DISPATCHED",
            "rejection_code": None,
            "session_spent_minor": self.session_spent_minor,
        }

    def evaluate_zero_token_system1_action(
        self,
        *,
        operation_id: str,
        plugin_id: str,
        discrete_option_id: int,
        scalar_amount_minor: int,
        spatial_target_xy: Tuple[float, float],
        answer_tokens_emitted: int,
        ownership_sponsor_id: str,
        decision_authority_cert_id: str,
        gate_signer: Ed25519PrivateKey,
        pinned_known_recipient: bool = True,
    ) -> Dict[str, Any]:
        """
        AT69: Governs zero-token System-1 classification actions (MJev-Spatial),
        binding 4-dimension governance accountability and measuring what changed
        as a result of boundary intervention.
        """
        if not ownership_sponsor_id or not decision_authority_cert_id:
            self.blocked_mutation_count += 1
            return {
                "disposition": "NOT_DISPATCHED",
                "rejection_code": "HALT_MISSING_4D_GOVERNANCE_BINDING",
            }

        step_res = self.execute_mcp_codemode_step(
            plugin_id=plugin_id,
            step_type="FINANCIAL_MUTATION",
            data_tier=self.session_high_water_taint,
            amount_minor=scalar_amount_minor,
            pinned_known_recipient=pinned_known_recipient,
        )
        verdict = step_res["disposition"]
        action_caid = sha256_prefixed(
            encode_jcs(
                {
                    "answer_tokens_emitted": answer_tokens_emitted,
                    "discrete_option_id": discrete_option_id,
                    "operation_id": operation_id,
                    "plugin_id": plugin_id,
                    "scalar_amount_minor": scalar_amount_minor,
                    "spatial_target_xy": [
                        round(spatial_target_xy[0], 4),
                        round(spatial_target_xy[1], 4),
                    ],
                }
            )
        )
        scitt_leaf_hash = sha256_prefixed(
            b"\x00"
            + encode_jcs(
                {
                    "action_caid": action_caid,
                    "operation_id": operation_id,
                    "verdict": verdict,
                }
            )
        )
        gov_record = FourDimensionGovernanceRecord(
            ownership_sponsor_id=ownership_sponsor_id,
            decision_authority_cert_id=decision_authority_cert_id,
            assurance_scitt_receipt_hash=scitt_leaf_hash,
            implementation_gate_verdict=verdict,
        )
        envelope = {
            "action_caid": action_caid,
            "answer_tokens_emitted": answer_tokens_emitted,
            "disposition": verdict,
            "four_dimension_governance": gov_record.to_canonical_dict(),
            "operation_id": operation_id,
            "rejection_code": step_res.get("rejection_code"),
            "what_changed_as_a_result": {
                "blocked_mutation_count": self.blocked_mutation_count,
                "dispatched_mutation_count": self.dispatched_mutation_count,
                "session_spent_minor": self.session_spent_minor,
            },
        }
        sig = gate_signer.sign(encode_jcs(envelope))
        envelope["gate_signature_b64"] = base64.b64encode(sig).decode("ascii")
        return envelope
