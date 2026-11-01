# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""
tests/test_specification_invariant_compiler.py
================================================================================
Comprehensive unit, adversarial, and boundary verification suite for
src/specification_invariant_compiler.py.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.specification_invariant_compiler import (
    AdaptiveMutationOperatorRegistry,
    AgentCoordinationContract,
    ClassifiedMutantOutcome,
    CompiledModuleNode,
    DualAnchoredSCITTReceipt,
    ExternalSCITTRegistrar,
    IndependentMutationAttestation,
    SpecificationInvariantCompiler,
    TransitiveKernelClosureAuditor,
)


def _pub_hex(priv: ed25519.Ed25519PrivateKey) -> str:
    return (
        priv.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


# ==============================================================================
# 1. AgentCoordinationContract & SpecificationInvariantCompiler Tests
# ==============================================================================


def test_coordination_contract_validation_boundaries() -> None:
    with pytest.raises(ValueError, match="ERR_EMPTY_CONTRACT_ID"):
        AgentCoordinationContract(
            contract_id="",
            max_steps=3,
            max_identical_step_repeats=2,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_STEPS"):
        AgentCoordinationContract(
            contract_id="c-0",
            max_steps=0,
            max_identical_step_repeats=2,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_STEPS"):
        AgentCoordinationContract(
            contract_id="c-neg",
            max_steps=-2,
            max_identical_step_repeats=2,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_IDENTICAL_STEP_REPEATS"):
        AgentCoordinationContract(
            contract_id="c-rep0",
            max_steps=2,
            max_identical_step_repeats=0,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_EMPTY_PLANNED_PHASE_TOOLS"):
        AgentCoordinationContract(
            contract_id="c-nophase",
            max_steps=2,
            max_identical_step_repeats=1,
            planned_phase_tools={},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_EMPTY_TERMINATION_STATE_KEYS"):
        AgentCoordinationContract(
            contract_id="c-noterm",
            max_steps=2,
            max_identical_step_repeats=1,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=(),
            completion_postcondition_keys=("verified_gate",),
        )

    with pytest.raises(ValueError, match="ERR_EMPTY_COMPLETION_POSTCONDITION_KEYS"):
        AgentCoordinationContract(
            contract_id="c-nocomp",
            max_steps=2,
            max_identical_step_repeats=1,
            planned_phase_tools={"plan": ("read_file",)},
            termination_state_keys=("loop_done",),
            completion_postcondition_keys=(),
        )

    valid_min = AgentCoordinationContract(
        contract_id="c-min-1",
        max_steps=1,
        max_identical_step_repeats=1,
        planned_phase_tools={"plan": ("read_file",)},
        termination_state_keys=("loop_done",),
        completion_postcondition_keys=("verified_gate",),
    )
    assert valid_min.contract_caid.startswith("sha256:")


def test_specification_invariant_compiler_step_budget_and_repetition_boundaries() -> None:
    contract = AgentCoordinationContract(
        contract_id="c-budget-rep",
        max_steps=3,
        max_identical_step_repeats=2,
        planned_phase_tools={
            "discover": ("grep_search", "read_file"),
            "verify": ("pytest_runner",),
        },
        termination_state_keys=("terminated",),
        completion_postcondition_keys=("tests_green", "audit_signed"),
    )
    compiler = SpecificationInvariantCompiler(contract)

    # Repeat 1 (allowed, with empty state_flags to exercise default False lookup)
    v1 = compiler.evaluate_step(
        "discover", "grep_search", {"q": "alpha"}, {}
    )
    assert v1.allowed is True
    assert v1.status_code == "ALLOW_STEP_IN_SPEC"
    assert v1.violation_reason == "NONE"
    assert v1.step_index == 1
    assert v1.contract_caid == contract.contract_caid
    assert v1.verdict_caid.startswith("sha256:")

    # Repeat 2 == max_identical_step_repeats (exact boundary: still allowed)
    v2 = compiler.evaluate_step(
        "discover", "grep_search", {"q": "alpha"}, {"terminated": False}
    )
    assert v2.allowed is True
    assert v2.status_code == "ALLOW_STEP_IN_SPEC"
    assert v2.step_index == 2
    assert v2.verdict_caid != v1.verdict_caid

    # Repeat 3 > max_identical_step_repeats (halted on repetition loop at step 3 == max_steps)
    v3 = compiler.evaluate_step(
        "discover", "grep_search", {"q": "alpha"}, {"terminated": False}
    )
    assert v3.allowed is False
    assert v3.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert v3.violation_reason == "REASON_STEP_REPETITION_LOOP"
    assert v3.step_index == 3

    # Step 4 > max_steps (halted on step budget exceeded)
    v4 = compiler.evaluate_step(
        "verify", "pytest_runner", {"suite": "unit"}, {"terminated": False}
    )
    assert v4.allowed is False
    assert v4.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert v4.violation_reason == "REASON_STEP_BUDGET_EXCEEDED"
    assert v4.step_index == 4


def test_specification_invariant_compiler_phase_mismatch_and_completion_vs_termination() -> None:
    contract = AgentCoordinationContract(
        contract_id="c-phase-post",
        max_steps=6,
        max_identical_step_repeats=1,
        planned_phase_tools={
            "edit": ("apply_patch",),
            "verify": ("run_gates",),
        },
        termination_state_keys=("loop_stopped",),
        completion_postcondition_keys=("gate_passed", "receipt_sealed"),
    )
    compiler = SpecificationInvariantCompiler(contract)

    # Unknown plan phase
    u1 = compiler.evaluate_step("deploy", "apply_patch", {"f": "a.py"}, {})
    assert u1.allowed is False
    assert u1.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert u1.violation_reason == "REASON_UNKNOWN_PLAN_PHASE"

    # Known phase, wrong tool
    u2 = compiler.evaluate_step("edit", "run_gates", {"f": "a.py"}, {})
    assert u2.allowed is False
    assert u2.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert u2.violation_reason == "REASON_PLAN_EXECUTION_MISMATCH"

    # Termination state key set True without completion postconditions met -> HALT
    u3 = compiler.evaluate_step(
        "verify",
        "run_gates",
        {"run": 1},
        {"loop_stopped": True, "gate_passed": True, "receipt_sealed": False},
        claim_task_completed=False,
    )
    assert u3.allowed is False
    assert u3.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert u3.violation_reason == "REASON_COMPLETION_POSTCONDITION_UNMET"

    # Explicit claim_task_completed=True without completion postconditions met -> HALT
    u4 = compiler.evaluate_step(
        "verify",
        "run_gates",
        {"run": 2},
        {"loop_stopped": False, "gate_passed": True},
        claim_task_completed=True,
    )
    assert u4.allowed is False
    assert u4.status_code == "HALT_COORDINATION_INVARIANT_VIOLATED"
    assert u4.violation_reason == "REASON_COMPLETION_POSTCONDITION_UNMET"

    # All completion postconditions met when claiming completion -> SATISFIED
    u5 = compiler.evaluate_step(
        "verify",
        "run_gates",
        {"run": 3},
        {"loop_stopped": True, "gate_passed": True, "receipt_sealed": True},
        claim_task_completed=True,
    )
    assert u5.allowed is True
    assert u5.status_code == "ALLOW_COORDINATION_CONTRACT_SATISFIED"
    assert u5.violation_reason == "NONE"


# ==============================================================================
# 2. ExternalSCITTRegistrar & DualAnchoredSCITTReceipt Tests
# ==============================================================================


def test_external_scitt_registrar_custodian_separation_and_verification() -> None:
    operator_key = ed25519.Ed25519PrivateKey.generate()
    custodian_key = ed25519.Ed25519PrivateKey.generate()
    other_key = ed25519.Ed25519PrivateKey.generate()

    with pytest.raises(ValueError, match="ERR_EMPTY_CUSTODIAN_SERVICE_ID"):
        ExternalSCITTRegistrar("", custodian_key)

    registrar = ExternalSCITTRegistrar("scitt-custodian-eu-1", custodian_key)

    # Self-custody (operator key == custodian key) must raise at registration time
    with pytest.raises(ValueError, match="ERR_SELF_CUSTODY_FORBIDDEN"):
        registrar.register_operator_receipt(
            "rcpt-self", {"action": "transfer"}, custodian_key
        )

    payload_1 = {"action": "deploy_gate", "sequence": 1}
    payload_2 = {"action": "deploy_gate", "sequence": 2}
    r1 = registrar.register_operator_receipt("rcpt-1", payload_1, operator_key)
    r2 = registrar.register_operator_receipt("rcpt-2", payload_2, operator_key)

    assert r1.leaf_index == 0
    assert r1.tree_size == 1
    assert r2.leaf_index == 1
    assert r2.tree_size == 2
    assert len(r2.inclusion_audit_path_hex) == 1
    assert r2.dual_receipt_caid.startswith("sha256:")

    op_pub = _pub_hex(operator_key)
    cust_pub = _pub_hex(custodian_key)
    other_pub = _pub_hex(other_key)

    ok1, code1 = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r1, payload_1, op_pub, cust_pub
    )
    assert ok1 is True
    assert code1 == "VERIFIED_DUAL_ANCHORED_SCITT_RECEIPT"

    ok2, code2 = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r2, payload_2, op_pub, cust_pub
    )
    assert ok2 is True
    assert code2 == "VERIFIED_DUAL_ANCHORED_SCITT_RECEIPT"

    # Reject self-custody at verification time
    ok_self, code_self = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r2, payload_2, op_pub, op_pub
    )
    assert ok_self is False
    assert code_self == "ERR_SELF_CUSTODY_FORBIDDEN"

    # Reject operator key pin mismatch
    ok_pin_op, code_pin_op = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r2, payload_2, other_pub, cust_pub
    )
    assert ok_pin_op is False
    assert code_pin_op == "ERR_KEY_PIN_MISMATCH"

    # Reject custodian key pin mismatch
    ok_pin_c, code_pin_c = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r2, payload_2, op_pub, other_pub
    )
    assert ok_pin_c is False
    assert code_pin_c == "ERR_KEY_PIN_MISMATCH"

    # Reject payload tampering
    ok_tamper, code_tamper = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        r2, {"action": "deploy_gate", "sequence": 99}, op_pub, cust_pub
    )
    assert ok_tamper is False
    assert code_tamper == "ERR_PAYLOAD_CAID_MISMATCH"

    # Reject forged operator signature
    bad_op_sig = DualAnchoredSCITTReceipt(
        **{**r2.__dict__, "operator_signature_hex": "00" * 64}
    )
    ok_opsig, code_opsig = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        bad_op_sig, payload_2, op_pub, cust_pub
    )
    assert ok_opsig is False
    assert code_opsig == "ERR_INVALID_OPERATOR_SIGNATURE"

    # Reject corrupted leaf hash
    bad_leaf = DualAnchoredSCITTReceipt(
        **{**r2.__dict__, "leaf_hash_hex": "ff" * 32}
    )
    ok_leaf, code_leaf = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        bad_leaf, payload_2, op_pub, cust_pub
    )
    assert ok_leaf is False
    assert code_leaf == "ERR_INCLUSION_PROOF_INVALID"

    # Reject corrupted inclusion audit path
    bad_path = DualAnchoredSCITTReceipt(
        **{**r2.__dict__, "inclusion_audit_path_hex": ("ab" * 32,)}
    )
    ok_path, code_path = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        bad_path, payload_2, op_pub, cust_pub
    )
    assert ok_path is False
    assert code_path == "ERR_INCLUSION_PROOF_INVALID"

    # Reject forged custodian STH signature
    bad_sth = DualAnchoredSCITTReceipt(
        **{**r2.__dict__, "custodian_sth_signature_hex": "11" * 64}
    )
    ok_sth, code_sth = ExternalSCITTRegistrar.verify_dual_anchored_receipt(
        bad_sth, payload_2, op_pub, cust_pub
    )
    assert ok_sth is False
    assert code_sth == "ERR_INVALID_CUSTODIAN_STH_SIGNATURE"


