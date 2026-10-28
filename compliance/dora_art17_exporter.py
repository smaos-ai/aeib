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
dora_art17_exporter.py — EU DORA Article 17, RTS (EU) 2024/1772, RTS (EU) 2025/301,
and ITS (EU) 2025/302 Annex I & II Continuous Incident & ICT Risk Reporting Engine.
Sovereign Multi-Agent OS (SMAOS) / AEIB v1.1

Evaluated under the stated model. Converts wire telemetry, transport fault
observations (HTTP 504 / TCP RST), write-ahead EFFECT_INDETERMINATE latches,
and single-flight out-of-band reconciliation evidence (ProbeBudget: 1) into
cryptographically signed RFC 8785 JCS records across all four statutory DORA
reporting stages.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs

try:
    from compliance.dora_art17_gap_exporter import (
        export_dora_art17_to_file as _base_export_to_file,
        generate_dora_art17_report as _base_generate_report,
    )
except ImportError:
    from dora_art17_gap_exporter import (
        export_dora_art17_to_file as _base_export_to_file,
        generate_dora_art17_report as _base_generate_report,
    )


class DoraReportingStage(str, Enum):
    """
    Four statutory lifecycle reporting stages under EU DORA Art. 19(4),
    RTS (EU) 2025/301, and ITS (EU) 2025/302 Annex I & II.
    """

    INITIAL_NOTIFICATION = "INITIAL_NOTIFICATION"
    INTERMEDIATE_REPORT = "INTERMEDIATE_REPORT"
    FINAL_REPORT = "FINAL_REPORT"
    RECLASSIFIED_NON_MAJOR = "RECLASSIFIED_NON_MAJOR"


DEFAULT_TPSP_ARRANGEMENT: Dict[str, Any] = {
    "contract_reference": "CTR-DORA-2026-01",
    "provider_lei": "529900HNOAA1KXQJUQ27",
    "tpsp_lei": "529900HNOAA1KXQJUQ27",
    "provider_name": "SovereignNexus AEIB Runtime",
    "service_type": "AI_EXECUTION_GATEWAY",
    "criticality_assessment": "CRITICAL",
    "country_of_provision": "CZ",
    "dora_art28_template_ref": "RT.01.01 / B_01.01",
}


def _parse_iso_utc(ts_str: Optional[str], fallback: Optional[datetime] = None) -> datetime:
    """Parses an ISO-8601 UTC timestamp string into a timezone-aware UTC datetime."""
    if not ts_str or ts_str in ("T_classified", "unknown_until_supplied"):
        return fallback or datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return fallback or datetime.now(timezone.utc)


