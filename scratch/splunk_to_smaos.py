#!/usr/bin/env python3
"""splunk_to_smaos.py — Zero-Dependency Telemetry Converter & Fuzzy Schema Extractor

Converts heterogeneous enterprise audit logs (Splunk, Elastic/ELK, Datadog,
OpenTelemetry, CloudWatch, CSV exports) into normalized JSONL traces compliant with
the SMAOS execution pipeline, ocr-audit-engine, and IETF SCITT action capsules.

Key Capabilities:
  1. Multi-Source Ingestion: Handles JSON array, newline-delimited JSON (JSONL/NDJSON), and CSV.
  2. Fuzzy Schema Extraction: Maps arbitrary client field names via FIELD_ALIASES table.
  3. Dot-Notation Unflattening: Resolves nested paths (e.g., http.response.status_code).
  4. Timestamp Normalization: Formats epoch (s/ms) and diverse date strings to ISO-8601 UTC (Z).
  5. Wire Fault & Verdict Deduction: Automatically infers transport drops and sets safe verdicts.
  6. Zero External Dependencies: Pure Python standard library (json, csv, re, sys, datetime).

Usage:
  python3 scratch/splunk_to_smaos.py splunk_export.json --output fixtures/staging_traces.jsonl
  cat elk_export.jsonl | python3 scratch/splunk_to_smaos.py - > fixtures/staging_traces.jsonl
  python3 scratch/splunk_to_smaos.py datadog_export.csv --filter-mutating --stats
  python3 scratch/splunk_to_smaos.py --test
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple


# ==============================================================================
# 1. FUZZY SCHEMA ALIASES TABLE
# ==============================================================================

FIELD_ALIASES: Dict[str, List[str]] = {
    "action_id": [
        "action_id", "trace_id", "traceId", "transaction_id", "transactionId",
        "txid", "tx_id", "event_id", "eventId", "id", "correlation_id",
        "correlationId", "req_id", "request_id", "requestId", "span_id", "spanId",
        "log_id", "uuid", "event.id", "trace.id", "transaction.id"
    ],
    "type": [
        "type", "action_type", "actionType", "operation", "operation_name",
        "operationName", "event_type", "eventType", "action", "cmd", "command",
        "task", "name", "event.action", "event.category", "tool_name", "toolName",
        "service_action", "api_endpoint"
    ],
    "timestamp": [
        "timestamp", "@timestamp", "_time", "time", "created_at", "createdAt",
        "date_time", "datetime", "event_time", "eventTime", "ts", "start_time",
        "startTime", "log_time"
    ],
    "status": [
        "status", "response_status", "result_status", "state", "verdict",
        "outcome", "result", "event.outcome"
    ],
    "http_status": [
        "http_status", "httpStatus", "status_code", "statusCode", "response_code",
        "responseCode", "http.response.status_code", "http.status_code", "code"
    ],
    "http_method": [
        "http_method", "httpMethod", "method", "verb", "http.request.method",
        "http_verb", "request_method"
    ],
    "amount": [
        "amount", "value", "payment_amount", "paymentAmount", "transfer_amount",
        "transferAmount", "txn_amount", "sum", "total", "transaction_amount",
        "payload.amount", "data.amount"
    ],
    "currency": [
        "currency", "ccy", "currency_code", "currencyCode", "iso_currency",
        "payload.currency", "data.currency"
    ],
    "counterparty": [
        "counterparty", "recipient", "beneficiary", "dest_account", "destAccount",
        "destination", "recipient_iban", "recipientIban", "target_account",
        "targetAccount", "payee", "creditor_account", "payload.counterparty"
    ],
    "wire_fault": [
        "wire_fault", "wireFault", "fault", "transport_fault", "transportFault",
        "error_code", "errorCode", "error_type", "errorType", "exception",
        "exception_class", "fault_code"
    ],
    "verdict": [
        "verdict", "claimed_verdict", "claimedVerdict", "model_verdict",
        "agent_verdict", "settlement_status", "disposition"
    ],
    "signature": [
        "signature", "sig", "cose_signature", "coseSignature", "jws", "jwt",
        "attestation_sig", "attestationSignature", "auth_sig", "token"
    ],
    "retry_held": [
        "retry_held", "retryHeld", "retry_blocked", "retryBlocked", "is_retry",
        "isRetry", "retry", "retry_count", "retryCount"
    ],
    "idempotency_key": [
        "idempotency_key", "idempotencyKey", "x_idempotency_key",
        "idempotency_token", "idempotencyToken", "header.idempotency_key",
        "client_request_token"
    ],
    "xid": [
        "xid", "commit_xid", "commitXid", "pg_xid", "transaction_xid",
        "db_txn_id", "db_transaction_id", "sql_xid"
    ],
    "error": [
        "error", "error_message", "errorMessage", "err", "exception_msg",
        "error_description", "message"
    ],
}

MUTATING_VERBS = {
    "POST", "PUT", "DELETE", "PATCH", "INSERT", "UPDATE", "DROP", "MUTATE"
}

MUTATING_ACTION_TYPES = {
    "CREDIT_SETTLEMENT", "WIRE_TRANSFER", "SEPA_TRANSFER", "PAYMENT_DISPATCH",
    "LEDGER_WRITE", "DB_INSERT", "DB_UPDATE", "DB_DELETE", "MUTATE", "REFUND",
    "LOAN_APPROVAL", "TREASURY_TRANSFER", "SHELL_EXECUTE", "DISBURSE_FUNDS",
    "EXECUTE_TRANSACTION", "CREATE_ORDER", "TRANSFER", "PAYMENT", "SETTLE"
}

WIRE_FAULT_MAP = {
    "504": "TIMEOUT",
    "GATEWAY_TIMEOUT": "TIMEOUT",
    "TIMEOUT": "TIMEOUT",
    "ETIMEDOUT": "TIMEOUT",
    "502": "DROP",
    "503": "DROP",
    "DROP": "DROP",
    "TCP_RST": "DROP",
    "CONNECTION_RESET": "DROP",
    "ECONNRESET": "DROP",
    "EBPF_KERNEL_DROP": "DROP",
    "409": "CONFLICT",
    "CONFLICT": "CONFLICT",
    "STATE_VERSION_MISMATCH": "CONFLICT",
    "429": "RATE_LIMIT",
    "500": "SERVER_ERROR",
    "NONE": "NONE",
    "OK": "NONE",
    "SUCCESS": "NONE",
}


# ==============================================================================
# 2. EXTRACTION & NORMALIZATION LOGIC
# ==============================================================================

def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Safely retrieves a value from a nested dict using dot-notation."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def extract_alias(record: Dict[str, Any], canonical_name: str) -> Any:
    """Extracts a value for canonical_name by searching all defined aliases."""
    aliases = FIELD_ALIASES.get(canonical_name, [canonical_name])
    for alias in aliases:
        if alias in record and record[alias] is not None:
            return record[alias]
        if "." in alias:
            val = get_nested_value(record, alias)
            if val is not None:
                return val
    # Case-insensitive direct key fallback
    lower_map = {k.lower(): v for k, v in record.items() if isinstance(k, str)}
    for alias in aliases:
        alias_lower = alias.lower()
        if alias_lower in lower_map and lower_map[alias_lower] is not None:
            return lower_map[alias_lower]
    return None


def parse_timestamp(raw_ts: Any) -> str:
    """Converts diverse timestamp formats (epoch s/ms, ISO strings, syslog) to standard ISO-8601 UTC."""
    if raw_ts is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Numeric Epoch
    if isinstance(raw_ts, (int, float)):
        sec = raw_ts / 1000.0 if raw_ts > 1e11 else float(raw_ts)
        try:
            return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ts_str = str(raw_ts).strip()
    # String numeric epoch
    if ts_str.replace(".", "", 1).isdigit():
        try:
            val = float(ts_str)
            sec = val / 1000.0 if val > 1e11 else val
            return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    # ISO-8601 with Z or offset
    try:
        clean = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    # Common Splunk/ELK formats
    common_patterns = [
        ("%Y-%m-%d %H:%M:%S.%f %z", None),
        ("%Y-%m-%d %H:%M:%S.%f", timezone.utc),
        ("%Y-%m-%d %H:%M:%S %z", None),
        ("%Y-%m-%d %H:%M:%S", timezone.utc),
        ("%d/%b/%Y:%H:%M:%S %z", None),
    ]
    for fmt, default_tz in common_patterns:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None and default_tz:
                dt = dt.replace(tzinfo=default_tz)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            continue

    # Fallback to current UTC
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_record(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Transforms a raw client log record into a canonical SMAOS audit trace."""
    # 1. Action / Trace ID
    raw_action_id = extract_alias(raw, "action_id")
    action_id = str(raw_action_id).strip() if raw_action_id else f"act-auto-{index:05d}"

    # 2. Action Type & HTTP Method
    raw_type = extract_alias(raw, "type")
    action_type = str(raw_type).strip().upper() if raw_type else "UNKNOWN"
    raw_method = extract_alias(raw, "http_method")
    http_method = str(raw_method).strip().upper() if raw_method else ""

    # 3. HTTP Status
    raw_status = extract_alias(raw, "http_status")
    http_status: Optional[int] = None
    if raw_status is not None:
        try:
            http_status = int(str(raw_status).strip())
        except (ValueError, TypeError):
            http_status = None

    # 4. Wire Fault Deduction
    raw_fault = extract_alias(raw, "wire_fault")
    wire_fault = "NONE"
    if raw_fault is not None:
        clean_fault = str(raw_fault).strip().upper()
        wire_fault = WIRE_FAULT_MAP.get(clean_fault, clean_fault)
    elif http_status is not None:
        if http_status == 504:
            wire_fault = "TIMEOUT"
        elif http_status in (502, 503):
            wire_fault = "DROP"
        elif http_status == 409:
            wire_fault = "CONFLICT"
        elif http_status == 429:
            wire_fault = "RATE_LIMIT"
        elif http_status >= 500:
            wire_fault = "SERVER_ERROR"

    # 5. Mutating Check
    is_mutating = bool(
        raw.get("is_mutating", False)
        or raw.get("mutating", False)
        or http_method in MUTATING_VERBS
        or action_type in MUTATING_ACTION_TYPES
        or any(verb in action_type for verb in ("TRANSFER", "PAYMENT", "SETTLE", "WRITE", "DELETE", "DISBURSE"))
    )

    # 6. Verdict & Proof-or-Stop Gate
    raw_verdict = extract_alias(raw, "verdict")
    raw_status_claim = extract_alias(raw, "status")
    verdict: str

    if wire_fault in ("TIMEOUT", "DROP", "SERVER_ERROR"):
        # Proof-or-stop gate: cannot claim CONFIRMED on dropped transport
        verdict = "UNKNOWN"
    elif raw_verdict:
        verdict = str(raw_verdict).strip().upper()
    elif raw_status_claim and str(raw_status_claim).upper() in ("CONFIRMED", "UNKNOWN", "EXECUTED", "REFUSED", "CONFLICT"):
        verdict = str(raw_status_claim).upper()
    elif http_status in (200, 201, 202, 204):
        verdict = "CONFIRMED"
    elif http_status and (400 <= http_status < 500):
        verdict = "REFUSED"
    else:
        verdict = "UNKNOWN"

    # 7. Retry Held
    raw_retry = extract_alias(raw, "retry_held")
    if raw_retry is not None:
        if isinstance(raw_retry, bool):
            retry_held = raw_retry
        elif isinstance(raw_retry, (int, float)):
            retry_held = raw_retry > 0
        else:
            retry_held = str(raw_retry).strip().lower() in ("true", "1", "yes", "held", "blocked")
    else:
        # Default safety: if fault occurred or UNKNOWN, retry should be held
        retry_held = wire_fault != "NONE" or verdict == "UNKNOWN"

    # 8. Timestamp
    raw_ts = extract_alias(raw, "timestamp")
    timestamp = parse_timestamp(raw_ts)

    # Assemble canonical trace
    normalized: Dict[str, Any] = {
        "action_id": action_id,
        "type": action_type,
        "timestamp": timestamp,
        "verdict": verdict,
        "retry_held": retry_held,
        "wire_fault": wire_fault,
    }

    # Optional Canonical Fields
    amount = extract_alias(raw, "amount")
    if amount is not None:
        try:
            normalized["amount"] = float(amount) if "." in str(amount) else int(amount)
        except (ValueError, TypeError):
            normalized["amount"] = amount

    currency = extract_alias(raw, "currency")
    if currency:
        normalized["currency"] = str(currency).strip().upper()

    counterparty = extract_alias(raw, "counterparty")
    if counterparty:
        normalized["counterparty"] = str(counterparty).strip()

    idempotency_key = extract_alias(raw, "idempotency_key")
    if idempotency_key:
        normalized["idempotency_key"] = str(idempotency_key).strip()

    signature = extract_alias(raw, "signature")
    if signature:
        normalized["signature"] = str(signature).strip()

    xid = extract_alias(raw, "xid")
    if xid is not None:
        try:
            normalized["xid"] = int(xid)
        except (ValueError, TypeError):
            pass

    if http_status is not None:
        normalized["http_status"] = http_status

    if http_method:
        normalized["http_method"] = http_method

    if is_mutating:
        normalized["is_mutating"] = True

    err = extract_alias(raw, "error")
    if err:
        normalized["error"] = str(err).strip()

    return normalized


