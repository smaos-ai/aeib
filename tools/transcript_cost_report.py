#!/usr/bin/env python3
"""
Local, zero-model-call report on where an agent conversation's context bytes go.

Reads a transcript JSONL (one JSON object per step) and prints, per
(source, type): step count and bytes, plus system wake-ups per UTC hour.
Unit: BYTES. Tokens are not computed here; use the provider's usage fields
for token counts.

Usage: python3 tools/transcript_cost_report.py <transcript_full.jsonl> [--json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict


def summarize(path: Path) -> Dict[str, Any]:
    counts: Dict[str, int] = collections.Counter()
    sizes: Dict[str, int] = collections.Counter()
    wakeups_by_hour: Dict[str, int] = collections.Counter()
    malformed = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(row, dict):
                malformed += 1
                continue
            key = f"{row.get('source')}/{row.get('type')}"
            counts[key] += 1
            sizes[key] += len(line.encode("utf-8"))
            if row.get("type") == "SYSTEM_MESSAGE":
                ts = str(row.get("created_at", ""))[:13]
                wakeups_by_hour[ts or "unknown"] += 1
    total = sum(sizes.values())
    return {
        "total_bytes": total,
        "malformed_lines": malformed,
        "by_step_type": {
            k: {"steps": counts[k], "bytes": sizes[k], "share_bps": (sizes[k] * 10000) // total if total else 0}
            for k in sorted(sizes, key=lambda x: -sizes[x])
        },
        "system_wakeups_per_hour": dict(sorted(wakeups_by_hour.items())),
    }


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    p = Path(args.transcript)
    if not p.is_file():
        print(f"ERR_TRANSCRIPT_NOT_FOUND: {p}", file=sys.stderr)
        return 2
    report = summarize(p)
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    print(f"total_bytes={report['total_bytes']} malformed={report['malformed_lines']}")
    for k, v in report["by_step_type"].items():
        print(f"{k:40s} steps={v['steps']:6d} bytes={v['bytes']:12d} share_bps={v['share_bps']}")
    print("system wake-ups per hour (UTC):")
    for h, n in report["system_wakeups_per_hour"].items():
        print(f"  {h} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
