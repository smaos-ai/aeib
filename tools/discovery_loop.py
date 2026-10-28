#!/usr/bin/env python3
"""Covering design discovery loop (prototype).

Pipeline per target C(v,k,t):
  1. Look up the pinned LJCR baseline (published size and lower bound).
  2. Proposers generate untrusted candidates at a fixed block budget:
       - CoveringDesignSearch.java explicit (simulated annealing, ForkJoinPool)
       - CoveringDesignSearch.java cyclic   (Z_v orbit template, ForkJoinPool)
       - optional --candidate-files: JSON candidates written by an LLM or a
         human (file-based ingestion keeps this module free of network egress)
  3. Every candidate is re-checked by tools/covering_design_verifier.py.
  4. Valid candidates are compared against the pinned baseline.
  5. Witnesses are exported with canonical digests and a reproduction command.

Budgets tried per target: the published size (reproduction calibration) and
published size minus one (improvement attempt) for the explicit proposer, and
the largest m*v below the published size for the cyclic proposer.
An attempt that yields no candidate within its time limit is recorded as
NO_CANDIDATE_WITHIN_BUDGET. That is a bounded negative result, not a proof of
non-existence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from covering_design_record_comparator import PinnedBaseline, compare  # noqa: E402
from covering_design_verifier import canonical_bytes, canonical_witness, verify  # noqa: E402
from src.jcs_canonicalizer import encode_jcs  # noqa: E402

ENGINE = ROOT / "experiments" / "covering_design" / "CoveringDesignSearch.java"


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_engine(java: str, mode: str, v: int, k: int, t: int, budget: int,
               seeds: int, seconds: float, seed0: int) -> tuple[list[dict[str, Any]], float]:
    cmd = [java, "-Xmx2g", str(ENGINE), mode, str(v), str(k), str(t), str(budget),
           str(seeds), str(seconds), str(seed0)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds * 4 + 120, check=False)
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"engine failed ({proc.returncode}): {proc.stderr[-2000:]}")
    out = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    return out, wall


def to_candidate(raw: dict[str, Any], mode: str) -> dict[str, Any]:
    v, k, t = raw["v"], raw["k"], raw["t"]
    cw = canonical_witness(v, k, t, raw["blocks"])
    return {
        "candidate_id": "sha256:" + hashlib.sha256(canonical_bytes(cw)).hexdigest(),
        "problem": "COVERING_DESIGN",
        "parameters": {"v": v, "k": k, "t": t},
        "construction_type": "CYCLIC_ORBITS_Z_V" if mode == "cyclic" else "EXPLICIT_BLOCKS",
        "blocks": cw["blocks"],
        "claimed_objective": {"metric": "block_count", "value": len(cw["blocks"])},
        "proposer": {"name": raw.get("proposer", f"CoveringDesignSearch.{mode}"), "seed": raw.get("seed"),
                     "moves": raw.get("moves"), "seconds": raw.get("seconds")},
    }


def process_candidate(cand: dict[str, Any], baseline: PinnedBaseline, out_dir: Path,
                      seen: set[str], metrics: dict[str, int]) -> dict[str, Any]:
    metrics["candidates_generated"] += 1
    p = cand["parameters"]
    ver = verify(p["v"], p["k"], p["t"], cand["blocks"], cand["claimed_objective"]["value"])
    if not ver["valid"]:
        metrics["verifier_rejections"] += 1
        return {"candidate_id": cand.get("candidate_id"), "verification": ver, "label": "INVALID_CANDIDATE"}
    metrics["candidates_valid"] += 1
    cw = canonical_witness(p["v"], p["k"], p["t"], cand["blocks"])
    if canonical_bytes(cw) != encode_jcs(cw):
        raise RuntimeError("canonical form disagrees with RFC 8785 encoder")
    digest = ver["witness_digest"]
    if digest in seen:
        metrics["candidates_deduplicated"] += 1
    seen.add(digest)
    cmp_res = compare(ver, baseline)
    label = cmp_res["label"]
    if label == "REPRODUCED_KNOWN_RESULT":
        metrics["known_records_reproduced"] += 1
    elif label == "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW":
        metrics["strict_improvements_found"] += 1
    elif label == "CONTRADICTS_PUBLISHED_LOWER_BOUND":
        metrics["false_improvement_claims_rejected"] += 1
    wdir = out_dir / "witnesses"
    wdir.mkdir(parents=True, exist_ok=True)
    wname = f"C{p['v']}_{p['k']}_{p['t']}_b{ver['block_count']}_{digest[7:19]}.json"
    wpath = wdir / wname
    wpath.write_text(json.dumps({**cand, "witness_digest": digest}, sort_keys=True, indent=1), encoding="utf-8")
    if label == "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW":
        metrics["human_review_queue"] += 1
    return {
        "candidate_id": cand["candidate_id"],
        "label": label,
        "block_count": ver["block_count"],
        "delta_vs_record": cmp_res.get("delta_vs_record"),
        "witness_file": str(wpath.relative_to(ROOT)),
        "witness_digest": digest,
        "verification": {k: ver[k] for k in ("status", "checks_passed", "checks_failed",
                                                 "t_subsets_total", "schoenheim_lower_bound")},
        "reproduction_command": f"python3 tools/covering_design_verifier.py --input {wpath.relative_to(ROOT)}",
        "status": "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW" if label.startswith("CANDIDATE") else label,
    }


def parse_targets(args: argparse.Namespace) -> list[tuple[int, int, int]]:
    targets = []
    if args.parameters:
        p = json.loads(args.parameters)
        targets.append((int(p["v"]), int(p["k"]), int(p["t"])))
    for spec in args.targets or []:
        v, k, t = (int(x) for x in spec.split(","))
        targets.append((v, k, t))
    return targets


def main() -> int:
    ap = argparse.ArgumentParser(description="Covering design discovery loop")
    ap.add_argument("--problem", default="covering_design", choices=["covering_design"])
    ap.add_argument("--parameters", help='JSON like {"v":13,"k":6,"t":4}')
    ap.add_argument("--targets", nargs="*", help="space-separated v,k,t triples")
    ap.add_argument("--modes", default="explicit,cyclic")
    ap.add_argument("--seeds", type=int, default=11)
    ap.add_argument("--seconds", type=float, default=30.0, help="time limit per (target, budget, mode)")
    ap.add_argument("--seed", type=int, default=20261023)
    ap.add_argument("--candidate-files", nargs="*", default=[], help="externally proposed candidate JSON files")
    ap.add_argument("--output", required=True)
    ap.add_argument("--java", default="java")
    args = ap.parse_args()

    out_dir = Path(args.output)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline = PinnedBaseline()
    if not baseline.pinned:
        print(json.dumps({"label": "BASELINE_UNPINNED", "baseline": baseline.provenance()}, indent=2))
        return 2

    metrics = {k: 0 for k in ("candidates_generated", "candidates_valid", "candidates_deduplicated",
                              "known_records_reproduced", "strict_improvements_found",
                              "false_improvement_claims_rejected", "verifier_rejections",
                              "human_review_queue", "attempts", "attempts_without_candidate")}
    seen: set[str] = set()
    attempts: list[dict[str, Any]] = []
    t_start = time.perf_counter()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    for v, k, t in parse_targets(args):
        entry = baseline.entry(v, k, t)
        if entry is None:
            attempts.append({"target": f"C({v},{k},{t})", "label": "ENTRY_NOT_IN_BASELINE"})
            continue
        rec, lb = entry["published_size"], entry["published_lower_bound"]
        plan: list[tuple[str, int, int, str]] = []
        if "explicit" in modes:
            plan.append(("explicit", rec, rec, "reproduce_record"))
            if rec - 1 >= lb:
                plan.append(("explicit", rec - 1, rec - 1, "strict_improvement_attempt"))
        if "cyclic" in modes:
            m = (rec - 1) // v
            if m >= 1 and m * v >= lb:
                plan.append(("cyclic", m, m * v, "strict_improvement_attempt"))
        for mode, budget, blocks_max, purpose in plan:
            metrics["attempts"] += 1
            raws, wall = run_engine(args.java, mode, v, k, t, budget, args.seeds, args.seconds, args.seed)
            results = [process_candidate(to_candidate(r, mode), baseline, out_dir, seen, metrics) for r in raws]
            if not raws:
                metrics["attempts_without_candidate"] += 1
            attempts.append({
                "target": entry["table_entry"], "published_size": rec, "published_lower_bound": lb,
                "last_improvement": entry["last_improvement"], "mode": mode, "purpose": purpose,
                "budget_param": budget, "max_blocks": blocks_max, "seeds": args.seeds,
                "time_limit_s": args.seconds, "wall_s": round(wall, 2),
                "outcome": results[0]["label"] if results else "NO_CANDIDATE_WITHIN_BUDGET",
                "results": results,
            })
            print(f"[{entry['table_entry']}] {mode:8s} budget={blocks_max:4d} ({purpose}) -> "
                  f"{attempts[-1]['outcome']} in {wall:.1f}s", flush=True)

    for f in args.candidate_files:
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        res = process_candidate(doc, baseline, out_dir, seen, metrics)
        attempts.append({"target": f"C({doc['parameters']['v']},{doc['parameters']['k']},{doc['parameters']['t']})",
                         "mode": "file", "source_file": f, "outcome": res["label"], "results": [res]})

    summary = {
        "run": {"seed": args.seed, "seeds_per_attempt": args.seeds, "time_limit_s": args.seconds,
                "modes": modes, "wall_s": round(time.perf_counter() - t_start, 2)},
        "engine": {"file": str(ENGINE.relative_to(ROOT)), "digest": sha256_file(ENGINE)},
        "verifier": {"file": "tools/covering_design_verifier.py",
                     "digest": sha256_file(ROOT / "tools" / "covering_design_verifier.py")},
        "baseline": baseline.provenance(),
        "metrics": metrics,
        "attempts": attempts,
        "claim_policy": "No result is a new record until a human confirms it against the maintainer's current data.",
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
