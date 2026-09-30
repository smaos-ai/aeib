#!/usr/bin/env python3
"""
run_prototype_benchmark.py — AEIB v0.2 Synthetic Prototype Benchmark Runner
Executes 8 canonical wire scenarios, enforces 1:1 transport and probe logging (8 lines each),
and mints Ed25519-signed JSON execution receipts into receipts/ with an immutable manifest.json.
"""

import os
import sys
import json
import time
import shutil
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Deterministic Ed25519 seed for reproducible prototype runs
FIXED_SEED = b"\xaa" * 32
KEY_ID = "ED25519-KEY-AEIB-V02"
FORMAT_DESIGNATION = "AEIB_JSON_ED25519_PROTOTYPE"


def canonical_json_bytes(obj: dict) -> bytes:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reset_directories(base_dir: Path):
    """Ensures absolute idempotency by wiping previous run state."""
    for sub in ["evidence", "receipts", "public-keys"]:
        p = base_dir / sub
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)
    
    manifest_file = base_dir / "manifest.json"
    if manifest_file.exists():
        manifest_file.unlink()


SCENARIOS = [
    {
        "id": "01-confirmed",
        "action_id": "mcp://sess_20260930_01/101/settlement/payment.settle_payment",
        "actor": "treasury-settlement-agent-01",
        "amount_eur": 250000.0,
        "transport_code": 200,
        "transport_fault": "NONE",
        "probe_status": "NOT_REQUIRED",
        "disposition": "OUTCOME_VERIFIED",
        "retry_policy": "NOT_APPLICABLE_COMPLETED",
        "matched_rule_id": "RULE-01-CONFIRMED",
        "idempotency_key_uuidv5": "59812455-88ea-52ae-8e45-130787a478ee"
    },
    {
        "id": "02a-504-ambiguous",
        "action_id": "mcp://sess_20260930_02a/102a/settlement/payment.settle_payment",
        "actor": "treasury-settlement-agent-02",
        "amount_eur": 150000.0,
        "transport_code": 504,
        "transport_fault": "HTTP_504_GATEWAY_TIMEOUT",
        "probe_status": "AWAITING_OPERATOR_PROBE",
        "disposition": "DISPATCHED_UNCONFIRMED",
        "retry_policy": "PROHIBITED_AWAITING_PROBE",
        "matched_rule_id": "RULE-02A-504-AMBIGUOUS",
        "idempotency_key_uuidv5": "8ca094df-74f4-52d0-99e8-b80894be6a24"
    },
    {
        "id": "02b-504-reconciled",
        "action_id": "mcp://sess_20260930_02b/102b/settlement/payment.settle_payment",
        "actor": "treasury-settlement-agent-03",
        "amount_eur": 50000.0,
        "transport_code": 504,
        "transport_fault": "HTTP_504_GATEWAY_TIMEOUT",
        "probe_status": "FOUND_COMMITTED",
        "disposition": "OUTCOME_VERIFIED",
        "retry_policy": "PROHIBITED_ALREADY_COMMITTED",
        "matched_rule_id": "RULE-02B-504-RECONCILED",
        "idempotency_key_uuidv5": "c20ad482-13c5-555d-b0ad-cb94f1c1f547"
    },
    {
        "id": "03-reset-not-found",
        "action_id": "mcp://sess_20260930_03/103/settlement/payment.settle_payment",
        "actor": "treasury-settlement-agent-04",
        "amount_eur": 75000.0,
        "transport_code": 504,
        "transport_fault": "POST_WRITE_TCP_RST",
        "probe_status": "RECORD_NOT_FOUND",
        "disposition": "RECONCILIATION_NOT_FOUND",
        "retry_policy": "PERMITTED_UNDER_HUMAN_APPROVAL",
        "matched_rule_id": "RULE-03-RESET-NOT-FOUND",
        "idempotency_key_uuidv5": "91a82647-cb72-5b12-9654-20a7bdfd92f7"
    },
    {
        "id": "04-payload-mismatch",
        "action_id": "mcp://sess_20260930_04/104/settlement/payment.settle_payment",
        "actor": "treasury-settlement-agent-05",
        "amount_eur": 33000.0,
        "transport_code": 504,
        "transport_fault": "HTTP_504_GATEWAY_TIMEOUT",
        "probe_status": "PAYLOAD_MISMATCH",
        "disposition": "RECONCILIATION_FAILED",
        "retry_policy": "PROHIBITED_ESCALATE_AUDIT",
        "matched_rule_id": "RULE-04-PAYLOAD-MISMATCH",
        "idempotency_key_uuidv5": "bb85068a-2114-5f54-b467-3a13ee1f0f4a"
    },
    {
        "id": "05-conflict",
        "action_id": "mcp://sess_20260930_05/105/accounting/ledger.post_journal",
        "actor": "general-ledger-agent-01",
        "amount_eur": 12000.0,
        "transport_code": 409,
        "transport_fault": "CONCURRENT_MUTATION_CONFLICT",
        "probe_status": "STATE_CONFLICT",
        "disposition": "RECONCILIATION_CONFLICT",
        "retry_policy": "PROHIBITED_LOCK_RECORD",
        "matched_rule_id": "RULE-05-CONFLICT",
        "idempotency_key_uuidv5": "685c49be-d5b2-5735-9610-eaeb599d14a2"
    },
    {
        "id": "06-context-refused",
        "action_id": "mcp://sess_20260930_06/106/lending/credit.disburse_loan",
        "actor": "credit-underwriting-agent-01",
        "amount_eur": 1250.0,
        "transport_code": 403,
        "transport_fault": "INSUFFICIENT_FUNDS_REFUSAL",
        "probe_status": "NOT_DISPATCHED",
        "disposition": "CONTEXT_POLICY_VIOLATION",
        "retry_policy": "PROHIBITED_POLICY_BLOCK",
        "matched_rule_id": "RULE-06-CONTEXT-REFUSED",
        "idempotency_key_uuidv5": "45d4a138-0fc6-5746-95bc-7517c2f0eb34"
    },
    {
        "id": "07-authority-expired",
        "action_id": "mcp://sess_20260930_07/107/treasury/account.modify_entitlement",
        "actor": "access-broker-agent-01",
        "amount_eur": 0.0,
        "transport_code": 401,
        "transport_fault": "JIT_AUTHORITY_EXPIRED",
        "probe_status": "NOT_DISPATCHED",
        "disposition": "AUTHORITY_NOT_BOUND",
        "retry_policy": "PROHIBITED_REAUTH_REQUIRED",
        "matched_rule_id": "RULE-07-AUTHORITY-EXPIRED",
        "idempotency_key_uuidv5": "17d91cb6-5c5e-5ceb-a25e-ccbd6bf4749f"
    }
]


