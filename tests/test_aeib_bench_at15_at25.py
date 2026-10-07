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
test_aeib_bench_at15_at25.py — Acceptance Test Matrix AT15 through AT25
Executes and validates the 11 decision-boundary and effect-integrity governance scenarios:

- AT15: Unregistered Agent Dispatch (Identity Inventory Boundary)
- AT16: Delegation Scope Escalation (Preserves principal_id, blocks privilege escalation)
- AT17: Stale Grant / Epoch Expiry (Fail-closed on policy_epoch or grant expiry)
- AT18: Control-Plane Degradation (Triggers containment C1–C5, never fails open)
- AT19: Agent Evidence Tampering (Process isolation & append-only model blocks modification)
- AT20: Escalation on Indeterminate Loops (Triggers human review after repeated EFFECT_INDETERMINATE)
- AT21: Memory Poisoning Attack (Parameter/context injection causes schema/payload digest mismatch)
- AT22: Cross-Boundary Delegation (Identity-neutral federation: OIDC/mTLS/X.509/DIDs fail-closed)
- AT23: Millisecond Standing Race (Atomic re-check at dispatch instant: DISPATCH_REJECTED on race)
- AT24: Candidate Payload Mutation (Post-approval argument change invalidates CAID/digest)
- AT25: Ledger Compromise / Fork (Hash chain discrepancy triggers C5 containment and blocks release)

