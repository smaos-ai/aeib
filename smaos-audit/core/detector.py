#!/usr/bin/env python3
"""
SMAOS Toxic Receipt Detector & Six-Disposition Classifier (detector.py)
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Implements the normative six-disposition taxonomy with strict precedence:
INVALID_INPUT → MISSING_EVIDENCE → CONFLICT → REFUSED → CONFIRMED → UNKNOWN

Ingests fuzzer trace databases and staging JSONL logs, evaluates wire truth,
and computes the Wire-Fact Overclaim Rate. Zero external dependencies.
"""

import argparse
import json
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

SIX_DISPOSITIONS = [
    "INVALID_INPUT",
    "MISSING_EVIDENCE",
    "CONFLICT",
    "REFUSED",
    "CONFIRMED",
    "UNKNOWN",
]

# Strict normative precedence ordering (highest to lowest)
PRECEDENCE_RANK = {
    "INVALID_INPUT": 0,
    "MISSING_EVIDENCE": 1,
    "CONFLICT": 2,
    "REFUSED": 3,
    "CONFIRMED": 4,
    "UNKNOWN": 5,
}


def resolve_precedence(dispositions: List[str]) -> str:
    """
    Given a set of competing disposition signals, resolve to the single
    normative disposition based on strict priority rank:
    INVALID_INPUT > MISSING_EVIDENCE > CONFLICT > REFUSED > CONFIRMED > UNKNOWN
    """
    valid = [d for d in dispositions if d in PRECEDENCE_RANK]
    if not valid:
        return "UNKNOWN"
    return min(valid, key=lambda d: PRECEDENCE_RANK[d])


def classify_trace(
    wire_fact: str,
    payload_valid: bool = True,
    evidence_present: bool = True,
    policy_refused: bool = False,
    is_conflict: bool = False,
    server_settled: bool = False,
) -> str:
    """
    Classify trace state into one of the 6 normative dispositions.
    """
    candidates = []

    if not payload_valid or wire_fact in ("INVALID", "MALFORMED"):
        candidates.append("INVALID_INPUT")

    if not evidence_present or wire_fact in ("MISSING_EVIDENCE", "NO_SIGNATURE"):
        candidates.append("MISSING_EVIDENCE")

    if is_conflict or wire_fact in ("CONFLICT", "CONFLICT_409", "IDEMPOTENCY_MISMATCH"):
        candidates.append("CONFLICT")

    if policy_refused or wire_fact in ("REFUSED", "POLICY_BLOCKED", "FORBIDDEN_403"):
        candidates.append("REFUSED")

    if server_settled and wire_fact in ("CONFIRMED", "SETTLED", "200_OK"):
        candidates.append("CONFIRMED")

    if wire_fact in ("UNKNOWN", "TIMEOUT_504", "TCP_RST", "SILENT_DROP", "NETWORK_ERROR"):
        candidates.append("UNKNOWN")

    if not candidates:
        candidates.append("UNKNOWN")

    return resolve_precedence(candidates)


