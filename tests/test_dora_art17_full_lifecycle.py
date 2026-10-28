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

"""
tests/test_dora_art17_full_lifecycle.py — EU DORA Article 17, RTS (EU) 2024/1772,
RTS (EU) 2025/301, and ITS (EU) 2025/302 Annex I & II Full Lifecycle Test Suite.

Evaluates and tests:
1. All 4 ITS 2025/302 lifecycle stages (`INITIAL_NOTIFICATION`, `INTERMEDIATE_REPORT`,
   `FINAL_REPORT`, `RECLASSIFIED_NON_MAJOR`).
2. RTS 2024/1772 6 materiality criteria evaluation (`evaluate_rts_2024_1772_criteria`).
3. `extract_ict_risk_framework_metrics` over real signed receipts and DORA Art. 28(3)
   TPSP Register of Information linkage (`contract_reference` and `provider_lei`).
4. Ed25519 signature verification over RFC 8785 `encode_jcs` and tamper rejection.
5. CLI `--self-test` and stage export via `subprocess.run`.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.dora_art17_exporter import (
    DoraReportingStage,
    evaluate_rts_2024_1772_criteria,
    export_dora_art17_to_file,
    extract_ict_risk_framework_metrics,
    generate_dora_art17_report,
    verify_dora_art17_report,
)
from src.eo1_write_before_execute import (
    PreDispatchIntentInterlock,
    compute_caid,
    verify_continuity_receipt,
)
from src.incident_evidence import AuthorityRevocationState, BoundaryVerdict
from src.jcs_canonicalizer import encode_jcs
from tools.export_dora_art17_evidence import DoraArt17Exporter


class TestDoraIts2025302LifecycleStages:
    def test_all_four_lifecycle_stages_in_exporter_and_compliance_module(self, tmp_path):
        seed = hashlib.sha256(b"test-dora-art17-lifecycle-ed25519-seed").digest()
        privkey = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        exporter = DoraArt17Exporter(signing_privkey=privkey)

        caid_hex = hashlib.sha256(
            encode_jcs({"noun": "Settlement", "verb": "Transfer", "amount": 500000})
        ).hexdigest()

        # 1. INITIAL_NOTIFICATION (4h from major_classification_time, within 24h of awareness)
        init_bundle = exporter.generate_incident_package(
            incident_id="INC-2026-DORA-401",
            operation_id="op:sepa:401",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T08:00:00Z",
            awareness_timestamp_utc="2026-10-17T08:10:00Z",
            classification_timestamp_utc="2026-10-17T08:30:00Z",
            resolved_timestamp_utc=None,
            financial_impact_minor_units=500000,
            currency="EUR",
            stage=DoraReportingStage.INITIAL_NOTIFICATION,
        )
        ok, err = exporter.verify_incident_package(init_bundle)
        assert ok is True, err
        init_pkg = init_bundle["package"]
        assert init_pkg["reporting_stage"] == "INITIAL_NOTIFICATION"
        assert init_pkg["timeline"]["initial_notification_deadline_utc"] == "2026-10-17T12:30:00Z"
        assert init_pkg["incident_candidate"]["reconciliation_state"] == "EFFECT_INDETERMINATE"
        its_init = init_pkg["its_2025_302_lifecycle_report"]
        assert its_init["reporting_stage"] == "INITIAL_NOTIFICATION"
        assert its_init["aeib_wire_latch_state"]["latch_state"] == "EFFECT_INDETERMINATE"
        assert its_init["aeib_wire_latch_state"]["retry_safe"] is False

        # 2. INTERMEDIATE_REPORT (within 72h of initial notification)
        inter_bundle = exporter.generate_incident_package(
            incident_id="INC-2026-DORA-401",
            operation_id="op:sepa:401",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T08:00:00Z",
            awareness_timestamp_utc="2026-10-17T08:10:00Z",
            classification_timestamp_utc="2026-10-17T08:30:00Z",
            resolved_timestamp_utc="2026-10-17T09:05:00Z",
            financial_impact_minor_units=500000,
            currency="EUR",
            stage=DoraReportingStage.INTERMEDIATE_REPORT,
            root_cause_category="SYSTEM_FAILURE_POST_DISPATCH_WIRE_SEVERANCE",
            affected_services=["SEPA Instant Settlement Gateway", "Treasury Ledger Router"],
            bcp_activated=True,
            dr_activated=False,
            probe_budget=1,
            probes_executed=1,
            tpsp_arrangement={
                "contract_reference": "CTR-DORA-2026-77",
                "provider_lei": "529900HNOAA1KXQJUQ27",
                "service_type": "AI_EXECUTION_GATEWAY",
            },
        )
        ok, err = exporter.verify_incident_package(inter_bundle)
        assert ok is True, err
        inter_pkg = inter_bundle["package"]
        assert inter_pkg["reporting_stage"] == "INTERMEDIATE_REPORT"
        assert inter_pkg["timeline"]["intermediate_report_deadline_utc"] == "2026-10-20T12:30:00Z"
        inter_details = inter_pkg["its_2025_302_lifecycle_report"]["intermediate_report_details"]
        assert int(inter_details["deadline_window_hours"]) == 72
        assert inter_details["root_cause_category"] == "SYSTEM_FAILURE_POST_DISPATCH_WIRE_SEVERANCE"
        assert "SEPA Instant Settlement Gateway" in inter_details["impacted_critical_functions"]
        assert inter_details["bcp_dr_activation_status"]["bcp_activated"] is True
        assert inter_details["single_flight_probe_reconciliation"]["probe_budget"] == 1
        assert inter_details["single_flight_probe_reconciliation"]["probes_executed"] == 1
        assert inter_details["single_flight_probe_reconciliation"]["observed_duplicate_mutations"] == 0
        assert inter_details["tpsp_linkage"]["contract_reference"] == "CTR-DORA-2026-77"
        assert inter_details["tpsp_linkage"]["provider_lei"] == "529900HNOAA1KXQJUQ27"

        # 3. FINAL_REPORT (within 1 month / 30 days of intermediate report)
        receipt_digest_1 = hashlib.sha256(b"receipt-chain-entry-1").hexdigest()
        receipt_digest_2 = hashlib.sha256(b"receipt-chain-entry-2").hexdigest()
        final_bundle = exporter.generate_incident_package(
            incident_id="INC-2026-DORA-401",
            operation_id="op:sepa:401",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T08:00:00Z",
            awareness_timestamp_utc="2026-10-17T08:10:00Z",
            classification_timestamp_utc="2026-10-17T08:30:00Z",
            resolved_timestamp_utc="2026-10-17T09:05:00Z",
            stage=DoraReportingStage.FINAL_REPORT,
            direct_costs_eur=110000,
            indirect_costs_eur=15000,
            financial_recoveries_eur=105000,
            cumulative_hash_chain_receipt_digests=[receipt_digest_1, receipt_digest_2],
        )
        ok, err = exporter.verify_incident_package(final_bundle)
        assert ok is True, err
        final_pkg = final_bundle["package"]
        assert final_pkg["reporting_stage"] == "FINAL_REPORT"
        assert final_pkg["timeline"]["final_report_deadline_utc"] == "2026-11-19T12:30:00Z"
        final_details = final_pkg["its_2025_302_lifecycle_report"]["final_report_details"]
        assert int(final_details["deadline_window_days"]) == 30
        assert final_details["economic_impact_eur"]["currency"] == "EUR"
        assert final_details["economic_impact_eur"]["direct_costs_eur"] == 110000
        assert int(final_details["economic_impact_eur"]["indirect_costs_eur"]) == 15000
        assert final_details["economic_impact_eur"]["total_gross_impact_eur"] == 125000
        assert final_details["economic_impact_eur"]["financial_recoveries_eur"] == 105000
        assert final_details["economic_impact_eur"]["net_economic_impact_eur"] == 20000
        assert len(final_details["permanent_remediation_actions"]) >= 2
        assert final_details["cumulative_hash_chain_receipt_digests"] == [
            receipt_digest_1,
            receipt_digest_2,
        ]
        assert len(final_details["hash_chain_tip_sha256"]) == 64

        # 4. RECLASSIFIED_NON_MAJOR (when ProbeBudget: 1 confirms 0 duplicate mutations & 0 data loss)
        reclass_bundle = exporter.generate_incident_package(
            incident_id="INC-2026-DORA-401",
            operation_id="op:sepa:401",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T08:00:00Z",
            awareness_timestamp_utc="2026-10-17T08:10:00Z",
            classification_timestamp_utc="2026-10-17T08:30:00Z",
            stage=DoraReportingStage.RECLASSIFIED_NON_MAJOR,
        )
        ok, err = exporter.verify_incident_package(reclass_bundle)
        assert ok is True, err
        reclass_pkg = reclass_bundle["package"]
        assert reclass_pkg["reporting_stage"] == "RECLASSIFIED_NON_MAJOR"
        assert reclass_pkg["rts_2024_1772_materiality"]["is_major_incident"] is False
        reclass_details = reclass_pkg["its_2025_302_lifecycle_report"]["reclassification_details"]
        assert reclass_details["reclassified_to"] == "NON_MAJOR_ICT_INCIDENT"
        assert reclass_details["single_flight_probe_reconciliation"]["probe_budget"] == 1
        assert reclass_details["single_flight_probe_reconciliation"]["observed_duplicate_mutations"] == 0
        assert reclass_details["single_flight_probe_reconciliation"]["confirmed_data_loss"] is False
        assert reclass_details["rts_2024_1772_materiality_breached"] is False

        # Verify compliance/dora_art17_exporter.py across all 4 stages as well
        for stg in DoraReportingStage:
            comp_rep = generate_dora_art17_report(
                incident_id="INC-2026-DORA-402",
                detection_timestamp_utc="2026-10-17T08:30:00Z",
                impacted_service="SEPA Instant Settlement Gateway",
                transport_fault="tcp_rst_mid_flight",
                caid=caid_hex,
                operation_id="op:sepa:402",
                stage=stg,
                signing_privkey=privkey,
            )
            assert comp_rep["reporting_stage"] == stg.value
            verified, verr = verify_dora_art17_report(comp_rep)
            assert verified is True, verr
            out_file = tmp_path / f"dora_{stg.value.lower()}.json"
            export_dora_art17_to_file(comp_rep, out_file)
            assert out_file.is_file()


class TestRts20241772MaterialityCriteria:
    def test_six_materiality_criteria_evaluation_and_reclassification(self):
        # Case A: Major incident triggered by data_losses (integrity/availability) and economic_impact
        major_eval = evaluate_rts_2024_1772_criteria(
            critical_services_affected=True,
            clients_counterparts_transactions={
                "affected_clients_count": 150_000,
                "affected_clients_pct": 14.5,
                "affected_counterparts_pct": 35.0,
                "affected_transactions_pct": 12.0,
                "affected_transactions_value_eur": 20_000_000,
            },
            reputational_impact={
                "media_coverage": True,
                "repetitive_client_complaints": True,
                "regulatory_market_visibility": False,
            },
            duration_and_service_downtime={
                "incident_duration_hours": 26.0,
                "critical_service_downtime_hours": 3.5,
            },
            geographical_spread={
                "affected_eu_member_states": ["DE", "FR", "NL"],
            },
            data_losses={
                "availability": True,
                "authenticity": False,
                "integrity": True,
                "confidentiality": False,
            },
            economic_impact={
                "direct_and_indirect_costs_eur": 250_000,
                "tier1_capital_bps": 15.0,
            },
        )

        expected_six = {
            "clients_counterparts_transactions",
            "reputational_impact",
            "duration_and_service_downtime",
            "geographical_spread",
            "data_losses",
            "economic_impact",
        }
        assert set(major_eval["criteria"].keys()) == expected_six
        for crit_name in expected_six:
            assert major_eval[crit_name]["threshold_breached"] is True
        assert major_eval["data_losses"]["availability"] is True
        assert major_eval["data_losses"]["authenticity"] is False
        assert major_eval["data_losses"]["integrity"] is True
        assert major_eval["data_losses"]["confidentiality"] is False
        assert major_eval["breached_criteria_count"] == 6
        assert major_eval["is_major_incident"] is True

        # Case B: Reclassified non-major when AEIB ProbeBudget: 1 confirms 0 duplicate mutations & 0 data loss
        non_major_eval = evaluate_rts_2024_1772_criteria(
            critical_services_affected=True,
            clients_counterparts_transactions={
                "affected_clients_count": 1,
                "affected_clients_pct": 0.001,
                "affected_counterparts_pct": 0.0,
                "affected_transactions_pct": 0.001,
                "affected_transactions_value_eur": 25_000,
            },
            reputational_impact={
                "media_coverage": False,
                "repetitive_client_complaints": False,
                "regulatory_market_visibility": False,
            },
            duration_and_service_downtime={
                "incident_duration_hours": 0.25,
                "critical_service_downtime_hours": 0.0,
            },
            geographical_spread={
                "affected_eu_member_states": ["CZ"],
            },
            data_losses={
                "availability": False,
                "authenticity": False,
                "integrity": False,
                "confidentiality": False,
            },
            economic_impact={
                "direct_and_indirect_costs_eur": 0,
                "tier1_capital_bps": 0.0,
            },
        )
        assert non_major_eval["breached_criteria_count"] == 0
        assert non_major_eval["data_losses"]["threshold_breached"] is False
        assert non_major_eval["is_major_incident"] is False


class TestIctRiskFrameworkMetricsExtraction:
    def test_extract_ict_risk_framework_metrics_over_real_signed_receipts(self, tmp_path):
        seed = hashlib.sha256(b"test-ict-risk-metrics-boundary-key").digest()
        privkey = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        pubkey = privkey.public_key()

        interlock = PreDispatchIntentInterlock(
            ledger_path=tmp_path / "eo1_ledger.jsonl",
            boundary_private_key=privkey,
            output_state_dir=tmp_path / "state",
            authority_id="auth-dora-metrics-01",
            policy_epoch=1,
        )

        # Create 2 real latched operations and reconcile them (1 SETTLED -> RESOLVED_CONFIRMED, 1 ABORTED -> RESOLVED_REFUTED)
        payload_1 = {"operation_id": "op:dora:m1", "amount": 10000, "currency": "EUR"}
        caid_1 = compute_caid(payload_1)
        interlock.record_intent(
            target_uri="http://127.0.0.1:8080/v1/sepa",
            tool_name="sepa_transfer",
            payload=payload_1,
            intent_id="intent-m1",
        )
        interlock.latch_intent(
            caid=caid_1,
            reason="HTTP_504_GATEWAY_TIMEOUT",
            intent_id="intent-m1",
            target_uri="http://127.0.0.1:8080/v1/sepa",
            tool_name="sepa_transfer",
        )
        receipt_1 = interlock.reconcile_out_of_band(
            caid=caid_1,
            reconciliation_evidence={"target_status": "SETTLED", "tx_ref": "TX-M1"},
            intent_id="intent-m1",
        )
        verify_continuity_receipt(receipt_1.to_dict(), pubkey)

        payload_2 = {"operation_id": "op:dora:m2", "amount": 20000, "currency": "EUR"}
        caid_2 = compute_caid(payload_2)
        interlock.record_intent(
            target_uri="http://127.0.0.1:8080/v1/sepa",
            tool_name="sepa_transfer",
            payload=payload_2,
            intent_id="intent-m2",
        )
        interlock.latch_intent(
            caid=caid_2,
            reason="TCP_RST_MID_FLIGHT",
            intent_id="intent-m2",
            target_uri="http://127.0.0.1:8080/v1/sepa",
            tool_name="sepa_transfer",
        )
        receipt_2 = interlock.reconcile_out_of_band(
            caid=caid_2,
            reconciliation_evidence={"target_status": "ABORTED", "tx_ref": "NONE"},
            intent_id="intent-m2",
        )
        verify_continuity_receipt(receipt_2.to_dict(), pubkey)

        # Create a 3rd signed incident package currently latched in EFFECT_INDETERMINATE
        exporter = DoraArt17Exporter(signing_privkey=privkey)
        bundle_3 = exporter.generate_incident_package(
            incident_id="INC-2026-M3",
            operation_id="op:dora:m3",
            caid=compute_caid({"operation_id": "op:dora:m3", "amount": 30000}),
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T10:00:00Z",
            classification_timestamp_utc="2026-10-17T10:15:00Z",
            resolved_timestamp_utc=None,
            stage=DoraReportingStage.INITIAL_NOTIFICATION,
        )

        r1_dict = {
            **receipt_1.to_dict(),
            "observed_duplicate_mutations": 0,
            "blocked_naive_retries": 2,
            "probe_budget": 1,
            "probes_executed": 1,
            "time_to_latch_ms": 1.10,
        }
        r2_dict = {
            **receipt_2.to_dict(),
            "observed_duplicate_mutations": 0,
            "blocked_naive_retries": 1,
            "probe_budget": 1,
            "probes_executed": 1,
            "time_to_latch_ms": 1.40,
        }

        tpsp_arrangements = [
            {
                "contract_reference": "CTR-DORA-2026-01",
                "provider_lei": "529900HNOAA1KXQJUQ27",
                "provider_name": "SovereignNexus AEIB Runtime",
                "service_type": "AI_EXECUTION_GATEWAY",
                "criticality_assessment": "CRITICAL",
            }
        ]

        metrics = extract_ict_risk_framework_metrics(
            [r1_dict, r2_dict, bundle_3],
            tpsp_arrangements=tpsp_arrangements,
        )

        assert metrics["total_evaluated_operations"] == 3
        assert metrics["confirmed_operations"] == 1
        assert metrics["refuted_operations"] == 1
        assert metrics["effect_indeterminate_latches"] == 3
        assert metrics["observed_duplicate_mutations"] == 0
        assert metrics["blocked_naive_retries"] == 4
        assert metrics["mean_time_to_latch_ms"] > 0.0
        assert metrics["single_flight_probe_budget_compliance_rate"] == 1.0
        assert len(metrics["third_party_tpsp_arrangements"]) == 1
        tpsp_entry = metrics["third_party_tpsp_arrangements"][0]
        assert tpsp_entry["contract_reference"] == "CTR-DORA-2026-01"
        assert tpsp_entry["provider_lei"] == "529900HNOAA1KXQJUQ27"
        assert len(metrics["metrics_digest_sha256"]) == 64


class TestEd25519JcsSignatureAndTamperRejection:
    def test_ed25519_jcs_signature_verification_and_tamper_rejection(self):
        privkey = ed25519.Ed25519PrivateKey.generate()
        exporter = DoraArt17Exporter(signing_privkey=privkey)
        caid_hex = hashlib.sha256(b"tamper-test-payload").hexdigest()

        bundle = exporter.generate_incident_package(
            incident_id="INC-2026-TAMPER-01",
            operation_id="op:sepa:9001",
            caid=caid_hex,
            fault_type="http_504_gateway_timeout",
            detection_timestamp_utc="2026-10-17T02:00:00Z",
            classification_timestamp_utc="2026-10-17T02:10:00Z",
            stage=DoraReportingStage.INTERMEDIATE_REPORT,
        )

        ok, err = exporter.verify_incident_package(bundle)
        assert ok is True, err

        # Tamper with observed_duplicate_mutations inside package
        tampered_bundle = copy.deepcopy(bundle)
        tampered_bundle["package"]["incident_candidate"]["observed_duplicate_mutations"] = 1
        ok_tampered, err_tampered = exporter.verify_incident_package(tampered_bundle)
        assert ok_tampered is False
        assert err_tampered is not None and "digest mismatch" in err_tampered.lower()

        # Recompute digest without valid private key signature -> must fail Ed25519 verification
        forged_bundle = copy.deepcopy(tampered_bundle)
        forged_bundle["package_digest"] = hashlib.sha256(
            encode_jcs(forged_bundle["package"])
        ).hexdigest()
        ok_forged, err_forged = exporter.verify_incident_package(forged_bundle)
        assert ok_forged is False
        assert err_forged is not None and "signature verification failed" in err_forged.lower()

        # Also test tamper rejection on compliance/dora_art17_exporter.py report
        comp_report = generate_dora_art17_report(
            incident_id="INC-2026-TAMPER-02",
            detection_timestamp_utc="2026-10-17T02:00:00Z",
            impacted_service="SEPA Gateway",
            transport_fault="http_504_gateway_timeout",
            caid=caid_hex,
            operation_id="op:sepa:9002",
            stage=DoraReportingStage.FINAL_REPORT,
            signing_privkey=privkey,
        )
        ok_comp, err_comp = verify_dora_art17_report(comp_report)
        assert ok_comp is True, err_comp

        tampered_comp = copy.deepcopy(comp_report)
        tampered_comp["telemetry_evidence"]["retry_suppressed"] = False
        ok_comp_t, _ = verify_dora_art17_report(tampered_comp)
        assert ok_comp_t is False


class TestDoraCliSelfTestAndStageExport:
    def test_cli_self_test_and_stage_flags_via_subprocess(self, tmp_path):
        out_self_test = tmp_path / "self_test_output.json"
        proc = subprocess.run(
            [
                sys.executable,
                "tools/export_dora_art17_evidence.py",
                "--self-test",
                "--output-json",
                str(out_self_test),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"CLI --self-test failed:\n{proc.stdout}\n{proc.stderr}"
        assert out_self_test.is_file()
        data = json.loads(out_self_test.read_text(encoding="utf-8"))
        assert data["self_test_status"] == "VERIFIED"
        assert set(data["stages_verified"].keys()) == {
            "INITIAL_NOTIFICATION",
            "INTERMEDIATE_REPORT",
            "FINAL_REPORT",
            "RECLASSIFIED_NON_MAJOR",
        }
        assert data["ict_risk_framework_metrics"]["observed_duplicate_mutations"] == 0
        assert data["tpsp_register_linkage"]["contract_reference"] == "CTR-DORA-2026-01"
        assert data["tpsp_register_linkage"]["provider_lei"] == "529900HNOAA1KXQJUQ27"

        # Test individual --stage CLI invocation
        out_stage = tmp_path / "stage_reclassified.json"
        proc_stage = subprocess.run(
            [
                sys.executable,
                "tools/export_dora_art17_evidence.py",
                "--stage",
                "RECLASSIFIED_NON_MAJOR",
                "--incident-id",
                "INC-2026-CLI-99",
                "--operation-id",
                "op:sepa:cli:99",
                "--fault-type",
                "tcp_rst_post_commit",
                "--output-json",
                str(out_stage),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_stage.returncode == 0, f"CLI --stage failed:\n{proc_stage.stderr}"
        stage_bundle = json.loads(out_stage.read_text(encoding="utf-8"))
        ok, err = DoraArt17Exporter.verify_incident_package(stage_bundle)
        assert ok is True, err
        assert stage_bundle["package"]["reporting_stage"] == "RECLASSIFIED_NON_MAJOR"
        assert stage_bundle["package"]["incident_id"] == "INC-2026-CLI-99"