# ==============================================================================
# 3. TransitiveKernelClosureAuditor Tests
# ==============================================================================


def test_transitive_kernel_closure_auditor_clean_and_all_failure_modes() -> None:
    auditor = TransitiveKernelClosureAuditor()

    clean_leaf = CompiledModuleNode(
        module_name="AEIB.Math.SafeArith",
        imports=(),
        source_text="theorem add_comm_safe (a b : Nat) : a + b = b + a := Nat.add_comm a b",
        olean_symbols=("AEIB.Math.SafeArith.add_comm_safe",),
        olean_bytes_sha256="sha256:leaf_clean_digest",
    )
    clean_root = CompiledModuleNode(
        module_name="AEIB.Policy.Gate",
        imports=("AEIB.Math.SafeArith", "AEIB.Math.SafeArith"),
        source_text="import AEIB.Math.SafeArith\ndef gateCheck : Bool := true",
        olean_symbols=("AEIB.Policy.Gate.gateCheck",),
        olean_bytes_sha256="sha256:root_clean_digest",
    )

    clean_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {
            "AEIB.Policy.Gate": clean_root,
            "AEIB.Math.SafeArith": clean_leaf,
        },
        {
            "AEIB.Policy.Gate": "sha256:root_clean_digest",
            "AEIB.Math.SafeArith": "sha256:leaf_clean_digest",
        },
    )
    assert clean_verdict.verified is True
    assert clean_verdict.status_code == "ALLOW_TRANSITIVE_CLOSURE_CLEAN"
    assert clean_verdict.violation_reason == "NONE"
    assert clean_verdict.offending_module == ""
    assert clean_verdict.audited_module_count == 2
    assert clean_verdict.closure_caid.startswith("sha256:")

    # 1. Missing transitive module
    missing_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {"AEIB.Policy.Gate": clean_root},
        {"AEIB.Policy.Gate": "sha256:root_clean_digest"},
    )
    assert missing_verdict.verified is False
    assert missing_verdict.status_code == "HALT_KERNEL_TRUST_CHAIN_VIOLATION"
    assert missing_verdict.violation_reason == "REASON_INCOMPLETE_CLOSURE_GRAPH"
    assert missing_verdict.offending_module == "AEIB.Math.SafeArith"

    # 2. .olean digest mismatch on transitive import
    digest_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {
            "AEIB.Policy.Gate": clean_root,
            "AEIB.Math.SafeArith": clean_leaf,
        },
        {
            "AEIB.Policy.Gate": "sha256:root_clean_digest",
            "AEIB.Math.SafeArith": "sha256:tampered_digest",
        },
    )
    assert digest_verdict.verified is False
    assert digest_verdict.violation_reason == "REASON_OLEAN_DIGEST_MISMATCH"
    assert digest_verdict.offending_module == "AEIB.Math.SafeArith"

    # 3. @[implemented_by] / @[extern] override in transitive import
    override_leaf = CompiledModuleNode(
        module_name="AEIB.Math.SafeArith",
        imports=(),
        source_text="@[implemented_by fastUnsafeCheck] def safeCheck : Bool := true",
        olean_symbols=(),
        olean_bytes_sha256="sha256:leaf_override",
    )
    override_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {
            "AEIB.Policy.Gate": clean_root,
            "AEIB.Math.SafeArith": override_leaf,
        },
        {
            "AEIB.Policy.Gate": "sha256:root_clean_digest",
            "AEIB.Math.SafeArith": "sha256:leaf_override",
        },
    )
    assert override_verdict.verified is False
    assert override_verdict.violation_reason == "REASON_IMPLEMENTED_BY_OR_EXTERN_OVERRIDE"

    # 4. native_decide / Lean.ofReduceBool in olean_Declarations
    native_leaf = CompiledModuleNode(
        module_name="AEIB.Math.SafeArith",
        imports=(),
        source_text="theorem t : true = true := rfl",
        olean_symbols=(),
        olean_bytes_sha256="sha256:leaf_native",
        olean_Declarations=("Lean.ofReduceBool",),
    )
    native_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {
            "AEIB.Policy.Gate": clean_root,
            "AEIB.Math.SafeArith": native_leaf,
        },
        {
            "AEIB.Policy.Gate": "sha256:root_clean_digest",
            "AEIB.Math.SafeArith": "sha256:leaf_native",
        },
    )
    assert native_verdict.verified is False
    assert (
        native_verdict.violation_reason
        == "REASON_NATIVE_DECIDE_COMPILER_TRUST_EXPANSION"
    )

    # 5. Transitive sorry / axiom / admit / unsafe
    sorry_leaf = CompiledModuleNode(
        module_name="AEIB.Math.SafeArith",
        imports=(),
        source_text="axiom false_axiom : False",
        olean_symbols=(),
        olean_bytes_sha256="sha256:leaf_axiom",
    )
    sorry_verdict = auditor.audit_closure(
        "AEIB.Policy.Gate",
        {
            "AEIB.Policy.Gate": clean_root,
            "AEIB.Math.SafeArith": sorry_leaf,
        },
        {
            "AEIB.Policy.Gate": "sha256:root_clean_digest",
            "AEIB.Math.SafeArith": "sha256:leaf_axiom",
        },
    )
    assert sorry_verdict.verified is False
    assert sorry_verdict.violation_reason == "REASON_TRANSITIVE_AXIOM_OR_SORRY"


