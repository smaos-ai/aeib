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
src/pre_tool_use_chain.py
================================================================================
Pre-Tool Use Interception Hook Chain (Osprey ALS Pattern).

Evaluated under the stated model (scaffold verifier):
Implements a multi-stage deterministic pre-execution boundary interceptor:
1. Kill Switch Stage: Blocks write dispatches when global or tenant-level writes are halted.
2. Parameter Limit Stage: Enforces strict bound checking on tool arguments.
3. Biometric HITL Approval Stage: Enforces physiological zero-trust verification for T3 actions.
4. Pre-Execution Review Generator: Formats deterministic, read-only scripts for human inspection.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

try:
    from src.biometric_hitl_gate import (
        AdjudicationVerdict,
        BiometricAdjudicationReceipt,
        BiometricHITLGate,
        BiometricTelemetry,
        T3ApprovalRequest,
    )
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from biometric_hitl_gate import (  # type: ignore[no-redef]
        AdjudicationVerdict,
        BiometricAdjudicationReceipt,
        BiometricHITLGate,
        BiometricTelemetry,
        T3ApprovalRequest,
    )
    from jcs_canonicalizer import encode_jcs  # type: ignore[no-redef]


@dataclass(frozen=True)
class ToolCallIntent:
    """Pre-dispatch description of tool invocation intent."""

    tool_name: str
    arguments: Mapping[str, Any]
    tenant_id: str
    risk_tier: str  # e.g. "T1", "T2", "T3"
    is_write: bool
    agent_id: str
    capability_id: str = ""

    def canonical_act_digest(self) -> str:
        """
        sha256 over RFC 8785 JCS of the full act, INCLUDING arguments, so an
        approval cannot be reused for a call whose arguments were substituted
        after approval (AGENTS.md section 2, post-approval substitution binding).
        """
        payload = {
            "agent_id": self.agent_id,
            "arguments": dict(self.arguments),
            "capability_id": self.capability_id,
            "is_write": self.is_write,
            "risk_tier": self.risk_tier,
            "tenant_id": self.tenant_id,
            "tool_name": self.tool_name,
        }
        return f"sha256:{hashlib.sha256(encode_jcs(payload)).hexdigest()}"


@dataclass(frozen=True)
class HookExecutionVerdict:
    """Structured outcome returned by pre-tool hook evaluation chain."""

    passed: bool
    reason_code: str
    stage: str
    adjudication_receipt: Optional[BiometricAdjudicationReceipt] = None
    execution_review: Optional[str] = None


