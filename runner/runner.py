#!/usr/bin/env python3
"""
AEIB v0.1 Reference Runner
Supports both single-file execution:
  python3 runner/runner.py fixtures/03_timeout_unknown.jsonl out/results.jsonl
And batch directory evaluation:
  python3 runner/runner.py fixtures/ out/
"""
import os
import sys
import json
import argparse
from pathlib import Path

def evaluate_file(file_path: Path):
    rows = []
    # 1. INVALID_INPUT: Schema validity is a prerequisite
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                row = json.loads(line_str)
                rows.append((idx, row))
            except Exception as e:
                return {
                    "action_id": f"LINE-{idx}",
                    "disposition": "INVALID_INPUT",
                    "reason": f"Syntax error on line {idx}: {str(e)}"
                }

    action_id = "UNKNOWN"
    for _, r in rows:
        if "action_id" in r:
            action_id = r["action_id"]
            break

    # 2. MISSING_EVIDENCE
    has_dispatch = any(r.get("row_type") in ("DISPATCH", "DISPATCH_REQUEST") for _, r in rows)
    has_receipt = any(r.get("row_type") == "RECEIPT" for _, r in rows)
    if has_receipt and not has_dispatch:
        return {
            "action_id": action_id,
            "disposition": "MISSING_EVIDENCE",
            "reason": "Receipt recorded without corresponding dispatch evidence"
        }

    # 3. CONFLICT
    for idx, r in rows:
        if r.get("row_type") in ("RETRY", "CONFLICT") and (r.get("http_status") == 409 or r.get("error") == "IDEMPOTENCY_LOCK_ACTIVE"):
            return {
                "action_id": action_id,
                "disposition": "CONFLICT",
                "reason": "Idempotency lock collision on active nonce"
            }

    dispatch_rows = [r for _, r in rows if r.get("row_type") == "DISPATCH"]
    retry_rows = [r for _, r in rows if r.get("row_type") == "RETRY"]
    if dispatch_rows and retry_rows:
        if dispatch_rows[0].get("amount") != retry_rows[0].get("amount"):
            return {
                "action_id": action_id,
                "disposition": "CONFLICT",
                "reason": f"Contradictory retry payload: amount {dispatch_rows[0].get('amount')} -> {retry_rows[0].get('amount')}"
            }

    adapter_states = [r.get("state") for _, r in rows if r.get("row_type") == "ADAPTER_CLAIM"]
    ledger_states = [r.get("state") for _, r in rows if r.get("row_type") == "LEDGER_CLAIM"]
    if adapter_states and ledger_states and adapter_states != ledger_states:
        return {
            "action_id": action_id,
            "disposition": "CONFLICT",
            "reason": f"Contradictory state claim: adapter ({adapter_states[0]}) vs ledger ({ledger_states[0]})"
        }

    dispatch_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "DISPATCH" and "payload_hash" in r]
    receipt_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "RECEIPT" and "payload_hash" in r]
    if dispatch_hashes and receipt_hashes and dispatch_hashes[0] != receipt_hashes[0]:
        return {
            "action_id": action_id,
            "disposition": "CONFLICT",
            "reason": "Contradictory payload hash between dispatch and receipt"
        }

    # 4. REFUSED
    for idx, r in rows:
        if r.get("row_type") == "POLICY_GATE" or r.get("decision") == "REFUSED" or r.get("http_status") == 403:
            return {
                "action_id": action_id,
                "disposition": "REFUSED",
                "reason": f"Policy refusal: {r.get('rule', 'Constraint violation')}"
            }
        if r.get("row_type") == "CIRCUIT_BREAKER" and r.get("decision") == "REFUSED":
            return {
                "action_id": action_id,
                "disposition": "REFUSED",
                "reason": r.get("message", "Request refused by circuit breaker before dispatch")
            }

    # 5. CONFIRMED
    if has_dispatch and any(r.get("row_type") == "RECEIPT" and r.get("http_status") == 200 for _, r in rows):
        return {
            "action_id": action_id,
            "disposition": "CONFIRMED",
            "reason": "Matching HTTP 200 receipt confirms execution"
        }

    # 6. UNKNOWN
    return {
        "action_id": action_id,
        "disposition": "UNKNOWN",
        "reason": "Action dispatched or claimed, but outcome unresolved"
    }

def main():
    if len(sys.argv) < 2:
        in_path = Path("fixtures")
        out_path = Path("out/results.jsonl")
    elif len(sys.argv) == 2:
        in_path = Path(sys.argv[1])
        out_path = Path("out/results.jsonl")
    else:
        in_path = Path(sys.argv[1])
        out_path = Path(sys.argv[2])

    # If single file mode
    if in_path.is_file():
        out_dir = out_path.parent
        if str(out_dir) != "":
            os.makedirs(out_dir, exist_ok=True)
        res = evaluate_file(in_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, sort_keys=True) + "\n")
        print(f"Evaluated {in_path} -> {out_path}: {res['disposition']}")
        return

    # If directory mode
    if in_path.is_dir():
        if out_path.is_file():
            out_file = out_path
        else:
            os.makedirs(out_path, exist_ok=True)
            out_file = out_path / "results.jsonl"
        os.makedirs(out_file.parent, exist_ok=True)

        results = []
        for ff in sorted(in_path.glob("*.jsonl")):
            res = evaluate_file(ff)
            res["scenario"] = ff.stem
            results.append(res)

        with open(out_file, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        print(f"Evaluated {len(results)} scenarios from {in_path} -> {out_file}")

if __name__ == "__main__":
    main()
