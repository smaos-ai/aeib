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
export_dora_incident.py — DORA Article 17 / RTS 2025/301 Incident Timeline Exporter
Generates structured, timestamped wire telemetry from AEIB receipts and transport
observations to accelerate the mandatory 4-hour classification and incident reporting window.

Does NOT auto-submit or self-classify incidents on behalf of the deployer.
Provides defensible technical input to human incident response teams.
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


def extract_incident_timeline(receipt_or_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts structured wire telemetry and timeline fields from an AEIB receipt
    or OpenTelemetry event for DORA Article 17 classification runbooks.
    """
    # Resolve timestamps
    now_utc = datetime.now(timezone.utc)
    detection_ts = (
        receipt_or_event.get("timestamp")
        or receipt_or_event.get("attestation_timestamp_utc")
        or receipt_or_event.get("time_unix_nano")
        or now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    # Standard 4-hour classification deadline per DORA RTS 2025/301
    try:
        if isinstance(detection_ts, (int, float)):
            dt = datetime.fromtimestamp(detection_ts / 1e9 if detection_ts > 1e11 else detection_ts, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(detection_ts).replace("Z", "+00:00"))
        deadline_dt = dt + timedelta(hours=4)
        deadline_str = deadline_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        detection_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        detection_str = str(detection_ts)
        deadline_str = (now_utc + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")

    attrs = receipt_or_event.get("attributes", {})
    if not attrs and "payload" in receipt_or_event:
        attrs = receipt_or_event.get("payload", {})
    if not attrs:
        attrs = receipt_or_event

    disposition = (
        attrs.get("aeib.disposition")
        or attrs.get("disposition")
        or attrs.get("evaluated_disposition")
        or "EFFECT_INDETERMINATE"
    )

    transport_fault = (
        attrs.get("aeib.transport.fault")
        or attrs.get("aeib.transport.observation")
        or attrs.get("transport_observation")
        or attrs.get("wire_status")
        or "UNKNOWN_TRANSPORT_FAULT"
    )

    status_code = (
        attrs.get("aeib.transport.status_code")
        or attrs.get("status_code")
        or attrs.get("http_status")
        or 0
    )

    target_service_id = (
        attrs.get("aeib.target.service_id")
        or attrs.get("target_service")
        or attrs.get("entity_id")
        or "SVC-PRIMARY-GATEWAY-01"
    )

    caid = attrs.get("aeib.caid") or attrs.get("caid") or attrs.get("action_id") or "CAID-UNASSIGNED"

    # Materiality indicator: indeterminate states on mutating actions trigger classification review
    is_indeterminate = disposition in ("DISPATCHED_UNCONFIRMED", "EFFECT_INDETERMINATE", "UNKNOWN", "PROBE_OUTAGE_HOLD")

    return {
        "standard": "DORA-Article-17-RTS-2025-301",
        "incident_classification_window_hours": 4.0,
        "detection_timestamp_utc": detection_str,
        "classification_deadline_utc": deadline_str,
        "caid": caid,
        "target_service_id": target_service_id,
        "disposition": disposition,
        "retry_safe": bool(attrs.get("aeib.retry_safe", False)),
        "raw_transport_fault_trace": {
            "observation": transport_fault,
            "status_code": status_code,
            "latch_engaged": bool(attrs.get("aeib.latch_engaged", True)),
        },
        "dora_materiality_trigger": is_indeterminate,
        "recommended_action": (
            "ENGAGE_RECONCILIATION_PROBE_IMMEDIATELY" if is_indeterminate else "LOG_TRANSACTION_CONFIRMED"
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export DORA Article 17 structured wire telemetry timeline from AEIB receipts."
    )
    parser.add_argument("--receipt", type=Path, help="Path to AEIB JSON receipt file")
    parser.add_argument("--input", type=Path, help="Path to JSONL wire events file")
    parser.add_argument("--out", type=Path, help="Path to write exported DORA incident JSON")
    args = parser.parse_args()

    records = []
    if args.receipt and args.receipt.is_file():
        data = json.loads(args.receipt.read_text(encoding="utf-8"))
        records.append(extract_incident_timeline(data))
    elif args.input and args.input.is_file():
        for line in args.input.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(extract_incident_timeline(json.loads(line)))
    else:
        # Default synthetic demonstration record
        sample = {
            "aeib.caid": "caid:99a8b7c6d5e4f3a2",
            "aeib.disposition": "DISPATCHED_UNCONFIRMED",
            "aeib.transport.fault": "http_504_gateway_timeout",
            "aeib.transport.status_code": 504,
            "aeib.retry_safe": False,
            "aeib.latch_engaged": True,
            "target_service": "CORE-BANKING-SEPA-GATEWAY",
        }
        records.append(extract_incident_timeline(sample))

    output_doc = {
        "framework": "Digital Operational Resilience Act (EU 2022/2554) Article 17",
        "rts_reference": "RTS 2025/301",
        "incidents_count": len(records),
        "incidents": records,
    }

    out_text = json.dumps(output_doc, indent=2)
    if args.out:
        args.out.write_text(out_text, encoding="utf-8")
        print(f"[*] DORA Article 17 Incident Timeline written to {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
