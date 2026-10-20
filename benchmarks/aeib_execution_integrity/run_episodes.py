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
benchmarks/aeib_execution_integrity/run_episodes.py
===================================================
AEIB Tier 1 Epistemic Baseline: Deterministic Multi-Episode Harness across
15 Fault Vectors and 4 Execution Arms.
Implemented with decoupled fault injection handlers driving state execution.

Execution Arms Evaluated:
  1. naive_retry_baseline:   Blind retry on transport drop without state verification.
  2. payload_derived_key:    Client payload hash key; evaluated under stochastic prompt drift.
  3. server_side_stable_key: Server-assigned stable key; leaves unresolved pre-commit and policy drops.
  4. aeib:                   Reconcile-before-retry interlock with authoritative probe and outbox anchor.
"""

import sys
import os
import json
import time
import random
import hashlib
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from benchmarks.aeib_execution_integrity.fault_registry import fault_inject, FAULT_REGISTRY

# ── 15 FAULT VECTORS VIA ANNOTATION-DRIVEN REGISTRY (ANT GROUP PATTERN) ──────

@fault_inject(
    vector="post_commit_504_drop",
    target="ledger.execute_mutation",
    scenarios={"transport_status": 504, "db_committed": True}
)
def simulate_post_commit_504(context: Dict[str, Any]) -> Dict[str, Any]:
    context["transport_interrupted"] = True
    context["wire_status"] = 504
    context["db_committed"] = True
    return context

@fault_inject(
    vector="tcp_rst_packet",
    target="ledger.execute_mutation",
    scenarios={"packet_verdict": "TCP_RST", "db_committed": True}
)
def simulate_post_commit_rst(context: Dict[str, Any]) -> Dict[str, Any]:
    context["transport_interrupted"] = True
    context["wire_status"] = "TCP_RST"
    context["db_committed"] = True
    return context

@fault_inject(
    vector="replica_lag_stale_read",
    target="probe.query_replica",
    scenarios={"replica_status": "NOT_FOUND", "primary_status": "COMMITTED"}
)
def simulate_replica_lag(context: Dict[str, Any]) -> Dict[str, Any]:
    context["replica_stale"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="delayed_commit",
    target="ledger.commit_window",
    scenarios={"commit_delay_ms": 3500, "client_timeout_ms": 3000}
)
def simulate_delayed_commit(context: Dict[str, Any]) -> Dict[str, Any]:
    context["commit_delayed"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="probe_statement_timeout",
    target="probe.statement_timeout",
    scenarios={"probe_timeout_ms": 3000, "exhausted": True}
)
def simulate_probe_statement_timeout(context: Dict[str, Any]) -> Dict[str, Any]:
    context["probe_timeout"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="half_open_socket_hang",
    target="transport.socket_state",
    scenarios={"socket_state": "HALF_OPEN", "timeout_ms": 5000}
)
def simulate_half_open_socket(context: Dict[str, Any]) -> Dict[str, Any]:
    context["socket_hung"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="pre_commit_400_drop",
    target="gateway.pre_routing",
    scenarios={"pre_commit_severance": True, "db_committed": False}
)
def simulate_pre_commit_drop(context: Dict[str, Any]) -> Dict[str, Any]:
    context["pre_commit_drop"] = True
    context["db_committed"] = False
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="server_reconciliation_conflict",
    target="outbox.reconciliation",
    scenarios={"outbox_state": "DISPATCHED", "ledger_state": "REFUSED"}
)
def simulate_reconciliation_conflict(context: Dict[str, Any]) -> Dict[str, Any]:
    context["conflict_detected"] = True
    context["db_committed"] = False
    return context

@fault_inject(
    vector="primary_failover_in_flight",
    target="cluster.leader_election",
    scenarios={"failover_active": True, "fenced_leader": True}
)
def simulate_primary_failover(context: Dict[str, Any]) -> Dict[str, Any]:
    context["failover"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="circuit_breaker_trip",
    target="circuit_breaker.state",
    scenarios={"state": "OPEN", "rejection_code": 503}
)
def simulate_circuit_breaker(context: Dict[str, Any]) -> Dict[str, Any]:
    context["circuit_open"] = True
    context["db_committed"] = False
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="concurrent_retry_race",
    target="dispatcher.in_flight_lock",
    scenarios={"concurrent_retries": 2, "race_detected": True}
)
def simulate_concurrent_race(context: Dict[str, Any]) -> Dict[str, Any]:
    context["race_condition"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="malformed_jsonrpc_response",
    target="serializer.jsonrpc",
    scenarios={"malformed_body": True, "parse_error": True}
)
def simulate_malformed_response(context: Dict[str, Any]) -> Dict[str, Any]:
    context["parse_error"] = True
    context["db_committed"] = True
    context["transport_interrupted"] = True
    return context

@fault_inject(
    vector="policy_quarantine_rejection",
    target="firewall.policy_engine",
    scenarios={"verdict": "QUARANTINED", "rule_id": "AML_HIGH_VELOCITY"}
)
def simulate_policy_quarantine(context: Dict[str, Any]) -> Dict[str, Any]:
    context["quarantined"] = True
    context["db_committed"] = False
    return context

@fault_inject(
    vector="unauthorized_handoff",
    target="auth.token_validator",
    scenarios={"delegation_valid": False, "err": "ERR_UNAUTHORIZED_HANDOFF"}
)
def simulate_unauthorized_handoff(context: Dict[str, Any]) -> Dict[str, Any]:
    context["unauthorized"] = True
    context["db_committed"] = False
    return context

@fault_inject(
    vector="clock_skew_drift",
    target="authority.ttl_verifier",
    scenarios={"skew_seconds": 3600, "ttl_expired": True}
)
def simulate_clock_skew(context: Dict[str, Any]) -> Dict[str, Any]:
    context["skew_expired"] = True
    context["db_committed"] = False
    return context

FAULT_VECTORS = list(FAULT_REGISTRY.keys())


def derive_caid(noun_entity_id: str, verb_action: str, payload: Dict[str, Any]) -> str:
    """CAID = caid:sha256:H(Noun_EntityID || Verb_Action || RFC8785_JCS(Payload))"""
    prefix = f"{noun_entity_id}::{verb_action}::".encode("utf-8")
    preimage = prefix + encode_jcs(payload)
    return f"caid:sha256:{hashlib.sha256(preimage).hexdigest()}"


class PhysicalBankLedger:
    """Authoritative ledger simulating database state transitions."""
    def __init__(self):
        self.committed_txs: Dict[str, Dict[str, Any]] = {}
        self.balances: Dict[str, int] = {"acct_alpha": 1_000_000, "acct_beta": 500_000}
        self.mutation_counter: int = 0
        self.duplicate_mutations: int = 0
        self.idempotent_replays_rejected: int = 0

    def execute(self, idem_key: str, caid: str, account_id: str, amount: int) -> Tuple[bool, str]:
        if idem_key in self.committed_txs:
            prev = self.committed_txs[idem_key]
            if prev["caid"] == caid:
                self.idempotent_replays_rejected += 1
                return True, "IDEMPOTENT_REPLAY"
            else:
                return False, "KEY_CONFLICT"

        # Detect duplicate mutations on authoritative ledger:
        # If another transaction with the identical semantic CAID was already committed
        # under a distinct idempotency key, record duplicate mutation.
        for prev_tx in self.committed_txs.values():
            if prev_tx["caid"] == caid:
                self.duplicate_mutations += 1
                break

        if self.balances.get(account_id, 0) < amount:
            return False, "INSUFFICIENT_FUNDS"

        self.balances[account_id] -= amount
        self.mutation_counter += 1
        self.committed_txs[idem_key] = {
            "caid": caid,
            "account_id": account_id,
            "amount": amount,
            "timestamp": time.time(),
            "tx_seq": self.mutation_counter
        }
        return True, "COMMITTED"

    def probe(self, caid: str, timeout_ms: int = 3000) -> Optional[Dict[str, Any]]:
        for idem_key, tx in self.committed_txs.items():
            if tx["caid"] == caid:
                return {
                    "found": True,
                    "idem_key": idem_key,
                    "caid": caid,
                    "status": "COMMITTED",
                    "account_id": tx["account_id"],
                    "amount": tx["amount"]
                }
        return None


@dataclass
class WireResponse:
    status_code: int
    body: Optional[Dict[str, Any]] = None
    network_error: Optional[str] = None
    is_replay: bool = False

    def is_transport_failure(self) -> bool:
        return self.status_code in (504, 502, 503, 0) or self.network_error is not None

    def is_refusal(self) -> bool:
        return self.status_code in (403, 409)


@dataclass
class ProbeResponse:
    found: bool
    status: str
    idem_key: Optional[str] = None
    caid: Optional[str] = None
    error: Optional[str] = None


class SimulatedServer:
    """
    Simulates the server and network environment, encapsulating internal database
    state transitions and fault injection. Clients interact strictly via wire
    methods (dispatch, probe_state, poll_status) with zero access to internal context.
    """
    def __init__(self):
        self.ledger = PhysicalBankLedger()

    def dispatch(
        self,
        idem_key: str,
        caid: str,
        account_id: str,
        amount: int,
        fault_vector: Optional[str] = None,
        episode_id: int = 0
    ) -> WireResponse:
        ctx: Dict[str, Any] = {}
        if fault_vector:
            fault_spec = FAULT_REGISTRY.get(fault_vector)
            if fault_spec and fault_spec.handler:
                ctx = fault_spec.handler({"episode": episode_id, "vector": fault_vector})

        # 1. Gateway Policy & Auth Rejections (pre-routing)
        if ctx.get("quarantined") or ctx.get("unauthorized") or ctx.get("skew_expired"):
            return WireResponse(
                status_code=403,
                body={"error": "POLICY_REFUSED", "vector": fault_vector}
            )

        # 2. Outbox/Reconciliation Conflict
        if ctx.get("conflict_detected"):
            return WireResponse(
                status_code=409,
                body={"error": "RECONCILIATION_CONFLICT", "vector": fault_vector}
            )

        # 3. Circuit Breaker
        if ctx.get("circuit_open"):
            return WireResponse(
                status_code=503,
                network_error="CIRCUIT_BREAKER_OPEN",
                body={"error": "CIRCUIT_BREAKER_TRIP"}
            )

        # 4. Pre-commit severance (connection dropped before reaching ledger)
        if ctx.get("pre_commit_drop"):
            return WireResponse(
                status_code=504,
                network_error="PRE_COMMIT_SEVERANCE",
                body=None
            )

        # 5. Authoritative Ledger Execution
        success, outcome = self.ledger.execute(idem_key, caid, account_id, amount)
        is_replay = (outcome == "IDEMPOTENT_REPLAY")

        # 6. Post-commit transport faults
        if ctx.get("transport_interrupted"):
            if ctx.get("wire_status") == "TCP_RST":
                return WireResponse(status_code=0, network_error="TCP_RST", is_replay=is_replay)
            elif ctx.get("socket_hung"):
                return WireResponse(status_code=504, network_error="SOCKET_HANG", is_replay=is_replay)
            elif ctx.get("parse_error"):
                return WireResponse(status_code=200, network_error="MALFORMED_JSONRPC", is_replay=is_replay)
            else:
                return WireResponse(status_code=504, network_error="GATEWAY_TIMEOUT", is_replay=is_replay)

        return WireResponse(
            status_code=200 if success else 400,
            body={"status": outcome},
            is_replay=is_replay
        )

    def probe_state(self, caid: str, fault_vector: Optional[str] = None) -> ProbeResponse:
        # Simulate replica lag or probe statement timeout where read is inconclusive
        if fault_vector in ("replica_lag_stale_read", "probe_statement_timeout"):
            return ProbeResponse(found=False, status="PROBE_TIMEOUT_OR_STALE", error="LAG_OR_TIMEOUT")

        res = self.ledger.probe(caid)
        if res:
            return ProbeResponse(found=True, status=res["status"], idem_key=res["idem_key"], caid=caid)
        return ProbeResponse(found=False, status="NOT_FOUND")

    def poll_status(self, idem_key: str) -> ProbeResponse:
        if idem_key in self.ledger.committed_txs:
            tx = self.ledger.committed_txs[idem_key]
            return ProbeResponse(found=True, status="COMMITTED", idem_key=idem_key, caid=tx["caid"])
        return ProbeResponse(found=False, status="NOT_FOUND")


@dataclass
class Episode:
    episode_id: int
    fault_vector: str
    noun: str
    verb: str
    base_payload: Dict[str, Any]
    rephrased_payload: Dict[str, Any]
    has_drift: bool


def generate_500_episodes(seed: int = 42, count: int = 500, drift_probability: float = 0.628) -> List[Episode]:
    """
    Generates episodes parameterized with stochastic prompt semantic drift.
    Drift is an independent probabilistic draw per episode, yielding natural
    cross-seed variance.
    """
    rng = random.Random(seed)
    episodes = []

    nouns = ["treasury:account:acct_alpha", "custody:vault:v1", "settlement:pool:p9"]
    verbs = ["DEBIT", "TRANSFER_OUT", "ESCROW_LOCK"]

    for i in range(count):
        fault = FAULT_VECTORS[i % len(FAULT_VECTORS)]
        noun = nouns[i % len(nouns)]
        verb = verbs[i % len(verbs)]
        amount = 100 + (i * 2)

        base_payload = {
            "destination": f"iban_beneficiary_{i % 25}",
            "amount": amount,
            "currency": "EUR",
            "instruction": "Execute priority wire transfer"
        }

        # Stochastic prompt drift per episode
        has_drift = rng.random() < drift_probability
        if has_drift:
            rephrased = dict(base_payload)
            rephrased["instruction"] = "Dispatch immediate verified bank transfer to recipient"
            rephrased["client_memo"] = f"Automated agent payment batch #{i}"
        else:
            rephrased = dict(base_payload)

        episodes.append(Episode(
            episode_id=i,
            fault_vector=fault,
            noun=noun,
            verb=verb,
            base_payload=base_payload,
            rephrased_payload=rephrased,
            has_drift=has_drift
        ))

    return episodes


# ── 4 EXECUTION ARMS ─────────────────────────────────────────────────────────

def run_arm_1_naive_retry(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 1: Naive Retry Baseline — re-dispatches with new idempotency key on transport failure."""
    server = SimulatedServer()
    total = len(episodes)

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        key1 = f"naive-att1-{ep.episode_id}"

        resp1 = server.dispatch(key1, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)

        # On transport failure, naive agent blindly retries with a fresh key
        if resp1.is_transport_failure():
            key2 = f"naive-att2-{ep.episode_id}"
            server.dispatch(key2, caid, "acct_alpha", 10, None, ep.episode_id)

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "naive_retry_baseline",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "duplicate_effects": duplicate_count,
        "failure_rate_pct": failure_rate_pct,
        "status": "FAIL_DUPLICATES_OBSERVED" if duplicate_count > 0 else "PASS"
    }


