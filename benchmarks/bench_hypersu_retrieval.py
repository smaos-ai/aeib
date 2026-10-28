#!/usr/bin/env python3
"""
benchmarks/bench_hypersu_retrieval.py — Empirical Benchmark for HyperSU FTS5 vs SQL LIKE.

Measures real p50 / p95 / p99 retrieval latency, ingestion throughput, on-disk SQLite
index size (MB), Recall@10, Precision@10, and provenance validity across configurable
corpus sizes (`--sizes 100 1000 10000 --queries 200 --output reports/hypersu-benchmark.json`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.hypersu_fts import HyperSUFTSRetriever
from src.hypersu_store import (
    FactRecord,
    HyperedgeEvidenceSpan,
    HyperedgeMember,
    HyperSUStore,
)

_VOCAB = (
    "interlock",
    "ledger",
    "durability",
    "quorum",
    "reconcile",
    "escrow",
    "merkle",
    "canonical",
    "idempotency",
    "transport",
    "timeout",
    "barrier",
    "semaphore",
    "checkpoint",
    "journal",
    "monotonic",
    "attestation",
    "signature",
    "digest",
    "warrant",
    "envelope",
    "boundary",
    "isolation",
    "validator",
    "auditor",
    "verifier",
    "sequence",
    "counterexample",
    "invariant",
    "transition",
    "snapshot",
    "recovery",
)

_ADVERSARIAL_QUERIES = (
    "",
    "   ",
    "%",
    "_",
    "%%__%%",
    '"unclosed quote',
    "AND OR NOT NEAR",
    "label:secret ^ * : - +",
    "((( )))",
    "'; DROP TABLE facts; --",
)


def percentile(sorted_vals: Sequence[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(
        len(sorted_vals) - 1,
        max(0, int(math.ceil((pct / 100.0) * len(sorted_vals))) - 1),
    )
    return round(sorted_vals[idx], 4)


def run_corpus_size_benchmark(
    corpus_size: int,
    num_queries: int,
    seed: int = 42,
) -> Dict[str, Any]:
    rng = random.Random(seed + corpus_size)

    with tempfile.TemporaryDirectory(prefix=f"hypersu_bench_{corpus_size}_") as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "hypersu_bench.sqlite"
        source_dir = tmp_path / "corpus"
        source_dir.mkdir(parents=True, exist_ok=True)

        # Create real backing source files on disk so provenance checks are genuine
        num_files = min(20, max(5, corpus_size // 100))
        file_chunks: Dict[int, List[str]] = {i: [] for i in range(num_files)}
        raw_fact_specs: List[Dict[str, Any]] = []

        # Plant 20 needle tokens with known ground-truth fact IDs (5 facts per needle token)
        needle_tokens = [f"needle_token_{k:02d}" for k in range(20)]
        ground_truth: Dict[str, List[str]] = {tok: [] for tok in needle_tokens}

        for i in range(corpus_size):
            file_idx = i % num_files
            words = [rng.choice(_VOCAB) for _ in range(18)]
            if i < 100:
                needle = needle_tokens[i % len(needle_tokens)]
                words[5] = needle
                words[10] = f"phrase_anchor_{i % len(needle_tokens):02d}"
                ground_truth[needle].append(f"fact-{i:06d}")

            line_text = f"fact_{i:06d}: " + " ".join(words) + "\n"
            raw_fact_specs.append(
                {
                    "fact_id": f"fact-{i:06d}",
                    "file_idx": file_idx,
                    "label": f"Fact unit {i:06d}",
                    "text": line_text,
                }
            )
            file_chunks[file_idx].append(line_text)

        file_hashes: Dict[int, str] = {}
        file_rel_paths: Dict[int, str] = {}
        for f_idx, lines in file_chunks.items():
            rel = f"corpus/doc_{f_idx:03d}.txt"
            full_text = "".join(lines)
            p = tmp_path / rel
            p.write_text(full_text, encoding="utf-8")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            file_hashes[f_idx] = f"sha256:{digest}"
            file_rel_paths[f_idx] = rel

        # Compute exact [start_char, end_char] offsets within each backing file
        file_cursors: Dict[int, int] = {i: 0 for i in range(num_files)}
        facts_to_insert: List[FactRecord] = []
        for spec in raw_fact_specs:
            f_idx = spec["file_idx"]
            start_c = file_cursors[f_idx]
            txt = spec["text"]
            end_c = start_c + len(txt)
            file_cursors[f_idx] = end_c
            rel = file_rel_paths[f_idx]
            facts_to_insert.append(
                FactRecord(
                    fact_id=spec["fact_id"],
                    episode_id=f"ep:{rel}",
                    label=spec["label"],
                    text=txt,
                    source_id=f"src:{rel}",
                    file_path=rel,
                    start_char=start_c,
                    end_char=end_c,
                    content_sha256=file_hashes[f_idx],
                )
            )

        store = HyperSUStore(db_path)
        t_ingest_0 = time.perf_counter()
        store.add_facts_batch(facts_to_insert)

        # Also add 10 variable-cardinality hyperedges (each linking 5 needle facts)
        for h_idx in range(10):
            needle = needle_tokens[h_idx]
            member_fact_ids = ground_truth[needle]
            members = [
                HyperedgeMember("FACT", f_id, role="supporting_fact")
                for f_id in member_fact_ids
            ]
            ev_spans = []
            for f_id in member_fact_ids:
                f_rec = facts_to_insert[int(f_id.split("-")[1])]
                ev_spans.append(
                    HyperedgeEvidenceSpan(
                        fact_id=f_rec.fact_id,
                        source_id=f_rec.source_id,
                        file_path=f_rec.file_path,
                        start_char=f_rec.start_char,
                        end_char=f_rec.end_char,
                        content_sha256=f_rec.content_sha256,
                    )
                )
            store.add_hyperedge(
                hyperedge_id=f"he-needle-{h_idx:02d}",
                relation="JOINTLY_SUPPORTS",
                members=members,
                evidence=ev_spans,
            )

        ingestion_time_s = round(time.perf_counter() - t_ingest_0, 4)
        sync_ok = store.check_fts_sync_integrity()
        index_size_mb = round(db_path.stat().st_size / (1024.0 * 1024.0), 4)

        retriever = HyperSUFTSRetriever(store, workspace_root=tmp_path)

        # Build query mix across all 6 required query types
        query_plan: List[ tuple[str, str, str] ] = []
        for q_i in range(num_queries):
            q_mod = q_i % 6
            needle = needle_tokens[q_i % len(needle_tokens)]
            anchor = f"phrase_anchor_{q_i % len(needle_tokens):02d}"
            if q_mod == 0:
                query_plan.append(("single_term", needle, "or"))
            elif q_mod == 1:
                query_plan.append(("multi_term", f"{needle} {anchor}", "and"))
            elif q_mod == 2:
                query_plan.append(("phrase", f"{needle} {anchor}", "phrase"))
            elif q_mod == 3:
                query_plan.append(
                    ("wildcard_or_special_characters", f"%_{needle}_%", "or")
                )
            elif q_mod == 4:
                query_plan.append(("empty_query", "", "or"))
            else:
                adv = _ADVERSARIAL_QUERIES[q_i % len(_ADVERSARIAL_QUERIES)]
                query_plan.append(("adversarial_fts_syntax", adv, "or"))

        fts_latencies_ms: List[float] = []
        like_latencies_ms: List[float] = []
        per_type_fts_ms: Dict[str, List[float]] = {}

        for q_type, q_str, q_mode in query_plan:
            t0 = time.perf_counter()
            _ = retriever.coarse_to_fine_retrieve(q_str, limit=10, mode=q_mode)
            dt_fts = (time.perf_counter() - t0) * 1000.0
            fts_latencies_ms.append(dt_fts)
            per_type_fts_ms.setdefault(q_type, []).append(dt_fts)

            t1 = time.perf_counter()
            _ = retriever.like_scan_retrieve(q_str, limit=10)
            dt_like = (time.perf_counter() - t1) * 1000.0
            like_latencies_ms.append(dt_like)

        # Evaluate Recall@10, Precision@10, and Provenance Validity on the 20 needle queries
        recalls: List[float] = []
        precisions: List[float] = []
        prov_valid_hits = 0
        prov_total_hits = 0

        for needle, expected_ids in ground_truth.items():
            hits = retriever.coarse_to_fine_retrieve(
                needle, limit=10, mode="or", verify_provenance=True
            )
            returned_ids = [h["fact_id"] for h in hits]
            expected_set = set(expected_ids)
            tp = len(expected_set.intersection(returned_ids))
            recalls.append(tp / float(len(expected_set)))
            precisions.append(
                tp / float(len(returned_ids)) if returned_ids else 0.0
            )
            for h in hits:
                prov_total_hits += 1
                if h.get("provenance_valid"):
                    prov_valid_hits += 1

        fts_sorted = sorted(fts_latencies_ms)
        like_sorted = sorted(like_latencies_ms)

        type_summary = {
            k: {
                "count": len(v),
                "p50_ms": percentile(sorted(v), 50),
                "p95_ms": percentile(sorted(v), 95),
            }
            for k, v in sorted(per_type_fts_ms.items())
        }

        store.close()
        return {
            "corpus_size": corpus_size,
            "queries_executed": num_queries,
            "ingestion_time_s": ingestion_time_s,
            "index_size_mb": index_size_mb,
            "fts_sync_integrity_ok": sync_ok,
            "fts5_latency_ms": {
                "p50_latency_ms": percentile(fts_sorted, 50),
                "p95_latency_ms": percentile(fts_sorted, 95),
                "p99_latency_ms": percentile(fts_sorted, 99),
            },
            "like_scan_latency_ms": {
                "p50_latency_ms": percentile(like_sorted, 50),
                "p95_latency_ms": percentile(like_sorted, 95),
                "p99_latency_ms": percentile(like_sorted, 99),
            },
            "speedup_p95_x": round(
                percentile(like_sorted, 95)
                / max(0.0001, percentile(fts_sorted, 95)),
                2,
            ),
            "recall_at_10": round(sum(recalls) / len(recalls), 4),
            "precision_at_10": round(sum(precisions) / len(precisions), 4),
            "provenance_validity_rate": round(
                prov_valid_hits / float(max(1, prov_total_hits)), 4
            ),
            "by_query_type": type_summary,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark HyperSU SQLite FTS5 vs LIKE retrieval"
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[100, 1000, 10000],
        help="Corpus sizes (number of facts) to benchmark",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=200,
        help="Number of queries to run per corpus size",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/hypersu-benchmark.json",
        help="Output JSON report path",
    )
    args = parser.parse_args()

    results = [
        run_corpus_size_benchmark(sz, args.queries) for sz in args.sizes
    ]
    report = {
        "benchmark": "hypersu_fts5_vs_like_retrieval",
        "queries_per_size": args.queries,
        "sizes": args.sizes,
        "results": results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
