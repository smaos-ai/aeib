#!/usr/bin/env python3
"""Generates synthetic high-volume JSONL logs for benchmarking OCR Audit Engine."""

import argparse
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path


def generate_logs(output_path: Path, count: int = 100000):
    start_time = datetime.now(timezone.utc)
    print(f"[*] Generating {count} synthetic trace lines to {output_path}...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for i in range(1, count + 1):
            ts = (start_time + timedelta(milliseconds=i * 50)).isoformat()
            # 95% healthy reads
            if i % 100 != 0 and i % 250 != 0:
                rec = {
                    "action_id": f"read-{i}",
                    "method": "GET",
                    "http_status": 200,
                    "verdict": "CONFIRMED",
                    "timestamp": ts,
                }
            # 4% healthy mutating
            elif i % 250 != 0:
                rec = {
                    "action_id": f"mut-{i}",
                    "method": "POST",
                    "http_status": 200,
                    "verdict": "CONFIRMED",
                    "xid": 100000 + i,
                    "timestamp": ts,
                }
            # 1% edge cases (504 timeouts, dropped signatures)
            else:
                rec = {
                    "action_id": f"fault-{i}",
                    "method": "POST",
                    "http_status": 504,
                    "wire_fault": "TIMEOUT",
                    "verdict": "CONFIRMED",
                    "timestamp": ts,
                }
            f.write(json.dumps(rec) + "\n")

    print(f"[*] Done. File size: {output_path.stat().st_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lines", type=int, default=10000, help="Number of trace lines")
    parser.add_argument("--output", default="traces/benchmark_sample.jsonl", help="Output path")
    args = parser.parse_args()
    generate_logs(Path(args.output), args.lines)
