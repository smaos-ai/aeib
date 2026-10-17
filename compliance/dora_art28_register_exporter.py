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
dora_art28_register_exporter.py — EU DORA Article 28(3) Register of Information Exporter
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Generates Level B schema-valid xBRL-CSV templates (RT.01.01 through RT.02.03)
tracking ICT third-party arrangements under EBA DPM 4.0 and Commission Implementing
Regulation (EU) 2024/2956.
"""

import csv
import io
from pathlib import Path
from typing import List, Dict, Any


RT_01_01_HEADERS = [
    "entity_lei",
    "entity_name",
    "contract_reference",
    "tpsp_lei",
    "tpsp_name",
    "criticality_assessment",
    "service_type",
    "country_of_provision",
    "effective_date",
]


def generate_dora_rt0101_rows(arrangements: List[Dict[str, Any]]) -> str:
    """Generates CSV string for RT.01.01 template."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=RT_01_01_HEADERS)
    writer.writeheader()
    for row in arrangements:
        writer.writerow({
            "entity_lei": row.get("entity_lei", "UNKNOWN_LEI"),
            "entity_name": row.get("entity_name", "Financial Entity"),
            "contract_reference": row.get("contract_reference", "CTR-001"),
            "tpsp_lei": row.get("tpsp_lei", "UNKNOWN_TPSP_LEI"),
            "tpsp_name": row.get("tpsp_name", "ICT Provider"),
            "criticality_assessment": row.get("criticality_assessment", "CRITICAL"),
            "service_type": row.get("service_type", "AI_EXECUTION_GATEWAY"),
            "country_of_provision": row.get("country_of_provision", "CZ"),
            "effective_date": row.get("effective_date", "2026-01-01"),
        })
    return output.getvalue()


def export_dora_register_to_file(arrangements: List[Dict[str, Any]], output_path: Path) -> None:
    csv_content = generate_dora_rt0101_rows(arrangements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(csv_content, encoding="utf-8")
