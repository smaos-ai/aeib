#!/usr/bin/env python3
r"""
generate_v020_receipts.py — Generates Canonical v0.2.0 Hash-Chained MCP Execution Receipts
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Generates a realistic stream of v0.2.0 execution receipts exercising:
  - Physical finality verification (OUTCOME_VERIFIED via Database/HTTP probers)
  - The Wire 200 != Verified Outcome invariant (ACK_UNVERIFIED)
  - Reverse proxy 504 / TCP RST fault trapping (DISPATCHED_UNCONFIRMED)
  - Downstream reconciliation missing (RECONCILIATION_NOT_FOUND)
  - Payload tampering / drift (RECONCILIATION_FAILED: expected != downstream hash)
  - Probe interface failures (PROBE_EXCEPTION)
  - Concurrent reconciliation race (RECONCILIATION_CONFLICT)
  - Pre-dispatch authority rejection (REFUSED)
  - Authority freshness anomalies (FRESH, STALE, CLOCK_ORDER_INVALID, UNMEASURED)
  - Cryptographic hash-chain continuity (prev_hash -> current_hash)
  - RFC 9052 COSE_Sign1 envelopes (alg: -8 / EdDSA over Ed25519)
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.hazmat.primitives.asymmetric import ed25519
from src.diagnostic_normalizer import (
    DiagnosticExecutionNormalizer,
    DatabaseStateProber,
    COSESign1Engine,
    MCPJSONRPCParser,
    deterministic_json_bytes,
    deterministic_digest,
    SERIALIZATION_LABEL,
    RECEIPT_VERSION,
    COSE_ALG_EDDSA
)

OUTPUT_FILE = PROJECT_ROOT / "audit_out" / "v0.2.0" / "receipts.jsonl"


def generate_v020_stream():
    out_dir = OUTPUT_FILE.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    priv_key = ed25519.Ed25519PrivateKey.generate()
    kid = "key:smaos-bank-ed25519-01"
    normalizer = DiagnosticExecutionNormalizer(signing_key=priv_key, key_id=kid, freshness_limit_ms=5000.0)

    # Initialize SQL ledger for database prober
    db_prober = DatabaseStateProber(":memory:")

    scenarios = [
        # 1. OUTCOME_VERIFIED: Swift wire settlement confirmed by downstream SQL ledger
        {
            "session_id": "sess-prod-001",
            "step": 1,
            "rpc_id": "rpc-101",
            "tool_name": "swift.settle_payment",
            "arguments": {"bic": "UNICREDIT_CZ", "amount": 1250000.0, "currency": "EUR", "ref": "SW-001"},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": {"status": "SETTLED", "details": '{"booked": true, "ack": "ACK_SWIFT_OK"}'},
            "valid_from_offset": -1.5,
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "db"
        },
        # 2. ACK_UNVERIFIED: HTTP 200 received on wire, but NO downstream probe supplied (The Core Invariant)
        {
            "session_id": "sess-prod-001",
            "step": 2,
            "rpc_id": "rpc-102",
            "tool_name": "treasury.allocate_collateral",
            "arguments": {"desk": "FX_SPOT", "collateral_eur": 500000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": None,
            "valid_from_offset": -0.8,
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": None  # No probe
        },
        # 3. DISPATCHED_UNCONFIRMED: HTTP 504 Gateway Timeout trapped on wire; no reconciliation attempted
        {
            "session_id": "sess-prod-002",
            "step": 1,
            "rpc_id": "rpc-201",
            "tool_name": "core.post_interbank_journal",
            "arguments": {"debit_acc": "DE-01992", "credit_acc": "CZ-99120", "amount": 750000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": None,
            "valid_from_offset": -2.0,
            "authority_ttl_offset": 3600,
            "fault": "HTTP_504_TIMEOUT",
            "probe_type": None
        },
        # 4. RECONCILIATION_NOT_FOUND: TCP RST drop; downstream prober queried but found ZERO rows
        {
            "session_id": "sess-prod-002",
            "step": 2,
            "rpc_id": "rpc-202",
            "tool_name": "liquidity.sweep_excess",
            "arguments": {"target_vault": "VAULT_PRG_01", "threshold_eur": 2000000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": None,  # No record inserted -> 0 rows
            "valid_from_offset": -1.2,
            "authority_ttl_offset": 3600,
            "fault": "TCP_RST_ECONNRESET",
            "probe_type": "db"
        },
        # 5. RECONCILIATION_FAILED: HTTP 504 trapped, but downstream ledger record has divergent payload hash (TAMPERING/DRIFT)
        {
            "session_id": "sess-prod-003",
            "step": 1,
            "rpc_id": "rpc-301",
            "tool_name": "credit.disburse_loan",
            "arguments": {"loan_id": "LN-4401", "principal_eur": 450000.0},
            "actor": "5493000IBP32UQZ0KL24",
            # Insert record with altered payload hash to model tampering/drift
            "tampered_db_insert": {"status": "COMMITTED", "tampered_hash": "sha256:TAMPERED_COLLATERAL_INJECTION"},
            "valid_from_offset": -0.5,
            "authority_ttl_offset": 3600,
            "fault": "HTTP_504_TIMEOUT",
            "probe_type": "db"
        },
        # 6. PROBE_EXCEPTION: Out-of-band probe endpoint timed out or threw network exception
        {
            "session_id": "sess-prod-003",
            "step": 2,
            "rpc_id": "rpc-302",
            "tool_name": "fx.execute_block_trade",
            "arguments": {"base": "EUR", "quote": "USD", "volume": 5000000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "manual_probe": {"exception": True, "error": "Reconciliation backend timeout (socket closed)"},
            "valid_from_offset": -1.0,
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "manual"
        },
        # 7. RECONCILIATION_CONFLICT: Prober detected conflicting duplicate downstream records
        {
            "session_id": "sess-prod-004",
            "step": 1,
            "rpc_id": "rpc-401",
            "tool_name": "clearing.submit_batch",
            "arguments": {"batch_id": "BAT-9941", "entries_count": 140},
            "actor": "5493000IBP32UQZ0KL24",
            "manual_probe": {"conflict_detected": True, "conflicting_records": 2},
            "valid_from_offset": -0.9,
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "manual"
        },
        # 8. REFUSED: Authority TTL expired before dispatch (Pre-dispatch security gate halted call)
        {
            "session_id": "sess-prod-004",
            "step": 2,
            "rpc_id": "rpc-402",
            "tool_name": "admin.force_override_limits",
            "arguments": {"override_reason": "emergency_liquidity"},
            "actor": "5493000IBP32UQZ0KL24",
            "valid_from_offset": -7200,
            "authority_ttl_offset": -3600,  # Expired 1 hour ago
            "fault": None,
            "probe_type": None
        },
        # 9. STALE Freshness: Delta_ms exceeds 5000ms policy threshold
        {
            "session_id": "sess-prod-005",
            "step": 1,
            "rpc_id": "rpc-501",
            "tool_name": "swift.settle_payment",
            "arguments": {"bic": "BNP_PARIBAS", "amount": 900000.0, "currency": "EUR"},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": {"status": "SETTLED", "details": '{"status": "OK"}'},
            "valid_from_offset": -8.5,  # 8.5 seconds ago (> 5s threshold)
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "db"
        },
        # 10. CLOCK_ORDER_INVALID: Backward clock drift / NTP step (tn < t0)
        {
            "session_id": "sess-prod-005",
            "step": 2,
            "rpc_id": "rpc-502",
            "tool_name": "rates.publish_benchmark",
            "arguments": {"tenor": "1M", "rate": 3.45},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": {"status": "COMMITTED"},
            "valid_from_offset": 5.0,  # Valid from 5 seconds in future!
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "db"
        },
        # 11. OUTCOME_VERIFIED: Nominal retail settlement verified via DB probe
        {
            "session_id": "sess-prod-006",
            "step": 1,
            "rpc_id": "rpc-601",
            "tool_name": "sepa.instant_credit",
            "arguments": {"creditor": "CZ-IBAN-888", "amount": 15000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": {"status": "SETTLED", "details": '{"sepa_ref": "SEPA-888"}'},
            "valid_from_offset": -1.1,
            "authority_ttl_offset": 3600,
            "fault": None,
            "probe_type": "db"
        },
        # 12. UNMEASURED Freshness: Explicitly unmanufactured (no t0 timestamp)
        {
            "session_id": "sess-prod-006",
            "step": 2,
            "rpc_id": "rpc-602",
            "tool_name": "sepa.instant_credit",
            "arguments": {"creditor": "CZ-IBAN-889", "amount": 25000.0},
            "actor": "5493000IBP32UQZ0KL24",
            "db_insert": {"status": "SETTLED", "details": '{"sepa_ref": "SEPA-889"}'},
            "valid_from_offset": None,  # Missing -> UNMEASURED
            "authority_ttl_offset": None,
            "fault": None,
            "probe_type": "db"
        }
    ]

    prev_hash = "0" * 64
    stream_records = []

    t_base = time.time()

    print(f"Generating {len(scenarios)} canonical v0.2.0 receipts...")

    for idx, sc in enumerate(scenarios, 1):
        action_id = MCPJSONRPCParser.generate_composite_action_id(
            sc["session_id"], sc["step"], sc["rpc_id"], sc["tool_name"]
        )
        payload_hash = deterministic_digest(sc["arguments"])
        idem_key = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, payload_hash)

        # Set up DB insert if specified
        if sc.get("db_insert"):
            db_prober.insert_record(
                idempotency_key=idem_key,
                action_id=action_id,
                payload_hash=payload_hash,
                status=sc["db_insert"]["status"],
                details=sc["db_insert"].get("details", "{}")
            )
        elif sc.get("tampered_db_insert"):
            db_prober.insert_record(
                idempotency_key=idem_key,
                action_id=action_id,
                payload_hash=sc["tampered_db_insert"]["tampered_hash"],
                status=sc["tampered_db_insert"]["status"]
            )

        # Timestamps
        t_dispatch = t_base + idx * 0.1
        t_dispatch_iso = datetime.fromtimestamp(t_dispatch, tz=timezone.utc).isoformat()
        t0 = t_dispatch + sc["valid_from_offset"] if sc["valid_from_offset"] is not None else None
        ttl_str = (
            datetime.fromtimestamp(t_dispatch + sc["authority_ttl_offset"], tz=timezone.utc).isoformat()
            if sc["authority_ttl_offset"] is not None else None
        )

        raw_rpc = {
            "jsonrpc": "2.0",
            "id": sc["rpc_id"],
            "method": "tools/call",
            "params": {
                "name": sc["tool_name"],
                "arguments": sc["arguments"]
            }
        }

        # Select probe
        selected_prober = db_prober if sc["probe_type"] == "db" else None
        manual_probe = sc.get("manual_probe")

        # Mock client with simulated wire fault
        class LocalMockClient:
            def __init__(self, fault):
                self.fault = fault
            def call_tool(self, name, args, headers=None):
                if self.fault == "HTTP_504_TIMEOUT":
                    raise TimeoutError("Gateway timeout (504)")
                elif self.fault == "TCP_RST_ECONNRESET":
                    raise ConnectionResetError("Connection reset (TCP RST)")
                return {"status": "SUCCESS", "ack": True}

        client = LocalMockClient(sc["fault"])

        # Execute four-step wrap
        receipt = normalizer.execute_lifecycle(
            raw_mcp_request=raw_rpc,
            actor=sc["actor"],
            session_id=sc["session_id"],
            step_sequence=sc["step"],
            authority_ttl=ttl_str,
            valid_time_t0=t0,
            mcp_client=client,
            state_prober=selected_prober,
            manual_probe_result=manual_probe
        )

        receipt_dict = receipt.to_dict()
        receipt_dict["session_id"] = sc["session_id"]
        receipt_dict["tool_name"] = sc["tool_name"]
        receipt_dict["idempotency_key"] = idem_key

        # Cryptographic Hash-Chain Linkage
        receipt_dict["prev_hash"] = prev_hash
        chain_input = f"{prev_hash}:{deterministic_json_bytes(receipt_dict).hex()}"
        current_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()
        receipt_dict["current_hash"] = current_hash
        prev_hash = current_hash

        stream_records.append(receipt_dict)

    # Write out JSONL file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for r in stream_records:
            f.write(json.dumps(r) + "\n")

    manifest = {
        "dataset": "SMAOS AEIB v0.2.0 Canonical Verification Stream",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(stream_records),
        "file_path": str(OUTPUT_FILE),
        "sha256_manifest_digest": hashlib.sha256(open(OUTPUT_FILE, "rb").read()).hexdigest(),
        "signing_key_id": kid,
        "serialization": SERIALIZATION_LABEL,
        "cose_alg": COSE_ALG_EDDSA
    }

    manifest_file = out_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"✅ Generated {len(stream_records)} receipts at: {OUTPUT_FILE}")
    print(f"   Manifest SHA-256: {manifest['sha256_manifest_digest']}")
    return OUTPUT_FILE, manifest_file


if __name__ == "__main__":
    generate_v020_stream()
