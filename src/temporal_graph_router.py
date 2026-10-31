#!/usr/bin/env python3
"""
SovereignNexus Temporal Graph & Raw-FTS5 Provenance Router (src/temporal_graph_router.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to address the "Memory Tax" (lossy vector summarization
and lost provenance) and "Temporal Disconnect" (stale context drift when underlying
configuration or source files are updated):
  1. Zero-Loss Raw Provenance Indexing: Uses SQLite FTS5 over exact source text chunks
     paired with SHA-256 content digests.
  2. Bitemporal Validity Intervals: Every indexed chunk carries [valid_from_epoch_sec,
     valid_to_epoch_sec]. When a document is updated at T_new, prior active chunks are
     automatically closed at T_new - 1.
  3. Stale-Context Drift Interlock: Verifies whether an agent's cached document digest
     is still valid at T_now; if superseded, halts with HALT_STALE_CONTEXT_DRIFT_REQUIRES_REREAD.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs
from src.temporal_authority_guard import sha256_caid


@dataclasses.dataclass(frozen=True)
class TemporalChunkRecord:
    """Exact-text provenance chunk with temporal validity bounds."""

    chunk_id: str
    doc_path: str
    raw_text: str
    content_sha256: str
    valid_from_epoch_sec: int
    valid_to_epoch_sec: int  # 0 indicates currently active (open interval)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content_sha256": self.content_sha256,
            "doc_path": self.doc_path,
            "raw_text": self.raw_text,
            "valid_from_epoch_sec": self.valid_from_epoch_sec,
            "valid_to_epoch_sec": self.valid_to_epoch_sec,
        }


@dataclasses.dataclass(frozen=True)
class TemporalRetrievalReceipt:
    """RFC 8785 canonical receipt for a temporal FTS5 retrieval operation."""

    query_text: str
    query_epoch_sec: int
    matched_chunks: Tuple[TemporalChunkRecord, ...]
    stale_Superseded_excluded_count: int
    freshness_bps: int
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "freshness_bps": self.freshness_bps,
            "matched_chunks": [c.to_dict() for c in self.matched_chunks],
            "query_epoch_sec": self.query_epoch_sec,
            "query_text": self.query_text,
            "receipt_caid": self.receipt_caid,
            "stale_superseded_excluded_count": self.stale_Superseded_excluded_count,
        }


class TemporalGraphRouter:
    """
    SQLite FTS5 temporal truth engine with bitemporal validity bounds and
    stale-context drift detection.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_meta (
                chunk_id TEXT PRIMARY KEY,
                doc_path TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                valid_from_epoch_sec INTEGER NOT NULL,
                valid_to_epoch_sec INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                chunk_id UNINDEXED,
                doc_path,
                raw_text
            )
            """
        )
        self._conn.commit()

    def ingest_document_version(
        self,
        doc_path: str,
        raw_text: str,
        valid_from_epoch_sec: int,
        valid_to_epoch_sec: int = 0,
    ) -> TemporalChunkRecord:
        """
        Ingests a document version at valid_from_epoch_sec.
        Any previously open (valid_to_epoch_sec == 0) chunks for doc_path are closed
        at valid_from_epoch_sec - 1 so stale versions are excluded from future queries.
        """
        if not doc_path:
            raise ValueError("ERR_EMPTY_DOC_PATH")
        if valid_from_epoch_sec <= 0:
            raise ValueError(f"ERR_INVALID_VALID_FROM:{valid_from_epoch_sec}")
        if valid_to_epoch_sec != 0 and valid_to_epoch_sec < valid_from_epoch_sec:
            raise ValueError("ERR_INVALID_VALIDITY_INTERVAL")

        cur = self._conn.cursor()
        close_at = valid_from_epoch_sec - 1
        cur.execute(
            """
            UPDATE chunk_meta
            SET valid_to_epoch_sec = ?
            WHERE doc_path = ? AND valid_to_epoch_sec = 0 AND valid_from_epoch_sec <= ?
            """,
            (close_at, doc_path, valid_from_epoch_sec),
        )

        content_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        chunk_id = f"chk_{hashlib.sha256(f'{doc_path}:{valid_from_epoch_sec}:{content_sha256}'.encode('utf-8')).hexdigest()[:16]}"

        cur.execute(
            """
            INSERT OR REPLACE INTO chunk_meta (
                chunk_id, doc_path, raw_text, content_sha256,
                valid_from_epoch_sec, valid_to_epoch_sec
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                doc_path,
                raw_text,
                content_sha256,
                valid_from_epoch_sec,
                valid_to_epoch_sec,
            ),
        )
        cur.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
        cur.execute(
            "INSERT INTO chunk_fts (chunk_id, doc_path, raw_text) VALUES (?, ?, ?)",
            (chunk_id, doc_path, raw_text),
        )
        self._conn.commit()

        return TemporalChunkRecord(
            chunk_id=chunk_id,
            doc_path=doc_path,
            raw_text=raw_text,
            content_sha256=content_sha256,
            valid_from_epoch_sec=valid_from_epoch_sec,
            valid_to_epoch_sec=valid_to_epoch_sec,
        )

    def query_temporal_truth(
        self,
        fts_query: str,
        query_epoch_sec: int,
    ) -> TemporalRetrievalReceipt:
        """
        Executes an FTS5 search filtered strictly by [valid_from_epoch_sec, valid_to_epoch_sec]
        at query_epoch_sec.
        """
        if not fts_query.strip():
            raise ValueError("ERR_EMPTY_FTS_QUERY")

        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT m.chunk_id, m.doc_path, m.raw_text, m.content_sha256,
                   m.valid_from_epoch_sec, m.valid_to_epoch_sec
            FROM chunk_fts f
            JOIN chunk_meta m ON f.chunk_id = m.chunk_id
            WHERE chunk_fts MATCH ?
            ORDER BY m.valid_from_epoch_sec DESC, m.chunk_id ASC
            """,
            (fts_query,),
        )
        rows = cur.fetchall()

        valid_matches: List[TemporalChunkRecord] = []
        superseded_count = 0

        for row in rows:
            cid, dpath, rtext, csha, v_from, v_to = row
            if v_from <= query_epoch_sec and (v_to == 0 or query_epoch_sec <= v_to):
                valid_matches.append(
                    TemporalChunkRecord(
                        chunk_id=cid,
                        doc_path=dpath,
                        raw_text=rtext,
                        content_sha256=csha,
                        valid_from_epoch_sec=v_from,
                        valid_to_epoch_sec=v_to,
                    )
                )
            else:
                superseded_count += 1

        total_candidates = len(valid_matches) + superseded_count
        freshness_bps = (
            (len(valid_matches) * 10000) // total_candidates
            if total_candidates > 0
            else 10000
        )

        core_payload: Dict[str, Any] = {
            "freshness_bps": freshness_bps,
            "matched_chunks": [c.to_dict() for c in valid_matches],
            "query_epoch_sec": query_epoch_sec,
            "query_text": fts_query,
            "stale_superseded_excluded_count": superseded_count,
        }
        receipt_caid = sha256_caid(encode_jcs(core_payload))

        return TemporalRetrievalReceipt(
            query_text=fts_query,
            query_epoch_sec=query_epoch_sec,
            matched_chunks=tuple(valid_matches),
            stale_Superseded_excluded_count=superseded_count,
            freshness_bps=freshness_bps,
            receipt_caid=receipt_caid,
        )

    def verify_agent_context_freshness(
        self,
        doc_path: str,
        agent_cached_sha256: str,
        current_epoch_sec: int,
    ) -> Tuple[bool, str]:
        """
        Verifies whether an agent's cached file digest is still the active truth at current_epoch_sec.
        If the document was updated after the agent read it, halts with
        HALT_STALE_CONTEXT_DRIFT_REQUIRES_REREAD.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT content_sha256, valid_from_epoch_sec, valid_to_epoch_sec
            FROM chunk_meta
            WHERE doc_path = ?
            ORDER BY valid_from_epoch_sec DESC
            """,
            (doc_path,),
        )
        rows = cur.fetchall()
        if not rows:
            return False, f"HALT_UNKNOWN_DOCUMENT:{doc_path}"

        for csha, v_from, v_to in rows:
            if v_from <= current_epoch_sec and (v_to == 0 or current_epoch_sec <= v_to):
                if csha == agent_cached_sha256:
                    return True, "OK_CONTEXT_FRESH"
                return (
                    False,
                    f"HALT_STALE_CONTEXT_DRIFT_REQUIRES_REREAD:active={csha[:12]}!=cached={agent_cached_sha256[:12]}",
                )

        return False, f"HALT_NO_VALID_VERSION_AT_EPOCH:{current_epoch_sec}"

    @staticmethod
    def evaluate_memory_truth_decay(
        chunk: TemporalChunkRecord,
        current_epoch_sec: int,
        max_api_ttl_sec: int = 2592000,  # claim: config (30 days default API validity horizon)
        source_authority_bps: int = 9000,  # claim: config
        cross_ref_count: int = 1,
        min_confidence_bps: int = 6000,  # claim: config
    ) -> Tuple[bool, int, str]:
        """
        Truth Decay Engine (Defense against Epistemic Poisoning via Legitimate Stale Memory):
        Computes integer basis-point confidence:
          age_sec = current_epoch_sec - chunk.valid_from_epoch_sec
        If age_sec > max_api_ttl_sec (or chunk is already closed at current_epoch_sec),
        halts with HALT_STALE_MEMORY_NEEDS_RESEARCH.
        Otherwise computes linear integer decay adjusted by source_authority_bps and
        cross_ref_count bonus (capped at 10000 bps). If confidence_bps < min_confidence_bps,
        halts with HALT_STALE_MEMORY_NEEDS_RESEARCH.
        """
        if max_api_ttl_sec <= 0:
            raise ValueError(f"ERR_INVALID_MAX_API_TTL:{max_api_ttl_sec}")
        if source_authority_bps < 0 or source_authority_bps > 10000:
            raise ValueError(f"ERR_INVALID_SOURCE_AUTHORITY_BPS:{source_authority_bps}")

        if current_epoch_sec < chunk.valid_from_epoch_sec:
            return False, 0, "HALT_PREMATURE_MEMORY_CHUNK"

        if chunk.valid_to_epoch_sec != 0 and current_epoch_sec > chunk.valid_to_epoch_sec:
            return False, 0, "HALT_STALE_MEMORY_NEEDS_RESEARCH:CHUNK_SUPERSEDED"

        age_sec = current_epoch_sec - chunk.valid_from_epoch_sec
        if age_sec > max_api_ttl_sec:
            return (
                False,
                0,
                f"HALT_STALE_MEMORY_NEEDS_RESEARCH:age={age_sec}>ttl={max_api_ttl_sec}",
            )

        remaining_ratio_bps = ((max_api_ttl_sec - age_sec) * 10000) // max_api_ttl_sec
        base_conf_bps = (remaining_ratio_bps * source_authority_bps) // 10000
        corroboration_bonus_bps = min(max(cross_ref_count - 1, 0) * 500, 1500)
        confidence_bps = min(base_conf_bps + corroboration_bonus_bps, 10000)

        if confidence_bps < min_confidence_bps:
            return (
                False,
                confidence_bps,
                f"HALT_STALE_MEMORY_NEEDS_RESEARCH:confidence_bps={confidence_bps}<min={min_confidence_bps}",
            )

        return True, confidence_bps, "OK_MEMORY_CONFIDENCE_VERIFIED"

