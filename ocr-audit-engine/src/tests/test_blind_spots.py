"""Unit tests for the 6 Operational Blind Spots and Hardened Enforcement Primitives."""

import time
import pytest
from ocr_audit.saga_reconciler import SagaReconciler
from ocr_audit.kms_enclave import HardwareAttestationKMS
from ocr_audit.rce_cockpit import RceCockpit
from ocr_audit.psi_circuit_breaker import PsiCircuitBreaker
from ocr_audit.capability_attenuation import CapabilityAttenuator
from ocr_audit.offline_ast_updater import OfflineAstHeuristicUpdater
from ocr_audit.kernel_omission_enforcer import KernelOmissionEnforcer
from ocr_audit.pre_access_gate import PreAccessComplianceGate


def test_saga_reconciler_confirmed():
    reconciler = SagaReconciler(sla_timeout_sec=300.0)
    receipt = {
        "capsule": {
            "txid": "tx-payment-1001",
            "amount": 150000.0,
            "timestamp": time.time(),
        }
    }
    wire_proof = {
        "target_committed": True,
        "valid_time_confirmed": True,
    }
    status, details = reconciler.reconcile_receipt(receipt, wire_proof)
    assert status == "CONFIRMED"
    assert details["status"] == "CONFIRMED"
    assert reconciler.ledger_state["tx-payment-1001"] == 150000.0


def test_saga_reconciler_compensated_rollback():
    reconciler = SagaReconciler(sla_timeout_sec=300.0)
    receipt = {
        "capsule": {
            "txid": "tx-payment-504-drop",
            "amount": 250000.0,
            "timestamp": time.time(),
        }
    }
    wire_proof = {
        "target_committed": False,
        "valid_time_confirmed": False,
    }
    status, details = reconciler.reconcile_receipt(receipt, wire_proof)
    assert status == "COMPENSATED_ROLLBACK"
    assert details["action"] == "REVERT_TRANSFER"
    assert details["delta_net"] == 0.00
    assert details["compensation_txid"].startswith("revert-")
    assert reconciler.ledger_state["tx-payment-504-drop"] == 0.0


def test_saga_reconciler_manual_escalation():
    reconciler = SagaReconciler(sla_timeout_sec=10.0)
    receipt = {
        "capsule": {
            "txid": "tx-conflict-01",
            "amount": 500000.0,
            "timestamp": time.time() - 20.0,  # Expired past 10s SLA
        }
    }
    wire_proof = {"conflict_detected": True}
    status, details = reconciler.reconcile_receipt(receipt, wire_proof)
    assert status == "MANUAL_ESCALATION"
    assert details["requires_dual_control_signoff"] is True


def test_hardware_kms_and_drl():
    kms = HardwareAttestationKMS(hardware_target="TPM2_0")
    quote = kms.get_enclave_quote("sha256-payload-digest-abcdef123456")
    assert quote["hardware_target"] == "TPM2_0"
    assert len(quote["pcr_quote"]) == 64

    actor = "did:key:z6MkpTHR8VNsBxYAAWeSt22wnP5r498gK2T3vE4t"
    assert kms.verify_drl(actor) is True
    kms.revoke_did(actor, reason="KEY_EXPOSURE")
    assert kms.verify_drl(actor) is False


def test_rce_cockpit_lifecycle():
    cockpit = RceCockpit()
    snapshot = cockpit.create_snapshot(
        workflow_id="wf-treasury-99",
        action_id="act-sepa-transfer",
        ast_callstack=["dispatch_payment", "execute_wire"],
        memory_diff={"amount": 420000.0, "status": "UNKNOWN"},
    )
    assert snapshot["status"] == "PAUSED_AWAITING_HUMAN_GATE"

    rendered = cockpit.render_terminal_cockpit(snapshot)
    assert "RCE COCKPIT" in rendered
    assert "wf-treasury-99" in rendered

    # Decision validation
    assert cockpit.validate_operator_decision("sig:ed25519:validhash", "RESUME", "act-sepa-transfer") is True
    assert cockpit.validate_operator_decision("sig:ed25519:validhash", "ABORT", "act-sepa-transfer") is True
    assert cockpit.validate_operator_decision("invalid_sig", "RESUME", "act-sepa-transfer") is False
    assert cockpit.validate_operator_decision("sig:ed25519:validhash", "INVALID_ACTION", "act-sepa-transfer") is False


def test_psi_circuit_breaker():
    breaker = PsiCircuitBreaker(memory_threshold_pct=90.0)
    pressure = breaker.get_memory_pressure_pct()
    assert isinstance(pressure, float)
    assert breaker.should_shed_tasks() is False  # Safe baseline

    hot_breaker = PsiCircuitBreaker(memory_threshold_pct=5.0)
    assert hot_breaker.should_shed_tasks() is True