# ==============================================================================
# 4. IndependentMutationAttestation & AdaptiveMutationOperatorRegistry Tests
# ==============================================================================


def test_independent_mutation_attestation_effsms_and_boundaries() -> None:
    # Single or empty engine checks (both primary="" and secondary="" with matching outcome rows)
    r_empty_primary = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "",
        "universalmutator",
        [
            ClassifiedMutantOutcome("m1", "", "src/a.py", True, "SEMANTIC", False),
            ClassifiedMutantOutcome(
                "m2", "universalmutator", "src/a.py", True, "SEMANTIC", False
            ),
        ],
    )
    assert r_empty_primary["authorized"] is False
    assert r_empty_primary["status_code"] == "BLOCK_SINGLE_ENGINE_OR_EMPTY"
    assert r_empty_primary["eff_sms_bps"] == 0
    assert r_empty_primary["semantic_share_of_kills_bps"] == 0

    r_empty_secondary = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "",
        [
            ClassifiedMutantOutcome(
                "m1", "ast-mut", "src/a.py", True, "SEMANTIC", False
            ),
            ClassifiedMutantOutcome("m2", "", "src/a.py", True, "SEMANTIC", False),
        ],
    )
    assert r_empty_secondary["authorized"] is False
    assert r_empty_secondary["status_code"] == "BLOCK_SINGLE_ENGINE_OR_EMPTY"

    r_same = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "ast-mut",
        [
            ClassifiedMutantOutcome(
                "m1", "ast-mut", "src/a.py", True, "SEMANTIC", True
            )
        ],
    )
    assert r_same["authorized"] is False
    assert r_same["status_code"] == "BLOCK_SINGLE_ENGINE_OR_EMPTY"
    assert r_same["eff_sms_bps"] == 0
    assert r_same["semantic_share_of_kills_bps"] == 0

    r_missing_secondary = (
        IndependentMutationAttestation.evaluate_dual_engine_attestation(
            "ast-mut",
            "universalmutator",
            [
                ClassifiedMutantOutcome(
                    "m1", "ast-mut", "src/a.py", True, "SEMANTIC", True
                )
            ],
        )
    )
    assert r_missing_secondary["authorized"] is False
    assert r_missing_secondary["status_code"] == "BLOCK_SINGLE_ENGINE_OR_EMPTY"
    assert r_missing_secondary["eff_sms_bps"] == 0
    assert r_missing_secondary["semantic_share_of_kills_bps"] == 0

    r_missing_primary = (
        IndependentMutationAttestation.evaluate_dual_engine_attestation(
            "ast-mut",
            "universalmutator",
            [
                ClassifiedMutantOutcome(
                    "m1", "universalmutator", "src/a.py", True, "SEMANTIC", True
                )
            ],
        )
    )
    assert r_missing_primary["authorized"] is False
    assert r_missing_primary["status_code"] == "BLOCK_SINGLE_ENGINE_OR_EMPTY"
    assert r_missing_primary["eff_sms_bps"] == 0
    assert r_missing_primary["semantic_share_of_kills_bps"] == 0

    # Default threshold check (7/10 = 7000 bps for both eff_sms_bps and semantic_share_of_kills_bps)
    ten_default_outcomes = [
        ClassifiedMutantOutcome(f"s{i}", "ast-mut", "src/a.py", True, "SEMANTIC", False)
        for i in range(6)
    ] + [
        ClassifiedMutantOutcome(
            "s6", "universalmutator", "src/a.py", True, "SEMANTIC", False
        ),
        ClassifiedMutantOutcome(
            "c1", "universalmutator", "src/a.py", True, "CRASH", False
        ),
        ClassifiedMutantOutcome(
            "c2", "universalmutator", "src/a.py", True, "CRASH", False
        ),
        ClassifiedMutantOutcome(
            "c3", "universalmutator", "src/a.py", True, "CRASH", False
        ),
    ]
    r_default_pass = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "universalmutator",
        ten_default_outcomes,
    )
    assert r_default_pass["authorized"] is True
    assert r_default_pass["status_code"] == "ALLOW_DUAL_ENGINE_SEMANTIC_ATTESTED"

    # Security-sensitive survivor blocks merge immediately
    r_sec_surv = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "universalmutator",
        [
            ClassifiedMutantOutcome(
                "m1", "ast-mut", "src/auth.py", True, "SEMANTIC", True
            ),
            ClassifiedMutantOutcome(
                "m2", "universalmutator", "src/auth.py", False, "SURVIVED", True
            ),
        ],
    )
    assert r_sec_surv["authorized"] is False
    assert r_sec_surv["status_code"] == "BLOCK_SECURITY_SURVIVOR"

    # High raw kills (all CRASH/INCIDENTAL), low semantic kills -> BLOCK_LOW_SEMANTIC_KILL_SHARE
    r_crash = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "universalmutator",
        [
            ClassifiedMutantOutcome(
                "m1", "ast-mut", "src/a.py", True, "SEMANTIC", True
            ),
            ClassifiedMutantOutcome(
                "m2", "universalmutator", "src/a.py", True, "CRASH", False
            ),
            ClassifiedMutantOutcome(
                "m3", "universalmutator", "src/a.py", True, "INCIDENTAL", False
            ),
            ClassifiedMutantOutcome(
                "m4", "ast-mut", "src/a.py", True, "CRASH", False
            ),
        ],
        min_eff_sms_bps=7500,
        min_semantic_share_bps=7500,
    )
    assert r_crash["authorized"] is False
    assert r_crash["status_code"] == "BLOCK_LOW_SEMANTIC_KILL_SHARE"
    assert r_crash["eff_sms_bps"] == 2500
    assert r_crash["semantic_share_of_kills_bps"] == 2500

    # Non-trivial 5/7 fraction (7142 bps) and exact threshold boundary check
    seven_outcomes = [
        ClassifiedMutantOutcome("m1", "ast-mut", "src/a.py", True, "SEMANTIC", True),
        ClassifiedMutantOutcome("m2", "ast-mut", "src/a.py", True, "SEMANTIC", True),
        ClassifiedMutantOutcome("m3", "ast-mut", "src/a.py", True, "SEMANTIC", False),
        ClassifiedMutantOutcome(
            "m4", "universalmutator", "src/a.py", True, "SEMANTIC", True
        ),
        ClassifiedMutantOutcome(
            "m5", "universalmutator", "src/a.py", True, "SEMANTIC", False
        ),
        ClassifiedMutantOutcome(
            "m6", "universalmutator", "src/a.py", True, "FUNCTIONAL", False
        ),
        ClassifiedMutantOutcome(
            "m7", "universalmutator", "src/a.py", False, "SURVIVED", False
        ),
    ]
    # 5 semantic kills out of 7 total = 7142 bps; 5 semantic kills out of 6 kills = 8333 bps
    r_pass_exact = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "universalmutator",
        seven_outcomes,
        min_eff_sms_bps=7142,
        min_semantic_share_bps=8333,
    )
    assert r_pass_exact["authorized"] is True
    assert r_pass_exact["status_code"] == "ALLOW_DUAL_ENGINE_SEMANTIC_ATTESTED"
    assert r_pass_exact["eff_sms_bps"] == 7142
    assert r_pass_exact["semantic_share_of_kills_bps"] == 8333

    # 1 bps above achieved eff_sms_bps must block
    r_fail_eff_bound = IndependentMutationAttestation.evaluate_dual_engine_attestation(
        "ast-mut",
        "universalmutator",
        seven_outcomes,
        min_eff_sms_bps=7143,
        min_semantic_share_bps=8333,
    )
    assert r_fail_eff_bound["authorized"] is False
    assert r_fail_eff_bound["status_code"] == "BLOCK_LOW_SEMANTIC_KILL_SHARE"

    # 1 bps above achieved semantic_share_of_kills_bps must block
    r_fail_share_bound = (
        IndependentMutationAttestation.evaluate_dual_engine_attestation(
            "ast-mut",
            "universalmutator",
            seven_outcomes,
            min_eff_sms_bps=7142,
            min_semantic_share_bps=8334,
        )
    )
    assert r_fail_share_bound["authorized"] is False
    assert r_fail_share_bound["status_code"] == "BLOCK_LOW_SEMANTIC_KILL_SHARE"


