#!/usr/bin/env python3
"""Export DORA Article 17 incident register from OCR audit findings."""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print("Usage: python export_dora_report.py <findings.json> <output_dora.json>")
        sys.exit(1)

    findings_file = Path(sys.argv[1])
    out_file = Path(sys.argv[2])

    with open(findings_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dora_incidents = []
    for finding in data.get("findings", []):
        dora_incidents.append({
            "incident_id": finding["finding_id"],
            "severity": finding["severity"],
            "category": finding["category"],
            "target_file": finding["target_file"],
            "lines": finding["anchor_lines"],
            "evidence_digest": finding["evidence_digest"],
            "classification": "DORA RTS 2024/1772 Material Incident",
            "fail_closed_action": finding["remediation"],
        })

    out = {
        "standard": "EU Regulation 2022/2554 (DORA)",
        "entity": "ICT Service Provider / Autonomous Harness",
        "incidents": dora_incidents,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"[*] Exported {len(dora_incidents)} incidents to {out_file}")


if __name__ == "__main__":
    main()