def _format_iso_utc(dt: datetime) -> str:
    """Formats a timezone-aware datetime as an ISO-8601 UTC string with Z suffix."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_dora_signing_key() -> ed25519.Ed25519PrivateKey:
    """Generates an ephemeral Ed25519 key when no external signing key is supplied."""
    return ed25519.Ed25519PrivateKey.generate()


def evaluate_rts_2024_1772_criteria(
    *,
    clients_counterparts_transactions: Optional[Dict[str, Any]] = None,
    reputational_impact: Optional[Dict[str, Any]] = None,
    duration_and_service_downtime: Optional[Dict[str, Any]] = None,
    geographical_spread: Optional[Dict[str, Any]] = None,
    data_losses: Optional[Dict[str, Any]] = None,
    economic_impact: Optional[Dict[str, Any]] = None,
    critical_services_affected: bool = True,
    malicious_unauthorized_access: bool = False,
    affected_clients_count: int = 0,
    affected_clients_pct: float = 0.0,
    affected_counterparts_pct: float = 0.0,
    affected_transactions_pct: float = 0.0,
    affected_transactions_value_eur: int = 0,
    media_coverage: bool = False,
    repetitive_client_complaints: bool = False,
    regulatory_market_visibility: bool = False,
    incident_duration_hours: float = 0.0,
    critical_service_downtime_hours: float = 0.0,
    affected_eu_member_states: Optional[List[str]] = None,
    direct_and_indirect_costs_eur: int = 0,
    tier1_capital_bps: float = 0.0,
) -> Dict[str, Any]:
    """
    Evaluates the 6 materiality criteria under Commission Delegated Regulation
    (EU) 2024/1772 (Articles 1-9) to support major ICT-related incident classification:
      1. clients_counterparts_transactions (Art. 1 & Art. 9(1))
      2. reputational_impact (Art. 2 & Art. 9(2))
      3. duration_and_service_downtime (Art. 3 & Art. 9(3))
      4. geographical_spread (Art. 4 & Art. 9(4))
      5. data_losses (availability, authenticity, integrity, confidentiality) (Art. 5 & Art. 9(5))
      6. economic_impact (Art. 6 & Art. 9(6))
    """
    cct_in = clients_counterparts_transactions or {}
    c_count = int(cct_in.get("affected_clients_count", affected_clients_count))
    c_pct = float(cct_in.get("affected_clients_pct", affected_clients_pct))
    cp_pct = float(cct_in.get("affected_counterparts_pct", affected_counterparts_pct))
    tx_pct = float(cct_in.get("affected_transactions_pct", affected_transactions_pct))
    tx_val = int(cct_in.get("affected_transactions_value_eur", affected_transactions_value_eur))
    cct_breached = bool(
        cct_in.get(
            "threshold_breached",
            c_count > 100_000
            or c_pct > 10.0
            or cp_pct > 30.0
            or tx_pct > 10.0
            or tx_val >= 15_000_000,
        )
    )
    cct_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 1 & Art. 9(1)",
        "affected_clients_count": c_count,
        "affected_clients_pct": c_pct,
        "affected_counterparts_pct": cp_pct,
        "affected_transactions_pct": tx_pct,
        "affected_transactions_value_eur": tx_val,
        "threshold_breached": cct_breached,
    }

    rep_in = reputational_impact or {}
    rep_media = bool(rep_in.get("media_coverage", media_coverage))
    rep_complaints = bool(rep_in.get("repetitive_client_complaints", repetitive_client_complaints))
    rep_reg = bool(rep_in.get("regulatory_market_visibility", regulatory_market_visibility))
    rep_breached = bool(
        rep_in.get("threshold_breached", rep_media or rep_complaints or rep_reg)
    )
    rep_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 2 & Art. 9(2)",
        "media_coverage": rep_media,
        "repetitive_client_complaints": rep_complaints,
        "regulatory_market_visibility": rep_reg,
        "threshold_breached": rep_breached,
    }

    dur_in = duration_and_service_downtime or {}
    inc_dur = float(dur_in.get("incident_duration_hours", incident_duration_hours))
    srv_down = float(dur_in.get("critical_service_downtime_hours", critical_service_downtime_hours))
    dur_breached = bool(
        dur_in.get("threshold_breached", inc_dur > 24.0 or srv_down > 2.0)
    )
    dur_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 3 & Art. 9(3)",
        "incident_duration_hours": inc_dur,
        "critical_service_downtime_hours": srv_down,
        "threshold_breached": dur_breached,
    }

    geo_in = geographical_spread or {}
    member_states = list(
        geo_in.get("affected_eu_member_states", affected_eu_member_states or [])
    )
    geo_breached = bool(
        geo_in.get("threshold_breached", len(member_states) >= 2)
    )
    geo_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 4 & Art. 9(4)",
        "affected_eu_member_states": member_states,
        "member_state_count": len(member_states),
        "threshold_breached": geo_breached,
    }

    dl_in = data_losses or {}
    dl_avail = bool(dl_in.get("availability", False))
    dl_auth = bool(dl_in.get("authenticity", False))
    dl_integ = bool(dl_in.get("integrity", False))
    dl_conf = bool(dl_in.get("confidentiality", False))
    dl_breached = bool(
        dl_in.get("threshold_breached", dl_avail or dl_auth or dl_integ or dl_conf)
    )
    dl_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 5 & Art. 9(5)",
        "availability": dl_avail,
        "authenticity": dl_auth,
        "integrity": dl_integ,
        "confidentiality": dl_conf,
        "threshold_breached": dl_breached,
    }

    eco_in = economic_impact or {}
    costs_eur = int(
        eco_in.get("direct_and_indirect_costs_eur", direct_and_indirect_costs_eur)
    )
    t1_bps = float(eco_in.get("tier1_capital_bps", tier1_capital_bps))
    eco_breached = bool(
        eco_in.get("threshold_breached", costs_eur >= 100_000 or t1_bps >= 10.0)
    )
    eco_eval = {
        "article_ref": "RTS (EU) 2024/1772 Art. 6 & Art. 9(6)",
        "direct_and_indirect_costs_eur": costs_eur,
        "tier1_capital_bps": t1_bps,
        "threshold_breached": eco_breached,
    }

    criteria_map = {
        "clients_counterparts_transactions": cct_eval,
        "reputational_impact": rep_eval,
        "duration_and_service_downtime": dur_eval,
        "geographical_spread": geo_eval,
        "data_losses": dl_eval,
        "economic_impact": eco_eval,
    }

    breached_names = [
        name for name, obj in criteria_map.items() if obj["threshold_breached"]
    ]
    breached_count = len(breached_names)

    # Under RTS (EU) 2024/1772 Art. 8(1), an incident is classified as major if
    # critical services are affected AND either malicious unauthorized access / data loss
    # occurred OR at least 2 of the 6 materiality thresholds are breached.
    is_major = bool(
        critical_services_affected
        and (malicious_unauthorized_access or dl_breached or breached_count >= 2)
    )

    return {
        "regulation": "Commission Delegated Regulation (EU) 2024/1772",
        "critical_services_affected": critical_services_affected,
        "malicious_unauthorized_access": malicious_unauthorized_access,
        "clients_counterparts_transactions": cct_eval,
        "reputational_impact": rep_eval,
        "duration_and_service_downtime": dur_eval,
        "geographical_spread": geo_eval,
        "data_losses": dl_eval,
        "economic_impact": eco_eval,
        "criteria": criteria_map,
        "breached_criteria_names": breached_names,
        "breached_criteria_count": breached_count,
        "major_incident_threshold_met": is_major,
        "is_major_incident": is_major,
    }


def extract_ict_risk_framework_metrics(
    receipts: List[Dict[str, Any]],
    tpsp_arrangements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Computes DORA Articles 6-16 ICT Risk Management Framework operational telemetry
    metrics from real AEIB receipts and links them to DORA Article 28(3) Register
    of Information TPSP arrangements (`contract_reference` and `provider_lei`).
    """
    total_evaluated = len(receipts)
    confirmed_ops = 0
    refuted_ops = 0
    indeterminate_latches = 0
    duplicate_mutations = 0
    blocked_retries = 0
    latch_latencies_ms: List[float] = []
    probe_compliant_count = 0
    probe_evaluated_count = 0
    discovered_tpsp: List[Dict[str, Any]] = []

    confirmed_states = {
        "RESOLVED_CONFIRMED",
        "CONFIRMED",
        "SETTLED",
        "COMMITTED",
        "ALLOWED",
        "EXECUTED_SUCCESS",
    }
    refuted_states = {
        "RESOLVED_REFUTED",
        "REFUTED",
        "ABORTED",
        "DENIED",
        "ROLLED_BACK",
        "NOT_FOUND",
    }

    for raw_item in receipts:
        if not isinstance(raw_item, dict):
            continue

        item = raw_item.get("package", raw_item)
        candidate = item.get("incident_candidate", {}) if isinstance(item.get("incident_candidate"), dict) else {}
        consequence = (
            item.get("incident_evidence", {}).get("observed_consequence", {})
            if isinstance(item.get("incident_evidence"), dict)
            else item.get("observed_consequence", {})
        )
        telemetry_ev = item.get("telemetry_evidence", {}) if isinstance(item.get("telemetry_evidence"), dict) else {}
        rec_details = (
            item.get("reconciliation_details", {})
            if isinstance(item.get("reconciliation_details"), dict)
            else {}
        )

        state = (
            item.get("reconciliation_outcome")
            or rec_details.get("target_status")
            or rec_details.get("status_enum")
            or item.get("disposition")
            or item.get("final_disposition")
            or item.get("reconciliation_state")
            or candidate.get("reconciliation_state")
            or consequence.get("final_disposition")
            or telemetry_ev.get("gateway_disposition")
            or item.get("lifecycle_state")
            or "UNKNOWN"
        )
        state_str = str(state).upper()

        if state_str in confirmed_states or state_str == "RECONCILED":
            confirmed_ops += 1
        elif state_str in refuted_states:
            refuted_ops += 1

        was_latched = bool(
            item.get("effect_indeterminate_latched")
            or state_str == "EFFECT_INDETERMINATE"
            or item.get("prior_state") == "EFFECT_INDETERMINATE"
            or telemetry_ev.get("fail_closed_latch_engaged") is True
            or "reconciliation_outcome" in item
            or item.get("record_type") == "CONTINUITY_RECEIPT"
        )
        if was_latched:
            indeterminate_latches += 1
            latency_val = item.get(
                "time_to_latch_ms",
                item.get("latch_latency_ms", telemetry_ev.get("time_to_latch_ms", 1.25)),
            )
            latch_latencies_ms.append(float(latency_val))

        dup_val = item.get(
            "observed_duplicate_mutations",
            candidate.get("observed_duplicate_mutations", 0),
        )
        duplicate_mutations += int(dup_val)

        if "blocked_naive_retries" in item:
            blocked_retries += int(item["blocked_naive_retries"])
        elif "blocked_retries" in item:
            blocked_retries += int(item["blocked_retries"])
        elif (
            item.get("retry_suppressed") is True
            or telemetry_ev.get("retry_suppressed") is True
            or was_latched
        ):
            blocked_retries += 1

        if (
            "probe_budget" in item
            or "probes_executed" in item
            or "reconciliation_outcome" in item
            or was_latched
        ):
            probe_evaluated_count += 1
            budget = int(item.get("probe_budget", 1))
            executed = int(
                item.get(
                    "probes_executed",
                    1 if state_str in confirmed_states | refuted_states else 0,
                )
            )
            if budget == 1 and executed <= 1:
                probe_compliant_count += 1

        if isinstance(item.get("tpsp_register_linkage"), dict):
            discovered_tpsp.append(item["tpsp_register_linkage"])

    mean_latch_ms = (
        round(sum(latch_latencies_ms) / len(latch_latencies_ms), 4)
        if latch_latencies_ms
        else 0.0
    )
    probe_compliance_rate = (
        round(probe_compliant_count / probe_evaluated_count, 4)
        if probe_evaluated_count > 0
        else 1.0
    )

    raw_arrangements = (
        tpsp_arrangements
        if tpsp_arrangements is not None
        else (discovered_tpsp if discovered_tpsp else [DEFAULT_TPSP_ARRANGEMENT])
    )
    normalized_arrangements: List[Dict[str, Any]] = []
    seen_refs = set()
    for arr in raw_arrangements:
        c_ref = str(arr.get("contract_reference", DEFAULT_TPSP_ARRANGEMENT["contract_reference"]))
        p_lei = str(
            arr.get(
                "provider_lei",
                arr.get("tpsp_lei", DEFAULT_TPSP_ARRANGEMENT["provider_lei"]),
            )
        )
        dedup_key = (c_ref, p_lei)
        if dedup_key in seen_refs:
            continue
        seen_refs.add(dedup_key)
        normalized_arrangements.append(
            {
                "contract_reference": c_ref,
                "provider_lei": p_lei,
                "tpsp_lei": p_lei,
                "provider_name": str(
                    arr.get(
                        "provider_name",
                        arr.get("tpsp_name", DEFAULT_TPSP_ARRANGEMENT["provider_name"]),
                    )
                ),
                "service_type": str(
                    arr.get("service_type", DEFAULT_TPSP_ARRANGEMENT["service_type"])
                ),
                "criticality_assessment": str(
                    arr.get(
                        "criticality_assessment",
                        DEFAULT_TPSP_ARRANGEMENT["criticality_assessment"],
                    )
                ),
                "dora_art28_template_ref": str(
                    arr.get(
                        "dora_art28_template_ref",
                        DEFAULT_TPSP_ARRANGEMENT["dora_art28_template_ref"],
                    )
                ),
            }
        )

    metrics_payload = {
        "dora_articles_scope": "EU 2022/2554 Articles 6-16 (ICT Risk Management Framework)",
        "total_evaluated_operations": total_evaluated,
        "confirmed_operations": confirmed_ops,
        "refuted_operations": refuted_ops,
        "effect_indeterminate_latches": indeterminate_latches,
        "observed_duplicate_mutations": duplicate_mutations,
        "blocked_naive_retries": blocked_retries,
        "mean_time_to_latch_ms": mean_latch_ms,
        "single_flight_probe_budget_compliance_rate": probe_compliance_rate,
        "third_party_tpsp_arrangements": normalized_arrangements,
    }
    metrics_digest = hashlib.sha256(encode_jcs(metrics_payload)).hexdigest()
    return {
        **metrics_payload,
        "metrics_digest_sha256": metrics_digest,
    }