# ==============================================================================
# 3. STREAMING PARSER & INPUT DETECTION
# ==============================================================================

def parse_input_stream(stream: Iterable[str], format_hint: str = "auto") -> Generator[Dict[str, Any], None, None]:
    """Yields parsed raw dictionary records from lines of text."""
    stream_iter = iter(stream)
    first_char = None
    lines: List[str] = []

    # Accumulate first non-empty lines to detect format
    for line in stream_iter:
        lines.append(line)
        stripped = line.strip()
        if not first_char and stripped:
            first_char = stripped[0]
            if format_hint == "auto":
                if first_char == "[":
                    format_hint = "json_array"
                elif first_char == "{" and "}" in stripped:
                    format_hint = "jsonl"
                elif "," in line:
                    format_hint = "csv"
        if len(lines) >= 5 and format_hint != "auto":
            break

    # Execute parser based on detected format
    if format_hint == "json_array":
        full_content = "".join(lines) + "".join(stream_iter)
        try:
            data = json.loads(full_content)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield item
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"[WARN] Failed to parse JSON array: {exc}\n")

    elif format_hint == "csv":
        all_text = io.StringIO("".join(lines) + "".join(stream_iter))
        reader = csv.DictReader(all_text)
        for row in reader:
            yield row

    else:
        # JSONL / NDJSON default streaming
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

        for line in stream_iter:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ==============================================================================
