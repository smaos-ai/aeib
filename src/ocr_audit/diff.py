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

"""Offline Audit Log Scanner (diff.py)

Ingests staging action traces, executes the 5-stage pipeline,
and emits unified git-diff patches remediating toxic claims into fail-closed UNKNOWN.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

from ocr_audit.pipeline_runner import HybridAuditPipeline


def main():
    parser = argparse.ArgumentParser(description="OCR Offline Audit Log Scanner (diff.py)")
    parser.add_argument("traces", help="Path to input JSONL trace file")
    parser.add_argument("--patch-out", help="Path to output unified diff patch", default=None)
    parser.add_argument("--json-out", help="Path to output JSON audit findings", default=None)
    parser.add_argument("--threshold", type=float, default=0.0, help="TRI percentage threshold")
    args = parser.parse_args()

    pipeline = HybridAuditPipeline(Path(args.traces))
    result = pipeline.run()
    s = result["summary"]

    print("\n" + "═" * 74)
    print("  🔍 OCR AUDIT ENGINE (diff.py)")
    print("═" * 74)
    print(f"  Total Ingested Traces : {s['total_traces_ingested']}")
    print(f"  Noise Discard Rate    : {s['stage1_noise_reduction_pct']}% ($0 token cost)")
    print(f"  Verified Findings     : {s['stage5_verified_findings']}")
    print(f"  Toxic Receipt Index   : {s['toxic_receipt_index_pct']}%")
    print(f"  Duration              : {s['total_duration_ms']} ms")
    print("─" * 74)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\n  💾 Findings saved to: {args.json_out}")

    patch_text = pipeline.generate_remediation_patch(result)
    if args.patch_out and patch_text:
        with open(args.patch_out, "w", encoding="utf-8") as f:
            f.write(patch_text)
        print(f"\n  💾 Remediation patch saved to: {args.patch_out}")

    sys.exit(0 if s["stage5_verified_findings"] == 0 else 1)


if __name__ == "__main__":
    main()
