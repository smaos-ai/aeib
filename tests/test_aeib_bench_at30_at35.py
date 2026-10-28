#!/usr/bin/env python3
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

r"""
tests/test_aeib_bench_at30_at35.py — Acceptance Test Matrix AT30 through AT35
Prior-art adjusted operational integration contract tests:

- AT30: Operation identity collision (same canonical payload, different operation_id -> distinct intent records)
- AT31: Request mutation (same operation_id, different request_digest -> reject with REQUEST_DIGEST_MUTATED)
- AT32: Idempotency-key mismatch (same business key, different payload -> IDEMPOTENCY_KEY_PAYLOAD_MISMATCH)
- AT33: LIMBO-style late commit (bounded wait expires, target commits later -> no blind retry -> later probe resolves state)
- AT34: Missing read-back (no status endpoint -> EFFECT_INDETERMINATE -> release blocked, no claim of absence)
- AT35: OTel projection (AEIB receipt -> OTel tool span/event gen_ai.effect_disposition)
"""

import hashlib
import json
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    CandidateAction,
)
from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


class TestAEIBBenchAT30AT35:
    """Acceptance test suite for scenarios AT30 through AT35."""

    def setup_method(self):
        self.boundary = GovernanceDecisionBoundary(
            active_policy_epoch="policy:epoch_104",
            active_standing_version="standing:v2026.10.07-epoch-14"
        )
        self.boundary.register_agent("agent:org:dept:subagent-01")

        self.identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104",
        )

    def test_at30_operation_identity_collision(self):
        """
        AT30: Operation Identity Collision Test.
        Two transactions have the exact same canonical payload (e.g. identical amount and beneficiary),
        but different operation_id. They MUST be recorded as distinct intent records in the ledger
        with distinct entry hashes, not conflated as duplicate content.
        """
        payload = {"recipient": "IBAN_CZ88000000001", "amount": 5000, "currency": "EUR"}
        canonical = encode_jcs(payload)
        digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"

        action_1 = CandidateAction(
            noun="Treasury",
            verb="Transfer",
            payload=payload,
            operation_id="op:01J_ALPHA_TX1",
            request_digest=digest,
            business_idempotency_key="idemp:biz_batch_1"
        )
        action_2 = CandidateAction(
            noun="Treasury",
            verb="Transfer",
            payload=payload,
            operation_id="op:01J_BETA_TX2",
            request_digest=digest,
            business_idempotency_key="idemp:biz_batch_2"
        )

        hash_1 = self.boundary.record_intent_operation(
            operation_id=action_1.operation_id,
            request_digest=digest,
            principal_id=self.identity.principal_id,
            candidate=action_1
        )
        hash_2 = self.boundary.record_intent_operation(
            operation_id=action_2.operation_id,
            request_digest=digest,
            principal_id=self.identity.principal_id,
            candidate=action_2
        )

        assert hash_1 != hash_2, "Distinct operations must yield distinct cryptographic ledger entries"
        assert len(self.boundary.ledger.entries) == 2, "Both transactions must be recorded independently"
        assert self.boundary.ledger.entries[0]["data"]["operation_id"] == "op:01J_ALPHA_TX1"
        assert self.boundary.ledger.entries[1]["data"]["operation_id"] == "op:01J_BETA_TX2"
        assert self.boundary.ledger.verify_integrity(), "Hash chain must remain valid"

    def test_at31_request_mutation(self):
        """
        AT31: Request Mutation Test.
        An action has an approved request_digest. If the arguments are modified prior to dispatch
        under the same operation_id, the gateway must reject the dispatch with REQUEST_DIGEST_MUTATED.
        """
        approved_payload = {"recipient": "IBAN_CZ88000000001", "amount": 1000}
        approved_canonical = encode_jcs(approved_payload)
        approved_digest = f"sha256:{hashlib.sha256(approved_canonical).hexdigest()}"

        # Tampered payload with amount altered to 9999
        tampered_payload = {"recipient": "IBAN_CZ88000000001", "amount": 9999}
        candidate = CandidateAction(
            noun="Treasury",
            verb="Transfer",
            payload=tampered_payload,
            operation_id="op:01J_MUT_TEST",
            approved_request_digest=approved_digest
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, self.identity, current_time_ms=1000)
        assert not decision.permitted
        assert decision.disposition == "REQUEST_DIGEST_MUTATED"
        assert not decision.retry_safe
        assert decision.containment_level == "C3"

    def test_at32_idempotency_key_mismatch(self):
        """
        AT32: Idempotency-Key Mismatch Test.
        Reusing an existing business idempotency key with conflicting payload parameters violates
        the provider idempotency contract and must be rejected with IDEMPOTENCY_KEY_PAYLOAD_MISMATCH.
        """
        payload_a = {"recipient": "IBAN_CZ88000000001", "amount": 100}
        candidate_a = CandidateAction(
            noun="Treasury",
            verb="Transfer",
            payload=payload_a,
            operation_id="op:01J_IDEMP_1",
            business_idempotency_key="idemp:fixed_biz_key_99"
        )
        decision_a = self.boundary.evaluate_pre_dispatch(candidate_a, self.identity, current_time_ms=1000)
        assert decision_a.permitted
        assert decision_a.disposition == "DISPATCH_PERMITTED"

        # Conflicting payload with same business idempotency key
        payload_b = {"recipient": "IBAN_CZ88000000001", "amount": 900}
        candidate_b = CandidateAction(
            noun="Treasury",
            verb="Transfer",
            payload=payload_b,
            operation_id="op:01J_IDEMP_2",
            business_idempotency_key="idemp:fixed_biz_key_99"
        )
        decision_b = self.boundary.evaluate_pre_dispatch(candidate_b, self.identity, current_time_ms=1010)
        assert not decision_b.permitted
        assert decision_b.disposition == "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH"
        assert not decision_b.retry_safe
        assert decision_b.containment_level == "C3"

    def test_at33_limbo_style_late_commit(self):
        """
        AT33: LIMBO-Style Late Commit Evaluation.
        Bounded wait expires (5000ms), but target commits later (7000ms).
        - At bounded wait expiration: wire timeout produces EFFECT_INDETERMINATE, retry_safe: False (zero speculative retry).
        - At subsequent probe (8000ms): resolves state to LATE_COMMIT_RESOLVED, effect_status: COMMITTED.
        """
        op_id = "op:01J_LIMBO_LATE"
        biz_key = "idemp:limbo_tx_42"

        # Observation at 5000ms (timeout expired, target has not yet committed)
        obs_timeout = self.boundary.evaluate_late_commit_probe(
            operation_id=op_id,
            business_key=biz_key,
            wait_timeout_ms=5000,
            target_commit_time_ms=7000,
            current_probe_time_ms=5000
        )
        assert obs_timeout["disposition"] == "EFFECT_INDETERMINATE"
        assert obs_timeout["effect_status"] == "UNKNOWN"
        assert not obs_timeout["retry_safe"]
        assert not obs_timeout["late_commit_observed"]

        # Subsequent probe at 8000ms (target committed at 7000ms)
        obs_resolved = self.boundary.evaluate_late_commit_probe(
            operation_id=op_id,
            business_key=biz_key,
            wait_timeout_ms=5000,
            target_commit_time_ms=7000,
            current_probe_time_ms=8000
        )
        assert obs_resolved["disposition"] == "LATE_COMMIT_RESOLVED"
        assert obs_resolved["effect_status"] == "COMMITTED"
        assert not obs_resolved["retry_safe"]
        assert obs_resolved["late_commit_observed"]

    def test_at34_missing_readback(self):
        """
        AT34: Missing Read-Back Target Evaluation.
        When target system lacks a read-back status endpoint, the system cannot reconcile.
        It must latch EFFECT_INDETERMINATE, block release authorization, and make NO speculative claim of absence.
        """
        res = self.boundary.evaluate_missing_readback(
            operation_id="op:01J_NO_STATUS",
            target_has_status_api=False
        )
        assert res["disposition"] == "EFFECT_INDETERMINATE"
        assert res["effect_status"] == "UNKNOWN"
        assert not res["retry_safe"]
        assert res["reconciliation_status"] == "READBACK_UNAVAILABLE"
        assert res["release_authorization"] == "BLOCKED"
        assert not res["absence_claimed"]

    def test_at35_otel_projection(self):
        """
        AT35: OpenTelemetry GenAI Semantic Convention Event Projection.
        Asserts that an AEIB governance receipt projects cleanly into a standard gen_ai.effect_disposition event
        preserving operation_id, tool_call_id, request_digest, effect_status, and retry_safe.
        """
        payload = {"to": "vendor_99", "amount": 2500}
        candidate = CandidateAction(
            noun="Disbursement",
            verb="Execute",
            payload=payload,
            operation_id="op:01J_OTEL_77",
            business_idempotency_key="idemp:disburse_77"
        )
        decision = self.boundary.evaluate_pre_dispatch(candidate, self.identity, current_time_ms=1000)
        assert decision.permitted

        receipt = self.boundary.sign_governance_receipt(candidate, self.identity, decision)
        otel_event = self.boundary.project_to_otel_event(receipt, tool_call_id="call_openai_9921_xyz")

        assert otel_event["event.name"] == "gen_ai.effect_disposition"
        assert otel_event["gen_ai.operation_id"] == "op:01J_OTEL_77"
        assert otel_event["gen_ai.tool.call.id"] == "call_openai_9921_xyz"
        assert otel_event["aeib.request_digest"].startswith("sha256:")
        assert otel_event["aeib.effect_status"] == "COMMITTED"
        assert not otel_event["aeib.retry_safe"]
        assert otel_event["aeib.release_authorization"] == "NOT_PROVIDED"