# 4. CONVERTER PIPELINE & SUMMARY REPORT
# ==============================================================================

def convert_telemetry(
    input_stream: Iterable[str],
    output_writer: Any,
    filter_mutating_only: bool = False,
    format_hint: str = "auto"
) -> Dict[str, Any]:
    """Runs the normalization pipeline and writes JSONL output."""
    stats = {
        "total_records_ingested": 0,
        "mutating_actions_extracted": 0,
        "read_only_noise_filtered": 0,
        "wire_faults_detected": 0,
        "overclaimed_confirmed_downgraded": 0,
        "total_monetary_volume": 0.0,
    }

    index = 0
    for raw in parse_input_stream(input_stream, format_hint=format_hint):
        index += 1
        stats["total_records_ingested"] += 1

        norm = normalize_record(raw, index)
        is_mut = norm.get("is_mutating", False)

        if is_mut:
            stats["mutating_actions_extracted"] += 1
        else:
            stats["read_only_noise_filtered"] += 1

        if norm.get("wire_fault", "NONE") != "NONE":
            stats["wire_faults_detected"] += 1
            # Check if original raw record had claimed success
            raw_claim = str(raw.get("verdict", raw.get("status", ""))).upper()
            if raw_claim in ("CONFIRMED", "SUCCESS", "EXECUTED", "200") and norm["verdict"] == "UNKNOWN":
                stats["overclaimed_confirmed_downgraded"] += 1

        amt = norm.get("amount")
        if isinstance(amt, (int, float)):
            stats["total_monetary_volume"] += float(amt)

        if filter_mutating_only and not is_mut:
            continue

        output_writer.write(json.dumps(norm) + "\n")

    return stats


