#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
benchmarks/run_10k_dst_protocol_suite.py — 10,000-Schedule Protocol-Aware DST Benchmark

Implements Item 11 of the AEIB 12-item master delivery scope:
Protocol-aware PRNG fault simulation (seed 20261020) driving the real
HardenedIdempotentMcpProxy against a simulated downstream target.
Evaluates 0 duplicate mutations on the target under transport drops,
HTTP 504 timeouts, and blind retry attempts.
"""

import argparse
import json
import os
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.mcp.idempotent_mcp_proxy import HardenedIdempotentMcpProxy


class SimulatedDownstreamTarget:
    """Downstream financial / API target maintaining authoritative commit counts."""

    def __init__(self) -> None:
        self.commits: Dict[str, int] = {}
        self.call_history: List[Dict[str, Any]] = []

    def execute_mutation(self, idempotency_key: str, amount_minor: int) -> bool:
        self.commits[idempotency_key] = self.commits.get(idempotency_key, 0) + 1
        self.call_history.append({"amount": amount_minor, "key": idempotency_key})
        return True


def run_10k_dst_benchmark(
    num_schedules: int = 10000,
    seed: int = 20261020,
    output_json: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the protocol-aware deterministic simulation suite across N schedules.
    """
    rng = random.Random(seed)
    target = SimulatedDownstreamTarget()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "proxy_dst_10k.db"

        # Scheduled fault generator
        fault_schedule: Dict[str, str] = {}

        def upstream_transport(req: Dict[str, Any]) -> Dict[str, Any]:
            params = req.get("params", {})
            k = params.get("idempotency_key", "")
            amt = params.get("arguments", {}).get("amount_minor", 1000)

            f_type = fault_schedule.get(k, "NOMINAL_SUCCESS")

            if f_type == "NOMINAL_SUCCESS":
                target.execute_mutation(k, amt)
                return {"result": {"content": [{"type": "text", "text": "Settled"}], "isError": False}}
            elif f_type == "POST_COMMIT_LOST_ACK":
                # Target received mutation, but gateway timeout returned
                target.execute_mutation(k, amt)
                return {"error": {"code": 504, "message": "Gateway Timeout"}}
            elif f_type == "PRE_COMMIT_DROP":
                # Connection dropped before reaching target
                return {"error": {"code": 502, "message": "Bad Gateway / Connection Dropped"}}
            else:
                target.execute_mutation(k, amt)
                return {"result": {"content": [{"type": "text", "text": "OK"}], "isError": False}}

        proxy = HardenedIdempotentMcpProxy(db_path=db_path, upstream_transport_fn=upstream_transport)

        dispatched_count = 0
        indeterminate_latched_count = 0
        blocked_blind_retries = 0
        nominal_successes = 0

        # We generate distinct operation IDs, each repeated across 2-3 schedules to test retries
        for schedule_idx in range(num_schedules):
            op_idx = schedule_idx // 2
            key_id = f"op_batch_{op_idx}"
            amount = 1000 + (op_idx % 500)

            # Assign fault profile for this operation on its first appearance
            if key_id not in fault_schedule:
                fault_schedule[key_id] = rng.choice([
                    "NOMINAL_SUCCESS",
                    "POST_COMMIT_LOST_ACK",
                    "PRE_COMMIT_DROP",
                ])

            frame = {
                "jsonrpc": "2.0",
                "id": f"req-{schedule_idx}",
                "method": "tools/call",
                "params": {
                    "name": "disburse_funds",
                    "idempotency_key": key_id,
                    "operation_id": key_id,
                    "arguments": {
                        "amount_minor": amount,
                        "recipient": f"DE8937040044053201{op_idx:04d}",
                    },
                },
            }

            resp = proxy.handle_json_rpc(frame)
            dispatched_count += 1

            if "result" in resp:
                nominal_successes += 1
            elif "error" in resp:
                err = resp["error"]
                msg = err.get("message", "")
                if "HALT_BLIND_RETRY" in msg:
                    blocked_blind_retries += 1
                elif err.get("code") in (504, 502, -32021) or "Timeout" in msg or "EFFECT_INDETERMINATE" in msg:
                    indeterminate_latched_count += 1

        proxy.close()

        # Evaluate invariants: target commits per key must be <= 1
        duplicate_mutations = 0
        for k, count in target.commits.items():
            if count > 1:
                duplicate_mutations += (count - 1)

        result = {
            "blind_retries_blocked": blocked_blind_retries,
            "dispatches_attempted": dispatched_count,
            "duplicate_mutations_observed": duplicate_mutations,
            "failure_rate_percent": (duplicate_mutations / max(dispatched_count, 1)) * 100.0,
            "indeterminate_latches_engaged": indeterminate_latched_count,
            "invariant_verdict": "PASSED" if duplicate_mutations == 0 else "FAILED",
            "nominal_successes": nominal_successes,
            "schedules_evaluated": num_schedules,
            "seed": seed,
        }

        if output_json:
            p = Path(output_json)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEIB 10,000-Schedule Protocol-Aware DST Suite")
    parser.add_argument("--schedules", type=int, default=10000, help="Number of schedules to simulate")
    parser.add_argument("--seed", type=int, default=20261020, help="PRNG random seed")
    parser.add_argument("--output-json", type=str, default="evidence/dst_10k_benchmark_results.json")
    args = parser.parse_args()

    res = run_10k_dst_benchmark(num_schedules=args.schedules, seed=args.seed, output_json=args.output_json)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["duplicate_mutations_observed"] == 0 else 1)
