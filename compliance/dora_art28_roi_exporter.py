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
dora_art28_roi_exporter.py — EU DORA Article 28(3) Register of Information (RoI) Exporter
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Generates Level B schema-valid xBRL-CSV templates and EBA DPM 4.0 Open Information
Model (OIM) report packages tracking ICT third-party arrangements under Commission
Implementing Regulation (EU) 2024/2956.
"""

import base64
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs

try:
    from compliance.dora_art28_register_exporter import (
        RT_01_01_HEADERS,
        generate_dora_rt0101_rows as _base_rt0101,
        export_dora_register_to_file as _base_export_file,
    )
except ImportError:
    from dora_art28_register_exporter import (
        RT_01_01_HEADERS,
        generate_dora_rt0101_rows as _base_rt0101,
        export_dora_register_to_file as _base_export_file,
    )

RT_02_01_HEADERS = [
    "entity_lei",
    "contract_reference",
    "service_identifier",
    "service_type",
    "criticality_flag",
    "recovery_time_objective_hours",
    "recovery_point_objective_hours",
]


def generate_dora_rt0101_rows(arrangements: List[Dict[str, Any]]) -> str:
    """Generates CSV string for RT.01.01 template (General information on contracts)."""
    return _base_rt0101(arrangements)


def generate_dora_rt0201_rows(services: List[Dict[str, Any]]) -> str:
    """Generates CSV string for RT.02.01 template (ICT services supporting critical functions)."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=RT_02_01_HEADERS)
    writer.writeheader()
    for row in services:
        writer.writerow({
            "entity_lei": row.get("entity_lei", "UNKNOWN_LEI"),
            "contract_reference": row.get("contract_reference", "CTR-001"),
            "service_identifier": row.get("service_identifier", "SVC-AEIB-01"),
            "service_type": row.get("service_type", "AI_EXECUTION_GATEWAY"),
            "criticality_flag": row.get("criticality_flag", "CRITICAL"),
            "recovery_time_objective_hours": row.get("recovery_time_objective_hours", 2),
            "recovery_point_objective_hours": row.get("recovery_point_objective_hours", 0),
        })
    return output.getvalue()


def export_dora_register_to_file(arrangements: List[Dict[str, Any]], output_path: Path) -> None:
    """Exports the RT.01.01 register CSV to the specified path."""
    _base_export_file(arrangements=arrangements, output_path=output_path)


