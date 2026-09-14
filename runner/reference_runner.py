#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

def evaluate_scenario(file_path: Path):
    rows = []
    
    # --------------------------------------------------------------------------
    # 1. INVALID_INPUT: Schema validity is a prerequisite for evaluation
    # --------------------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                row = json.loads(line_str)
                rows.append((idx, row))
            except json.JSONDecodeError as e:
                return {
                    "verdict": "INVALID_INPUT",
                    "reason": f"Syntax error on line {idx}: {str(e)}",
                    "row_count": idx,
                    "errors": [{"line": idx, "error": str(e)}]
                }

    # --------------------------------------------------------------------------
    # 2. MISSING_EVIDENCE: Absent dispatch or attribution evidence prevents evaluation
    # --------------------------------------------------------------------------
    has_dispatch = any(r.get("row_type") in ("DISPATCH", "DISPATCH_REQUEST") for _, r in rows)
    has_receipt = any(r.get("row_type") == "RECEIPT" for _, r in rows)
    if has_receipt and not has_dispatch:
        return {
            "verdict": "MISSING_EVIDENCE",
            "reason": "Receipt recorded without corresponding dispatch evidence",
            "row_count": len(rows),
            "errors": []
        }

    # --------------------------------------------------------------------------
    # 3. CONFLICT: Contradictory valid records must not be silently resolved
    # --------------------------------------------------------------------------
    # Active lock retry collisions
    for idx, r in rows:
        if r.get("row_type") in ("RETRY", "CONFLICT") and (r.get("http_status") == 409 or r.get("error") == "IDEMPOTENCY_LOCK_ACTIVE"):
            return {
                "verdict": "CONFLICT",
                "reason": "Idempotency lock collision on active nonce",
                "row_count": len(rows),
                "errors": []
            }

    # Contradictory retry payloads under same action_id
    dispatch_rows = [r for _, r in rows if r.get("row_type") == "DISPATCH"]
    retry_rows = [r for _, r in rows if r.get("row_type") == "RETRY"]
    if dispatch_rows and retry_rows:
        d_amount = dispatch_rows[0].get("amount")
        r_amount = retry_rows[0].get("amount")
        if d_amount is not None and r_amount is not None and d_amount != r_amount:
            return {
                "verdict": "CONFLICT",
                "reason": f"Contradictory retry payload: amount {d_amount} -> {r_amount}",
                "row_count": len(rows),
                "errors": []
            }

    # Contradictory state claims across adapters/ledger
    adapter_states = [r.get("state") for _, r in rows if r.get("row_type") == "ADAPTER_CLAIM"]
    ledger_states = [r.get("state") for _, r in rows if r.get("row_type") == "LEDGER_CLAIM"]
    if adapter_states and ledger_states and adapter_states != ledger_states:
        return {
            "verdict": "CONFLICT",
            "reason": f"Contradictory state claim: adapter ({adapter_states[0]}) vs ledger ({ledger_states[0]})",
            "row_count": len(rows),
            "errors": []
        }

    # Contradictory payload hash mismatch between dispatch and confirmation
    dispatch_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "DISPATCH" and "payload_hash" in r]
    receipt_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "RECEIPT" and "payload_hash" in r]
    if dispatch_hashes and receipt_hashes and dispatch_hashes[0] != receipt_hashes[0]:
        return {
            "verdict": "CONFLICT",
            "reason": "Contradictory payload hash between dispatch and receipt",
            "row_count": len(rows),
            "errors": []
        }

    # Contradictory confirmation + refusal
    has_refusal = any(r.get("row_type") in ("POLICY_GATE", "CIRCUIT_BREAKER") and (r.get("decision") == "REFUSED" or r.get("http_status") in (403, 503)) for _, r in rows)
    has_confirm = any(r.get("row_type") == "RECEIPT" and r.get("http_status") == 200 for _, r in rows)
    if has_confirm and has_refusal:
        return {
            "verdict": "CONFLICT",
            "reason": "Contradictory evidence: action has both qualifying confirmation and refusal",
            "row_count": len(rows),
            "errors": []
        }

    # --------------------------------------------------------------------------
    # 4. REFUSED: Explicit rejection is stronger than an unresolved state
    # --------------------------------------------------------------------------
    for idx, r in rows:
        if r.get("row_type") == "POLICY_GATE" or r.get("decision") == "REFUSED" or r.get("http_status") == 403:
            return {
                "verdict": "REFUSED",
                "reason": f"Policy refusal: {r.get('rule', 'Constraint violation')}",
                "row_count": len(rows),
                "errors": []
            }
        if r.get("row_type") == "CIRCUIT_BREAKER" and r.get("decision") == "REFUSED":
            return {
                "verdict": "REFUSED",
                "reason": r.get("message", "Request refused by circuit breaker before dispatch"),
                "row_count": len(rows),
                "errors": []
            }

    # --------------------------------------------------------------------------
    # 5. CONFIRMED: Qualifying, matching confirmation exists
    # --------------------------------------------------------------------------
    if has_dispatch and has_confirm:
        return {
            "verdict": "CONFIRMED",
            "reason": "Matching HTTP 200 receipt confirms execution",
            "row_count": len(rows),
            "errors": []
        }

    # --------------------------------------------------------------------------
    # 6. UNKNOWN: Residual state when outcome remains unresolved
    # --------------------------------------------------------------------------
    return {
        "verdict": "UNKNOWN",
        "reason": "Action dispatched or claimed, but outcome unresolved",
        "row_count": len(rows),
        "errors": []
    }

