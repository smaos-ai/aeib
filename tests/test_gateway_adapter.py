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
test_gateway_adapter.py — Acceptance Test for AEIB Gateway Adapter & Exporters
Verifies extended CAID derivation, Candidate Identity Triad, uncertainty latching,
Miyazaki HOLD schema, transparency log freshness, non-compensatory execution predicates,
and DORA exporter outputs.
"""

import json
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.aeib_gateway_adapter import (
    AEIBGatewayAdapter,
    check_transparency_log_freshness,
    ExecutionEvaluationResult,
)
from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    CandidateAction,
    DelegationGrant,
)
from compliance.dora_art17_gap_exporter import generate_dora_art17_report
from compliance.dora_art28_register_exporter import generate_dora_rt0101_rows


class TestAEIBGatewayAdapterAndExporters:
    def setup_method(self):
        self.boundary = GovernanceDecisionBoundary()
        self.adapter = AEIBGatewayAdapter(governance_boundary=self.boundary)

    def test_extended_caid_derivation_structure(self):
        caid = self.adapter.derive_extended_caid(
            noun="Treasury",
            verb="Disburse",
            payload={"amount": 100.0, "currency": "EUR"},
            memory_digest="mem:hash:abc12345",
            harness_digest="harness:hash:def67890",
            process_trace_digest="trace:hash:13579bdf",
            manifest_hash="manifest:hash:2468ace0",
        )
        assert caid.startswith("caid:sha256:")

    def test_candidate_identity_triad_derivation(self):
        payload = {"recipient": "IBAN_CZ123", "amount": 5000.0}
        req_digest = self.adapter.compute_request_digest(payload)
        assert len(req_digest) == 64

        triad_caid = self.adapter.derive_triad_caid(
            operation_id="intent:appr:9901",
            noun="Treasury",
            verb="Disburse",
            payload=payload,
            business_idempotency_key="bizkey:payment:batch:441",
            memory_digest="mem:sha256:11223344",
            harness_digest="harness:sha256:55667788",
            process_trace_digest="trace:sha256:99aabbcc",
            manifest_hash="manifest:sha256:ddeeff00",
        )
        assert triad_caid.startswith("caid:sha256:")

        # Two different operation_ids with identical payload produce distinct CAIDs
        distinct_caid = self.adapter.derive_triad_caid(
            operation_id="intent:appr:9902",
            noun="Treasury",
            verb="Disburse",
            payload=payload,
            business_idempotency_key="bizkey:payment:batch:441",
            memory_digest="mem:sha256:11223344",
            harness_digest="harness:sha256:55667788",
            process_trace_digest="trace:sha256:99aabbcc",
            manifest_hash="manifest:sha256:ddeeff00",
        )
        assert triad_caid != distinct_caid

    def test_uncertainty_latching_locks_state_with_miyazaki_hold(self):
        caid = "caid:sha256:test1234"
        latch = self.adapter.latch_uncertainty(
            caid=caid,
            wire_fault="http_504_gateway_timeout",
            operation_id="op:9901",
            assigned_to="principal:chief_compliance_officer",
            review_deadline_hours=4,
        )
        assert latch["disposition"] == "EFFECT_INDETERMINATE"
        assert latch["retry_safe"] is False
        assert self.adapter.is_latched(caid) is True

        # Verify Miyazaki HOLD accountability schema
        hold = latch["miyazaki_hold"]
        assert hold["assigned_to"] == "principal:chief_compliance_officer"
        assert hold["expiration_action"] == "EXPIRED_RELEASE_DENIED"
        assert "review_deadline" in hold
        assert len(hold["escalation_path"]) == 3
        assert hold["raw_evidence_inspected"] is False

    def test_transparency_log_freshness_evaluation(self):
        current_time_ms = 1_000_000

        # Fresh log with valid proof
        fresh_log = {"consistency_proof_valid": True, "last_verified_ms": 980_000}
        assert check_transparency_log_freshness(fresh_log, current_time_ms, max_staleness_ms=60_000) is True

        # Stale log exceeding max_staleness_ms
        stale_log = {"consistency_proof_valid": True, "last_verified_ms": 900_000}
        assert check_transparency_log_freshness(stale_log, current_time_ms, max_staleness_ms=60_000) is False

        # Invalid consistency proof fails closed
        invalid_proof_log = {"consistency_proof_valid": False, "last_verified_ms": 990_000}
        assert check_transparency_log_freshness(invalid_proof_log, current_time_ms, max_staleness_ms=60_000) is False

    def test_non_compensatory_execution_predicate(self):
        current_time_ms = 100_000
        epoch = "policy:epoch_104"
        grant = DelegationGrant(
            grant_id="grant_01",
            principal_id="ciso_user",
            authorized_agent_id="agent_alpha",
            allowed_verbs={"Treasury:Disburse"},
            policy_epoch=epoch,
            expires_at_epoch_ms=200_000,
        )
        self.boundary.add_grant(grant)
        self.boundary.register_agent("agent_alpha")

        identity = AgentIdentityContext(
            agent_id="agent_alpha",
            principal_id="ciso_user",
            tenant_id="tenant_main",
            delegation_chain=["grant_01"],
            standing_version="v1.0",
            policy_epoch=epoch,
        )

        payload = {"amount": 50.0, "currency": "EUR"}
        caid = self.adapter.derive_extended_caid(
            noun="Treasury",
            verb="Disburse",
            payload=payload,
        )

        candidate = CandidateAction(
            noun="Treasury",
            verb="Disburse",
            payload=payload,
            approved_caid=caid,
            grant_id="grant_01",
            policy_epoch=epoch,
        )

        log_state = {"consistency_proof_valid": True, "last_verified_ms": current_time_ms - 5000}
        harness_hash = "harness:sha256:0123456789abcdef"

        # Baseline: All predicates satisfied -> permitted
        result = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            transport_disposition="CONFIRMED",
            retry_safe=True,
            target_probe_status="AUTHORITATIVE",
            entropy_bits=256,
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
            release_authorized=True,
        )
        assert result.permitted is True
        assert result.failed_clause is None

        # Fail on stale transparency log
        stale_log_state = {"consistency_proof_valid": True, "last_verified_ms": current_time_ms - 100_000}
        res_stale = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=stale_log_state,
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_stale.permitted is False
        assert res_stale.failed_clause == "TRANSPARENCY_LOG_STALE_OR_INVALID"

        # Fail on EFFECT_INDETERMINATE without retry suppression
        res_retry = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            transport_disposition="EFFECT_INDETERMINATE",
            retry_safe=True,  # VIOLATION: Must be False
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_retry.permitted is False
        assert res_retry.failed_clause == "INDETERMINATE_WITHOUT_RETRY_SUPPRESSION"

        # Fail on entropy starvation (< 256 bits)
        res_entropy = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            entropy_bits=128,  # VIOLATION
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_entropy.permitted is False
        assert res_entropy.failed_clause == "INSUFFICIENT_ENTROPY"

        # Fail on harness digest mutation
        res_tamper = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            boot_harness_digest=harness_hash,
            current_harness_digest="harness:sha256:tampered_digest",
        )
        assert res_tamper.permitted is False
        assert res_tamper.failed_clause == "HARNESS_DIGEST_MUTATED"

    def test_evaluate_execution_predicate_crypto_inventory(self):
        current_time_ms = 100_000
        epoch = "policy:epoch_104"
        grant = DelegationGrant(
            grant_id="grant_crypto",
            principal_id="ciso_user",
            authorized_agent_id="agent_crypto",
            allowed_verbs={"Treasury:Disburse"},
            policy_epoch=epoch,
            expires_at_epoch_ms=200_000,
        )
        self.boundary.add_grant(grant)
        self.boundary.register_agent("agent_crypto")

        identity = AgentIdentityContext(
            agent_id="agent_crypto",
            principal_id="ciso_user",
            tenant_id="tenant_main",
            delegation_chain=["grant_crypto"],
            standing_version="v1.0",
            policy_epoch=epoch,
        )

        payload = {"amount": 50.0, "currency": "EUR"}
        caid = self.adapter.derive_extended_caid(noun="Treasury", verb="Disburse", payload=payload)

        candidate = CandidateAction(
            noun="Treasury",
            verb="Disburse",
            payload=payload,
            approved_caid=caid,
            grant_id="grant_crypto",
            policy_epoch=epoch,
        )

        log_state = {"consistency_proof_valid": True, "last_verified_ms": current_time_ms - 5000}
        harness_hash = "harness:sha256:0123456789abcdef"

        valid_crypto_inventory = {
            "algorithm": "NIST_FIPS_204_ML_DSA_65",
            "pqc_migration_target": "NIST_FIPS_204_ML_DSA_65",
            "key_id": "key_001",
            "key_epoch": "epoch_2026",
            "purpose": "attestation",
            "owner": "ciso",
            "storage": "hsm",
            "validity_interval": "P1Y",
            "rotation_policy": "annual",
            "revocation_status": "ACTIVE_UNREVOKED",
            "migration_status": "MIGRATED"
        }

        # Baseline: Valid crypto inventory
        res_valid = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            crypto_inventory=valid_crypto_inventory,
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_valid.permitted is True
        assert res_valid.failed_clause is None

        # Revoked crypto inventory
        revoked_crypto_inventory = dict(valid_crypto_inventory)
        revoked_crypto_inventory["revocation_status"] = "REVOKED_COMPROMISED"
        res_revoked = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            crypto_inventory=revoked_crypto_inventory,
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_revoked.permitted is False
        assert res_revoked.failed_clause == "CRYPTO_INVENTORY_INVALID"

        # Invalid algorithm crypto inventory
        invalid_alg_inventory = dict(valid_crypto_inventory)
        invalid_alg_inventory["algorithm"] = "RSA_1024"
        res_invalid_alg = self.adapter.evaluate_execution_predicate(
            candidate=candidate,
            identity=identity,
            current_time_ms=current_time_ms,
            log_state=log_state,
            crypto_inventory=invalid_alg_inventory,
            boot_harness_digest=harness_hash,
            current_harness_digest=harness_hash,
        )
        assert res_invalid_alg.permitted is False
        assert res_invalid_alg.failed_clause == "CRYPTO_INVENTORY_INVALID"


    def test_dora_art17_report_generation(self):
        report = generate_dora_art17_report(
            incident_id="INC-2026-001",
            detection_timestamp_utc="2026-10-08T12:00:00Z",
            impacted_service="Treasury Gateway",
            transport_fault="http_504_gateway_timeout",
            caid="caid:sha256:test1234",
            operation_id="op:9901",
        )
        assert report["regulation"] == "EU 2022/2554 (DORA)"
        assert report["timeline"]["regulatory_notification_deadline_utc"] == "2026-10-08T16:00:00Z"
        assert report["telemetry_evidence"]["fail_closed_latch_engaged"] is True

    def test_dora_art28_register_csv_generation(self):
        arrangements = [
            {
                "entity_lei": "12345678901234567890",
                "entity_name": "Test Bank CZ",
                "contract_reference": "CTR-9942",
                "tpsp_lei": "98765432109876543210",
                "tpsp_name": "SovereignNexus AEIB",
            }
        ]
        csv_out = generate_dora_rt0101_rows(arrangements)
        assert "entity_lei,entity_name,contract_reference" in csv_out
        assert "Test Bank CZ" in csv_out
        assert "SovereignNexus AEIB" in csv_out

    def test_dora_v041_official_esa_roi_package(self, tmp_path):
        from compliance.dora_art17_exporter import export_dora_art17_to_file
        from compliance.dora_art28_roi_exporter import export_dora_roi_package

        rep = generate_dora_art17_report(
            incident_id="INC-2026-ESA-01",
            detection_timestamp_utc="2026-10-08T14:00:00Z",
            impacted_service="Gateway",
            transport_fault="tcp_reset",
            caid="caid:sha256:esa01",
            operation_id="op:esa01",
        )
        art17_file = tmp_path / "dora_art17_incident.json"
        export_dora_art17_to_file(rep, art17_file)
        assert art17_file.is_file()

        arrangements = [
            {
                "entity_lei": "12345678901234567890",
                "contract_reference": "CTR-ESA-01",
                "tpsp_lei": "98765432109876543210",
                "tpsp_name": "SovereignNexus AEIB",
            }
        ]
        services = [
            {
                "entity_lei": "12345678901234567890",
                "contract_reference": "CTR-ESA-01",
                "service_identifier": "SVC-01",
                "service_type": "AI_EXECUTION_GATEWAY",
                "criticality_flag": "CRITICAL",
            }
        ]
        roi_files = export_dora_roi_package(arrangements, services, tmp_path / "roi_out")
        assert "RT.01.01" in roi_files
        assert "RT.02.01" in roi_files
        assert roi_files["RT.01.01"].is_file()
        assert roi_files["RT.02.01"].is_file()
        rt0101_content = roi_files["RT.01.01"].read_text(encoding="utf-8")
        assert "entity_lei,entity_name,contract_reference" in rt0101_content