# ==============================================================================
# 5. SELF-TEST BATTERY
# ==============================================================================

def run_self_tests() -> bool:
    """Validates the converter against Splunk, ELK, Datadog, and CSV test fixtures."""
    print(">>> Running splunk_to_smaos self-tests...")

    # Test 1: Splunk JSON array export
    splunk_json = json.dumps([
        {
            "_time": "2026-09-17 08:30:00.000 +0000",
            "txid": "sp-101",
            "event_type": "WIRE_TRANSFER",
            "http.response.status_code": 504,
            "payment_amount": 250000,
            "ccy": "EUR",
            "dest_account": "DE89370400440532013000",
            "verdict": "CONFIRMED"  # Overclaim on 504!
        },
        {
            "_time": "2026-09-17 08:30:05.000 +0000",
            "txid": "sp-102",
            "event_type": "GET_BALANCE",
            "http.response.status_code": 200,
            "verdict": "CONFIRMED"
        }
    ])
    buf = io.StringIO()
    stats = convert_telemetry(splunk_json.splitlines(keepends=True), buf, format_hint="json_array")
    assert stats["total_records_ingested"] == 2, f"Expected 2, got {stats['total_records_ingested']}"
    assert stats["wire_faults_detected"] == 1, f"Expected 1 fault, got {stats['wire_faults_detected']}"
    assert stats["overclaimed_confirmed_downgraded"] == 1, "Expected 1 overclaim downgrade"
    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert lines[0]["action_id"] == "sp-101"
    assert lines[0]["wire_fault"] == "TIMEOUT"
    assert lines[0]["amount"] == 250000
    assert lines[0]["currency"] == "EUR"
    print("  ✓ Splunk JSON array parsing passed.")

    # Test 2: Elastic / ELK Common Schema JSONL
    elk_lines = [
        json.dumps({
            "@timestamp": "2026-09-17T08:31:00Z",
            "trace": {"id": "elk-trace-999"},
            "event": {"action": "CREDIT_SETTLEMENT", "outcome": "failure"},
            "http": {"response": {"status_code": 502}},
            "amount": 1850000,
            "currency": "EUR"
        }) + "\n"
    ]
    buf = io.StringIO()
    stats = convert_telemetry(elk_lines, buf, format_hint="jsonl")
    assert stats["total_records_ingested"] == 1
    norm = json.loads(buf.getvalue().strip())
    assert norm["action_id"] == "elk-trace-999"
    assert norm["wire_fault"] == "DROP"
    assert norm["verdict"] == "UNKNOWN"
    assert norm["amount"] == 1850000
    print("  ✓ Elastic ECS JSONL parsing passed.")

    # Test 3: Datadog / Splunk CSV export
    csv_data = (
        "time,transaction_id,action,status_code,amount,currency,counterparty\n"
        "2026-09-17T08:32:00Z,dd-tx-42,PAYMENT_DISPATCH,200,50000,EUR,NL91ABNA0417164300\n"
        "2026-09-17T08:32:01Z,dd-tx-43,HEALTH_CHECK,200,0,EUR,\n"
    )
    buf = io.StringIO()
    stats = convert_telemetry(csv_data.splitlines(keepends=True), buf, format_hint="csv", filter_mutating_only=True)
    assert stats["total_records_ingested"] == 2
    assert stats["mutating_actions_extracted"] == 1
    assert stats["read_only_noise_filtered"] == 1
    norm_lines = [json.loads(l) for l in buf.getvalue().splitlines()]
    assert len(norm_lines) == 1
    assert norm_lines[0]["action_id"] == "dd-tx-42"
    assert norm_lines[0]["amount"] == 50000
    print("  ✓ CSV export & mutating filter passed.")

    print(">>> All splunk_to_smaos self-tests passed successfully!\n")
    return True