def test_capability_attenuation():
    attenuator = CapabilityAttenuator()
    root_cap = attenuator.mint_root_capability(
        parent_agent="did:root:orchestrator",
        tool_allowlist=["read_db", "query_ledger", "transfer_funds"],
        spending_cap_eur=100000.0,
        ttl_sec=3600,
    )
    assert root_cap["depth"] == 0

    # Attenuate to sub-agent
    child_cap = attenuator.attenuate_sub_capability(
        parent_cap=root_cap,
        child_agent="did:child:payment_worker",
        requested_tools=["query_ledger", "transfer_funds", "unauthorized_admin_tool"],
        requested_cap_eur=25000.0,
    )
    assert child_cap["depth"] == 1
    # Verify unauthorized tool was stripped monotonically
    assert "unauthorized_admin_tool" not in child_cap["tool_allowlist"]
    assert "transfer_funds" in child_cap["tool_allowlist"]
    assert child_cap["spending_cap_eur"] == 25000.0
    assert child_cap["ttl_sec"] == 1800

    # Verification function
    assert attenuator.verify_capability(child_cap, "transfer_funds", 20000.0) is True
    assert attenuator.verify_capability(child_cap, "transfer_funds", 30000.0) is False  # Exceeds cap
    assert attenuator.verify_capability(child_cap, "read_db", 1000.0) is False  # Not in child allowlist


def test_offline_ast_heuristic_updater():
    updater = OfflineAstHeuristicUpdater()
    sample_traces = [
        {"verdict": "CONFIRMED", "policy_rule_id": "RULE_1", "ast_callstack": ["dispatch"]},
        {"verdict": "REJECT_FAIL_CLOSED", "policy_rule_id": "RULE_2", "ast_callstack": ["dispatch", "sql_mutation"]},
        {"verdict": "UNKNOWN", "policy_rule_id": "RULE_3", "ast_callstack": ["dispatch", "http_post_payment"]},
    ]
    result = updater.process_offline_traces(sample_traces)
    assert result["processed_traces"] == 3
    assert result["rejections_found"] == 2
    assert result["ast_rules_tightened"] == 2
    assert result["cloud_egress_bytes"] == 0
    assert result["rules"][0]["node_path"] == "sql_mutation"
    assert result["rules"][1]["node_path"] == "http_post_payment"


def test_kernel_omission_enforcer():
    enforcer = KernelOmissionEnforcer(max_unregistered_delta_sec=0.050)
    sock1 = enforcer.register_socket_connect(socket_fd=12, remote_ip="10.0.0.5", port=443)
    sock2 = enforcer.register_socket_connect(socket_fd=14, remote_ip="10.0.0.8", port=5432)

    # Emit capsule for sock1 immediately
    matched = enforcer.register_capsule_emission(capsule_id="capsule-101", sock_key=sock1)
    assert matched is True

    # Sleep past max delta for sock2
    time.sleep(0.060)
    dangling = enforcer.audit_dangling_sockets()
    assert len(dangling) == 1
    assert dangling[0]["socket"] == sock2
    assert dangling[0]["violation"] == "SILENT_OMISSION_UNCACHED_EGRESS"


def test_pre_access_compliance_gate_spiffe_and_scitt():
    gate = PreAccessComplianceGate()

    valid_svid = "spiffe://smaos.internal/ns/workloads/sa/payment-agent-01"
    valid_capsule = {
        "capsule": {
            "policy_id": "pol-dora-art17-strict",
            "payload_hash": "sha256-abcdef123456",
            "execution_mode": "AIR_GAPPED",
        },
        "signature": "sig:ed25519:validkmsquote999",
    }

    # 1. Valid handshake
    admitted, reason = gate.evaluate_handshake(valid_svid, valid_capsule)
    assert admitted is True
    assert "ADMISSIBLE" in reason

    # 2. Invalid SVID
    bad_svid = "spiffe://rogue.external/workload"
    admitted, reason = gate.evaluate_handshake(bad_svid, valid_capsule)
    assert admitted is False
    assert "Invalid or expired SPIFFE SVID" in reason

    # 3. Non-airgapped execution mode
    online_capsule = {
        "capsule": {
            "policy_id": "pol-dora-art17-strict",
            "payload_hash": "sha256-abcdef123456",
            "execution_mode": "CLOUD_EGRESS_PERMITTED",
        },
        "signature": "sig:ed25519:validkmsquote999",
    }
    admitted, reason = gate.evaluate_handshake(valid_svid, online_capsule)
    assert admitted is False
    assert "AIR_GAPPED execution mode" in reason

    # 4. Unsigned SCITT capsule
    unsigned_capsule = {
        "capsule": {
            "policy_id": "pol-dora-art17-strict",
            "payload_hash": "sha256-abcdef123456",
            "execution_mode": "AIR_GAPPED",
        }
    }
    admitted, reason = gate.evaluate_handshake(valid_svid, unsigned_capsule)
    assert admitted is False
    assert "Invalid or unsigned SCITT" in reason