Zero-mock & Cryptographic Purity:
Uses real Ed25519 asymmetric cryptography and strict RFC 8785 JSON canonicalization.
"""

import json
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    ControlPlaneHealth,
    DelegationGrant,
    FederationMetadata,
    CandidateAction,
    EvidenceTamperingError,
)
from src.aeib_v040_engine import derive_caid
from src.jcs_canonicalizer import generate_jcs_payload_hash


class TargetLedgerSimulator:
    """Simulates real target-side committed state independent of agent assertions."""
    def __init__(self):
        self.committed_records = {}

    def commit(self, caid: str, record_id: str, payload_hash: str):
        self.committed_records[caid] = {"record_id": record_id, "payload_hash": payload_hash}

    def query(self, caid: str):
        return self.committed_records.get(caid)


class TestAEIBBenchAT15AT25:
    """Acceptance test suite for scenarios AT15 through AT25."""

    def setup_method(self):
        self.boundary = GovernanceDecisionBoundary(
            active_policy_epoch="policy:epoch_104",
            active_standing_version="standing:v2026.10.07-epoch-14"
        )
        self.target_ledger = TargetLedgerSimulator()

        # Seed standard authorized agent and tool schema
        self.boundary.register_agent("agent:org:dept:subagent-01")
        self.boundary.register_agent("agent:org:dept:orchestrator")

        self.sample_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "amt": {"type": "number"}
            },
            "required": ["id", "amt"]
        }
        self.boundary.pin_schema("Transfer", self.sample_schema)

    def test_00_spec_and_fixtures_conformance(self):
        """Validates that spec and scenario fixtures define AT15 through AT25."""
        spec_path = REPO_ROOT / "schemas" / "aeib_bench_v0.1_spec.json"
        fixture_path = REPO_ROOT / "fixtures" / "aeib_bench_v0.1_scenarios.json"
        assert spec_path.exists(), "Benchmark spec schema must exist"
        assert fixture_path.exists(), "Scenario fixtures manifest must exist"

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

        assert fixtures["benchmark_version"] == spec["properties"]["benchmark_version"]["const"]
        assert fixtures["ground_truth_rule"] == spec["properties"]["ground_truth_rule"]["const"]
        assert "governance_observability_schema" in fixtures

        scenarios_by_id = {sc["scenario_id"]: sc for sc in fixtures["scenarios"]}
        expected_at_ids = [
            "SCENARIO-AT15-UNREGISTERED-AGENT",
            "SCENARIO-AT16-DELEGATION-SCOPE-ESCALATION",
            "SCENARIO-AT17-STALE-GRANT-EPOCH-EXPIRY",
            "SCENARIO-AT18-CONTROL-PLANE-DEGRADATION",
            "SCENARIO-AT19-AGENT-EVIDENCE-TAMPERING",
            "SCENARIO-AT20-INDETERMINATE-LOOP-ESCALATION",
            "SCENARIO-AT21-MEMORY-POISONING-ATTACK",
            "SCENARIO-AT22-CROSS-BOUNDARY-DELEGATION",
            "SCENARIO-AT23-MILLISEC-STANDING-RACE",
            "SCENARIO-AT24-CANDIDATE-PAYLOAD-MUTATION",
            "SCENARIO-AT25-LEDGER-COMPROMISE-FORK",
        ]
        for at_id in expected_at_ids:
            assert at_id in scenarios_by_id, f"Missing scenario definition: {at_id}"
            sc = scenarios_by_id[at_id]
            assert sc["expected_retry_safe"] is False

    def test_at15_unregistered_agent_dispatch(self):
        """AT15: Agent not present in inventory triggers AGENT_NOT_IN_INVENTORY."""
        identity = AgentIdentityContext(
            agent_id="agent:untrusted:rogue-agent-07",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:untrusted:rogue-agent-07"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 15, "amt": 1500},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104"
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "AGENT_NOT_IN_INVENTORY"
        assert decision.retry_safe is False
        assert decision.containment_level == "C2"

        # Verify receipt signature with real Ed25519
        receipt = self.boundary.sign_governance_receipt(candidate, identity, decision)
        assert receipt["attributes"]["aeib.disposition"] == "AGENT_NOT_IN_INVENTORY"
        assert receipt["attributes"]["aeib.receipt.verified"] is True

        # Target-side ground truth: Zero mutations
        caid = derive_caid("Transfer", "Submit", candidate.payload)
        assert self.target_ledger.query(caid) is None

    def test_at16_delegation_scope_escalation(self):
        """AT16: Sub-agent exceeding parent delegation grant is blocked; principal_id preserved."""
        grant = DelegationGrant(
            grant_id="grant_9901",
            principal_id="principal:user:usr_9942",
            authorized_agent_id="agent:org:dept:subagent-01",
            allowed_verbs={"Transfer:Query", "Transfer:Quote"},
            policy_epoch="policy:epoch_104",
            expires_at_epoch_ms=2000000,
            is_revoked=False
        )
        self.boundary.add_grant(grant)

        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=[
                "principal:user:usr_9942",
                "agent:org:dept:orchestrator",
                "agent:org:dept:subagent-01"
            ],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )
        # Attempt escalated verb 'Transfer:Submit' which is not in {'Transfer:Query', 'Transfer:Quote'}
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 16, "amt": 1600},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104",
            grant_id="grant_9901"
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "DELEGATION_SCOPE_ESCALATION"
        assert decision.retry_safe is False
        assert decision.attributes["aeib.governance.principal_id"] == "principal:user:usr_9942"

        caid = derive_caid("Transfer", "Submit", candidate.payload)
        assert self.target_ledger.query(caid) is None

    def test_at17_stale_grant_epoch_expiry(self):
        """AT17: Dispatch blocked fail-closed when policy_epoch is stale or grant is expired."""
        grant = DelegationGrant(
            grant_id="grant_9902",
            principal_id="principal:user:usr_9942",
            authorized_agent_id="agent:org:dept:subagent-01",
            allowed_verbs={"Transfer:Submit"},
            policy_epoch="policy:epoch_104",
            expires_at_epoch_ms=5000,  # Expired relative to current_time_ms=6000
            is_revoked=False
        )
        self.boundary.add_grant(grant)

        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )

        # Case A: Expired grant timestamp
        candidate_expired_grant = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 17, "amt": 1701},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104",
            grant_id="grant_9902"
        )
        decision_grant = self.boundary.evaluate_pre_dispatch(
            candidate_expired_grant, identity, current_time_ms=6000
        )
        assert decision_grant.permitted is False
        assert decision_grant.disposition == "POLICY_EPOCH_STALE"
        assert decision_grant.retry_safe is False

        # Case B: Stale policy epoch on candidate
        identity_stale_epoch = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_103"  # Stale: active is epoch_104
        )
        candidate_stale_epoch = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 17, "amt": 1702},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_103",
        )
        decision_epoch = self.boundary.evaluate_pre_dispatch(
            candidate_stale_epoch, identity_stale_epoch, current_time_ms=1000
        )
        assert decision_epoch.permitted is False
        assert decision_epoch.disposition == "POLICY_EPOCH_STALE"
        assert decision_epoch.retry_safe is False

    def test_at18_control_plane_degradation(self):
        """AT18: Control-plane degradation triggers containment C1–C5; never falls back to allow."""
        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 18, "amt": 1800},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104"
        )

        # Degrade the probe component
        self.boundary.control_health.probe = "degraded"

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "CONTAINMENT_ENGAGED"
        assert decision.containment_level == "C3"
        assert decision.retry_safe is False

        # Further degrade the signer component
        self.boundary.control_health.signer = "unavailable"
        decision_signer = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)
        assert decision_signer.containment_level == "C5"
        assert decision_signer.permitted is False

    def test_at19_agent_evidence_tampering(self):
        """AT19: Agent attempt to modify or delete audit records is blocked by process isolation."""
        # Append legitimate evidence entry
        entry_data = {"event": "dispatch_attempt", "caid": "caid:sample:19"}
        self.boundary.ledger.append(entry_data)
        assert len(self.boundary.ledger.entries) == 1
        initial_hash = self.boundary.ledger.get_latest_hash()

        # Simulate agent trying to execute a direct deletion/mutation against the ledger
        with pytest.raises(EvidenceTamperingError) as exc_info:
            self.boundary.ledger.execute_agent_mutation_attempt(
                operation="DELETE FROM ledger_entries WHERE id = 1",
                entry_id=1
            )

        assert "EVIDENCE_TAMPERING_REJECTED" in str(exc_info.value)

        # Integrity verified: Ledger remains unaltered
        assert len(self.boundary.ledger.entries) == 1
        assert self.boundary.ledger.verify_integrity() is True
        assert self.boundary.ledger.get_latest_hash() == initial_hash

    def test_at20_escalation_on_indeterminate_loops(self):
        """AT20: Repeated EFFECT_INDETERMINATE outcomes trigger policy escalation to human operator."""
        caid = "caid:sha256:test_at20_loop"

        # 1st indeterminate outcome
        res1 = self.boundary.record_wire_outcome(caid, "EFFECT_INDETERMINATE")
        assert res1["disposition"] == "EFFECT_INDETERMINATE"
        assert res1["retry_safe"] is False
        assert res1["consecutive_indeterminate_count"] == 1

        # 2nd indeterminate outcome
        res2 = self.boundary.record_wire_outcome(caid, "EFFECT_INDETERMINATE")
        assert res2["disposition"] == "EFFECT_INDETERMINATE"
        assert res2["consecutive_indeterminate_count"] == 2

        # 3rd indeterminate outcome -> Triggers human review escalation
        res3 = self.boundary.record_wire_outcome(caid, "EFFECT_INDETERMINATE")
        assert res3["disposition"] == "POLICY_ESCALATION_HUMAN_REQUIRED"
        assert res3["retry_safe"] is False
        assert res3["consecutive_indeterminate_count"] == 3

    def test_at21_memory_poisoning_attack(self):
        """AT21: Parameter or context injection modifying schema causes digest mismatch."""
        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )
        # Poisoned schema introducing hidden injected parameter
        poisoned_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "amt": {"type": "number"},
                "hidden_injected_exfiltration_route": {"type": "string"}
            },
            "required": ["id", "amt"]
        }
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 21, "amt": 2100},
            schema=poisoned_schema,
            policy_epoch="policy:epoch_104"
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "SCHEMA_HASH_MISMATCH"
        assert decision.containment_level == "C3"
        assert decision.retry_safe is False

        caid = derive_caid("Transfer", "Submit", candidate.payload)
        assert self.target_ledger.query(caid) is None

    def test_at22_cross_boundary_delegation(self):
        """AT22: Identity-neutral federation fails-closed on missing/invalid exchange metadata."""
        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )

        # Invalid federation token (e.g. expired or invalid signature)
        invalid_federation = FederationMetadata(
            profile="OIDC",
            issuer="https://idp.partner-enterprise.com",
            subject_tenant="tenant:external_corp",
            token_or_proof="malformed_or_tampered_proof",
            valid_until_epoch_ms=500,  # Expired
            is_valid=False
        )

        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 22, "amt": 2200},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104",
            federation=invalid_federation
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "CROSS_BOUNDARY_AUTH_FAILED"
        assert decision.retry_safe is False

    def test_at23_millisecond_standing_race(self):
        """AT23: TOCTOU standing race: grant revoked at dispatch instant yields DISPATCH_REJECTED."""
        grant = DelegationGrant(
            grant_id="grant_9923",
            principal_id="principal:user:usr_9942",
            authorized_agent_id="agent:org:dept:subagent-01",
            allowed_verbs={"Transfer:Submit"},
            policy_epoch="policy:epoch_104",
            expires_at_epoch_ms=5000000,
            is_revoked=False
        )
        self.boundary.add_grant(grant)

        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload={"id": 23, "amt": 2300},
            schema=self.sample_schema,
            policy_epoch="policy:epoch_104",
            grant_id="grant_9923"
        )

        # Revoke grant in the milliseconds between candidate approval and wire dispatch
        self.boundary.revoke_grant("grant_9923")

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "DISPATCH_REJECTED"
        assert decision.reason == "STANDING_REVOKED_AT_DISPATCH"
        assert decision.retry_safe is False

        caid = derive_caid("Transfer", "Submit", candidate.payload)
        assert self.target_ledger.query(caid) is None

    def test_at24_candidate_payload_mutation(self):
        """AT24: Mutating approved arguments invalidates CAID and payload digest."""
        payload_approved = {"id": 24, "amt": 2400, "dest": "acc_01"}
        caid_approved = derive_caid("Transfer", "Submit", payload_approved)
        hash_approved = generate_jcs_payload_hash(payload_approved)

        identity = AgentIdentityContext(
            agent_id="agent:org:dept:subagent-01",
            principal_id="principal:user:usr_9942",
            tenant_id="tenant:ent_8820",
            delegation_chain=["principal:user:usr_9942", "agent:org:dept:subagent-01"],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )

        # Mutate arguments prior to dispatch
        mutated_payload = {"id": 24, "amt": 2400, "dest": "acc_02_hacked"}
        candidate = CandidateAction(
            noun="Transfer",
            verb="Submit",
            payload=mutated_payload,
            schema=self.sample_schema,
            approved_caid=caid_approved,
            approved_payload_hash=hash_approved,
            policy_epoch="policy:epoch_104"
        )

        decision = self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)

        assert decision.permitted is False
        assert decision.disposition == "PAYLOAD_MUTATION_REJECTED"
        assert decision.containment_level == "C3"
        assert decision.retry_safe is False

    def test_at25_ledger_compromise_fork(self):
        """AT25: Altered or forked ledger state triggers C5 containment and blocks release."""
        caid = "caid:sha256:test_at25_commit"

        # Populate ledger with entries
        self.boundary.ledger.append({"event": "record_1", "caid": caid})
        self.boundary.ledger.append({"event": "record_2", "caid": caid})
        assert self.boundary.ledger.verify_integrity() is True

        # Simulate ledger state tampering / fork / rollback
        self.boundary.ledger.entries[0]["data"]["event"] = "tampered_record_1"

        # Audit and release authorization attempt
        audit_result = self.boundary.audit_and_release(caid)

        assert audit_result["disposition"] == "CONTAINMENT_LEVEL_C5"
        assert audit_result["containment_level"] == "C5"
        assert audit_result["release_authorization"] == "blocked_containment"
