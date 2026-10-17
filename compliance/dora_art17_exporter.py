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
dora_art17_exporter.py — EU DORA Article 17 Major ICT Incident Exporter
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Converts wire telemetry, transport fault observations (HTTP 504 / TCP RST),
and write-ahead EFFECT_INDETERMINATE latches into structured JSON records tailored
for the mandatory 4-hour initial notification window under EU RTS 2024/1772.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from compliance.dora_art17_gap_exporter import (
        generate_dora_art17_report as _base_generate_report,
        export_dora_art17_to_file as _base_export_to_file,
    )
except ImportError:
    from dora_art17_gap_exporter import (
        generate_dora_art17_report as _base_generate_report,
        export_dora_art17_to_file as _base_export_to_file,
    )


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
    return _base_generate_report(
        incident_id=incident_id,
        detection_timestamp_utc=detection_timestamp_utc,
        impacted_service=impacted_service,
        transport_fault=transport_fault,
        caid=caid,
        operation_id=operation_id,
        disposition=disposition,
    )


def export_dora_art17_to_file(report: Dict[str, Any], output_path: Path) -> None:
    """Exports the Article 17 incident report to disk in formatted JSON."""
    _base_export_to_file(report=report, output_path=output_path)