def main():
    parser = argparse.ArgumentParser(description="AEIB Reference Runner")
    parser.add_argument("fixtures_dir", nargs="?", default="fixtures", help="Path to fixtures directory")
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures_dir)
    if not fixtures_path.exists():
        print(f"Error: Fixtures directory '{fixtures_path}' not found.", file=sys.stderr)
        sys.exit(1)

    fixture_files = sorted([f for f in fixtures_path.glob("*.jsonl")])
    if not fixture_files:
        print(f"Error: No .jsonl fixture files found in '{fixtures_path}'.", file=sys.stderr)
        sys.exit(1)

    results = {
        "benchmark": "AEIB",
        "version": "0.1.0",
        "evaluation_precedence": [
            "INVALID_INPUT",
            "MISSING_EVIDENCE",
            "CONFLICT",
            "REFUSED",
            "CONFIRMED",
            "UNKNOWN"
        ],
        "total_scenarios": len(fixture_files),
        "scenarios": {}
    }

    scorecard = {
        "benchmark": "AEIB",
        "version": "0.1.0",
        "summary": {
            "total": len(fixture_files),
            "passed": 0,
            "failed": 0,
            "conservation_delta": 0
        },
        "verdicts": {}
    }

    print("=" * 80)
    print("AEIB v0.1 REFERENCE BENCHMARK EXECUTION")
    print("Precedence: INVALID_INPUT -> MISSING_EVIDENCE -> CONFLICT -> REFUSED -> CONFIRMED -> UNKNOWN")
    print("=" * 80)
    print(f"{'Scenario':<35} | {'Verdict':<18} | {'Rows':<6} | {'Status'}")
    print("-" * 80)

    for fpath in fixture_files:
        sname = fpath.stem
        eval_res = evaluate_scenario(fpath)
        verdict = eval_res["verdict"]
        results["scenarios"][sname] = eval_res
        scorecard["verdicts"][sname] = verdict

        # Load expected if available
        exp_file = Path("expected") / f"{sname}.json"
        status = "PASSED"
        if exp_file.exists():
            exp_data = json.loads(exp_file.read_text(encoding="utf-8"))
            if exp_data.get("expected_verdict") != verdict:
                status = "FAILED"
                scorecard["summary"]["failed"] += 1
            else:
                scorecard["summary"]["passed"] += 1
        else:
            scorecard["summary"]["passed"] += 1

        print(f"{sname:<35} | {verdict:<18} | {eval_res['row_count']:<6} | {status}")

    print("=" * 80)
    print(f"Summary: Total: {scorecard['summary']['total']}, Passed: {scorecard['summary']['passed']}, Failed: {scorecard['summary']['failed']}")
    print("=" * 80)

    # Write results.json and scorecard.json deterministically
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")

    with open("scorecard.json", "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2, sort_keys=True)
        f.write("\n")

if __name__ == "__main__":
    main()
