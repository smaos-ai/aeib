#!/usr/bin/env python3
"""Example: Generating a DORA RTS Art. 17 Incident Classification Report."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocr_audit.pipeline_runner import HybridAuditPipeline


def generate_dora_report(trace_path: str, report_out: str):
    pipeline = HybridAuditPipeline(Path(trace_path))
    result = pipeline.run()

    dora_findings = []
    for f in result["findings"]:
        dora_findings.append({
            "incident_id": f["finding_id"],
            "dora_article": "Article 17(3) - Logging & Incident Integrity",
            "severity": f["severity"],
            "category": f["category"],
            "impacted_lines": f["anchor_lines"],
            "remediation_held": f["remediation"],
            "evidence_digest": f["evidence_digest"],
        })

    report = {
        "standard": "DORA Regulation (EU) 2022/2554 / RTS 2024/1772",
        "target_trace": trace_path,
        "toxic_receipt_index": result["summary"]["toxic_receipt_index_pct"],
        "material_incidents": dora_findings,
    }

    with open(report_out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[*] DORA Art. 17 report exported to {report_out}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_dora_report(sys.argv[1], "dora_art17_report.json")
    else:
        print("Usage: python dora_art17_report.py <trace.jsonl>")