def run_arm_2_payload_derived_key(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 2: Payload-Derived Key — derives key from payload; evaluates vulnerability to prompt drift."""
    server = SimulatedServer()
    total = len(episodes)

    for ep in episodes:
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        key1 = hashlib.sha256(encode_jcs(ep.base_payload)).hexdigest()

        resp1 = server.dispatch(key1, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)

        # On transport failure, agent retries:
        if resp1.is_transport_failure():
            # Under prompt drift, rephrased payload alters client-side key
            payload_to_retry = ep.rephrased_payload if ep.has_drift else ep.base_payload
            key2 = hashlib.sha256(encode_jcs(payload_to_retry)).hexdigest()
            server.dispatch(key2, caid, "acct_alpha", 10, None, ep.episode_id)

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "payload_derived_key",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "duplicate_effects": duplicate_count,
        "failure_rate_pct": failure_rate_pct,
        "status": "FAIL_DRIFT_VULNERABLE" if duplicate_count > 0 else "PASS"
    }


def run_arm_3_server_side_stable_key(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 3: Server-Side Stable Key — static session token; leaves pre-commit and policy drops unresolved."""
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
                # Key was committed; re-dispatching with stable key is deduplicated
                server.dispatch(stable_key, caid, "acct_alpha", 10, None, ep.episode_id)
            else:
                # Pre-commit drop or circuit trip: static key polling cannot resolve state
                unresolved_count += 1

    duplicate_count = server.ledger.duplicate_mutations
    failure_rate_pct = round((duplicate_count / total) * 100.0, 1)

    return {
        "arm": "server_side_stable_key",
        "total_episodes": total,
        "duplicate_mutations": duplicate_count,
        "duplicate_effects": duplicate_count,
        "unresolved_episodes": unresolved_count,
        "failure_rate_pct": failure_rate_pct,
        "status": "ZERO_DUPLICATES_UNRESOLVED_DROPS" if unresolved_count > 0 else "PASS"
    }


def run_arm_4_aeib(episodes: List[Episode]) -> Dict[str, Any]:
    """Arm 4: AEIB Protocol — Reconcile-before-retry interlock with authoritative probe and outbox anchor."""
    server = SimulatedServer()
    outbox: Dict[str, str] = {}
    blocked_by_gate = 0
    blocked_by_ledger = 0
    latencies_ms: List[float] = []
    dispositions = {
        "OUTCOME_VERIFIED": 0,
        "NOT_FOUND_AFTER_GRACE": 0,
        "RECONCILIATION_CONFLICT": 0,
        "POLICY_REFUSED": 0
    }

    for ep in episodes:
        t0 = time.perf_counter()
        caid = derive_caid(ep.noun, ep.verb, ep.base_payload)
        caid_hex = caid.split(":")[-1]
        idem_key = f"aeib-{caid_hex[:24]}"

        # 1. Stage in local outbox
        outbox[idem_key] = "DISPATCHED_UNCONFIRMED"

        # 2. Dispatch via interlock
        resp = server.dispatch(idem_key, caid, "acct_alpha", 10, ep.fault_vector, ep.episode_id)

        if resp.status_code == 403:
            dispositions["POLICY_REFUSED"] += 1
            outbox[idem_key] = "POLICY_REFUSED"
        elif resp.status_code == 409:
            dispositions["RECONCILIATION_CONFLICT"] += 1
            outbox[idem_key] = "RECONCILIATION_CONFLICT"
        elif resp.status_code == 200 and not resp.network_error:
            outbox[idem_key] = "COMMITTED"
            dispositions["OUTCOME_VERIFIED"] += 1
        elif resp.is_transport_failure():
            # 3. Transport Interruption: Reconcile-Before-Retry Interlock
            probe_res = server.probe_state(caid, ep.fault_vector)

            if probe_res.found and probe_res.status == "COMMITTED":
                # Gate catches mutation already committed -> suppress re-dispatch
                outbox[idem_key] = "COMMITTED"
                dispositions["OUTCOME_VERIFIED"] += 1
                blocked_by_gate += 1
            else:
                # Probe unconfirmed (e.g. pre-commit severance or replica lag):
                # Re-dispatch anchored to the immutable outbox idempotency key
                retry_resp = server.dispatch(idem_key, caid, "acct_alpha", 10, None, ep.episode_id)
                outbox[idem_key] = "COMMITTED"

                if retry_resp.is_replay:
                    # Inconclusive probe caught by authoritative ledger idempotency
                    blocked_by_ledger += 1
                    dispositions["OUTCOME_VERIFIED"] += 1
                else:
                    # Truly uncommitted pre-commit drop safely committed after grace
                    dispositions["NOT_FOUND_AFTER_GRACE"] += 1

        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed)

    latencies_ms.sort()
    p50_latency = latencies_ms[len(latencies_ms) // 2]
    p99_latency = latencies_ms[int(len(latencies_ms) * 0.99)]
    rule_of_three_upper_bound = (3.0 / len(episodes)) * 100.0
    duplicate_count = server.ledger.duplicate_mutations

    return {
        "arm": "aeib",
        "total_episodes": len(episodes),
        "duplicate_mutations": duplicate_count,
        "duplicate_writes": duplicate_count,
        "duplicate_attempts_blocked": blocked_by_gate + blocked_by_ledger,
        "duplicate_attempts_blocked_by_gate": blocked_by_gate,
        "duplicate_attempts_blocked_by_ledger_idempotency": blocked_by_ledger,
        "duplicate_effects": duplicate_count,
        "failure_rate_pct": round((duplicate_count / len(episodes)) * 100.0, 1),
        "rule_of_three_95_upper_bound_pct": round(rule_of_three_upper_bound, 2),
        "latency_p50_ms": round(p50_latency, 2),
        "latency_p99_ms": round(p99_latency, 2),
        "disposition_counts": dispositions,
        "status": "PASS_ZERO_DUPLICATES" if duplicate_count == 0 else "FAIL"
    }


def run_all_episodes(seed: int = 42, count: int = 500) -> Dict[str, Any]:
    print("=" * 80)
    print(f"AEIB TIER 1 BASELINE HARNESS: {count} EPISODES / {len(FAULT_VECTORS)} FAULT VECTORS / 4 ARMS")
    print(f"[*] Configuration: seed={seed}, vectors={len(FAULT_VECTORS)}, episodes={count}")
    print("=" * 80)

    episodes = generate_500_episodes(seed=seed, count=count)

    print("\n[+] Running Arm 1: Naive Retry Baseline...")
    r1 = run_arm_1_naive_retry(episodes)
    print(f"    -> Duplicates: {r1['duplicate_mutations']}/{count} ({r1['failure_rate_pct']}%)")

    print("\n[+] Running Arm 2: Payload-Derived Key (Stochastic Prompt Drift)...")
    r2 = run_arm_2_payload_derived_key(episodes)
    print(f"    -> Duplicates: {r2['duplicate_mutations']}/{count} ({r2['failure_rate_pct']}%)")

    print("\n[+] Running Arm 3: Server-Side Stable Key...")
    r3 = run_arm_3_server_side_stable_key(episodes)
    print(f"    -> Duplicates: {r3['duplicate_mutations']}/{count} | Unresolved: {r3['unresolved_episodes']}")

    print("\n[+] Running Arm 4: AEIB Protocol (Deterministic Staging + CAID + Probe)...")
    r4 = run_arm_4_aeib(episodes)
    print(f"    -> Duplicates: {r4['duplicate_mutations']}/{count} ({r4['failure_rate_pct']}%)")
    print(f"    -> Rule-of-Three 95% Upper Bound: ~{r4['rule_of_three_95_upper_bound_pct']}%")

    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": seed,
        "total_episodes": count,
        "fault_vector_count": len(FAULT_VECTORS),
        "results": {
            "naive_retry_baseline": r1,
            "payload_derived_key": r2,
            "server_side_stable_key": r3,
            "aeib": r4
        }
    }

    # Verify behavioral invariants without fixed tautological outputs
    assert r1["duplicate_mutations"] > 0, "Arm 1 must exhibit duplicate mutations from post-commit drops"
    assert r2["duplicate_mutations"] > 0, "Arm 2 must exhibit duplicate mutations under semantic prompt drift"
    assert r3["duplicate_mutations"] == 0, "Arm 3 must exhibit 0 duplicate mutations"
    assert r3["unresolved_episodes"] > 0, "Arm 3 must exhibit unresolved drops under pre-commit and policy failures"
    assert r4["duplicate_mutations"] == 0, "Arm 4 (AEIB) must exhibit 0 duplicate mutations"
    assert r4["failure_rate_pct"] == 0.0, "Arm 4 (AEIB) must achieve 0.0% failure rate"

    return report


