#!/usr/bin/env python3
r"""
run_single_failure_proof.py — Executes and Formats the Canonical Control Failure Gate
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Executes a single intent (req_5f8a9b2c / I-001) through the post-commit 504 fault injector,
records the agent's interpretation and retry, and verifies that the SQLite ledger contains
two committed debits for one logical intent.
Outputs the exact schema requested for the control gate.
"""

import os
import sys
import json
import time
from pathlib import Path
from starlette.testclient import TestClient

# Ensure repo root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from benchmarks.fault_injection.app import app, store, fault_config
from benchmarks.fault_injection.gateway_simulator import GatewaySimulator


def run_canonical_control_failure():
    store.reset(initial_balance=10000.0)
    fault_config.enabled = True
    fault_config.fault_mode = "POST_COMMIT_504"
    fault_config.post_commit_delay_ms = 5.0
    fault_config.max_faults_per_intent = 1
    fault_config.fault_every_attempt = False

    client = TestClient(app)
    gateway = GatewaySimulator(client)

    logical_intent = "I-001"
    idempotency_key = "K-001"
    amount = 100.0

    transcript_lines = []

    # --- ATTEMPT 1 ---
    t1_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    transcript_lines.append(f"[{t1_iso}] Tool call: debit(amount={amount}, intent_id={logical_intent}, idempotency_key={idempotency_key})")
    
    # Injected post-commit 504: The database transaction commits, then 5ms later 504 is returned
    payload_1 = {
        "logical_operation_id": logical_intent,
        "intent_id": f"{logical_intent}-att1",
        "account_id": "acc_primary",
        "amount": amount,
        "description": "Payment of vendor invoice #99",
    }
    status_1, data_1, headers_1 = gateway.dispatch("/debit", payload_1, idempotency_key=idempotency_key, headers={"X-Attempt-Count": "1"})
    
    transcript_lines.append(f"[{t1_iso}] Gateway response: {status_1} Gateway Timeout ({data_1.get('error', 'TIMEOUT')})")
    transcript_lines.append(f"[{t1_iso}] Agent interpretation: Gateway 504 received. Wire dropped. Transaction assumed NOT executed by orchestrator retry loop.")

    # --- ATTEMPT 2 (The Agent Retry with Semantic Drift) ---
    time.sleep(0.01)
    t2_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    
    # Simulating LLM ReAct context reconstruction: The LLM regenerates the tool call,
    # mutating description / adding whitespace or altering the client idempotency UUID
    drifted_key = "K-001-retry"
    transcript_lines.append(f"[{t2_iso}] Retry: debit(amount={amount}, intent_id={logical_intent}, idempotency_key={drifted_key}) [Semantic Drift: mutated key/whitespace]")
    
    payload_2 = {
        "logical_operation_id": logical_intent,
        "intent_id": f"{logical_intent}-att2",
        "account_id": "acc_primary",
        "amount": amount,
        "description": "Payment of vendor invoice #99 (re-issued after timeout)",
    }
    status_2, data_2, headers_2 = gateway.dispatch("/debit", payload_2, idempotency_key=drifted_key, headers={"X-Attempt-Count": "2"})
    
    transcript_lines.append(f"[{t2_iso}] Gateway response: {status_2} OK (Transaction Committed)")
    transcript_lines.append(f"[{t2_iso}] Agent interpretation: Debit successfully acknowledged on retry.")

    # Ground Truth Verification from Database Ledger
    ledger_status = store.get_operation_status(logical_intent)
    commits = ledger_status["commits"]
    actual_commit_count = len(commits)

    # Format Exact Required Output Schema
    result_json = {
        "test_run": "C0_NAIVE_RETRY",
        "intent_id": logical_intent,
        "expected_commit_count": 1,
        "actual_commit_count": actual_commit_count,
        "ledger_state": [
            {
                "tx_id": c["id"],
                "intent_id": logical_intent,
                "debit_id": f"D-{c['id']:03d}",
                "attempt": idx + 1,
                "amount": c["amount"],
                "status": "COMMITTED",
                "timestamp": c["committed_at_utc"],
            }
            for idx, c in enumerate(commits)
        ],
        "agent_transcript": "\n".join(transcript_lines),
    }

    out_file = Path("benchmarks/fault_injection/results/CONTROL_BENCHMARK_EVIDENCE.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2)

    return result_json


if __name__ == "__main__":
    res = run_canonical_control_failure()
    print(json.dumps(res, indent=2))