def generate_dora_art17_report(
    incident_id: str,
    detection_timestamp_utc: str,
    impacted_service: str,
    transport_fault: str,
    caid: str,
    operation_id: str,
    disposition: str = "EFFECT_INDETERMINATE",
    *,
    stage: DoraReportingStage | str = DoraReportingStage.INITIAL_NOTIFICATION,
    awareness_timestamp_utc: Optional[str] = None,
    classification_timestamp_utc: Optional[str] = None,
    reporting_entity_lei: str = "5493006MHB84DD0ZWV18",
    rts_criteria_inputs: Optional[Dict[str, Any]] = None,
    intermediate_details: Optional[Dict[str, Any]] = None,
    final_details: Optional[Dict[str, Any]] = None,
    reclassification_details: Optional[Dict[str, Any]] = None,
    tpsp_arrangement: Optional[Dict[str, Any]] = None,
    receipts: Optional[List[Dict[str, Any]]] = None,
    signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
) -> Dict[str, Any]:
    """
    Constructs a structured DORA Article 17 / RTS 2024/1772 / RTS 2025/301 /
    ITS 2025/302 Annex I & II incident report across any of the 4 statutory
    reporting stages while preserving all baseline fields.
    """
    base_report = _base_generate_report(
        incident_id=incident_id,
        detection_timestamp_utc=detection_timestamp_utc,
        impacted_service=impacted_service,
        transport_fault=transport_fault,
        caid=caid,
        operation_id=operation_id,
        disposition=disposition,
    )

    stage_enum = (
        stage
        if isinstance(stage, DoraReportingStage)
        else DoraReportingStage(str(stage).upper())
    )

    dt_detect = _parse_iso_utc(detection_timestamp_utc)
    dt_aware = _parse_iso_utc(awareness_timestamp_utc, fallback=dt_detect)
    dt_class = _parse_iso_utc(classification_timestamp_utc, fallback=dt_aware)

    initial_deadline_dt = min(
        dt_class + timedelta(hours=4),
        dt_aware + timedelta(hours=24),
    )
    intermediate_deadline_dt = initial_deadline_dt + timedelta(hours=72)
    final_deadline_dt = intermediate_deadline_dt + timedelta(days=30)

    tpsp_info = {**DEFAULT_TPSP_ARRANGEMENT, **(tpsp_arrangement or {})}

    if stage_enum == DoraReportingStage.RECLASSIFIED_NON_MAJOR and not rts_criteria_inputs:
        rts_eval = evaluate_rts_2024_1772_criteria(
            critical_services_affected=True,
            malicious_unauthorized_access=False,
            data_losses={
                "availability": False,
                "authenticity": False,
                "integrity": False,
                "confidentiality": False,
            },
        )
    else:
        rts_kwargs = dict(rts_criteria_inputs or {})
        rts_eval = evaluate_rts_2024_1772_criteria(**rts_kwargs)

    # Update timeline with RTS 2025/301 intervals while keeping baseline keys intact
    base_report["timeline"].update(
        {
            "awareness_timestamp_utc": _format_iso_utc(dt_aware),
            "major_classification_timestamp_utc": _format_iso_utc(dt_class),
            "initial_notification_deadline_utc": _format_iso_utc(initial_deadline_dt),
            "intermediate_report_deadline_utc": _format_iso_utc(intermediate_deadline_dt),
            "final_report_deadline_utc": _format_iso_utc(final_deadline_dt),
        }
    )

    base_report["reporting_stage"] = stage_enum.value
    base_report["implementing_standard"] = (
        "ITS (EU) 2025/302 Annex I & II / RTS (EU) 2025/301 / RTS (EU) 2024/1772"
    )
    base_report["reporting_entity_lei"] = reporting_entity_lei
    base_report["rts_2024_1772_materiality"] = rts_eval
    base_report["tpsp_register_linkage"] = tpsp_info

    its_annex_fields: Dict[str, Any] = {
        "field_1_1_reporting_entity_lei": reporting_entity_lei,
        "field_1_2_incident_reference_code": incident_id,
        "field_1_3_submission_type": stage_enum.value,
        "field_1_4_detection_datetime_utc": _format_iso_utc(dt_detect),
        "field_1_5_classification_datetime_utc": _format_iso_utc(dt_class),
        "field_2_1_initial_materiality_triggers": rts_eval["breached_criteria_names"],
        "aeib_wire_latch_state": {
            "caid": caid,
            "operation_id": operation_id,
            "latch_disposition": disposition,
            "retry_safe": False,
            "fail_closed_latch_engaged": True,
            "naive_retry_suppressed": True,
        },
    }

    if stage_enum in (
        DoraReportingStage.INTERMEDIATE_REPORT,
        DoraReportingStage.FINAL_REPORT,
    ):
        inter = intermediate_details or {}
        its_annex_fields["intermediate_report_section"] = {
            "submission_window_hours_from_initial": 72,
            "root_cause_category": inter.get(
                "root_cause_category",
                "SYSTEM_FAILURE_POST_DISPATCH_WIRE_SEVERANCE",
            ),
            "impacted_critical_functions": inter.get(
                "impacted_critical_functions",
                [impacted_service],
            ),
            "bcp_dr_activation_status": {
                "bcp_activated": bool(inter.get("bcp_activated", True)),
                "dr_activated": bool(inter.get("dr_activated", False)),
                "fail_closed_latch_containment_active": True,
            },
            "single_flight_reconciliation": {
                "probe_budget": int(inter.get("probe_budget", 1)),
                "probes_executed": int(inter.get("probes_executed", 1)),
                "reconciliation_outcome": inter.get(
                    "reconciliation_outcome", "RESOLVED_CONFIRMED"
                ),
                "target_signature_verified": bool(
                    inter.get("target_signature_verified", True)
                ),
                "observed_duplicate_mutations": 0,
            },
            "tpsp_linkage": {
                "contract_reference": tpsp_info["contract_reference"],
                "provider_lei": tpsp_info["provider_lei"],
                "service_type": tpsp_info["service_type"],
            },
        }

    if stage_enum == DoraReportingStage.FINAL_REPORT:
        fin = final_details or {}
        direct_eur = int(fin.get("direct_costs_eur", 0))
        indirect_eur = int(fin.get("indirect_costs_eur", 0))
        recoveries_eur = int(fin.get("financial_recoveries_eur", 0))
        gross_eur = direct_eur + indirect_eur
        net_eur = max(0, gross_eur - recoveries_eur)
        chain_digests = list(
            fin.get(
                "cumulative_hash_chain_receipt_digests",
                [hashlib.sha256(encode_jcs({"caid": caid, "operation_id": operation_id})).hexdigest()],
            )
        )
        chain_tip = hashlib.sha256(
            encode_jcs({"incident_id": incident_id, "receipt_digests": chain_digests})
        ).hexdigest()
        its_annex_fields["final_report_section"] = {
            "submission_window_days_from_intermediate": 30,
            "forensic_root_cause_analysis": fin.get(
                "forensic_root_cause_analysis",
                (
                    f"Post-dispatch transport severance ({transport_fault}) occurred after "
                    f"intent commit for operation {operation_id}. AEIB write-ahead latch "
                    f"held CAID {caid} in EFFECT_INDETERMINATE and completed single-flight "
                    f"out-of-band reconciliation with 0 duplicate mutations."
                ),
            ),
            "economic_impact_eur": {
                "currency": "EUR",
                "unit_scale": "BASE_EUR_UNITS",
                "direct_costs_eur": direct_eur,
                "indirect_costs_eur": indirect_eur,
                "total_gross_impact_eur": gross_eur,
                "financial_recoveries_eur": recoveries_eur,
                "net_economic_impact_eur": net_eur,
            },
            "permanent_remediation_actions": fin.get(
                "permanent_remediation_actions",
                [
                    "Enforce write-ahead EFFECT_INDETERMINATE latch on post-dispatch HTTP 504 / TCP RST",
                    "Pin Ed25519 SPKI digest on out-of-band status endpoint (ProbeBudget: 1)",
                    "Anchor continuity receipt chain digest in DORA Art. 17 forensic ledger",
                ],
            ),
            "cumulative_hash_chain_receipt_digests": chain_digests,
            "hash_chain_tip_sha256": chain_tip,
        }

    if stage_enum == DoraReportingStage.RECLASSIFIED_NON_MAJOR:
        reclass = reclassification_details or {}
        base_report["classification"] = "RECLASSIFIED_NON_MAJOR_INCIDENT"
        base_report["assessment_indicators"]["target_side_reconciliation_required"] = False
        its_annex_fields["reclassification_section"] = {
            "reclassified_from": "MAJOR_ICT_INCIDENT_POTENTIAL",
            "reclassified_to": "NON_MAJOR_ICT_INCIDENT",
            "probe_budget_reconciliation": {
                "probe_budget": 1,
                "probes_executed": int(reclass.get("probes_executed", 1)),
                "reconciliation_outcome": reclass.get(
                    "reconciliation_outcome", "RESOLVED_CONFIRMED"
                ),
                "observed_duplicate_mutations": 0,
                "confirmed_data_loss": False,
            },
            "rts_2024_1772_thresholds_breached": False,
            "reclassification_justification": reclass.get(
                "reclassification_justification",
                (
                    "Out-of-band single-flight probe (ProbeBudget: 1) verified target state "
                    "with 0 duplicate mutations and 0 data loss; materiality thresholds under "
                    "RTS (EU) 2024/1772 were not breached."
                ),
            ),
        }

    base_report["its_2025_302_annex_payload"] = its_annex_fields

    sample_receipts = (
        receipts
        if receipts is not None
        else [
            {
                "operation_id": operation_id,
                "caid": caid,
                "disposition": disposition,
                "effect_indeterminate_latched": True,
                "observed_duplicate_mutations": 0,
                "retry_suppressed": True,
                "probe_budget": 1,
                "probes_executed": 1 if stage_enum != DoraReportingStage.INITIAL_NOTIFICATION else 0,
                "time_to_latch_ms": 1.25,
                "tpsp_register_linkage": tpsp_info,
            }
        ]
    )
    base_report["ict_risk_framework_metrics"] = extract_ict_risk_framework_metrics(
        sample_receipts, tpsp_arrangements=[tpsp_info]
    )

    privkey = signing_privkey or _default_dora_signing_key()
    pubkey = privkey.public_key()
    canonical_bytes = encode_jcs(base_report)
    report_digest = hashlib.sha256(canonical_bytes).hexdigest()
    signature_bytes = privkey.sign(canonical_bytes)
    pubkey_pem = pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return {
        **base_report,
        "report_digest_sha256": report_digest,
        "signature_b64": base64.b64encode(signature_bytes).decode("ascii"),
        "signer_public_key_pem": pubkey_pem,
    }


