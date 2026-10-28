"""
Tests for October 2026 Frontier Runtime Verification, Provenance-Bound Memory,
ContextCart Archival Forgetting, and STPA Hazard Control Gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.oct2026_runtime_trace_contextcart_and_hazard_gate import (
    GENESIS_TRACE_HASH,
    ContextCartArchivalForgettingEngine,
    ContextRecordKind,
    CrashAmbiguityState,
    DelegatedTaintAndHazardGate,
    EO1EnforcementTraceV1,
    JanusOfflineSagaLogVerifier,
    ProvenanceBoundLookupRegistry,
    SignedApprovalArtifact,
    classify_crash_ambiguity,
)


def test_crash_ambiguity_three_states_and_duplicate_payment_block() -> None:
    """
    Verifies the 3-state crash ambiguity classifier (Atomix arXiv:2602.14849v2 &
    Agent libOS arXiv:2606.03895v3) and ensures DISPATCH_MAY_HAVE_STARTED blocks retry.
    """
    state_a, retry_a = classify_crash_ambiguity(
        intent_durable_on_disk=False, wire_socket_opened=False
    )
    assert state_a == CrashAmbiguityState.NO_DURABLE_INTENT
    assert retry_a is True

    state_b, retry_b = classify_crash_ambiguity(
        intent_durable_on_disk=True, wire_socket_opened=False
    )
    assert state_b == CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED
    assert retry_b is True

    state_c, retry_c = classify_crash_ambiguity(
        intent_durable_on_disk=True, wire_socket_opened=True
    )
    assert state_c == CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED
    assert retry_c is False


def test_janus_offline_verifier_catches_post_approval_substitution() -> None:
    """
    Verifies Janus (arXiv:2609.38266v1) pure-function offline log verification:
    - Nominal 2-step hash-chained trace log verifies cleanly using only public keys.
    - Negative 1: Post-Approval Payload Substitution (approved amount_minor=100,
      dispatched amount_minor=1000000) fails closed with HALT_POST_APPROVAL_SUBSTITUTION.
    - Negative 2: Post-Approval Tool Substitution (approved tool 'refund_api_v1',
      dispatched tool 'wire_transfer_v1') fails closed with HALT_POST_APPROVAL_SUBSTITUTION.
    - Negative 3: Duplicate dispatch on a latched idempotency_key after
      DISPATCH_MAY_HAVE_STARTED fails closed with HALT_AMBIGUOUS_DISPATCH_RETRY_FORBIDDEN.
    """
    approver_sk = Ed25519PrivateKey.generate()
    agent_sk = Ed25519PrivateKey.generate()
    pub_keys = {
        "human-approver-01": approver_sk.public_key(),
        "gateway-actor-01": agent_sk.public_key(),
    }

    registry = ProvenanceBoundLookupRegistry()
    lookup_receipt = registry.record_lookup(
        lookup_id="lkp-001",
        query_text="fetch invoice inv-900",
        retrieved_fact_ids=["fact-inv-900", "fact-policy-refund"],
        traversal_path=["root", "cluster-billing", "fact-inv-900"],
        source_span_digests=["sha256:" + "a" * 64],
    )

    approved_payload = {"invoice_id": "inv-900", "amount_minor": 100, "currency": "EUR"}
    approval = SignedApprovalArtifact.issue(
        approval_id="appr-001",
        approver_actor_id="human-approver-01",
        subject_agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:refund:small",
        action_payload=approved_payload,
        policy_version="policy-2026-10",
        approver_private_key=approver_sk,
    )

    trace_1 = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-001",
        timestamp_ns=1_761_300_000_000_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:refund:small",
        operation_id="op-001",
        idempotency_key="idem-001",
        action_payload=approved_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="NOMINAL_APPROVED",
        crash_state=CrashAmbiguityState.DISPATCH_MAY_HAVE_STARTED,
        prev_trace_hash=GENESIS_TRACE_HASH,
        actor_private_key=agent_sk,
    )

    res = JanusOfflineSagaLogVerifier.verify_signed_log_offline(
        traces=[trace_1],
        approvals_by_digest={approval.approval_digest: approval},
        public_keys_by_actor=pub_keys,
        provenance_registry=registry,
    )
    assert res["verified_trace_count"] == 1
    assert res["terminal_chain_tip"] == trace_1.trace_hash
    with pytest.raises(AttributeError):
        trace_1.decision = "DENY"  # type: ignore[misc]

    # Negative 1: Post-Approval Payload Substitution (100 -> 1,000,000)
    substituted_payload = {"invoice_id": "inv-900", "amount_minor": 1_000_000, "currency": "EUR"}
    trace_bad_amount = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-bad-amount",
        timestamp_ns=1_761_300_000_100_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:refund:small",
        operation_id="op-002",
        idempotency_key="idem-002",
        action_payload=substituted_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="ATTEMPT_SUBSTITUTION",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash=GENESIS_TRACE_HASH,
        actor_private_key=agent_sk,
    )
    with pytest.raises(ValueError, match="HALT_POST_APPROVAL_SUBSTITUTION"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_bad_amount],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor=pub_keys,
            provenance_registry=registry,
        )

    # Negative 2: Post-Approval Tool Substitution (refund_api_v1 -> wire_transfer_v1)
    trace_bad_tool = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-bad-tool",
        timestamp_ns=1_761_300_000_200_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="wire_transfer_v1",
        capability_id="cap:refund:small",
        operation_id="op-003",
        idempotency_key="idem-003",
        action_payload=approved_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="ATTEMPT_TOOL_SWAP",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash=GENESIS_TRACE_HASH,
        actor_private_key=agent_sk,
    )
    with pytest.raises(ValueError, match="HALT_POST_APPROVAL_SUBSTITUTION"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_bad_tool],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor=pub_keys,
            provenance_registry=registry,
        )

    # Negative 3: Duplicate dispatch on latched idempotency_key
    trace_dup_idem = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-dup",
        timestamp_ns=1_761_300_000_300_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:refund:small",
        operation_id="op-004",
        idempotency_key="idem-001",
        action_payload=approved_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="RETRY_AFTER_AMBIGUITY",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash=trace_1.trace_hash,
        actor_private_key=agent_sk,
    )
    with pytest.raises(ValueError, match="HALT_AMBIGUOUS_DISPATCH_RETRY_FORBIDDEN"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_1, trace_dup_idem],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor=pub_keys,
            provenance_registry=registry,
        )

    assert len(GENESIS_TRACE_HASH) == 64

    # Negative 4: Broken hash chain (prev_trace_hash mismatch)
    trace_broken_chain = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-broken-chain",
        timestamp_ns=1_761_300_000_400_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:refund:small",
        operation_id="op-005",
        idempotency_key="idem-005",
        action_payload=approved_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="BROKEN_CHAIN",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash="f" * 64,
        actor_private_key=agent_sk,
    )
    with pytest.raises(ValueError, match="HALT_TRACE_HASH_CHAIN_BROKEN"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_broken_chain],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor=pub_keys,
            provenance_registry=registry,
        )

    # Negative 5: Unknown approver actor
    with pytest.raises(ValueError, match="HALT_UNKNOWN_APPROVER_ACTOR"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_1],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor={"gateway-actor-01": agent_sk.public_key()},
            provenance_registry=registry,
        )

    # Negative 6: Invalid approval signature (wrong approver public key)
    wrong_approver_sk = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="HALT_INVALID_APPROVAL_SIGNATURE"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_1],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor={
                "human-approver-01": wrong_approver_sk.public_key(),
                "gateway-actor-01": agent_sk.public_key(),
            },
            provenance_registry=registry,
        )

    # Negative 7: Post-Approval Capability Substitution
    trace_bad_cap = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-bad-cap",
        timestamp_ns=1_761_300_000_500_000_000,
        actor_id="gateway-actor-01",
        session_id="sess-01",
        agent_id="builder-agent-01",
        tool_id="refund_api_v1",
        capability_id="cap:wire:admin",
        operation_id="op-006",
        idempotency_key="idem-006",
        action_payload=approved_payload,
        approval=approval,
        input_taint_tier=0,
        provenance_lookup_digest=lookup_receipt.provenance_lookup_digest,
        policy_version="policy-2026-10",
        decision="ALLOW",
        decision_reason="ATTEMPT_CAP_SWAP",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash=GENESIS_TRACE_HASH,
        actor_private_key=agent_sk,
    )
    with pytest.raises(ValueError, match="HALT_POST_APPROVAL_SUBSTITUTION"):
        JanusOfflineSagaLogVerifier.verify_signed_log_offline(
            traces=[trace_bad_cap],
            approvals_by_digest={approval.approval_digest: approval},
            public_keys_by_actor=pub_keys,
            provenance_registry=registry,
        )


def test_provenance_bound_lookup_and_mhg_evolutionary_hyperedge() -> None:
    """
    Verifies MHG-Mem (arXiv:2610.29995v1) ternary evolutionary hyperedges and
    provenance-bound retrieval verification (arXiv:2610.09793v1):
    - Unbound/forged provenance_lookup_digest is rejected.
    - Citing a fact_id that was not returned in the lookup is rejected.
    - Recording a ternary evolutionary hyperedge [old_fact, new_fact, evidence_span]
      supersedes old_fact and blocks stale citations when reject_superseded=True.
    """
    registry = ProvenanceBoundLookupRegistry()
    receipt = registry.record_lookup(
        lookup_id="lkp-mhg-01",
        query_text="endpoint status for payment gateway",
        retrieved_fact_ids=["fact-v1", "fact-span-doc"],
        traversal_path=["root", "fact-v1"],
        source_span_digests=["sha256:" + "b" * 64],
    )

    verified = registry.verify_trace_provenance(
        receipt.provenance_lookup_digest,
        cited_fact_ids=["fact-v1"],
    )
    assert verified.lookup_id == "lkp-mhg-01"

    # Forged lookup digest rejected
    with pytest.raises(ValueError, match="HALT_UNBOUND_OR_FORGED_PROVENANCE_LOOKUP"):
        registry.verify_trace_provenance("sha256:" + "f" * 64, cited_fact_ids=["fact-v1"])

    # Unretrieved fact citation rejected
    with pytest.raises(ValueError, match="HALT_UNBOUND_OR_FORGED_PROVENANCE_LOOKUP"):
        registry.verify_trace_provenance(
            receipt.provenance_lookup_digest,
            cited_fact_ids=["fact-hallucinated-999"],
        )

    # Ternary evolutionary hyperedge transitions fact-v1 -> fact-v2 via fact-span-doc
    edge = registry.record_evolutionary_transition(
        hyperedge_id="he-evo-001",
        old_fact_id="fact-v1",
        new_fact_id="fact-v2",
        evidence_span_fact_id="fact-span-doc",
        transition_reason="Endpoint migrated to v2 TLS gateway",
    )
    assert edge.vertices == ("fact-v1", "fact-v2", "fact-span-doc")
    assert edge.relation == "MHG_EVOLUTIONARY_TRANSITION"
    with pytest.raises(AttributeError):
        edge.old_fact_id = "tamper"  # type: ignore[misc]

    # Citing superseded fact-v1 now fails closed with HALT_SUPERSEDED_FACT_CITATION
    with pytest.raises(ValueError, match="HALT_SUPERSEDED_FACT_CITATION"):
        registry.verify_trace_provenance(
            receipt.provenance_lookup_digest,
            cited_fact_ids=["fact-v1"],
            reject_superseded=True,
        )


def test_contextcart_archival_forgetting_and_protected_record_invariants() -> None:
    """
    Verifies ContextCart archival forgetting (arXiv:2610.10590v1):
    - Bulky TOOL_OBSERVATION is replaced by a compact note while storing the full
      payload by SHA-256 and reclaiming active context bytes.
    - Lossless recovery restores the exact original string and verifies SHA-256.
    - Protected records (USER_INSTRUCTION, SAFETY_INVARIANT, EO1_APPROVAL_RECORD)
      cannot be compressed or archived (HALT_PROTECTED_RECORD_COMPRESSION_FORBIDDEN).
    """
    engine = ContextCartArchivalForgettingEngine()
    engine.append_slot(
        "slot-user",
        ContextRecordKind.USER_INSTRUCTION,
        "Never execute wire transfers above 500 EUR without human step-up.",
    )
    engine.append_slot(
        "slot-safety",
        ContextRecordKind.SAFETY_INVARIANT,
        "EO1 write-before-execute must fsync before socket connect.",
    )
    engine.append_slot(
        "slot-eo1",
        ContextRecordKind.EO1_APPROVAL_RECORD,
        "approval_id=appr-001 canonical_act_digest=sha256:1234",
    )

    bulky_log = "TRACE_LINE: " + ("0123456789abcdef" * 120)
    engine.append_slot("slot-obs-1", ContextRecordKind.TOOL_OBSERVATION, bulky_log)

    before_bytes = engine.active_byte_footprint()
    archive_stats = engine.archive_observation("slot-obs-1", compact_note="120-chunk hex trace ok")
    after_bytes = engine.active_byte_footprint()

    assert after_bytes < before_bytes
    assert archive_stats["bytes_reclaimed"] == before_bytes - after_bytes

    # Protected slots must refuse archival
    for protected_slot in ("slot-user", "slot-safety", "slot-eo1"):
        with pytest.raises(ValueError, match="HALT_PROTECTED_RECORD_COMPRESSION_FORBIDDEN"):
            engine.archive_observation(protected_slot, compact_note="short")

    # Lossless recovery restores exact byte-for-byte original observation
    restored = engine.recover_observation("slot-obs-1")
    assert restored == bulky_log
    assert engine.active_byte_footprint() == before_bytes


def test_delegated_misalignment_taint_penalty_and_no_exemption() -> None:
    """
    Verifies Delegated Misalignment controls (arXiv:2609.27900v1):
    - Subordinate taint score must be >= source_taint_score + delegation_penalty.
    - Supervisor cannot grant a subordinate safety-gate exemption.
    """
    ok = DelegatedTaintAndHazardGate.validate_delegation_handoff(
        source_agent_id="supervisor-01",
        target_agent_id="worker-01",
        source_taint_score=1,
        claimed_target_taint_score=2,
        delegation_penalty=1,
        bypass_subordinate_safety_gate=False,
    )
    assert ok["effective_target_taint_score"] == 2
    assert ok["subordinate_gate_mandatory"] is True

    with pytest.raises(ValueError, match="HALT_DELEGATED_TAINT_DOWNGRADE"):
        DelegatedTaintAndHazardGate.validate_delegation_handoff(
            source_agent_id="supervisor-01",
            target_agent_id="worker-01",
            source_taint_score=2,
            claimed_target_taint_score=2,
            delegation_penalty=1,
        )

    with pytest.raises(ValueError, match="HALT_DELEGATION_SAFETY_EXEMPTION_FORBIDDEN"):
        DelegatedTaintAndHazardGate.validate_delegation_handoff(
            source_agent_id="supervisor-01",
            target_agent_id="worker-01",
            source_taint_score=0,
            claimed_target_taint_score=2,
            delegation_penalty=1,
            bypass_subordinate_safety_gate=True,
        )


def test_test_gated_repair_and_escalation_channel() -> None:
    """
    Verifies 'If It's Not Buggy, Don't Fix It' (arXiv:2609.10123v1) and
    structured escalation channel anti-reward-hacking controls (arXiv:2608.29460v3):
    - Open-loop repair without a failing deterministic test fails closed.
    - Builder attempting to edit verification tests fails closed.
    - Spec conflict or attempt_index > 3 routes to HUMAN_ESCALATION_REQUIRED.
    """
    with pytest.raises(ValueError, match="HALT_UNPROVOKED_ITERATIVE_REPAIR_FORBIDDEN"):
        DelegatedTaintAndHazardGate.authorize_iterative_repair(
            agent_id="builder-01",
            has_deterministic_failing_test=False,
            failing_oracle_id="",
            attempt_index=1,
        )

    with pytest.raises(ValueError, match="HALT_REWARD_HACKING_TEST_EDIT_FORBIDDEN"):
        DelegatedTaintAndHazardGate.authorize_iterative_repair(
            agent_id="builder-01",
            has_deterministic_failing_test=True,
            failing_oracle_id="test_refund_limit",
            attempt_index=1,
            builder_attempted_test_edit=True,
        )

    esc = DelegatedTaintAndHazardGate.authorize_iterative_repair(
        agent_id="builder-01",
        has_deterministic_failing_test=True,
        failing_oracle_id="test_ambiguous_spec",
        attempt_index=4,
        max_attempts=3,
    )
    assert esc["action"] == "ESCALATE_TO_HUMAN"
    assert esc["ticket"].status == "HUMAN_ESCALATION_REQUIRED"
    assert esc["ticket"].reward_hacking_blocked is True

    authorized = DelegatedTaintAndHazardGate.authorize_iterative_repair(
        agent_id="builder-01",
        has_deterministic_failing_test=True,
        failing_oracle_id="test_refund_rounding",
        attempt_index=1,
        max_attempts=3,
    )
    assert authorized["action"] == "REPAIR_AUTHORIZED"
    assert authorized["attempt_index"] == 1
    assert authorized["failing_oracle_id"] == "test_refund_rounding"


def test_stpa_hazard_register_controls_and_secret_leakage_halt(tmp_path: Path) -> None:
    """
    Verifies specs/aeib_hazard_register.yaml completeness and secret-leakage halt (H-03).
    """
    repo_root = Path(__file__).resolve().parent.parent
    reg_path = repo_root / "specs" / "aeib_hazard_register.yaml"
    res = DelegatedTaintAndHazardGate.verify_hazard_register_file(reg_path)
    assert res["verified_hazard_ids"] == ["H-01", "H-02", "H-03", "H-04", "H-05", "H-06"]

    incomplete_yaml = tmp_path / "incomplete_hazard.yaml"
    incomplete_yaml.write_text('hazard_id: "H-01"\nname: "duplicate_payment"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="HALT_INCOMPLETE_HAZARD_REGISTER"):
        DelegatedTaintAndHazardGate.verify_hazard_register_file(incomplete_yaml)

    # Clean payload passes
    DelegatedTaintAndHazardGate.scan_payload_for_secret_leakage(
        {"tool": "refund_api_v1", "invoice_id": "inv-100"}
    )

    # Leaked credential halts fail-closed
    with pytest.raises(ValueError, match="HALT_SECRET_LEAKAGE_DETECTED"):
        DelegatedTaintAndHazardGate.scan_payload_for_secret_leakage(
            {"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload"}
        )