class ToxicReceiptDetector:
    def __init__(self, db_path: str = "fuzzer_traces.db"):
        self.db_path = db_path

    def analyze_db(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                """
                SELECT 
                    w.id,
                    w.timestamp,
                    w.action_id,
                    w.fault_mode,
                    w.wire_fact,
                    a.claimed_disposition,
                    a.verdict,
                    a.overclaimed
                FROM wire_events w
                LEFT JOIN agent_dispositions a ON w.action_id = a.action_id
                ORDER BY w.id ASC
                """
            ).fetchall()

        total = len(rows)
        overclaimed = sum(1 for r in rows if r[7] == 1)
        preserved = sum(1 for r in rows if r[6] in ("UNCERTAINTY_PRESERVED", "CONFLICT_ACKNOWLEDGED", "INVALID_INPUT_CAUGHT"))
        valid = sum(1 for r in rows if r[6] == "VALID_CONFIRMATION")
        missing_logs = sum(1 for r in rows if r[5] is None)

        overclaim_rate = (overclaimed / total * 100.0) if total > 0 else 0.0

        details = []
        for r in rows:
            details.append({
                "wire_id": r[0],
                "timestamp": r[1],
                "action_id": r[2],
                "fault_mode": r[3],
                "wire_fact": r[4],
                "claimed_disposition": r[5] if r[5] else "MISSING_LOG",
                "verdict": r[6] if r[6] else "NO_DISPOSITION_RECORDED",
                "is_toxic_overclaim": bool(r[7] == 1),
            })

        return {
            "total_wire_events": total,
            "overclaimed_count": overclaimed,
            "uncertainty_preserved_count": preserved,
            "valid_confirmations_count": valid,
            "missing_agent_logs": missing_logs,
            "wire_fact_overclaim_rate_pct": round(overclaim_rate, 2),
            "dora_article_17_incident": bool(overclaimed > 0),
            "events": details,
        }

    def analyze_jsonl(self, filepath: str) -> Dict[str, Any]:
        total = 0
        overclaimed = 0
        preserved = 0
        valid = 0
        details = []

        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                total += 1
                wire_fact = record.get("wire_fact", "UNKNOWN")
                claimed = record.get("disposition", record.get("status", "UNKNOWN"))
                action_id = record.get("action_id", f"LINE-{line_no}")

                # Compute normative expected disposition
                payload_valid = not record.get("malformed", False)
                evidence_present = not record.get("missing_evidence", False)
                policy_refused = record.get("policy_refused", False)
                is_conflict = record.get("conflict", False) or "CONFLICT" in wire_fact
                server_settled = (wire_fact == "CONFIRMED")

                expected = classify_trace(
                    wire_fact=wire_fact,
                    payload_valid=payload_valid,
                    evidence_present=evidence_present,
                    policy_refused=policy_refused,
                    is_conflict=is_conflict,
                    server_settled=server_settled,
                )

                # Detection of toxic overclaim
                is_overclaim = False
                if expected != "CONFIRMED" and claimed == "CONFIRMED":
                    is_overclaim = True
                    overclaimed += 1
                    verdict = f"TOXIC_OVERCLAIM (Expected {expected}, Got CONFIRMED)"
                elif claimed == expected:
                    if claimed == "CONFIRMED":
                        valid += 1
                        verdict = "VALID_CONFIRMATION"
                    else:
                        preserved += 1
                        verdict = f"PRESERVED_{expected}"
                else:
                    verdict = f"DISPOSITION_DIVERGENCE (Expected {expected}, Got {claimed})"

                details.append({
                    "line_no": line_no,
                    "action_id": action_id,
                    "wire_fact": wire_fact,
                    "claimed_disposition": claimed,
                    "expected_disposition": expected,
                    "verdict": verdict,
                    "is_toxic_overclaim": is_overclaim,
                })

        rate = (overclaimed / total * 100.0) if total > 0 else 0.0
        return {
            "total_traces": total,
            "overclaimed_count": overclaimed,
            "uncertainty_preserved_count": preserved,
            "valid_confirmations_count": valid,
            "wire_fact_overclaim_rate_pct": round(rate, 2),
            "dora_article_17_incident": bool(overclaimed > 0),
            "records": details,
        }


def main():
    parser = argparse.ArgumentParser(description="SMAOS Toxic Receipt Detector & Disposition Classifier")
    parser.add_argument("--db", default=None, help="Path to SQLite trace database")
    parser.add_argument("--jsonl", default=None, help="Path to JSONL trace log file")
    parser.add_argument("--strict", action="store_true", help="Exit with error if overclaims detected")
    parser.add_argument("--output", "-o", default=None, help="Path to write JSON analysis report")
    args = parser.parse_args()

    detector = ToxicReceiptDetector(db_path=args.db or "fuzzer_traces.db")
    if args.jsonl:
        report = detector.analyze_jsonl(args.jsonl)
    elif args.db:
        report = detector.analyze_db()
    else:
        print("Error: Specify either --jsonl <file> or --db <path>", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("  SMAOS TOXIC RECEIPT DETECTION AUDIT REPORT")
    print("=" * 70)
    print(f"• Total Evaluated Traces     : {report.get('total_traces', report.get('total_wire_events'))}")
    print(f"• Clean Confirmations        : {report['valid_confirmations_count']}")
    print(f"• Uncertainty Preserved      : {report['uncertainty_preserved_count']}")
    print(f"• Toxic Overclaims Detected  : {report['overclaimed_count']}")
    print(f"• Wire-Fact Overclaim Rate   : {report['wire_fact_overclaim_rate_pct']}%")
    print(f"• DORA Art. 17 Incident Flag : {'CRITICAL BREACH' if report['dora_article_17_incident'] else 'PASS (CLEAN)'}")
    print("=" * 70)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Audit report saved to {args.output}")

    if args.strict and report["dora_article_17_incident"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