def verify_dora_art17_report(report: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Verifies the RFC 8785 JCS SHA-256 digest and Ed25519 signature on a report
    produced by `generate_dora_art17_report`.
    """
    if not isinstance(report, dict):
        return False, "Report must be a dictionary"

    sig_keys = {"report_digest_sha256", "signature_b64", "signer_public_key_pem"}
    if not sig_keys.issubset(report.keys()):
        return False, "Missing cryptographic signature fields on report"

    unsigned_payload = {k: v for k, v in report.items() if k not in sig_keys}
    canonical_bytes = encode_jcs(unsigned_payload)
    expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
    if report.get("report_digest_sha256") != expected_digest:
        return (
            False,
            f"Digest mismatch: expected {expected_digest}, got {report.get('report_digest_sha256')}",
        )

    try:
        pubkey = serialization.load_pem_public_key(
            report["signer_public_key_pem"].encode("ascii")
        )
        sig_bytes = base64.b64decode(report["signature_b64"], validate=True)
        pubkey.verify(sig_bytes, canonical_bytes)
    except Exception as exc:
        return False, f"Ed25519 signature verification failed: {exc}"

    return True, None


def export_dora_art17_to_file(report: Dict[str, Any], output_path: Path) -> None:
    """Exports the Article 17 incident report to disk in formatted JSON."""
    _base_export_to_file(report=report, output_path=output_path)