class PreToolUseHookChain:
    """
    Coordinates pre-dispatch gating stages inspired by the Berkeley Lab ALS
    Osprey control plane architecture.
    """

    def __init__(
        self,
        global_writes_enabled: bool = True,
        tenant_writes_disabled: Optional[Sequence[str]] = None,
        argument_limits: Optional[Dict[str, Dict[str, Tuple[float, float]]]] = None,
        signing_key: Optional[Ed25519PrivateKey] = None,
        historical_urgency_rate: float = 0.10,  # claim: config
    ) -> None:
        self.global_writes_enabled: bool = global_writes_enabled
        self.tenant_writes_disabled: FrozenSet[str] = (
            frozenset(tenant_writes_disabled) if tenant_writes_disabled else frozenset()
        )
        self.argument_limits: Dict[str, Dict[str, Tuple[float, float]]] = (
            argument_limits if argument_limits is not None else {}
        )
        self.signing_key: Optional[Ed25519PrivateKey] = signing_key
        self.historical_urgency_rate: float = historical_urgency_rate

    def check_kill_switch(self, intent: ToolCallIntent) -> Tuple[bool, str]:
        """
        Stage 1: Evaluates write authorization against global and tenant kill switches.
        """
        if not intent.is_write:
            return True, "OK_READ_ONLY_CALL"

        if not self.global_writes_enabled:
            return False, "HALT_GLOBAL_WRITE_DISABLED"

        if intent.tenant_id in self.tenant_writes_disabled:
            return False, "HALT_TENANT_WRITE_DISABLED"

        return True, "OK_KILL_SWITCH_OPEN"

    def check_limits(self, intent: ToolCallIntent) -> Tuple[bool, str]:
        """
        Stage 2: Validates argument ranges against configured threshold envelopes.
        """
        if intent.tool_name not in self.argument_limits:
            return True, "OK_NO_LIMITS_CONFIGURED"

        limits = self.argument_limits[intent.tool_name]
        for param, (min_v, max_v) in limits.items():
            if param in intent.arguments:
                val = intent.arguments[param]
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    return False, "ERR_LIMIT_TYPE_INVALID"
                if val < min_v or val > max_v:
                    return False, "HALT_ARGUMENT_OUT_OF_BOUNDS"

        return True, "OK_LIMITS_SATISFIED"

    def check_approval(
        self,
        intent: ToolCallIntent,
        telemetry: Optional[BiometricTelemetry] = None,
        agent_claimed_urgency: bool = False,
        human_intent_hash: str = "",
        timestamp_ns: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[BiometricAdjudicationReceipt]]:
        """
        Stage 3: Evaluates physiological zero-trust verification for T3 actions.
        """
        if intent.risk_tier != "T3":
            return True, "OK_TIER_EXEMPT_FROM_BIOMETRIC_GATE", None

        # Derive action digest over the full act (arguments included)
        action_digest = intent.canonical_act_digest()

        req = T3ApprovalRequest(
            action_digest=action_digest,
            risk_tier="T3",
            agent_claimed_urgency=agent_claimed_urgency,
            human_intent_hash=human_intent_hash,
        )

        verdict = BiometricHITLGate.evaluate_adjudication_capacity(
            request=req,
            telemetry=telemetry,
            historical_urgency_rate=self.historical_urgency_rate,
        )

        ts = timestamp_ns if timestamp_ns is not None else time.time_ns()
        receipt = BiometricHITLGate.mint_adjudication_receipt(
            request=req,
            telemetry=telemetry,
            verdict=verdict,
            timestamp_ns=ts,
            signing_key=self.signing_key,
        )

        if verdict == AdjudicationVerdict.ALLOW_T3_APPROVAL:
            return True, "OK_BIOMETRIC_APPROVAL_GRANTED", receipt

        return False, verdict.value, receipt

    @staticmethod
    def verify_dispatch_binding(
        intent: ToolCallIntent,
        receipt: Optional[BiometricAdjudicationReceipt],
        trusted_issuer_public_key_hex: str,
    ) -> Tuple[bool, str]:
        """
        Dispatch-time re-check: the call about to be dispatched must hash to the
        exact digest that was approved, the receipt must be an ALLOW verdict, and
        it must be signed by the pinned issuer key (not a key the receipt carries
        for itself). Fails closed on any mismatch.
        """
        if receipt is None:
            return False, "HALT_MISSING_APPROVAL_RECEIPT"
        if receipt.verdict != AdjudicationVerdict.ALLOW_T3_APPROVAL:
            return False, "HALT_RECEIPT_NOT_ALLOW"
        if receipt.issuer_public_key_hex != trusted_issuer_public_key_hex:
            return False, "HALT_UNPINNED_RECEIPT_ISSUER"
        if not receipt.verify_signature():
            return False, "HALT_RECEIPT_SIGNATURE_INVALID"
        if receipt.action_digest != intent.canonical_act_digest():
            return False, "HALT_POST_APPROVAL_SUBSTITUTION"
        return True, "OK_DISPATCH_BOUND_TO_APPROVED_ACT"

    def generate_pre_execution_review(self, intent: ToolCallIntent) -> str:
        """
        Stage 4: Formats a deterministic read-only script inspection summary.
        """
        arg_dict = dict(intent.arguments)
        canonical_args = encode_jcs(arg_dict).decode("utf-8")
        review_lines = [
            "# === OSPREY ALS PRE-EXECUTION REVIEW SCRIPT ===",
            f"# Tool:      {intent.tool_name}",
            f"# Tenant:    {intent.tenant_id}",
            f"# Agent:     {intent.agent_id}",
            f"# Risk Tier: {intent.risk_tier}",
            f"# Write Op:  {intent.is_write}",
            f"# Arguments: {canonical_args}",
            f"# Act digest: {intent.canonical_act_digest()}",
            "# Status:    READY FOR OPERATOR ATTESTATION",
            "# ===============================================",
        ]
        return "\n".join(review_lines)

    def evaluate_chain(
        self,
        intent: ToolCallIntent,
        telemetry: Optional[BiometricTelemetry] = None,
        agent_claimed_urgency: bool = False,
        human_intent_hash: str = "",
        timestamp_ns: Optional[int] = None,
    ) -> HookExecutionVerdict:
        """
        Executes full pre-tool use interception chain in fail-closed order.
        """
        # 1. Kill switch
        ks_ok, ks_reason = self.check_kill_switch(intent)
        if not ks_ok:
            return HookExecutionVerdict(
                passed=False,
                reason_code=ks_reason,
                stage="KILL_SWITCH",
                adjudication_receipt=None,
                execution_review=None,
            )

        # 2. Argument limits
        lim_ok, lim_reason = self.check_limits(intent)
        if not lim_ok:
            return HookExecutionVerdict(
                passed=False,
                reason_code=lim_reason,
                stage="LIMITS",
                adjudication_receipt=None,
                execution_review=None,
            )

        # 3. Biometric HITL approval
        app_ok, app_reason, receipt = self.check_approval(
            intent=intent,
            telemetry=telemetry,
            agent_claimed_urgency=agent_claimed_urgency,
            human_intent_hash=human_intent_hash,
            timestamp_ns=timestamp_ns,
        )
        if not app_ok:
            return HookExecutionVerdict(
                passed=False,
                reason_code=app_reason,
                stage="APPROVAL",
                adjudication_receipt=receipt,
                execution_review=None,
            )

        # 4. Operator Review generation
        review = self.generate_pre_execution_review(intent)
        return HookExecutionVerdict(
            passed=True,
            reason_code="OK_PRE_TOOL_USE_PASSED",
            stage="DISPATCH_READY",
            adjudication_receipt=receipt,
            execution_review=review,
        )