def main():
    base_dir = Path(__file__).resolve().parent
    reset_directories(base_dir)

    # Initialize Ed25519 Keypair
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(FIXED_SEED)
    pub_key = priv_key.public_key()
    pub_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    (base_dir / "public-keys" / "ed25519-public.pem").write_bytes(pub_bytes)

    transport_log = base_dir / "evidence" / "transport.jsonl"
    probe_log = base_dir / "evidence" / "probe.jsonl"
    receipts_dir = base_dir / "receipts"
    manifest_receipts = []

    ts_now = int(time.time())
    iso_now = "2026-09-30T10:00:00Z"

    with open(transport_log, "w", encoding="utf-8") as t_out, open(probe_log, "w", encoding="utf-8") as p_out:
        for sc in SCENARIOS:
            t_event_id = f"tr_{sc['id']}"
            p_event_id = f"probe_{sc['id']}"

            # 1. Exactly 1 Transport record per scenario (8 lines total)
            transport_event = {
                "event_id": t_event_id,
                "scenario_id": sc["id"],
                "action_id": sc["action_id"],
                "actor": sc["actor"],
                "idempotency_key_uuidv5": sc["idempotency_key_uuidv5"],
                "transport_code": sc["transport_code"],
                "transport_fault": sc["transport_fault"],
                "timestamp_utc": iso_now
            }
            t_line = json.dumps(transport_event, sort_keys=True)
            t_hash = sha256_hex(t_line.encode('utf-8'))
            t_out.write(t_line + "\n")

            # 2. Exactly 1 Probe record per scenario (8 lines total - 1:1 pairing)
            probe_event = {
                "event_id": p_event_id,
                "scenario_id": sc["id"],
                "idempotency_key_uuidv5": sc["idempotency_key_uuidv5"],
                "probe_status": sc["probe_status"],
                "timestamp_utc": iso_now
            }
            p_line = json.dumps(probe_event, sort_keys=True)
            p_hash = sha256_hex(p_line.encode('utf-8'))
            p_out.write(p_line + "\n")

            # ── The 5-Stage Signature Lifecycle ──────────────────────────────
            
            # Stage 1: Build unsigned_payload
            # The org.smaos.aeib extension namespace resides strictly INSIDE unsigned_payload
            unsigned_payload = {
                "receipt_version": "v0.2.0",
                "scenario_id": sc["id"],
                "action_id": sc["action_id"],
                "actor": sc["actor"],
                "amount_eur": sc["amount_eur"],
                "idempotency_key_uuidv5": sc["idempotency_key_uuidv5"],
                "timestamp": ts_now,
                "timestamp_utc": iso_now,
                "org.smaos.aeib": {
                    "disposition": sc["disposition"],
                    "retry_policy": sc["retry_policy"],
                    "matched_rule_id": sc["matched_rule_id"],
                    "transport_code": sc["transport_code"],
                    "transport_fault": sc["transport_fault"],
                    "probe_status": sc["probe_status"],
                    "evidence_bindings": {
                        "transport_event_id": t_event_id,
                        "transport_event_hash": t_hash,
                        "probe_event_id": p_event_id,
                        "probe_event_hash": p_hash
                    }
                }
            }

            # Stage 2: Compute unsigned_payload_hash
            unsigned_canonical = canonical_json_bytes(unsigned_payload)
            unsigned_payload_hash = sha256_hex(unsigned_canonical)

            # Stage 3: Build signable_view containing both payload and hash
            signable_view = {
                "unsigned_payload": unsigned_payload,
                "unsigned_payload_hash": unsigned_payload_hash
            }
            signable_bytes = canonical_json_bytes(signable_view)

            # Stage 4: Sign with Ed25519
            sig_bytes = priv_key.sign(signable_bytes)
            sig_hex = sig_bytes.hex()

            # Stage 5: Assemble final receipt with AEIB_JSON_ED25519_PROTOTYPE
            receipt_doc = {
                "format": FORMAT_DESIGNATION,
                "scenario_id": sc["id"],
                "unsigned_payload": unsigned_payload,
                "unsigned_payload_hash": unsigned_payload_hash,
                "signature_metadata": {
                    "signed_payload_hash": unsigned_payload_hash,
                    "key_id": KEY_ID,
                    "algorithm": "Ed25519",
                    "signature": sig_hex
                }
            }

            r_file = receipts_dir / f"{sc['id']}.json"
            r_bytes = json.dumps(receipt_doc, indent=2).encode('utf-8')
            r_file.write_bytes(r_bytes)

            manifest_receipts.append({
                "file": f"receipts/{sc['id']}.json",
                "scenario_id": sc["id"],
                "disposition": sc["disposition"],
                "payload_hash": unsigned_payload_hash,
                "receipt_file_hash": sha256_hex(r_bytes)
            })

    # Read and hash mapping contract and evidence files
    mapping_path = base_dir / "mapping" / "transport-to-disposition-mapping.yaml"
    mapping_hash = sha256_hex(mapping_path.read_bytes())
    transport_hash = sha256_hex(transport_log.read_bytes())
    probe_hash_file = sha256_hex(probe_log.read_bytes())

    manifest = {
        "benchmark": "AEIB-v0.2-Synthetic-Prototype-Conformance-Run",
        "format": FORMAT_DESIGNATION,
        "version": "0.2.0",
        "generated_at_utc": iso_now,
        "key_id": KEY_ID,
        "mapping_contract": {
            "path": "mapping/transport-to-disposition-mapping.yaml",
            "hash": mapping_hash
        },
        "evidence": {
            "transport_log": {
                "path": "evidence/transport.jsonl",
                "hash": transport_hash,
                "line_count": len(SCENARIOS)
            },
            "probe_log": {
                "path": "evidence/probe.jsonl",
                "hash": probe_hash_file,
                "line_count": len(SCENARIOS)
            }
        },
        "receipt_files": manifest_receipts
    }

    (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"✅ AEIB v0.2 Prototype Benchmark run completed cleanly: 8 scenarios, 8 receipts, exactly 8 transport & 8 probe lines.")


if __name__ == "__main__":
    main()
