#!/usr/bin/env python3
"""
tests/test_external_idempotency_probes.py — Zero-Mock Unit & Mutation Verification Suite for External Probes

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.
"""

from __future__ import annotations

import json
import pytest

from src.external_idempotency_probes import (
    AuthoritativeProbeIndeterminateError,
    AuthoritativeProbeReceipt,
    DeterministicSimulatedProbeTransport,
    ExternalIdempotencyProbeOrchestrator,
    GenericRestAuditProbe,
    GitHubCommitOrPrProbe,
    IdempotencyProbeOutcome,
    ProbeTransportResponse,
    StripeIdempotencyKeyProbe,
)
from src.substrate_cube_interlock import (
    SubstrateCubeInterlock,
    SubstrateCubeInterlockManager,
)


def test_1_github_probe_commit_and_pr_discovery() -> None:
    transport = DeterministicSimulatedProbeTransport()
    probe = GitHubCommitOrPrProbe()

    caid = "sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    actor = "spiffe://sovereign.nexus/agent/builder_01"

    # Route 1: CAID found in commit message
    commits_body = json.dumps([
        {
            "sha": "c0ffee1234567890",
            "commit": {"message": f"feat: implement secure gateway\nX-EO1-Intent-CAID: {caid}"},
        }
    ]).encode("utf-8")
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/commits?sha=main", 200, {}, commits_body)

    outcome, meta = probe.probe_effect(transport, actor, caid, {})
    assert outcome == IdempotencyProbeOutcome.SUCCESS_CONFIRMED
    assert meta["commit_sha"] == "c0ffee1234567890"
    assert meta["verified_at_endpoint"] == "commits"

    # Route 2: CAID not in commits, but found in Pull Request body
    caid_pr = "sha256:9999888877776666555544443333222211110000aaaabbbbccccddddeeeeffff"
    empty_commits = b"[]"
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/commits?sha=develop", 200, {}, empty_commits)
    pulls_body = json.dumps([
        {
            "number": 42,
            "title": "PR Title",
            "body": f"Automated merge request with intent {caid_pr}",
        }
    ]).encode("utf-8")
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/pulls?state=all", 200, {}, pulls_body)

    outcome_pr, meta_pr = probe.probe_effect(transport, actor, caid_pr, {"branch": "develop"})
    assert outcome_pr == IdempotencyProbeOutcome.SUCCESS_CONFIRMED
    assert meta_pr["pull_number"] == 42
    assert meta_pr["verified_at_endpoint"] == "pulls"

    # Route 3: CAID found in PR title
    caid_title = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    pulls_title_body = json.dumps([
        {
            "number": 43,
            "title": f"Patch for {caid_title}",
            "body": "No caid here",
        }
    ]).encode("utf-8")
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/pulls?state=all", 200, {}, pulls_title_body)
    outcome_t, meta_t = probe.probe_effect(transport, actor, caid_title, {"branch": "develop"})
    assert outcome_t == IdempotencyProbeOutcome.SUCCESS_CONFIRMED
    assert meta_t["pull_number"] == 43

    # Route 4: Neither commit nor PR contains CAID -> FAILURE_CONFIRMED
    caid_missing = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    pulls_empty = b"[]"
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/pulls?state=all", 200, {}, pulls_empty)
    outcome_fail, meta_fail = probe.probe_effect(transport, actor, caid_missing, {"branch": "develop"})
    assert outcome_fail == IdempotencyProbeOutcome.FAILURE_CONFIRMED
    assert meta_fail["reason"] == "CAID_NOT_FOUND_IN_COMMITS_OR_PRS"