def test_adaptive_mutation_operator_registry_retroactive_scan() -> None:
    registry = AdaptiveMutationOperatorRegistry()

    with pytest.raises(ValueError, match="ERR_EMPTY_ESCAPED_DEFECT_SPEC"):
        registry.register_escaped_defect("", "pattern", "INC-1")
    with pytest.raises(ValueError, match="ERR_EMPTY_ESCAPED_DEFECT_SPEC"):
        registry.register_escaped_defect("OP-1", "", "INC-1")
    with pytest.raises(ValueError, match="ERR_EMPTY_ESCAPED_DEFECT_SPEC"):
        registry.register_escaped_defect("OP-1", "pattern", "")

    registry.register_escaped_defect(
        "OP_LEAN_REDUCE_BOOL", "Lean.ofReduceBool", "INC-2026-1031"
    )

    merges = [
        {"merge_id": "PR-101", "source_text": "def safe : Bool := true"},
        {
            "merge_id": "PR-102",
            "source_text": "theorem bad : true := by Lean.ofReduceBool",
        },
    ]
    advisories = registry.scan_historical_merges(merges)
    assert len(advisories) == 1
    assert advisories[0] == {
        "advisory_status": "RETROACTIVE_ADVISORY_REQUIRED",
        "cve_or_incident_ref": "INC-2026-1031",
        "merge_id": "PR-102",
        "operator_id": "OP_LEAN_REDUCE_BOOL",
    }