# ==============================================================================
# 6. CLI ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Splunk, ELK, Datadog, or CSV logs into normalized SMAOS JSONL traces."
    )
    parser.add_argument("input", nargs="?", default="-", help="Input file path or '-' for stdin (default: '-')")
    parser.add_argument("-o", "--output", default="-", help="Output file path or '-' for stdout (default: '-')")
    parser.add_argument("-f", "--format", choices=["auto", "json_array", "jsonl", "csv"], default="auto",
                        help="Input format hint (default: auto)")
    parser.add_argument("--filter-mutating", action="store_true", help="Emit only mutating action events")
    parser.add_argument("--stats", action="store_true", help="Print summary ingestion metrics to stderr")
    parser.add_argument("--test", action="store_true", help="Run self-test verification suite and exit")

    args = parser.parse_args()

    if args.test:
        success = run_self_tests()
        sys.exit(0 if success else 1)

    # Setup Input Stream
    if args.input == "-":
        input_stream = sys.stdin
    else:
        in_path = Path(args.input)
        if not in_path.exists():
            sys.stderr.write(f"[ERROR] Input file not found: {args.input}\n")
            sys.exit(1)
        input_stream = open(in_path, "r", encoding="utf-8")

    # Setup Output Writer
    if args.output == "-":
        output_writer = sys.stdout
        should_close_out = False
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        output_writer = open(out_path, "w", encoding="utf-8")
        should_close_out = True

    try:
        stats = convert_telemetry(
            input_stream,
            output_writer,
            filter_mutating_only=args.filter_mutating,
            format_hint=args.format
        )
    finally:
        if args.input != "-":
            input_stream.close()
        if should_close_out:
            output_writer.close()

    if args.stats:
        sys.stderr.write("\n" + "=" * 60 + "\n")
        sys.stderr.write("📊 SMAOS TELEMETRY CONVERSION REPORT\n")
        sys.stderr.write("=" * 60 + "\n")
        sys.stderr.write(f"Total Records Ingested          : {stats['total_records_ingested']}\n")
        sys.stderr.write(f"Mutating Actions Extracted      : {stats['mutating_actions_extracted']}\n")
        sys.stderr.write(f"Read-Only Noise Filtered        : {stats['read_only_noise_filtered']}\n")
        sys.stderr.write(f"Wire Faults Detected            : {stats['wire_faults_detected']}\n")
        sys.stderr.write(f"Overclaimed CONFIRMED Downgraded: {stats['overclaimed_confirmed_downgraded']}\n")
        sys.stderr.write(f"Total Monetary Volume Extracted : €{stats['total_monetary_volume']:,.2f}\n")
        sys.stderr.write("=" * 60 + "\n\n")


if __name__ == "__main__":
    main()
