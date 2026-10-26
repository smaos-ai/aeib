#!/usr/bin/env python3
"""
benchmarks/cascade_router_sim.py — Seeded SYNTHETIC simulation of routing policies.

All task-distribution parameters below are `# claim: assumption` inputs, NOT measurements
of any real model. The output demonstrates policy mechanics (cost per verified change,
false-accept rate) under those assumptions only. Replace with a ledger built from real
oracle runs on your repository before drawing conclusions.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.accuracy_cascade_router import (  # noqa: E402
    AccuracyCascadeRouter,
    CodingTask,
    LedgerEntry,
    RoutingLedger,
)

# claim: assumption — hypothetical per-cluster true pass probabilities and costs
CLUSTERS = {
    "simple_cleanup": {"cheap": 0.95, "strong": 0.97, "tier": "T1"},
    "bugfix": {"cheap": 0.70, "strong": 0.85, "tier": "T1"},
    "multi_file_refactor": {"cheap": 0.55, "strong": 0.80, "tier": "T2"},
    "payment_change": {"cheap": 0.60, "strong": 0.82, "tier": "T3"},
}
COST = {"cheap": 0.40, "strong": 2.00}  # claim: assumption (USD per attempt)
ORACLE_MISS = 0.02  # claim: assumption — P(oracle passes a wrong patch)
REPAIR_COST_FRACTION = 0.3  # claim: assumption — slice-only escalation cost vs full


def attempt(rng, p_true):
    correct = rng.random() < p_true
    oracle_pass = correct or (rng.random() < ORACLE_MISS)
    return correct, oracle_pass


def run(policy, episodes, seed):
    rng = random.Random(seed)
    ledger = RoutingLedger()
    router = AccuracyCascadeRouter(
        ledger, "cheap", "strong", accuracy_floor=0.85, min_samples=30, exploration_bps=2000
    )
    cost = verified = accepted_wrong = unresolved = 0.0
    names = list(CLUSTERS)
    for i in range(episodes):
        c = rng.choice(names)
        spec = CLUSTERS[c]
        task = CodingTask(f"ep{i}", c, spec["tier"], False, COST)
        if policy == "always_cheap":
            first = "cheap"
        elif policy == "always_strong":
            first = "strong"
        else:
            first = router.route(task).model
        correct, ok = attempt(rng, spec[first])
        cost += COST[first]
        ledger.record(LedgerEntry(c, first, ok, ok and not correct, COST[first], 0))
        if not ok:
            # Fair comparison: every policy gets bounded slice-only repair (B <= 3).
            # Cascade escalates to strong; fixed policies repair with their own model.
            repair_model = "strong" if policy == "oracle_cascade" else first
            for _a in range(3):
                cost += COST[repair_model] * REPAIR_COST_FRACTION
                correct, ok = attempt(rng, spec[repair_model])
                if ok:
                    break
        if ok:
            verified += int(correct)
            accepted_wrong += int(not correct)
        else:
            unresolved += 1
    return {
        "policy": policy,
        "episodes": episodes,
        "verified_correct_bps": int(verified * 10000 // episodes),
        "accepted_wrong_bps": int(accepted_wrong * 10000 // episodes),
        "unresolved_bps": int(unresolved * 10000 // episodes),
        "cost_per_verified_change_usd": round(cost / verified, 4) if verified else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rows = [run(p, a.episodes, a.seed) for p in ("always_cheap", "always_strong", "oracle_cascade")]
    print("SYNTHETIC SIMULATION — parameters are assumptions, not measured model accuracy")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