def test_frozen_dataclass_immutability_invariants() -> None:
    contract = AgentCoordinationContract(
        contract_id="c-imm",
        max_steps=2,
        max_identical_step_repeats=1,
        planned_phase_tools={"plan": ("read_file",)},
        termination_state_keys=("done",),
        completion_postcondition_keys=("verified",),
    )
    with pytest.raises(Exception):
        contract.max_steps = 99  # type: ignore[misc]

    compiler = SpecificationInvariantCompiler(contract)
    verdict = compiler.evaluate_step("plan", "read_file", {}, {})
    with pytest.raises(Exception):
        verdict.allowed = False  # type: ignore[misc]

    op_key = ed25519.Ed25519PrivateKey.generate()
    cust_key = ed25519.Ed25519PrivateKey.generate()
    reg = ExternalSCITTRegistrar("cust-1", cust_key)
    rcpt = reg.register_operator_receipt("r-1", {"k": 1}, op_key)
    with pytest.raises(Exception):
        rcpt.tree_size = 99  # type: ignore[misc]

    node = CompiledModuleNode("Mod", (), "def x := 1", (), "sha256:1")
    with pytest.raises(Exception):
        node.module_name = "Other"  # type: ignore[misc]

    auditor = TransitiveKernelClosureAuditor()
    k_verdict = auditor.audit_closure("Mod", {"Mod": node}, {"Mod": "sha256:1"})
    with pytest.raises(Exception):
        k_verdict.verified = False  # type: ignore[misc]

    outcome = ClassifiedMutantOutcome("m1", "e1", "f.py", True, "SEMANTIC", True)
    with pytest.raises(Exception):
        outcome.killed = False  # type: ignore[misc]

