#!/usr/bin/env python3
"""Covering design record comparator (stdlib only, prototype).

Compares a VERIFIED candidate against a pinned published baseline. It never
uses a model's memory of a record: the baseline file must match the SHA-256
recorded in PIN.json, otherwise it fails closed.

Labels:
  INVALID_CANDIDATE                       verifier rejected the design
  BASELINE_UNPINNED                       baseline digest missing or mismatched
  ENTRY_NOT_IN_BASELINE                   (v,k,t) absent from the pinned table
  WORSE_THAN_RECORD                       blocks > published size
  REPRODUCED_KNOWN_RESULT                 blocks == published size
  CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW  blocks < published size (and >= lower bound)
  CONTRADICTS_PUBLISHED_LOWER_BOUND       blocks < published lower bound: treat as a defect

A strict improvement is only a candidate: the snapshot may be stale, and human
review plus maintainer confirmation are required before any public claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_BASELINE_DIR = Path(__file__).resolve().parent.parent / "experiments" / "covering_design" / "baseline"


class PinnedBaseline:
    def __init__(self, baseline_dir: Path = DEFAULT_BASELINE_DIR) -> None:
        self.dir = Path(baseline_dir)
        pin_path = self.dir / "PIN.json"
        self.pin: dict[str, Any] = json.loads(pin_path.read_text(encoding="utf-8"))
        raw = (self.dir / "coverdata.json").read_bytes()
        self.actual_sha256 = hashlib.sha256(raw).hexdigest()
        self.pinned = self.actual_sha256 == self.pin.get("sha256")
        self.table: dict[str, Any] = json.loads(raw) if self.pinned else {}

    def entry(self, v: int, k: int, t: int) -> dict[str, Any] | None:
        e = self.table.get(f"C({v},{k},{t})")
        if e is None:
            return
        last = e["imps"][0] if e.get("imps") else ["", "", "", ""]
        return {
            "table_entry": f"C({v},{k},{t})",
            "published_size": int(e["size"]),
            "published_lower_bound": int(e["low_bd"]),
            "last_improvement": {"size": last[0], "method": last[1], "submitter": last[2], "timestamp": last[3]},
        }

    def provenance(self) -> dict[str, Any]:
        return {
            "source": self.pin.get("source"),
            "repository": self.pin.get("repository"),
            "commit": self.pin.get("commit"),
            "commit_date": self.pin.get("commit_date"),
            "fetched_at": self.pin.get("fetched_at"),
            "source_digest": "sha256:" + self.actual_sha256,
            "pinned_digest_match": self.pinned,
            "staleness_warning": self.pin.get("staleness_warning"),
        }


def compare(verification: dict[str, Any], baseline: PinnedBaseline) -> dict[str, Any]:
    p = verification["parameters"]
    out: dict[str, Any] = {"parameters": p, "block_count": verification.get("block_count"),
                           "baseline": baseline.provenance()}
    if not baseline.pinned:
        out["label"] = "BASELINE_UNPINNED"
        return out
    if not verification.get("valid"):
        out["label"] = "INVALID_CANDIDATE"
        return out
    entry = baseline.entry(p["v"], p["k"], p["t"])
    if entry is None:
        out["label"] = "ENTRY_NOT_IN_BASELINE"
        return out
    out["baseline"].update(entry)
    n = verification["block_count"]
    if n < entry["published_lower_bound"]:
        out["label"] = "CONTRADICTS_PUBLISHED_LOWER_BOUND"
    elif n < entry["published_size"]:
        out["label"] = "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW"
    elif n == entry["published_size"]:
        out["label"] = "REPRODUCED_KNOWN_RESULT"
    else:
        out["label"] = "WORSE_THAN_RECORD"
    out["delta_vs_record"] = n - entry["published_size"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare a verifier result against the pinned LJCR baseline")
    ap.add_argument("--verification", required=True, help="JSON output of covering_design_verifier.py")
    ap.add_argument("--baseline-dir", default=str(DEFAULT_BASELINE_DIR))
    args = ap.parse_args()
    ver = json.loads(Path(args.verification).read_text(encoding="utf-8"))
    res = compare(ver, PinnedBaseline(Path(args.baseline_dir)))
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["label"] in ("REPRODUCED_KNOWN_RESULT", "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW") else 1


if __name__ == "__main__":
    sys.exit(main())