def test_2_stripe_and_generic_rest_probes() -> None:
    transport = DeterministicSimulatedProbeTransport()
    stripe_probe = StripeIdempotencyKeyProbe()
    rest_probe = GenericRestAuditProbe("aiplatform.googleapis.com")

    actor = "spiffe://sovereign.nexus/agent/billing_01"
    caid = "sha256:stripe_test_caid_1111222233334444555566667777888899990000aaaabbbb"

    # Stripe Case A: Event found
    events_body = json.dumps({
        "data": [{"id": "evt_12345", "type": "payment_intent.succeeded"}]
    }).encode("utf-8")
    transport.register_route("GET", "api.stripe.com", f"/v1/events?idempotency_key={caid}", 200, {}, events_body)
    outcome, meta = stripe_probe.probe_effect(transport, actor, caid, {})
    assert outcome == IdempotencyProbeOutcome.SUCCESS_CONFIRMED
    assert meta["event_id"] == "evt_12345"
    assert meta["event_type"] == "payment_intent.succeeded"

    # Stripe Case B: 404 Not Found
    transport.register_route("GET", "api.stripe.com", f"/v1/events?idempotency_key={caid}_missing", 404, {}, b'{"error": "not_found"}')
    outcome_404, meta_404 = stripe_probe.probe_effect(transport, actor, f"{caid}_missing", {})
    assert outcome_404 == IdempotencyProbeOutcome.FAILURE_CONFIRMED
    assert meta_404["reason"] == "KEY_NOT_FOUND_404"

    # Stripe Case C: Empty event list
    transport.register_route("GET", "api.stripe.com", f"/v1/events?idempotency_key={caid}_empty", 200, {}, b'{"data": []}')
    outcome_empty, meta_empty = stripe_probe.probe_effect(transport, actor, f"{caid}_empty", {})
    assert outcome_empty == IdempotencyProbeOutcome.FAILURE_CONFIRMED
    assert meta_empty["reason"] == "EMPTY_EVENT_LOG_FOR_KEY"

    # Generic REST Case A: 200 OK
    transport.register_route("GET", "aiplatform.googleapis.com", f"/api/v1/intent-receipts/{caid}", 200, {}, b'{"status": "CONFIRMED"}')
    res_outcome, res_meta = rest_probe.probe_effect(transport, actor, caid, {})
    assert res_outcome == IdempotencyProbeOutcome.SUCCESS_CONFIRMED
    assert res_meta["http_status"] == 200

    # Generic REST Case B: 204 No Content
    transport.register_route("GET", "aiplatform.googleapis.com", f"/api/v1/intent-receipts/{caid}_204", 204, {}, b"")
    res_outcome_204, _ = rest_probe.probe_effect(transport, actor, f"{caid}_204", {})
    assert res_outcome_204 == IdempotencyProbeOutcome.SUCCESS_CONFIRMED

    # Generic REST Case C: 404
    transport.register_route("GET", "aiplatform.googleapis.com", f"/api/v1/intent-receipts/{caid}_404", 404, {}, b'{"error": "not found"}')
    res_outcome_404, _ = rest_probe.probe_effect(transport, actor, f"{caid}_404", {})
    assert res_outcome_404 == IdempotencyProbeOutcome.FAILURE_CONFIRMED


def test_3_transport_failure_modes_and_indeterminate_timeouts() -> None:
    transport = DeterministicSimulatedProbeTransport()
    gh_probe = GitHubCommitOrPrProbe()
    stripe_probe = StripeIdempotencyKeyProbe()
    rest_probe = GenericRestAuditProbe("api.anthropic.com")

    actor = "spiffe://sovereign.nexus/agent/bot_01"
    caid = "sha256:fault_injection_caid"

    # 1. GitHub 502 Bad Gateway
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/commits?sha=main", 502, {}, b"Bad Gateway")
    out_gh, _ = gh_probe.probe_effect(transport, actor, caid, {})
    assert out_gh == IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT

    # 2. Stripe Simulated Network Timeout
    transport.set_timeout_for_host("api.stripe.com", True)
    out_stripe, _ = stripe_probe.probe_effect(transport, actor, caid, {})
    assert out_stripe == IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT

    # 3. Generic REST 500 Internal Server Error
    transport.register_route("GET", "api.anthropic.com", f"/api/v1/intent-receipts/{caid}", 500, {}, b"Internal Error")
    out_rest, _ = rest_probe.probe_effect(transport, actor, caid, {})
    assert out_rest == IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT

    # 4. Pulls endpoint returns 500 when commits was clean
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/commits?sha=main", 200, {}, b"[]")
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/pulls?state=all", 500, {}, b"PR DB Down")
    out_pr_down, meta_pr_down = gh_probe.probe_effect(transport, actor, caid, {})
    assert out_pr_down == IdempotencyProbeOutcome.INDETERMINATE_TIMEOUT
    assert meta_pr_down["phase"] == "PULLS_LOOKUP"


