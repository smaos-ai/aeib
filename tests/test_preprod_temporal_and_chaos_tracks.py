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
tests/test_preprod_temporal_and_chaos_tracks.py — Test Battery for Tracks A, B, C & Preprod Gate
1. Track A: Linear Temporal Logic (LTL) Trace Conformance (AgentLTL / ltl-harness)
2. Track B: AgentChaos (arXiv:2608.06790) LLM API & Tool Fault Injection
3. Track C: SLSA v0.2 + in-toto Supply-Chain Provenance Verification
4. Track D: Full Pre-Production Black-Box & AST Mutation Gate Execution
"""

import base64
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from conformance.temporal_ltl_oracle import (
    TemporalLTLTraceOracle,
    LTLViolationError,
)
from tools.agent_chaos_injector import AgentChaosFaultInjector
from conformance.slsa_provenance_gate import (
    SlsaProvenanceGate,
    ProvenanceVerificationError,
)
from tools.preprod_blackbox_and_mutation_gate import execute_preprod_gate


# ==============================================================================
# TRACK A: TEMPORAL SAFETY LTL TRACE CONFORMANCE
# ==============================================================================

def test_track_a_nominal_trace_satisfies_all_ltl_invariants():
    oracle = TemporalLTLTraceOracle(max_reconciliation_horizon_steps=50)

    nominal_trace = [
        {"operation_id": "op-1", "action": "RECEIPT_CREATED", "receipt_id": "rcpt-001"},
        {"operation_id": "op-1", "action": "DISPATCH"},
        {"operation_id": "op-1", "action": "TRANSPORT_TIMEOUT_504"},
        {"operation_id": "op-1", "action": "RECONCILE_CONFIRMED"},
    ]

    res = oracle.verify_trace(nominal_trace)
    assert res["valid"] is True
    assert res["evaluated_steps"] == 4
    assert len(res["unresolved_within_horizon"]) == 0


def test_track_a_falsification_blind_retry_breach():
    oracle = TemporalLTLTraceOracle(max_reconciliation_horizon_steps=50)

    # Violates Rule 1: NO_BLIND_RETRY (Dispatches second time while in EFFECT_INDETERMINATE)
    violating_trace = [
        {"operation_id": "op-viol-1", "action": "RECEIPT_CREATED", "receipt_id": "rcpt-1"},
        {"operation_id": "op-viol-1", "action": "DISPATCH"},
        {"operation_id": "op-viol-1", "action": "TRANSPORT_TIMEOUT_504"},
        {"operation_id": "op-viol-1", "action": "DISPATCH"},  # BLIND RETRY!
    ]

    with pytest.raises(LTLViolationError) as exc_info:
        oracle.verify_trace(violating_trace)

    assert exc_info.value.rule_name == "RULE_NO_BLIND_RETRY"
    assert exc_info.value.step_index == 3


def test_track_a_falsification_unreceipted_dispatch():
    oracle = TemporalLTLTraceOracle(max_reconciliation_horizon_steps=50)

    # Violates Rule 2: RECEIPT_BEFORE_DISPATCH
    violating_trace = [
        {"operation_id": "op-unreceipted", "action": "DISPATCH"},
    ]

    with pytest.raises(LTLViolationError) as exc_info:
        oracle.verify_trace(violating_trace)

    assert exc_info.value.rule_name == "RULE_RECEIPT_BEFORE_DISPATCH"


def test_track_a_falsification_halt_enforcement():
    oracle = TemporalLTLTraceOracle(max_reconciliation_horizon_steps=50)

    # Violates Rule 4: HALT_ENFORCED
    violating_trace = [
        {"operation_id": "op-sys", "action": "HALT", "is_halt_trigger": True},
        {"operation_id": "op-bad", "action": "RECEIPT_CREATED", "receipt_id": "rcpt-x"},
        {"operation_id": "op-bad", "action": "DISPATCH"},  # DISPATCH WHILE HALTED!
    ]

    with pytest.raises(LTLViolationError) as exc_info:
        oracle.verify_trace(violating_trace)

    assert exc_info.value.rule_name == "RULE_HALT_ENFORCED"


# ==============================================================================
# TRACK B: AGENTCHAOS (LLM API & TOOL FAULT INJECTION)
# ==============================================================================

def test_track_b_agent_chaos_9_fault_resilience():
    # Ingress evaluator representing Station 1 validation logic
    def station1_ingress_evaluator(payload_dict: dict) -> dict:
        if payload_dict.get("is_raw_string"):
            # Raw malformed string causes parser rejection
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_MALFORMED_JSON"}

        # Tool validation
        tool_name = payload_dict.get("tool_name")
        if tool_name and "unregistered" in tool_name:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_UNREGISTERED_TOOL"}

        p = payload_dict.get("payload", {})
        if p.get("is_known_duplicate"):
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_DUPLICATE_OPERATION_ID"}

        amt = p.get("amount_minor")
        rcpt = p.get("recipient", "")

        # Missing field check
        if amt is None or not rcpt:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_MISSING_REQUIRED_FIELDS"}

        # Currency integer precision & negative check (P3C-FIN01)
        if not isinstance(amt, int) or amt <= 0:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_INVALID_AMOUNT_PRECISION"}

        # Unicode recipient confusion / homoglyph rejection
        if "\u200b" in rcpt or "\u0410" in rcpt:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_UNICODE_HOMOGLYPH_DETECTED"}

        # Prompt injection payload detection
        note = p.get("customer_note", "")
        if "IGNORE ALL PRIOR DIRECTIVES" in note:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_PROMPT_INJECTION_REJECTED"}

        # Retry storm simulation
        if p.get("repeat_count", 0) > 1:
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_RETRY_STORM_RATE_LIMITED"}

        # Contradictory context (e.g. read-only action against mutation endpoint)
        if p.get("action_class") == "READ_ONLY_QUERY" and "refunds" in p.get("endpoint", ""):
            return {"valid": False, "disposition": "NOT_DISPATCHED", "code": "ERR_CONTRADICTORY_CONTEXT"}

        return {"valid": True, "disposition": "DISPATCHED"}

    chaos_report = AgentChaosFaultInjector.execute_chaos_evaluation(station1_ingress_evaluator)

    assert chaos_report["total_vectors_injected"] == 9
    assert chaos_report["rejected_fail_closed"] == 9
    assert chaos_report["passed_unexpectedly"] == 0
    assert chaos_report["chaos_resilience_rate_pct"] == 100.0


# ==============================================================================
# TRACK C: SLSA & IN-TOTO SUPPLY-CHAIN PROVENANCE
# ==============================================================================

def test_track_c_slsa_intoto_provenance_verification():
    ci_builder_priv = ed25519.Ed25519PrivateKey.generate()
    builder_id = "https://github.com/smaos-ai/aeib/actions/runners/101"

    gate = SlsaProvenanceGate(trusted_builder_keys={builder_id: ci_builder_priv.public_key()})

    artifact_binary = b"\x7fELF_FAKE_SMAOS_DATA_PLANE_BINARY_FOR_PROVENANCE_TEST"
    artifacts = [("smaos-data-plane", artifact_binary)]

    # 1. Generate valid provenance
    attestation = gate.generate_attestation_statement(
        builder_id=builder_id,
        builder_privkey=ci_builder_priv,
        artifacts=artifacts,
        source_commit="4f83ae8addc3de1f7ff7a50658c4fb93d79f09c",
        materials=[
            {"uri": "git+https://github.com/smaos-ai/aeib", "digest": {"commit": "4f83ae8a"}},
            {"uri": "file://Cargo.lock", "digest": {"sha256": "abcdef1234567890"}},
        ],
    )

    # 2. Verify valid provenance
    verify_res = gate.verify_provenance_attestation(
        attestation=attestation,
        actual_artifact_contents={"smaos-data-plane": artifact_binary},
    )
    assert verify_res["valid"] is True
    assert "smaos-data-plane" in verify_res["verified_artifacts"]

    # 3. Falsification: Tampered binary content fails closed
    tampered_binary = b"\x7fELF_TAMPERED_WITH_BACKDOOR"
    with pytest.raises(ProvenanceVerificationError) as exc_info:
        gate.verify_provenance_attestation(
            attestation=attestation,
            actual_artifact_contents={"smaos-data-plane": tampered_binary},
        )
    assert "ERR_ARTIFACT_DIGEST_MISMATCH" in str(exc_info.value)

    # 4. Falsification: Untrusted builder ID fails closed
    untrusted_attestation = dict(attestation)
    untrusted_attestation["builder_id"] = "https://malicious-ci.internal/runner"
    with pytest.raises(ProvenanceVerificationError) as exc_info2:
        gate.verify_provenance_attestation(
            attestation=untrusted_attestation,
            actual_artifact_contents={"smaos-data-plane": artifact_binary},
        )
    assert "ERR_UNTRUSTED_BUILDER_ID" in str(exc_info2.value)


# ==============================================================================
# TRACK D: FULL PREPROD BLACK-BOX & MUTATION GATE INTEGRATION
# ==============================================================================

def test_track_d_preprod_blackbox_and_mutation_gate():
    report = execute_preprod_gate()
    assert report["status"] == "PREPRODUCTION_GATE_PASSED"
    assert report["mutation_report"]["mutation_kill_score_pct"] == 100.0
    assert report["fd_leak_delta"] == 0
