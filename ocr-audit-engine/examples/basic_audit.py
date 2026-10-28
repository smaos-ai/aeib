#!/usr/bin/env python3
"""Example: Basic Audit using OCR Audit Engine."""

import argparse
import sys
from pathlib import Path

# Add src to path if running directly from repo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocr_audit.pipeline_runner import HybridAuditPipeline


def main():
    parser = argparse.ArgumentParser(description="Run basic OCR audit")
    parser.add_argument("--input", required=True, help="Path to input JSONL trace")
    parser.add_argument("--output", default="audit_report.json", help="Path to output report")
    parser.add_argument("--patch-out", default="fix.patch", help="Path to remediation patch")
    args = parser.parse_args()

    pipeline = HybridAuditPipeline(Path(args.input))
    result = pipeline.run()

    print(f"[*] Audit complete on {args.input}")
    print(f"[*] Total ingested: {result['summary']['total_traces_ingested']}")
    print(f"[*] Verified findings: {result['summary']['stage5_verified_findings']}")
    print(f"[*] Toxic Receipt Index: {result['summary']['toxic_receipt_index_pct']}%")

    patch = pipeline.generate_remediation_patch(result)
    if patch:
        with open(args.patch_out, "w", encoding="utf-8") as f:
            f.write(patch)
        print(f"[*] Remediation patch saved to: {args.patch_out}")


if __name__ == "__main__":
    main()