def test_4_orchestrator_sqlite_wal_reconciliation_lifecycle() -> None:
    orchestrator = ExternalIdempotencyProbeOrchestrator()
    transport = DeterministicSimulatedProbeTransport()
    mgr = SubstrateCubeInterlockManager(":memory:")

    actor = "spiffe://sovereign.nexus/agent/orchestrator_agent"
    req_success = "req_success_1001"
    req_failed = "req_failed_1002"
    req_timeout = "req_timeout_1003"

    mgr.register_actor(actor, actor)

    # 1. Dispatch 3 mutating requests and trigger AutoPause to freeze them
    mgr.submit_request(req_success, actor, "POST", "https://api.github.com/commits", '{"action": "commit"}', "idem_01")
    mgr.submit_request(req_failed, actor, "POST", "https://api.stripe.com/charges", '{"action": "charge"}', "idem_02")
    mgr.submit_request(req_timeout, actor, "POST", "https://aiplatform.googleapis.com/predict", '{"action": "inference"}', "idem_03")

    mgr.trigger_autopause(actor, b"snap_hash_wal_001")
    resume_receipt = mgr.trigger_autoresume(actor)
    assert resume_receipt["new_state"] == "RESUMED_PROBE_REQUIRED"
    assert resume_receipt["pending_indeterminate_count"] == 3

    # Route configuration in transport
    # A: GitHub success
    commits_body = json.dumps([{"sha": "abc1234", "commit": {"message": f"merge {req_success}"}}]).encode("utf-8")
    transport.register_route("GET", "api.github.com", "/repos/sovereign-nexus/core-repo/commits?sha=main", 200, {}, commits_body)

    receipt_1 = orchestrator.execute_and_reconcile(
        actor_spiffe_id=actor,
        effect_key_caid=req_success,
        target_host="api.github.com",
        transport=transport,
        interlock_manager=mgr,
    )
    assert receipt_1.probe_outcome == "SUCCESS_CONFIRMED"
    assert receipt_1.resolved_status == "COMMITTED"
    assert orchestrator.verify_probe_receipt(receipt_1) is True

    # B: Stripe failure (not committed downstream)
    transport.register_route("GET", "api.stripe.com", f"/v1/events?idempotency_key={req_failed}", 404, {}, b'{"error":"none"}')
    receipt_2 = orchestrator.execute_and_reconcile(
        actor_spiffe_id=actor,
        effect_key_caid=req_failed,
        target_host="api.stripe.com",
        transport=transport,
        interlock_manager=mgr,
    )
    assert receipt_2.probe_outcome == "FAILURE_CONFIRMED"
    assert receipt_2.resolved_status == "ROLLED_BACK"
    assert orchestrator.verify_probe_receipt(receipt_2) is True

    # C: Google Vertex timeout (cannot resolve, must fail closed)
    transport.set_timeout_for_host("aiplatform.googleapis.com", True)
    with pytest.raises(AuthoritativeProbeIndeterminateError, match="ERR_PROBE_INDETERMINATE_TIMEOUT"):
        orchestrator.execute_and_reconcile(
            actor_spiffe_id=actor,
            effect_key_caid=req_timeout,
            target_host="aiplatform.googleapis.com",
            transport=transport,
            interlock_manager=mgr,
        )

    # Actor state must remain RESUMED_PROBE_REQUIRED because req_timeout is still indeterminate!
    cursor = mgr.conn.cursor()
    cursor.execute("SELECT state FROM actor_state WHERE actor_id = ?", (actor,))
    assert cursor.fetchone()["state"] == "RESUMED_PROBE_REQUIRED"

    # Now recover Vertex AI and resolve the final indeterminate request
    transport.set_timeout_for_host("aiplatform.googleapis.com", False)
    transport.register_route("GET", "aiplatform.googleapis.com", f"/api/v1/intent-receipts/{req_timeout}", 200, {}, b'{"ok": true}')

    receipt_3 = orchestrator.execute_and_reconcile(
        actor_spiffe_id=actor,
        effect_key_caid=req_timeout,
        target_host="aiplatform.googleapis.com",
        transport=transport,
        interlock_manager=mgr,
    )
    assert receipt_3.probe_outcome == "SUCCESS_CONFIRMED"

    # Now all 3 requests are resolved, actor state must transition to ACTOR_ACTIVE
    cursor.execute("SELECT state FROM actor_state WHERE actor_id = ?", (actor,))
    assert cursor.fetchone()["state"] == "ACTOR_ACTIVE"
    mgr.close()