def export_dora_roi_package(
    arrangements: List[Dict[str, Any]],
    services: List[Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, Path]:
    """
    Exports a complete Level B Register of Information package matching official ESA naming:
    - RT.01.01.csv
    - RT.02.01.csv
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rt0101_path = output_dir / "RT.01.01.csv"
    rt0201_path = output_dir / "RT.02.01.csv"

    rt0101_path.write_text(generate_dora_rt0101_rows(arrangements), encoding="utf-8")
    rt0201_path.write_text(generate_dora_rt0201_rows(services), encoding="utf-8")

    return {
        "RT.01.01": rt0101_path,
        "RT.02.01": rt0201_path,
    }


def _generate_parameters_csv(entity_lei: str, ref_period: str) -> str:
    """Generates EBA DPM 4.0 OIM parameters.csv content."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["name", "value"])
    writer.writerow(["entityID", f"rs:{entity_lei}"])
    writer.writerow(["refPeriod", ref_period])
    writer.writerow(["baseCurrency", "iso4217:EUR"])
    writer.writerow(["decimalsInteger", "0"])
    writer.writerow(["decimalsMonetary", "-2"])
    return output.getvalue()


def _generate_filing_indicators_csv() -> str:
    """Generates EBA DPM 4.0 OIM FilingIndicators.csv content."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["templateID", "reported"])
    writer.writerow(["B_01.01", "true"])
    writer.writerow(["B_02.01", "true"])
    writer.writerow(["B_05.01", "true"])
    return output.getvalue()


def export_eba_dpm40_xbrl_csv_package(
    entity_lei: str,
    ref_period: str,
    arrangements: List[Dict[str, Any]],
    services: List[Dict[str, Any]],
    output_dir: Path,
    signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
) -> Dict[str, Any]:
    """
    Builds the EBA DPM 4.0 / Implementing Regulation (EU) 2024/2956 xBRL-CSV
    Open Information Model (OIM) report package inside `output_dir / package_name`,
    packages it into `{package_name}.zip` with a single matching top-level directory,
    computes SHA-256 digests of every file, and signs a JCS-canonicalized
    `package_manifest_receipt.json` using Ed25519.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    privkey = signing_privkey or ed25519.Ed25519PrivateKey.generate()
    pubkey = privkey.public_key()

    package_name = f"{entity_lei}.CON_FR_DORA010000_DORA_{ref_period}"
    package_dir = output_dir / package_name
    meta_inf_dir = package_dir / "META-INF"
    reports_dir = package_dir / "reports"

    meta_inf_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_package_obj = {
        "documentInfo": {
            "documentType": "https://xbrl.org/report-package/2023"
        }
    }
    report_obj = {
        "documentInfo": {
            "documentType": "https://xbrl.org/2021/xbrl-csv",
            "extends": [
                "http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/dora/4.0/mod/dora.json"
            ],
        }
    }

    oim_files: Dict[str, str] = {
        "META-INF/reportPackage.json": json.dumps(report_package_obj, indent=2),
        "reports/report.json": json.dumps(report_obj, indent=2),
        "reports/parameters.csv": _generate_parameters_csv(entity_lei, ref_period),
        "reports/FilingIndicators.csv": _generate_filing_indicators_csv(),
        "reports/b_01.01.csv": generate_dora_rt0101_rows(arrangements),
        "reports/b_02.01.csv": generate_dora_rt0201_rows(services),
    }

    file_digests: Dict[str, str] = {}
    written_paths: Dict[str, Path] = {}

    for rel_path, content in oim_files.items():
        target_path = package_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content_bytes = content.encode("utf-8")
        target_path.write_bytes(content_bytes)
        file_digests[rel_path] = hashlib.sha256(content_bytes).hexdigest()
        written_paths[rel_path] = target_path

    manifest_payload = {
        "schema": "eba-dpm-4.0-xbrl-csv-oim-v1",
        "regulation": "Commission Implementing Regulation (EU) 2024/2956",
        "package_name": package_name,
        "entity_lei": entity_lei,
        "ref_period": ref_period,
        "files_sha256": file_digests,
    }

    canonical_manifest_bytes = encode_jcs(manifest_payload)
    manifest_digest = hashlib.sha256(canonical_manifest_bytes).hexdigest()
    signature_bytes = privkey.sign(canonical_manifest_bytes)
    signature_b64 = base64.b64encode(signature_bytes).decode("ascii")
    pubkey_pem = pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    manifest_receipt = {
        "manifest": manifest_payload,
        "manifest_digest_sha256": manifest_digest,
        "signature_b64": signature_b64,
        "signer_public_key_pem": pubkey_pem,
    }

    receipt_bytes = json.dumps(manifest_receipt, indent=2).encode("utf-8")
    pkg_receipt_path = package_dir / "package_manifest_receipt.json"
    pkg_receipt_path.write_bytes(receipt_bytes)
    out_receipt_path = output_dir / "package_manifest_receipt.json"
    out_receipt_path.write_bytes(receipt_bytes)

    zip_path = output_dir / f"{package_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in sorted(oim_files.keys()):
            full_path = package_dir / rel_path
            arcname = f"{package_name}/{rel_path}"
            zf.write(full_path, arcname=arcname)
        zf.write(pkg_receipt_path, arcname=f"{package_name}/package_manifest_receipt.json")

    zip_sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    return {
        "package_name": package_name,
        "package_dir": package_dir,
        "zip_path": zip_path,
        "zip_sha256": zip_sha256,
        "manifest_receipt_path": pkg_receipt_path,
        "manifest_receipt": manifest_receipt,
        "manifest_digest_sha256": manifest_digest,
        "signature_b64": signature_b64,
        "signer_public_key_pem": pubkey_pem,
        "files_sha256": file_digests,
        "written_paths": written_paths,
    }
