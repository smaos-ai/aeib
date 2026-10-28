#!/usr/bin/env python3
"""
src/hypersu_fts.py — Safe SQLite FTS5 Lexical Retriever with Query Sanitization & Provenance Check.

Implements the deterministic lexical retrieval layer over `HyperSUStore`:
  1. `sanitize_fts5_query`: Escapes FTS5 operators (`AND`, `OR`, `NOT`, `NEAR`),
     column filters (`col:term`), wildcards (`*`, `^`, `%`, `_`), quotes (`"`),
     and unbalanced parentheses so adversarial user input never causes an
     `sqlite3.OperationalError: fts5: syntax error`.
  2. `HyperSUFTSRetriever.coarse_to_fine_retrieve`: Executes parameterized
     `fact_fts MATCH ?` with BM25 ranking (`bm25(fact_fts)`), joins back to
     `facts`, and optionally attaches incident n-ary hyperedges and verifies
     on-disk source-span provenance.
  3. `HyperSUFTSRetriever.like_scan_retrieve`: Provides the baseline SQL `LIKE`
     substring scan (with `ESCAPE '\\'` for `%` and `_`) for head-to-head
     latency benchmarking against FTS5.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.hypersu_store import HyperSUStore

# Extracts safe alphanumeric/underscore tokens so FTS5 syntax characters are never interpreted as operators
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def sanitize_fts5_query(user_query: str, mode: str = "or") -> str:
    """
    Converts raw user input into a safe FTS5 `MATCH` expression.

    - Extracts alphanumeric/underscore lexical tokens and wraps each token in
      double quotes (`"token"`) with internal quotes doubled (`""`).
    - Prevents FTS5 reserved keywords (`AND`, `OR`, `NOT`, `NEAR`), column filters
      (`label:foo`), prefix wildcards (`*`, `^`), and punctuation (`"`, `(`, `)`,
      `:`, `-`, `%`, `_`) from triggering `fts5: syntax error`.
    - Returns `""` if no indexable lexical token is present.
    """
    if not user_query or not isinstance(user_query, str):
        return ""

    raw_tokens = [
        t for t in _SAFE_TOKEN_RE.findall(user_query) if any(ch.isalnum() for ch in t)
    ]
    if not raw_tokens:
        return ""

    if mode == "phrase":
        joined = " ".join(t.replace('"', '""') for t in raw_tokens)
        return f'"{joined}"'

    joiner = " AND " if mode == "and" else " OR "
    quoted_tokens: List[str] = []
    seen: set[str] = set()
    for tok in raw_tokens:
        lower = tok.lower()
        if lower in seen:
            continue
        seen.add(lower)
        cleaned = tok.replace('"', '""')
        quoted_tokens.append(f'"{cleaned}"')

    return joiner.join(quoted_tokens)


def escape_like_pattern(user_query: str) -> str:
    """Escapes `\\`, `%`, and `_` for safe `LIKE ? ESCAPE '\\'` baseline comparisons."""
    return (
        user_query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


class HyperSUFTSRetriever:
    """Indexed SQLite FTS5 retriever with BM25 ranking over `HyperSUStore`."""

    def __init__(
        self,
        store: HyperSUStore,
        workspace_root: Optional[Path] = None,
    ) -> None:
        self.store = store
        self.workspace_root = workspace_root

    @staticmethod
    def _fts_query(user_query: str, mode: str = "or") -> str:
        return sanitize_fts5_query(user_query, mode=mode)

    def coarse_to_fine_retrieve(
        self,
        query: str,
        limit: int = 10,
        mode: str = "or",
        verify_provenance: bool = False,
        include_hyperedges: bool = False,
        expand_hyperedge_hops: int = 0,
        max_hyperedge_degree: int = 12,
    ) -> List[Dict[str, Any]]:
        r"""
        Executes an FTS5 BM25-ranked lookup over `fact_fts` joined to `facts`.

        - Returns `[]` cleanly when `query` is empty or contains only punctuation/wildcards.
        - When `verify_provenance=True` and `self.workspace_root` is set, verifies each
          hit's on-disk SHA-256 digest and `[start_char:end_char]` slice, filtering out
          any fact whose source file was deleted or mutated.
        - When `expand_hyperedge_hops >= 1` (`Dual-Hypergraph Indexing` arXiv:2609.28108v2 &
          `Asymmetric Dynamic Routing` arXiv:2609.29282v2), traverses incident hyperedges $e$
          satisfying $2 \le |e| \le \text{max\_hyperedge\_degree}$ (degree-penalized per
          Science Advances PMID:42566539) to bridge connected `FACT` nodes across knowledge islands.
        """
        if limit <= 0:
            return []
        fts_expr = sanitize_fts5_query(query, mode=mode)
        if not fts_expr:
            return []

        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            WITH top_fts AS (
                SELECT
                    fact_id,
                    bm25(fact_fts) AS score
                FROM fact_fts
                WHERE fact_fts MATCH ?
                ORDER BY score
                LIMIT ?
            )
            SELECT
                f.fact_id,
                f.episode_id,
                f.label,
                f.text,
                f.file_path,
                f.start_char,
                f.end_char,
                f.source_id,
                f.content_sha256,
                f.extractor_version,
                top_fts.score AS score
            FROM top_fts
            JOIN facts f ON f.fact_id = top_fts.fact_id
            ORDER BY top_fts.score, f.fact_id;
            """,
            (fts_expr, int(limit)),
        )

        rows = cursor.fetchall()
        results: List[Dict[str, Any]] = []
        seen_fact_ids: set[str] = set()
        for row in rows:
            item = dict(row)
            item["retrieval_hop"] = 0
            if verify_provenance and self.workspace_root is not None:
                prov = self.store.verify_fact_provenance(
                    item["fact_id"], self.workspace_root
                )
                item["provenance_valid"] = prov.valid
                item["provenance_status"] = prov.status_code
                if not prov.valid:
                    continue
            if include_hyperedges:
                item["hyperedges"] = self.store.get_hyperedges_for_fact(
                    item["fact_id"]
                )
            seen_fact_ids.add(item["fact_id"])
            results.append(item)

        if expand_hyperedge_hops > 0 and results and len(results) < limit:
            seed_items = list(results)
            hop1_candidates: List[Dict[str, Any]] = []
            for seed in seed_items:
                seed_edges = self.store.get_hyperedges_for_fact(seed["fact_id"])
                seed_score = float(seed.get("score", -1.0))
                for edge in seed_edges:
                    deg = int(edge.get("arity", len(edge.get("members", []))))
                    if deg < 2 or deg > max_hyperedge_degree:
                        continue
                    # Degree-penalized score attenuation (Science Advances PMID:42566539)
                    degree_penalty = 1.0 + math.log(deg)
                    bridged_score = seed_score / degree_penalty
                    for mem in edge.get("members", []):
                        if mem.get("member_kind") != "FACT":
                            continue
                        neighbor_id = mem.get("member_id", "")
                        if not neighbor_id or neighbor_id in seen_fact_ids:
                            continue
                        neighbor_fact = self.store.get_fact(neighbor_id)
                        if neighbor_fact is None:
                            continue
                        n_item: Dict[str, Any] = {
                            "fact_id": neighbor_fact.fact_id,
                            "episode_id": neighbor_fact.episode_id,
                            "label": neighbor_fact.label,
                            "text": neighbor_fact.text,
                            "file_path": neighbor_fact.file_path,
                            "start_char": neighbor_fact.start_char,
                            "end_char": neighbor_fact.end_char,
                            "source_id": neighbor_fact.source_id,
                            "content_sha256": neighbor_fact.content_sha256,
                            "extractor_version": neighbor_fact.extractor_version,
                            "score": bridged_score,
                            "retrieval_hop": 1,
                            "bridging_hyperedge_id": edge["hyperedge_id"],
                        }
                        if verify_provenance and self.workspace_root is not None:
                            prov = self.store.verify_fact_provenance(
                                neighbor_fact.fact_id, self.workspace_root
                            )
                            n_item["provenance_valid"] = prov.valid
                            n_item["provenance_status"] = prov.status_code
                            if not prov.valid:
                                continue
                        if include_hyperedges:
                            n_item["hyperedges"] = self.store.get_hyperedges_for_fact(
                                neighbor_fact.fact_id
                            )
                        seen_fact_ids.add(neighbor_fact.fact_id)
                        hop1_candidates.append(n_item)

            hop1_candidates.sort(key=lambda x: (float(x["score"]), str(x["fact_id"])))
            remaining = int(limit) - len(results)
            results.extend(hop1_candidates[:remaining])

        return results

    def like_scan_retrieve(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Baseline unindexed SQL `LIKE` substring scan used by `benchmarks/bench_hypersu_retrieval.py`
        to measure indexed FTS5 lookup vs full-table substring scanning.
        """
        if not query or limit <= 0 or not any(ch.isalnum() for ch in query):
            return []
        escaped = escape_like_pattern(query.strip())
        pattern = f"%{escaped}%"
        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            SELECT
                f.fact_id,
                f.episode_id,
                f.label,
                f.text,
                f.file_path,
                f.start_char,
                f.end_char,
                f.source_id,
                f.content_sha256,
                f.extractor_version
            FROM facts f
            WHERE f.label LIKE ? ESCAPE '\\'
               OR f.text LIKE ? ESCAPE '\\'
            ORDER BY f.fact_id
            LIMIT ?;
            """,
            (pattern, pattern, int(limit)),
        )
        return [dict(r) for r in cursor.fetchall()]
