#!/usr/bin/env python3
"""
AEIB v0.1 Independent Specification Validator (Grounding Oracle)

Pure, independent evaluation logic derived strictly from SPEC.md Section 2 rules.
Contains zero dependencies on runner.py or any shared runtime modules.
Used to establish verifiable provenance of expected/ scorecards and prevent tautologies.

Normative Precedence:
  INVALID_INPUT -> MISSING_EVIDENCE -> CONFLICT -> REFUSED -> CONFIRMED -> UNKNOWN
"""
import os
import sys
import json
from pathlib import Path

def validate_fixture_text(file_path: Path) -> str:
    """
    Evaluates a raw fixture stream strictly against SPEC.md Section 2 precedence rules.
    """
    rows = []

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 1: INVALID_INPUT
    # "The row or event stream violates the input schema, cannot be parsed,
    # or contains an invalid required structure. Invalid input dominates."
    # -------------------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rows.append((idx, json.loads(line_str)))
            except Exception:
                return "INVALID_INPUT"

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 2: MISSING_EVIDENCE
    # "Required dispatch or attribution evidence is absent, so the action
    # cannot be reliably evaluated."
    # Canonical semantic: no dispatch + downstream confirmation = MISSING_EVIDENCE
    # -------------------------------------------------------------------------
    has_dispatch = any(r.get("row_type") in ("DISPATCH", "DISPATCH_REQUEST") for _, r in rows)
    has_receipt = any(r.get("row_type") == "RECEIPT" for _, r in rows)
    if has_receipt and not has_dispatch:
        return "MISSING_EVIDENCE"

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 3: CONFLICT
    # "Valid evidence contains contradictory outcomes, payloads, ownership,
    # or confirmation identities."
    # Canonical semantic: dispatch present + matching confirmation + contradictory refusal = CONFLICT
    # -------------------------------------------------------------------------
    # Sub-rule 3a: Active lock collision (HTTP 409 / IDEMPOTENCY_LOCK_ACTIVE)
    for idx, r in rows:
        if r.get("row_type") in ("RETRY", "CONFLICT") and (r.get("http_status") == 409 or r.get("error") == "IDEMPOTENCY_LOCK_ACTIVE"):
            return "CONFLICT"

    # Sub-rule 3b: Mutated payload across retries under identical action identifier
    dispatch_rows = [r for _, r in rows if r.get("row_type") == "DISPATCH"]
    retry_rows = [r for _, r in rows if r.get("row_type") == "RETRY"]
    if dispatch_rows and retry_rows:
        if dispatch_rows[0].get("amount") != retry_rows[0].get("amount"):
            return "CONFLICT"

    # Sub-rule 3c: Contradictory external state claims (e.g. SETTLED vs CANCELLED)
    adapter_states = [r.get("state") for _, r in rows if r.get("row_type") == "ADAPTER_CLAIM"]
    ledger_states = [r.get("state") for _, r in rows if r.get("row_type") == "LEDGER_CLAIM"]
    if adapter_states and ledger_states and adapter_states != ledger_states:
        return "CONFLICT"

    # Sub-rule 3d: Payload hash divergence between dispatch and receipt
    dispatch_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "DISPATCH" and "payload_hash" in r]
    receipt_hashes = [r.get("payload_hash") for _, r in rows if r.get("row_type") == "RECEIPT" and "payload_hash" in r]
    if len(set(receipt_hashes)) > 1:
        return "CONFLICT"
    if dispatch_hashes and receipt_hashes and dispatch_hashes[0] != receipt_hashes[0]:
        return "CONFLICT"

    # Sub-rule 3e: Contradictory confirmation + refusal on the same action
    has_refusal = any(r.get("row_type") in ("POLICY_GATE", "CIRCUIT_BREAKER") and (r.get("decision") == "REFUSED" or r.get("http_status") in (403, 503)) for _, r in rows)
    has_confirm = any(r.get("row_type") == "RECEIPT" and r.get("http_status") == 200 for _, r in rows)
    if has_confirm and has_refusal:
        return "CONFLICT"

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 4: REFUSED
    # "The action was explicitly rejected and no higher-priority condition applies."
    # Canonical semantic: dispatch refused before execution + no contradictory effect = REFUSED
    # -------------------------------------------------------------------------
    for idx, r in rows:
        if r.get("row_type") == "POLICY_GATE" or r.get("decision") == "REFUSED" or r.get("http_status") == 403:
            return "REFUSED"
        if r.get("row_type") == "CIRCUIT_BREAKER" and r.get("decision") == "REFUSED":
            return "REFUSED"

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 5: CONFIRMED
    # "A qualifying, matching confirmation exists and no higher-priority condition applies."
    # -------------------------------------------------------------------------
    if has_dispatch and has_confirm:
        return "CONFIRMED"

    # -------------------------------------------------------------------------
    # SPEC.md Section 2.1 Rule 6: UNKNOWN
    # "The action was dispatched or claimed, but no qualifying confirmation,
    # refusal, or conflict resolves the outcome. Residual fail-closed state."
    # Canonical semantic: dispatch present + timeout + no confirmation = UNKNOWN
    # -------------------------------------------------------------------------
    return "UNKNOWN"

def main():
    fixtures_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures")
    expected_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "expected")

    print(f"Executing SPEC.md Rule-Grounding Oracle: {fixtures_dir} vs {expected_dir}...")
    fixture_files = sorted(fixtures_dir.glob("*.jsonl"))
    if not fixture_files:
        print(f"Error: No fixtures found in {fixtures_dir}", file=sys.stderr)
        sys.exit(1)

    all_matched = True
    for ff in fixture_files:
        sname = ff.stem
        oracle_verdict = validate_fixture_text(ff)
        exp_file_json = expected_dir / f"{sname}.json"
        exp_file_jsonl = expected_dir / f"{sname}.jsonl"

        expected_verdict = None
        if exp_file_json.exists():
            data = json.loads(exp_file_json.read_text(encoding="utf-8"))
            expected_verdict = data.get("expected_verdict") or data.get("disposition")
        elif exp_file_jsonl.exists():
            for line in exp_file_jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    data = json.loads(line)
                    expected_verdict = data.get("disposition") or data.get("expected_verdict")
                    break

        if expected_verdict != oracle_verdict:
            print(f"[FAIL] {sname}: Oracle rule derived {oracle_verdict}, expected file specifies {expected_verdict}", file=sys.stderr)
            all_matched = False
        else:
            print(f"[OK] {sname:<35} -> {oracle_verdict:<16} (Rule match)")

    if all_matched:
        print(f"ORACLE VALIDATION PASSED: {len(fixture_files)}/{len(fixture_files)} fixtures match SPEC.md rules with 100% agreement.")
        sys.exit(0)
    else:
        print("ORACLE VALIDATION FAILED: Specification divergence detected.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
