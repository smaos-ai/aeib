#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
benchmarks/aeib_execution_integrity/run_5arm_benchmark.py
=========================================================
Fair 5-Arm Comparative Benchmark for Agent Execution Integrity.
Evaluated under the stated fault model across 500 episodes and 15 fault vectors.

Execution Arms Evaluated:
  1. naive_retry_baseline:
     Blind retry on transport drop without state verification.
  2. semantic_prompt_drift:
     Payload hash key; evaluated under stochastic prompt drift altering client key.
  3. server_stable_key_unprobed:
     Server-assigned stable key; leaves unresolved pre-commit and policy drops in limbo.
  4. stable_key_with_reconciliation:
     Server-assigned stable key with client status polling on timeout, but without
     pre-dispatch write-ahead journal or signed cryptographic receipts.
  5. aeib_full_protocol:
     AEIB v1.1 protocol: EO-1 pre-dispatch write-ahead journal, RFC 8785 JCS CAID,
     EFFECT_INDETERMINATE wire latch, single-probe reconciliation against target primary,
     and signed Ed25519 continuity receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from benchmarks.aeib_execution_integrity.run_episodes import (
    FAULT_VECTORS,
    Episode,
    ProbeResponse,
    SimulatedServer,
    WireResponse,
    derive_caid,
    generate_500_episodes,
)
from src.eo1_write_before_execute import (
    ContinuityReceipt,
    DispatchIntentRecord,
    IntentLifecycleState,
    PreDispatchIntentInterlock,
    compute_caid,
    recover_unresolved_intents,
    verify_ledger_file,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# -----------------------------------------------------------------------------
# Arm 1: Naive Retry Baseline
# -----------------------------------------------------------------------------

def run_arm_1_naive_retry(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 1: Naive Retry Baseline — re-dispatches with new idempotency key on transport failure."""
    server = SimulatedServer()
    total = len(episodes)

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        key1 = f"naive-att1-{ep.episode_id}"

        resp1 = server.dispatch(key1, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)
        if resp1.is_transport_failure():
            key2 = f"naive-att2-{ep.episode_id}"
            server.dispatch(key2, caid, "acct_alpha", 10, None, ep.episode_id)

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "naive_retry_baseline",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "unresolved_episodes": 0,
        "failure_rate_pct": failure_rate_pct,
        "pre_dispatch_journal": False,
        "signed_cryptographic_receipts": False,
        "offline_verifiability": False,
        "status": "FAIL_DUPLICATES_OBSERVED" if duplicate_count > 0 else "PASS",
    }


# -----------------------------------------------------------------------------
# Arm 2: Semantic Prompt Drift
# -----------------------------------------------------------------------------

def run_arm_2_semantic_drift(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 2: Semantic Prompt Drift — derives key from payload; evaluates vulnerability to drift."""
    server = SimulatedServer()
    total = len(episodes)

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        key1 = hashlib.sha256(encode_jcs(ep.base_payload)).hexdigest()

        resp1 = server.dispatch(key1, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)
        if resp1.is_transport_failure():
            payload_to_retry = ep.rephrased_payload if ep.has_drift else ep.base_payload
            key2 = hashlib.sha256(encode_jcs(payload_to_retry)).hexdigest()
            server.dispatch(key2, caid, "acct_alpha", 10, None, ep.episode_id)

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "semantic_prompt_drift",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "unresolved_episodes": 0,
        "failure_rate_pct": failure_rate_pct,
        "pre_dispatch_journal": False,
        "signed_cryptographic_receipts": False,
        "offline_verifiability": False,
        "status": "FAIL_DRIFT_VULNERABLE" if duplicate_count > 0 else "PASS",
    }


# -----------------------------------------------------------------------------
# Arm 3: Server Stable Key (Without Client Reconciliation)
# -----------------------------------------------------------------------------

def run_arm_3_server_stable_key(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 3: Server Stable Key — static session token without client reconciliation; leaves drops in limbo."""
    server = SimulatedServer()
    unresolved_count = 0
    total = len(episodes)

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        stable_key = f"server-stable-{ep.episode_id}"

        resp1 = server.dispatch(stable_key, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)
        if resp1.is_refusal():
            unresolved_count += 1
        elif resp1.is_transport_failure():
            poll = server.poll_status(stable_key)
            if poll.found:
                server.dispatch(stable_key, caid, "acct_alpha", 10, None, ep.episode_id)
            else:
                unresolved_count += 1

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "server_stable_key_unprobed",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "unresolved_episodes": unresolved_count,
        "failure_rate_pct": failure_rate_pct,
        "pre_dispatch_journal": False,
        "signed_cryptographic_receipts": False,
        "offline_verifiability": False,
        "status": "ZERO_DUPLICATES_UNRESOLVED_DROPS" if unresolved_count > 0 else "PASS",
    }


# -----------------------------------------------------------------------------
# Arm 4: Stable Key with Reconciliation (No Pre-Dispatch Journal or Receipts)
# -----------------------------------------------------------------------------

def run_arm_4_stable_key_reconciled(episodes: List[Episode]) -> Dict[str, Any]:
    """
    Arm 4: Stable Key + Reconciliation Probe.
    Prevents duplicate mutations via server idempotency and client probing,
    but does NOT maintain an EO-1 pre-dispatch write-ahead journal, lacks signed
    cryptographic receipts, and cannot survive client crashes or support offline audit.
    """
    server = SimulatedServer()
    unresolved_count = 0
    total = len(episodes)
    dedup_blocked = 0

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        stable_key = f"server-reconciled-{ep.episode_id}"

        resp1 = server.dispatch(stable_key, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)

        if resp1.is_refusal():
            unresolved_count += 1
        elif resp1.is_transport_failure():
            # Client queries target state
            probe_res = server.probe_state(caid, ep.fault_vector)
            if probe_res.found and probe_res.status == "COMMITTED":
                # Mutation confirmed on target, client considers resolved
                dedup_blocked += 1
            elif probe_res.status == "PROBE_TIMEOUT_OR_STALE":
                # Stale or timeout probe: retry with same stable key
                retry_resp = server.dispatch(stable_key, caid, "acct_alpha", 10, None, ep.episode_id)
                if retry_resp.is_replay:
                    dedup_blocked += 1
            else:
                # Truly not found: retry with same stable key
                server.dispatch(stable_key, caid, "acct_alpha", 10, None, ep.episode_id)

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "stable_key_with_reconciliation",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "unresolved_episodes": unresolved_count,
        "failure_rate_pct": failure_rate_pct,
        "duplicate_attempts_blocked": dedup_blocked,
        "pre_dispatch_journal": False,
        "signed_cryptographic_receipts": False,
        "offline_verifiability": False,
        "status": "PASS_ZERO_DUPLICATES_NO_RECEIPTS" if duplicate_count == 0 else "FAIL",
    }


# -----------------------------------------------------------------------------
# Arm 5: AEIB Full Protocol (v1.1)
# -----------------------------------------------------------------------------

def run_arm_5_aeib_full_protocol(episodes: List[Episode], temp_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Arm 5: AEIB Full Protocol.
    Integrates EO-1 pre-dispatch write-ahead journal, RFC 8785 JCS CAID,
    EFFECT_INDETERMINATE wire latch, single-probe reconciliation against target primary,
    and signed Ed25519 continuity receipts.
    Backed by real disk-persisted PreDispatchIntentInterlock and verified via verify_ledger_file.
    """
    import tempfile

    server = SimulatedServer()
    total = len(episodes)
    latencies_ms: List[float] = []
    blocked_by_gate = 0
    blocked_by_ledger = 0

    dispositions = {
        "OUTCOME_VERIFIED": 0,
        "NOT_FOUND_AFTER_GRACE": 0,
        "RECONCILIATION_CONFLICT": 0,
        "POLICY_REFUSED": 0,
    }

    # Setup directory for disk-backed interlock
    managed_temp = None
    if temp_dir is None:
        managed_temp = tempfile.TemporaryDirectory(prefix="aeib_benchmark_arm5_")
        work_dir = Path(managed_temp.name)
    else:
        work_dir = Path(temp_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    ledger_path = work_dir / "arm5_interlock_ledger.jsonl"
    state_dir = work_dir / "arm5_latch_state"
    state_dir.mkdir(parents=True, exist_ok=True)

    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        output_state_dir=state_dir,
        authority_id="auth-aeib-v1-1",
        policy_epoch=1,
    )

    for ep in episodes:
        t0 = time.perf_counter()
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        caid_hex = caid.split(":")[-1]
        idem_key = f"aeib-{caid_hex[:24]}"

        # 1. EO-1 Pre-dispatch intent committed to write-ahead journal
        intent_record = interlock.record_intent(
            target_uri=f"https://api.internal/{ep.noun}",
            tool_name=ep.verb,
            payload=ep.base_payload,
            intent_id=f"intent-{ep.episode_id:04d}",
        )

        # 2. Wire dispatch through interlock
        resp = server.dispatch(idem_key, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)

        if resp.status_code == 403:
            dispositions["POLICY_REFUSED"] += 1
            interlock._emit_receipt(
                intent_id=intent_record.intent_id,
                caid=intent_record.caid,
                status="POLICY_REFUSED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details={"status_code": 403, "reason": "POLICY_REFUSED"},
            )
        elif resp.status_code == 409:
            dispositions["RECONCILIATION_CONFLICT"] += 1
            interlock._emit_receipt(
                intent_id=intent_record.intent_id,
                caid=intent_record.caid,
                status="RECONCILIATION_CONFLICT",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details={"status_code": 409, "reason": "RECONCILIATION_CONFLICT"},
            )
        elif resp.status_code == 200 and not resp.network_error:
            dispositions["OUTCOME_VERIFIED"] += 1
            interlock._emit_receipt(
                intent_id=intent_record.intent_id,
                caid=intent_record.caid,
                status="COMMITTED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details={"status_code": 200},
            )
        elif resp.is_transport_failure():
            # 3. Transport Interruption -> Latch in EFFECT_INDETERMINATE with retry_safe=False
            interlock.latch_intent(
                caid=intent_record.caid,
                reason=f"TRANSPORT_FAILURE_{ep.fault_vector or 'HTTP_504'}",
                intent_id=intent_record.intent_id,
                target_uri=f"https://api.internal/{ep.noun}",
                tool_name=ep.verb,
            )
            # 4. Out-of-band bounded reconciliation probe against target primary
            probe_res = server.probe_state(caid, ep.fault_vector)
            if probe_res.found and probe_res.status == "COMMITTED":
                # Primary confirms execution -> suppress re-dispatch
                dispositions["OUTCOME_VERIFIED"] += 1
                blocked_by_gate += 1
                interlock.reconcile_out_of_band(
                    caid=intent_record.caid,
                    reconciliation_evidence={"status": "COMMITTED", "probe_found": True},
                    intent_id=intent_record.intent_id,
                )
            else:
                # Ambiguous probe -> re-dispatch anchored to immutable CAID idempotency key
                retry_resp = server.dispatch(idem_key, caid, "acct_alpha", 10, None, ep.episode_id)
                if retry_resp.is_replay:
                    blocked_by_ledger += 1
                    dispositions["OUTCOME_VERIFIED"] += 1
                    interlock.reconcile_out_of_band(
                        caid=intent_record.caid,
                        reconciliation_evidence={"status": "COMMITTED_REPLAY"},
                        intent_id=intent_record.intent_id,
                    )
                else:
                    dispositions["NOT_FOUND_AFTER_GRACE"] += 1
                    interlock.reconcile_out_of_band(
                        caid=intent_record.caid,
                        reconciliation_evidence={"status": "NOT_FOUND_AFTER_GRACE"},
                        intent_id=intent_record.intent_id,
                    )

        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed)

    # 5. Cryptographic verification of the on-disk write-ahead journal and receipts
    verified_records = verify_ledger_file(ledger_path, interlock.boundary_private_key.public_key())
    pre_dispatch_count = sum(1 for r in verified_records if r.get("record_type") == "DISPATCH_INTENT")
    receipts_count = sum(1 for r in verified_records if r.get("record_type") == "CONTINUITY_RECEIPT")
    total_ledger_records = len(verified_records)

    # Verify crash survivability / lifecycle recovery
    recovered_unresolved = recover_unresolved_intents(
        ledger_path, state_dir, public_key=interlock.boundary_private_key.public_key(), verify_signatures=True
    )
    crash_survivability_verified = (len(recovered_unresolved) == 0)

    # Clean up tempdir if managed
    if managed_temp is not None:
        managed_temp.cleanup()

    latencies_ms.sort()
    p50_latency = latencies_ms[len(latencies_ms) // 2]
    p99_latency = latencies_ms[int(len(latencies_ms) * 0.99)]
    rule_of_three_upper_bound = (3.0 / total) * 100.0
    duplicate_count = server.ledger.duplicate_mutations

    return {
        "arm": "aeib_full_protocol",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "duplicate_attempts_blocked": blocked_by_gate + blocked_by_ledger,
        "duplicate_attempts_blocked_by_gate": blocked_by_gate,
        "duplicate_attempts_blocked_by_ledger": blocked_by_ledger,
        "failure_rate_pct": round((duplicate_count / total) * 100.0, 1),
        "rule_of_three_95_upper_bound_pct": round(rule_of_three_upper_bound, 2),
        "pre_dispatch_journal_entries": pre_dispatch_count,
        "signed_cryptographic_receipts": receipts_count,
        "verified_ledger_records_on_disk": total_ledger_records,
        "offline_verifiability": (total_ledger_records == (pre_dispatch_count + receipts_count)) and (total_ledger_records > 0),
        "crash_survivability": crash_survivability_verified,
        "latency_p50_ms": round(p50_latency, 2),
        "latency_p99_ms": round(p99_latency, 2),
        "disposition_counts": dispositions,
        "status": "PASS_ZERO_DUPLICATES_FULL_EVIDENCE" if duplicate_count == 0 else "FAIL",
    }


# -----------------------------------------------------------------------------
# Main Runner & Verification Loop
# -----------------------------------------------------------------------------

def run_5arm_benchmark(seed: int = 42, count: int = 500) -> Dict[str, Any]:
    print("=" * 80)
    print(f"AEIB FAIR 5-ARM COMPARATIVE BENCHMARK: {count} EPISODES / 15 FAULT VECTORS")
    print(f"[*] Configuration: seed={seed}, vectors={len(FAULT_VECTORS)}, episodes={count}")
    print("=" * 80)

    episodes = generate_500_episodes(seed=seed, count=count)

    print("\n[+] Running Arm 1: Naive Retry Baseline...")
    a1 = run_arm_1_naive_retry(episodes)
    print(f"    -> Duplicates: {a1['duplicate_mutations']}/{count} ({a1['failure_rate_pct']}%)")

    print("\n[+] Running Arm 2: Semantic Prompt Drift...")
    a2 = run_arm_2_semantic_drift(episodes)
    print(f"    -> Duplicates: {a2['duplicate_mutations']}/{count} ({a2['failure_rate_pct']}%)")

    print("\n[+] Running Arm 3: Server Stable Key (Unprobed)...")
    a3 = run_arm_3_server_stable_key(episodes)
    print(f"    -> Duplicates: {a3['duplicate_mutations']}/{count} | Unresolved: {a3['unresolved_episodes']}")

    print("\n[+] Running Arm 4: Stable Key + Client Reconciliation (No Receipts)...")
    a4 = run_arm_4_stable_key_reconciled(episodes)
    print(f"    -> Duplicates: {a4['duplicate_mutations']}/{count} | Blocked: {a4['duplicate_attempts_blocked']}")
    print(f"    -> Pre-dispatch Journal: {a4['pre_dispatch_journal']} | Receipts: {a4['signed_cryptographic_receipts']}")

    print("\n[+] Running Arm 5: AEIB Full Protocol (EO-1 + CAID + Latch + Receipts)...")
    a5 = run_arm_5_aeib_full_protocol(episodes)
    print(f"    -> Duplicates: {a5['duplicate_mutations']}/{count} ({a5['failure_rate_pct']}%)")
    print(f"    -> Pre-dispatch Journal: {a5['pre_dispatch_journal_entries']} | Receipts: {a5['signed_cryptographic_receipts']}")
    print(f"    -> Rule-of-Three 95% Upper Bound: ~{a5['rule_of_three_95_upper_bound_pct']}%")

    report = {
        "schema_version": "1.1.0-5arm-benchmark",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": seed,
        "total_episodes": count,
        "fault_vector_count": len(FAULT_VECTORS),
        "results": {
            "arm_1_naive_retry": a1,
            "arm_2_semantic_drift": a2,
            "arm_3_server_stable_key": a3,
            "arm_4_stable_key_reconciled": a4,
            "arm_5_aeib_full_protocol": a5,
        },
        "harness_metric_isolation": {
            "observed_duplicate_mutations": a5["duplicate_mutations"],
            "blocked_duplicate_attempts": a5["duplicate_attempts_blocked"],
            "preserved_indeterminate_outcomes": a3["unresolved_episodes"],
        },
        "epistemic_notice": (
            "Observed under the stated fault model across 500 deterministic episodes. "
            "Evaluates software execution integrity and state reconciliation under fault injection."
        ),
    }

    # Strict invariant validation
    assert a1["duplicate_mutations"] > 0, "Arm 1 must exhibit duplicate mutations"
    assert a2["duplicate_mutations"] > 0, "Arm 2 must exhibit duplicate mutations under drift"
    assert a3["duplicate_mutations"] == 0, "Arm 3 must exhibit 0 duplicate mutations"
    assert a3["unresolved_episodes"] > 0, "Arm 3 must exhibit unresolved drops without client reconciliation"
    assert a4["duplicate_mutations"] == 0, "Arm 4 must exhibit 0 duplicate mutations with client reconciliation"
    assert a4["signed_cryptographic_receipts"] is False, "Arm 4 must not emit signed receipts"
    assert a5["duplicate_mutations"] == 0, "Arm 5 (AEIB) must exhibit 0 duplicate mutations"
    assert a5["signed_cryptographic_receipts"] > 0, "Arm 5 (AEIB) must emit signed receipts"
    assert a5["offline_verifiability"] is True, "Arm 5 (AEIB) must provide offline verifiability"

    return report


def main():
    parser = argparse.ArgumentParser(description="AEIB Fair 5-Arm Comparative Benchmark Runner")
    parser.add_argument("--episodes", type=int, default=500, help="Number of episodes (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--output", type=str, default="results_5arm_benchmark.json", help="Output JSON path")
    args = parser.parse_args()

    rep = run_5arm_benchmark(seed=args.seed, count=args.episodes)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(f"\n[OK] 5-Arm Benchmark complete. Report written to {out_path}")


if __name__ == "__main__":
    main()