def test_5_orchestrator_in_memory_interlock_and_signature_tamper_detection() -> None:
    orchestrator = ExternalIdempotencyProbeOrchestrator()
    transport = DeterministicSimulatedProbeTransport()
    interlock = SubstrateCubeInterlock(
        trusted_spiffe_prefix="spiffe://sovereign.nexus/agent/",
        allowed_egress_hosts=frozenset({"localhost"}),
        credential_vault={},
    )

    actor = "spiffe://sovereign.nexus/agent/local_worker"
    caid = "sha256:in_memory_caid_9999"

    # Simulate in-memory interlock mid-flight pause
    interlock.intercept_outbound_egress(actor, "localhost", "POST", {"task": "local"}, {})
    interlock.auto_pause_actor(actor, "cube_kvm", b"MEMORY", True)
    assert interlock.get_effect_state(caid) in ("EFFECT_INDETERMINATE", "UNSEEN")

    # Set indeterminate state directly for reconciliation test
    interlock._effect_ledger[caid] = "EFFECT_INDETERMINATE"

    # Register local probe
    transport.register_route("GET", "localhost", f"/api/v1/intent-receipts/{caid}", 200, {}, b'{"executed": true}')

    receipt = orchestrator.execute_and_reconcile(
        actor_spiffe_id=actor,
        effect_key_caid=caid,
        target_host="localhost",
        transport=transport,
        interlock_manager=interlock,
    )
    assert receipt.probe_outcome == "SUCCESS_CONFIRMED"
    assert interlock.get_effect_state(caid) == "COMMITTED"
    assert orchestrator.verify_probe_receipt(receipt) is True

    # Tamper test: mutate metadata or timestamp in receipt
    tampered_receipt = AuthoritativeProbeReceipt(
        actor_spiffe_id=receipt.actor_spiffe_id,
        effect_key_caid=receipt.effect_key_caid,
        target_host=receipt.target_host,
        probe_outcome=receipt.probe_outcome,
        resolved_status="ROLLED_BACK",  # Tampered field!
        probe_metadata=receipt.probe_metadata,
        timestamp_epoch_s=receipt.timestamp_epoch_s,
        receipt_caid=receipt.receipt_caid,
        signature_secp256r1_hex=receipt.signature_secp256r1_hex,
    )
    assert orchestrator.verify_probe_receipt(tampered_receipt) is False

    # Tamper test 2: corrupt signature hex
    tampered_sig = AuthoritativeProbeReceipt(
        actor_spiffe_id=receipt.actor_spiffe_id,
        effect_key_caid=receipt.effect_key_caid,
        target_host=receipt.target_host,
        probe_outcome=receipt.probe_outcome,
        resolved_status=receipt.resolved_status,
        probe_metadata=receipt.probe_metadata,
        timestamp_epoch_s=receipt.timestamp_epoch_s,
        receipt_caid=receipt.receipt_caid,
        signature_secp256r1_hex="00" * 32,
    )
    assert orchestrator.verify_probe_receipt(tampered_sig) is False


def test_6_input_validation_and_unregistered_hosts() -> None:
    orchestrator = ExternalIdempotencyProbeOrchestrator()
    transport = DeterministicSimulatedProbeTransport()

    # Case A: Untrusted SPIFFE ID
    with pytest.raises(ValueError, match="ERR_UNTRUSTED_SPIFFE_PREFIX"):
        orchestrator.execute_and_reconcile(
            actor_spiffe_id="spiffe://attacker.nexus/agent/rogue",
            effect_key_caid="sha256:caid",
            target_host="api.github.com",
            transport=transport,
        )

    # Case B: Unregistered target host
    with pytest.raises(KeyError, match="ERR_UNREGISTERED_PROBE_HOST"):
        orchestrator.execute_and_reconcile(
            actor_spiffe_id="spiffe://sovereign.nexus/agent/valid",
            effect_key_caid="sha256:caid",
            target_host="unregistered-exfil.org",
            transport=transport,
        )

    # Case C: ProbeTransportResponse json parsing helper coverage
    resp_empty = ProbeTransportResponse(200, {}, b"")
    assert resp_empty.json_payload() == {}

    resp_non_json = ProbeTransportResponse(200, {}, b"raw unparseable text")
    assert resp_non_json.json_payload() == {"raw_string": "raw unparseable text"}

    resp_scalar_json = ProbeTransportResponse(200, {}, b"12345")
    assert resp_scalar_json.json_payload() == {"data": 12345}


def test_7_mutation_killers_and_exact_invariants() -> None:
    transport = DeterministicSimulatedProbeTransport()
    # 1. Kill line 131 (exact 504)
    transport.set_timeout_for_host("test.timeout", True)
    resp_timeout = transport.execute_probe("GET", "test.timeout", "/any", {}, 1000)
    assert resp_timeout.status_code == 504
    assert resp_timeout.headers["X-Probe-Error"] == "GATEWAY_TIMEOUT"

    # 2. Kill line 141 (unmapped route returns exact 404 response object)
    resp_unmapped = transport.execute_probe("GET", "unmapped.host", "/not-there", {}, 1000)
    assert resp_unmapped is not None
    assert resp_unmapped.status_code == 404
    assert resp_unmapped.headers["X-Probe-Result"] == "NOT_FOUND"

    # 3. Call history assertion
    assert len(transport.call_history) == 2
    assert transport.call_history[0]["host"] == "test.timeout"

    # 4. JSON payload list/scalar/boolean checks
    resp_bool = ProbeTransportResponse(200, {}, b"true")
    assert resp_bool.json_payload() == {"data": True}
    resp_list = ProbeTransportResponse(200, {}, b'["a", "b"]')
    assert resp_list.json_payload() == {"data": ["a", "b"]}
    resp_dict = ProbeTransportResponse(200, {}, b'{"key": "val"}')
    assert resp_dict.json_payload() == {"key": "val"}