def main():
    parser = argparse.ArgumentParser(description="AEIB Execution Integrity Benchmark Runner")
    parser.add_argument("--episodes", type=int, default=500, help="Number of episodes (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--output", "--report", type=str, default="results_v0.2.4.json", help="Output JSON path")
    args = parser.parse_args()

    rep = run_all_episodes(seed=args.seed, count=args.episodes)
    r1 = rep["results"]["naive_retry_baseline"]
    r2 = rep["results"]["payload_derived_key"]
    r3 = rep["results"]["server_side_stable_key"]
    r4 = rep["results"]["aeib"]
    count = args.episodes

    print(f"\nARM 1 (Naive Retry)      : {r1['failure_rate_pct']:.1f}% Duplicates ({r1['duplicate_mutations']}/{count})")
    print(f"ARM 2 (Semantic Drift)   : {r2['failure_rate_pct']:.1f}% Duplicates ({r2['duplicate_mutations']}/{count})")
    print(f"ARM 3 (Server Stable)    : {r3['failure_rate_pct']:.1f}% Duplicates ({r3['duplicate_mutations']}/{count}) | {r3['unresolved_episodes']} Unresolved Drops")
    print(f"ARM 4 (AEIB Protocol)    : {r4['duplicate_writes']} duplicate writes / {count} | {r4['duplicate_attempts_blocked']} duplicate retry attempts blocked (gate={r4['duplicate_attempts_blocked_by_gate']}, ledger={r4['duplicate_attempts_blocked_by_ledger_idempotency']}) | Upper Bound <= {r4['rule_of_three_95_upper_bound_pct']:.2f}% (95% CI, deterministic simulation)")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    if out_path.name != "benchmark_results.json":
        Path("benchmark_results.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(f"\n[OK] {args.episodes}-Episode Benchmark complete. Report written to {out_path} and benchmark_results.json")


if __name__ == "__main__":
    main()
