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
dora_art17_gap_exporter.py — EU DORA Article 17 Major ICT Incident Gap Exporter
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Converts wire telemetry, transport fault observations (HTTP 504 / TCP RST),
and EFFECT_INDETERMINATE latches into structured JSON records tailored for
the mandatory 4-hour initial notification window under EU RTS 2024/1772.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path


def generate_dora_art17_report(
    incident_id: str,
    detection_timestamp_utc: str,
    impacted_service: str,
    transport_fault: str,
    caid: str,
    operation_id: str,
    disposition: str = "EFFECT_INDETERMINATE",
) -> Dict[str, Any]:
    """
    Constructs a structured DORA Article 17 initial notification telemetry record.
    """
    try:
        dt = datetime.fromisoformat(detection_timestamp_utc.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)

    notification_deadline = (dt + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")

    report = {
        "regulation": "EU 2022/2554 (DORA)",
        "article": "Article 17 (Major ICT-related incident notification)",
        "regulatory_standard": "RTS 2024/1772",
        "incident_id": incident_id,
        "classification": "MAJOR_ICT_INCIDENT_POTENTIAL",
        "timeline": {
            "detection_timestamp_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regulatory_notification_deadline_utc": notification_deadline,
            "window_hours": 4,
        },
        "telemetry_evidence": {
            "impacted_service": impacted_service,
            "transport_fault": transport_fault,
            "caid": caid,
            "operation_id": operation_id,
            "gateway_disposition": disposition,
            "retry_suppressed": True,
            "fail_closed_latch_engaged": True,
        },
        "assessment_indicators": {
            "critical_services_affected": True,
            "data_loss_observed": False,
            "target_side_reconciliation_required": True,
        },
    }
    return report


def export_dora_art17_to_file(report: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
