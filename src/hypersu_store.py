#!/usr/bin/env python3
"""
src/hypersu_store.py — Provenance-Grounded Fact & Variable-Cardinality Hyperedge Store.

Implements the deterministic storage and provenance verification layer for HyperSU:
  1. Dedicated `facts` table with immutable source spans (`file_path`, `start_char`,
     `end_char`, `content_sha256`, `extractor_version`, `created_at`).
  2. Explicitly synchronized `fact_fts` SQLite FTS5 virtual table (`porter unicode61`).
  3. Variable-cardinality n-ary `hyperedges`, `hyperedge_members`, and
     `hyperedge_evidence` tables (e.g., `JOINTLY_SUPPORTS` across N facts/episodes).
  4. Strict on-disk source-span and SHA-256 provenance verification
     (`verify_fact_provenance`, `verify_all_provenance`).
  5. Read-only `EO1` explanation helper (`explain_eo1_block`) that inspects
     `PreDispatchIntentInterlock` state without modifying latch/ledger state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs


def compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_sha256_prefixed(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class FactRecord:
    fact_id: str
    episode_id: str
    label: str
    text: str
    source_id: str
    file_path: str
    start_char: int
    end_char: int
    content_sha256: str
    extractor_version: str = "deterministic-v1"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class HyperedgeMember:
    member_kind: str  # "FACT" | "EPISODE" | "TOPIC"
    member_id: str
    role: str = "participant"


@dataclass(frozen=True)
class HyperedgeEvidenceSpan:
    fact_id: str
    source_id: str
    file_path: str
    start_char: int
    end_char: int
    content_sha256: str


@dataclass(frozen=True)
class HyperedgeRecord:
    hyperedge_id: str
    relation: str
    relation_version: str
    confidence: float
    members: Tuple[HyperedgeMember, ...]
    evidence: Tuple[HyperedgeEvidenceSpan, ...]
    evidence_digest: str = ""


@dataclass(frozen=True)
class ProvenanceCheckResult:
    fact_id: str
    valid: bool
    status_code: str
    file_path: str
    start_char: int
    end_char: int
    detail: str = ""


class HyperSUStore:
    """
    SQLite-backed provenance store with explicit FTS5 synchronization and
    variable-cardinality n-ary hyperedges.
    """

    VALID_MEMBER_KINDS = frozenset({"FACT", "EPISODE", "TOPIC"})

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else None
        target = str(self.db_path) if self.db_path else ":memory:"
        self.conn = sqlite3.connect(target)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        self.conn.close()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    fact_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    extractor_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS fact_fts USING fts5(
                    fact_id UNINDEXED,
                    label,
                    text,
                    tokenize = 'porter unicode61'
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hyperedges (
                    hyperedge_id TEXT PRIMARY KEY,
                    relation TEXT NOT NULL,
                    relation_version TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_digest TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hyperedge_members (
                    hyperedge_id TEXT NOT NULL,
                    member_kind TEXT NOT NULL,
                    member_id TEXT NOT NULL,
                    role TEXT,
                    PRIMARY KEY (hyperedge_id, member_kind, member_id),
                    FOREIGN KEY (hyperedge_id) REFERENCES hyperedges(hyperedge_id) ON DELETE CASCADE
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hyperedge_evidence (
                    hyperedge_id TEXT NOT NULL,
                    fact_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY (hyperedge_id, fact_id),
                    FOREIGN KEY (hyperedge_id) REFERENCES hyperedges(hyperedge_id) ON DELETE CASCADE,
                    FOREIGN KEY (fact_id) REFERENCES facts(fact_id) ON DELETE CASCADE
                )
                """
            )

    def add_fact(self, fact: FactRecord) -> None:
        """
        Inserts or updates a fact and explicitly synchronizes `fact_fts` inside the
        same transaction so duplicate or stale FTS rows never accumulate.
        """
        if fact.start_char < 0 or fact.end_char < fact.start_char:
            raise ValueError(
                f"Invalid source span [{fact.start_char}, {fact.end_char}] for {fact.fact_id}"
            )
        if len(fact.text) != (fact.end_char - fact.start_char):
            raise ValueError(
                f"Fact text length ({len(fact.text)}) does not match span width "
                f"({fact.end_char - fact.start_char}) for {fact.fact_id}"
            )

        with self.conn:
            # Remove any existing FTS row for this fact_id before inserting
            self.conn.execute(
                "DELETE FROM fact_fts WHERE fact_id = ?", (fact.fact_id,)
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO facts (
                    fact_id, episode_id, label, text, source_id,
                    file_path, start_char, end_char,
                    content_sha256, extractor_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact.fact_id,
                    fact.episode_id,
                    fact.label,
                    fact.text,
                    fact.source_id,
                    fact.file_path,
                    fact.start_char,
                    fact.end_char,
                    fact.content_sha256,
                    fact.extractor_version,
                    fact.created_at,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO fact_fts (fact_id, label, text)
                VALUES (?, ?, ?)
                """,
                (fact.fact_id, fact.label, fact.text),
            )

    def add_facts_batch(self, facts: Sequence[FactRecord]) -> None:
        """Batch-inserts facts and synchronizes `fact_fts` in a single transaction."""
        for fact in facts:
            if fact.start_char < 0 or fact.end_char < fact.start_char:
                raise ValueError(
                    f"Invalid source span [{fact.start_char}, {fact.end_char}] for {fact.fact_id}"
                )
            if len(fact.text) != (fact.end_char - fact.start_char):
                raise ValueError(
                    f"Fact text length ({len(fact.text)}) != span width for {fact.fact_id}"
                )

        with self.conn:
            fact_ids = [(f.fact_id,) for f in facts]
            self.conn.executemany(
                "DELETE FROM fact_fts WHERE fact_id = ?", fact_ids
            )
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO facts (
                    fact_id, episode_id, label, text, source_id,
                    file_path, start_char, end_char,
                    content_sha256, extractor_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f.fact_id,
                        f.episode_id,
                        f.label,
                        f.text,
                        f.source_id,
                        f.file_path,
                        f.start_char,
                        f.end_char,
                        f.content_sha256,
                        f.extractor_version,
                        f.created_at,
                    )
                    for f in facts
                ],
            )
            self.conn.executemany(
                "INSERT INTO fact_fts (fact_id, label, text) VALUES (?, ?, ?)",
                [(f.fact_id, f.label, f.text) for f in facts],
            )

    def delete_fact(self, fact_id: str) -> None:
        """Deletes a fact from both `facts` and `fact_fts`."""
        with self.conn:
            self.conn.execute("DELETE FROM fact_fts WHERE fact_id = ?", (fact_id,))
            self.conn.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))

    def get_fact(self, fact_id: str) -> Optional[FactRecord]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return FactRecord(
            fact_id=row["fact_id"],
            episode_id=row["episode_id"],
            label=row["label"],
            text=row["text"],
            source_id=row["source_id"],
            file_path=row["file_path"],
            start_char=int(row["start_char"]),
            end_char=int(row["end_char"]),
            content_sha256=row["content_sha256"],
            extractor_version=row["extractor_version"],
            created_at=row["created_at"],
        )

    def ingest_file_span(
        self,
        workspace_root: Path,
        rel_file_path: str,
        start_char: int,
        end_char: int,
        label: str,
        episode_id: Optional[str] = None,
        fact_id: Optional[str] = None,
        extractor_version: str = "deterministic-v1",
    ) -> FactRecord:
        """
        Extracts a slice `[start_char:end_char]` from a real file under `workspace_root`,
        computes its SHA-256 content digest, and stores the provenance-bound `FactRecord`.
        """
        target = workspace_root / rel_file_path
        if not target.is_file():
            raise FileNotFoundError(f"Source file not found: {target}")
        raw_bytes = target.read_bytes()
        content_sha256 = f"sha256:{compute_sha256_hex(raw_bytes)}"
        full_text = raw_bytes.decode("utf-8")

        if start_char < 0 or end_char > len(full_text) or start_char > end_char:
            raise ValueError(
                f"Span [{start_char}, {end_char}] out of bounds for {rel_file_path} (len={len(full_text)})"
            )
        slice_text = full_text[start_char:end_char]
        ep_id = episode_id or compute_sha256_prefixed(f"episode:{rel_file_path}")
        src_id = compute_sha256_prefixed(f"source:{rel_file_path}:{content_sha256}")
        f_id = fact_id or compute_sha256_prefixed(
            f"fact:{rel_file_path}:{start_char}:{end_char}:{content_sha256}"
        )

        record = FactRecord(
            fact_id=f_id,
            episode_id=ep_id,
            label=label,
            text=slice_text,
            source_id=src_id,
            file_path=rel_file_path,
            start_char=start_char,
            end_char=end_char,
            content_sha256=content_sha256,
            extractor_version=extractor_version,
        )
        self.add_fact(record)
        return record

    @staticmethod
    def compute_evidence_digest(
        relation: str,
        members: Sequence[HyperedgeMember],
        evidence: Sequence[HyperedgeEvidenceSpan],
    ) -> str:
        payload = {
            "relation": relation,
            "members": sorted(
                [asdict(m) for m in members],
                key=lambda item: (item["member_kind"], item["member_id"], item["role"] or ""),
            ),
            "evidence": sorted(
                [asdict(e) for e in evidence],
                key=lambda item: (item["fact_id"], item["file_path"], item["start_char"]),
            ),
        }
        return f"sha256:{hashlib.sha256(encode_jcs(payload)).hexdigest()}"

    def add_hyperedge(
        self,
        hyperedge_id: str,
        relation: str,
        members: Sequence[HyperedgeMember],
        evidence: Sequence[HyperedgeEvidenceSpan],
        relation_version: str = "v1",
        confidence: float = 1.0,
    ) -> HyperedgeRecord:
        """
        Adds a variable-cardinality n-ary hyperedge (`len(members) >= 2`) backed by
        verifiable fact evidence spans.
        """
        if len(members) < 2:
            raise ValueError(
                f"Hyperedge {hyperedge_id} must connect at least 2 members (got {len(members)})"
            )
        if not evidence:
            raise ValueError(
                f"Hyperedge {hyperedge_id} must include at least 1 evidence span"
            )
        for m in members:
            if m.member_kind not in self.VALID_MEMBER_KINDS:
                raise ValueError(f"Invalid member_kind: {m.member_kind}")

        digest = self.compute_evidence_digest(relation, members, evidence)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO hyperedges (
                    hyperedge_id, relation, relation_version, confidence, evidence_digest
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (hyperedge_id, relation, relation_version, confidence, digest),
            )
            self.conn.execute(
                "DELETE FROM hyperedge_members WHERE hyperedge_id = ?",
                (hyperedge_id,),
            )
            self.conn.execute(
                "DELETE FROM hyperedge_evidence WHERE hyperedge_id = ?",
                (hyperedge_id,),
            )
            self.conn.executemany(
                """
                INSERT INTO hyperedge_members (hyperedge_id, member_kind, member_id, role)
                VALUES (?, ?, ?, ?)
                """,
                [(hyperedge_id, m.member_kind, m.member_id, m.role) for m in members],
            )
            self.conn.executemany(
                """
                INSERT INTO hyperedge_evidence (
                    hyperedge_id, fact_id, source_id, file_path,
                    start_char, end_char, content_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        hyperedge_id,
                        ev.fact_id,
                        ev.source_id,
                        ev.file_path,
                        ev.start_char,
                        ev.end_char,
                        ev.content_sha256,
                    )
                    for ev in evidence
                ],
            )

        return HyperedgeRecord(
            hyperedge_id=hyperedge_id,
            relation=relation,
            relation_version=relation_version,
            confidence=confidence,
            members=tuple(members),
            evidence=tuple(evidence),
            evidence_digest=digest,
        )

    def get_hyperedges_for_fact(self, fact_id: str) -> List[Dict[str, Any]]:
        """Returns all hyperedges (and their full member sets) incident on `fact_id`."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT he.hyperedge_id, he.relation, he.relation_version,
                            he.confidence, he.evidence_digest
            FROM hyperedges he
            LEFT JOIN hyperedge_members hm ON he.hyperedge_id = hm.hyperedge_id
            LEFT JOIN hyperedge_evidence hev ON he.hyperedge_id = hev.hyperedge_id
            WHERE (hm.member_kind = 'FACT' AND hm.member_id = ?)
               OR hev.fact_id = ?
            """,
            (fact_id, fact_id),
        )
        edges: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            h_id = row["hyperedge_id"]
            cur.execute(
                """
                SELECT member_kind, member_id, role
                FROM hyperedge_members
                WHERE hyperedge_id = ?
                ORDER BY member_kind, member_id
                """,
                (h_id,),
            )
            members = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT fact_id, source_id, file_path, start_char, end_char, content_sha256
                FROM hyperedge_evidence
                WHERE hyperedge_id = ?
                ORDER BY fact_id
                """,
                (h_id,),
            )
            evidence = [dict(r) for r in cur.fetchall()]
            edges.append(
                {
                    "hyperedge_id": h_id,
                    "relation": row["relation"],
                    "relation_version": row["relation_version"],
                    "confidence": float(row["confidence"]),
                    "evidence_digest": row["evidence_digest"],
                    "arity": len(members),
                    "members": members,
                    "evidence": evidence,
                }
            )
        return edges

    def verify_fact_provenance(
        self, fact_id: str, workspace_root: Path
    ) -> ProvenanceCheckResult:
        """
        Verifies that `fact_id` exists in `facts`, its `file_path` exists on disk under
        `workspace_root`, the file's SHA-256 matches `content_sha256`, and
        `file_text[start_char:end_char] == fact.text`.
        """
        fact = self.get_fact(fact_id)
        if fact is None:
            return ProvenanceCheckResult(
                fact_id=fact_id,
                valid=False,
                status_code="FACT_NOT_FOUND",
                file_path="",
                start_char=0,
                end_char=0,
                detail="Fact ID not present in store",
            )

        target = workspace_root / fact.file_path
        if not target.is_file():
            return ProvenanceCheckResult(
                fact_id=fact.fact_id,
                valid=False,
                status_code="SOURCE_FILE_MISSING",
                file_path=fact.file_path,
                start_char=fact.start_char,
                end_char=fact.end_char,
                detail=f"File missing on disk: {target}",
            )

        raw_bytes = target.read_bytes()
        observed_sha256 = f"sha256:{compute_sha256_hex(raw_bytes)}"
        if observed_sha256 != fact.content_sha256:
            return ProvenanceCheckResult(
                fact_id=fact.fact_id,
                valid=False,
                status_code="SOURCE_DIGEST_MISMATCH",
                file_path=fact.file_path,
                start_char=fact.start_char,
                end_char=fact.end_char,
                detail=f"Expected {fact.content_sha256}, observed {observed_sha256}",
            )

        try:
            full_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            return ProvenanceCheckResult(
                fact_id=fact.fact_id,
                valid=False,
                status_code="SOURCE_DECODE_ERROR",
                file_path=fact.file_path,
                start_char=fact.start_char,
                end_char=fact.end_char,
                detail=str(exc),
            )

        if (
            fact.start_char < 0
            or fact.end_char > len(full_text)
            or fact.start_char > fact.end_char
        ):
            return ProvenanceCheckResult(
                fact_id=fact.fact_id,
                valid=False,
                status_code="SPAN_OUT_OF_BOUNDS",
                file_path=fact.file_path,
                start_char=fact.start_char,
                end_char=fact.end_char,
                detail=f"Span [{fact.start_char}, {fact.end_char}] exceeds file length {len(full_text)}",
            )

        actual_slice = full_text[fact.start_char : fact.end_char]
        if actual_slice != fact.text:
            return ProvenanceCheckResult(
                fact_id=fact.fact_id,
                valid=False,
                status_code="SPAN_SLICE_MISMATCH",
                file_path=fact.file_path,
                start_char=fact.start_char,
                end_char=fact.end_char,
                detail="Slice on disk does not match stored fact text",
            )

        return ProvenanceCheckResult(
            fact_id=fact.fact_id,
            valid=True,
            status_code="PROVENANCE_OK",
            file_path=fact.file_path,
            start_char=fact.start_char,
            end_char=fact.end_char,
            detail="Source file digest and character slice match",
        )

    def verify_all_provenance(
        self, workspace_root: Path
    ) -> Tuple[int, int, List[ProvenanceCheckResult]]:
        """Verifies provenance for every fact in the store. Returns `(valid_count, total_count, results)`."""
        cur = self.conn.cursor()
        cur.execute("SELECT fact_id FROM facts ORDER BY fact_id")
        fact_ids = [r["fact_id"] for r in cur.fetchall()]
        results = [
            self.verify_fact_provenance(f_id, workspace_root) for f_id in fact_ids
        ]
        valid_count = sum(1 for r in results if r.valid)
        return valid_count, len(results), results

    def refresh_fact_evolution(
        self,
        workspace_root: Path,
        old_fact_id: str,
        new_start_char: int,
        new_end_char: int,
        label: Optional[str] = None,
        extractor_version: str = "deterministic-v1",
    ) -> Tuple[FactRecord, str]:
        """
        Provenance-preserving state evolution (`MHG-Mem`, arXiv:2610.29995v1):
        When an on-disk source file changes and invalidates `old_fact_id`, this method:
          1. Ingests the updated file span `[new_start_char:new_end_char]` as a new
             `FactRecord` (`new_fact`) bound to the current file SHA-256 digest.
          2. Removes the superseded `old_fact_id` from `fact_fts` so stale text is no
             longer returned as current by FTS5, while keeping the historical `facts`
             row intact for audit lineage.
          3. Creates an explicit `EVOLVES_FROM` hyperedge linking `new_fact`
             (`role="current_state"`) and `old_fact` (`role="superseded_state"`).
        """
        old_fact = self.get_fact(old_fact_id)
        if old_fact is None:
            raise KeyError(f"Cannot evolve unknown fact_id: {old_fact_id}")

        new_fact = self.ingest_file_span(
            workspace_root=workspace_root,
            rel_file_path=old_fact.file_path,
            start_char=new_start_char,
            end_char=new_end_char,
            label=label or old_fact.label,
            episode_id=old_fact.episode_id,
            extractor_version=extractor_version,
        )
        with self.conn:
            self.conn.execute(
                "DELETE FROM fact_fts WHERE fact_id = ?", (old_fact.fact_id,)
            )

        he_id = compute_sha256_prefixed(
            f"evolves:{old_fact.fact_id}->{new_fact.fact_id}"
        )
        self.add_hyperedge(
            hyperedge_id=he_id,
            relation="EVOLVES_FROM",
            members=[
                HyperedgeMember("FACT", new_fact.fact_id, role="current_state"),
                HyperedgeMember("FACT", old_fact.fact_id, role="superseded_state"),
            ],
            evidence=[
                HyperedgeEvidenceSpan(
                    fact_id=new_fact.fact_id,
                    source_id=new_fact.source_id,
                    file_path=new_fact.file_path,
                    start_char=new_fact.start_char,
                    end_char=new_fact.end_char,
                    content_sha256=new_fact.content_sha256,
                ),
                HyperedgeEvidenceSpan(
                    fact_id=old_fact.fact_id,
                    source_id=old_fact.source_id,
                    file_path=old_fact.file_path,
                    start_char=old_fact.start_char,
                    end_char=old_fact.end_char,
                    content_sha256=old_fact.content_sha256,
                ),
            ],
            confidence=1.0,
        )
        return new_fact, he_id

    def ingest_file_span_with_eo1_latch(
        self,
        interlock: Any,
        workspace_root: Path,
        rel_file_path: str,
        start_char: int,
        end_char: int,
        label: Optional[str] = None,
        episode_id: Optional[str] = None,
        extractor_version: str = "deterministic-v1",
        simulate_transport_drop: bool = False,
    ) -> Tuple[FactRecord, Any]:
        """
        EO1-latched memory ingestion (Vector 1: `Hy-Memory-30B` / `Mem0` / `HyperSU`
        write-path governance):
          - Wraps effectful persistent memory writes (`ingest_file_span`) inside
            `PreDispatchIntentInterlock.dispatch()`.
          - Ensures duplicate or ambiguous memory-ingestion retries cannot corrupt
            or double-append hypergraph state without out-of-band reconciliation.
        """
        target = workspace_root / rel_file_path
        raw_bytes = target.read_bytes()
        content_sha256 = f"sha256:{compute_sha256_hex(raw_bytes)}"
        payload = {
            "content_sha256": content_sha256,
            "end_char": int(end_char),
            "episode_id": episode_id,
            "extractor_version": extractor_version,
            "file_path": rel_file_path,
            "op": "HYPERSU_INGEST_FILE_SPAN",
            "start_char": int(start_char),
        }
        ingested_holder: List[FactRecord] = []

        def _commit_memory_span() -> Dict[str, Any]:
            fact = self.ingest_file_span(
                workspace_root=workspace_root,
                rel_file_path=rel_file_path,
                start_char=start_char,
                end_char=end_char,
                label=label,
                episode_id=episode_id,
                extractor_version=extractor_version,
            )
            ingested_holder.append(fact)
            if simulate_transport_drop:
                raise TimeoutError("simulated post-write memory ack drop")
            return {
                "fact_id": fact.fact_id,
                "source_id": fact.source_id,
                "status": "INGESTED",
            }

        receipt = interlock.dispatch(
            target_uri=f"sqlite://{self.db_path}",
            tool_name="hypersu.ingest_file_span",
            payload=payload,
            dispatch_fn=_commit_memory_span,
        )
        return ingested_holder[0], receipt

    def check_fts_sync_integrity(self) -> bool:
        """
        Checks that `fact_fts` contains no orphan `fact_id` rows missing from `facts`
        and that active `facts` match `fact_fts` (accounting for superseded evolution rows).
        """
        cur = self.conn.cursor()
        cur.execute("SELECT fact_id FROM facts")
        fact_ids = {r["fact_id"] for r in cur.fetchall()}
        cur.execute("SELECT fact_id FROM fact_fts")
        fts_rows = [r["fact_id"] for r in cur.fetchall()]
        fts_ids = set(fts_rows)
        cur.execute(
            "SELECT member_id FROM hyperedge_members WHERE member_kind = 'FACT' AND role = 'superseded_state'"
        )
        superseded_ids = {r["member_id"] for r in cur.fetchall()}
        expected_active = fact_ids - superseded_ids
        return len(fts_rows) == len(fts_ids) and fts_ids == expected_active

    def explain_eo1_block(
        self,
        interlock: Any,
        caid: str,
        workspace_root: Path,
        mcp_tool_annotations: Optional[Dict[str, Any]] = None,
        mcp_server_pinned: bool = False,
    ) -> Dict[str, Any]:
        """
        Read-only EO1 integration (Section 7 separation of authority + `AgentTriage`
        arXiv:2610.30738v1 replayable diagnosis contract + MCP `ToolAnnotations` zero-trust check):
          - Explains why `caid` is blocked by `interlock` without modifying `interlock` state.
          - Enforces `AgentTriage` mandatory-evidence abstention: if `caid` is blocked but
            either the canonical `DISPATCH_INTENT` runtime record or provenance-valid policy
            facts are missing, returns `diagnosis_status="ABSTAIN_MISSING_MANDATORY_EVIDENCE"`.
          - Evaluates MCP `ToolAnnotations` (`readOnlyHint`, `idempotentHint`, `destructiveHint`):
            unpinned MCP server hints are marked `UNTRUSTED_HINT_IGNORED_ENFORCE_EO1`.
        """
        is_latched = bool(interlock.is_caid_latched(caid))
        if hasattr(interlock, "is_caid_committed"):
            is_committed = bool(interlock.is_caid_committed(caid))
        else:
            committed_set = getattr(interlock, "_committed_caids", set())
            is_committed = caid in committed_set

        if is_latched:
            block_reason = "EFFECT_INDETERMINATE_LATCHED"
            reconciliation_required = True
        elif is_committed:
            block_reason = "DENY_ALREADY_COMMITTED_NO_RESEND"
            reconciliation_required = False
        else:
            block_reason = "NOT_BLOCKED"
            reconciliation_required = False

        # Read-only lookup of prior intent record from ledger file if present
        prior_intent: Optional[Dict[str, Any]] = None
        ledger_path = getattr(interlock, "ledger_path", None)
        if ledger_path and Path(ledger_path).is_file():
            for line in Path(ledger_path).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("caid") == caid and rec.get("record_type") == "DISPATCH_INTENT":
                    prior_intent = {
                        "intent_id": rec.get("intent_id"),
                        "caid": rec.get("caid"),
                        "record_type": rec.get("record_type"),
                        "tool_name": rec.get("tool_name"),
                    }

        cur = self.conn.cursor()
        cur.execute(
            "SELECT fact_id FROM facts WHERE file_path LIKE '%eo1_write_before_execute.py%' ORDER BY start_char"
        )
        eo1_fact_ids = [r["fact_id"] for r in cur.fetchall()]
        policy_facts: List[Dict[str, Any]] = []
        valid_policy_facts: List[Dict[str, Any]] = []
        hyperedges: List[Dict[str, Any]] = []
        seen_edges: set[str] = set()

        for f_id in eo1_fact_ids:
            fact = self.get_fact(f_id)
            prov = self.verify_fact_provenance(f_id, workspace_root)
            if fact is not None:
                entry = {
                    "fact_id": fact.fact_id,
                    "label": fact.label,
                    "file_path": fact.file_path,
                    "start_char": fact.start_char,
                    "end_char": fact.end_char,
                    "content_sha256": fact.content_sha256,
                    "provenance_valid": prov.valid,
                }
                policy_facts.append(entry)
                if prov.valid:
                    valid_policy_facts.append(entry)
            if prov.valid:
                for edge in self.get_hyperedges_for_fact(f_id):
                    if edge["hyperedge_id"] not in seen_edges:
                        seen_edges.add(edge["hyperedge_id"])
                        hyperedges.append(edge)

        # AgentTriage (arXiv:2610.30738v1) mandatory-evidence abstention check
        abstention_reasons: List[str] = []
        if block_reason != "NOT_BLOCKED":
            if prior_intent is None:
                abstention_reasons.append("MISSING_CANONICAL_DISPATCH_INTENT_RECORD")
            if not valid_policy_facts:
                abstention_reasons.append("NO_PROVENANCE_VALID_POLICY_FACTS")

        diagnosis_status = (
            "ABSTAIN_MISSING_MANDATORY_EVIDENCE"
            if abstention_reasons
            else "GROUNDED_DIAGNOSIS"
        )

        # MCP ToolAnnotations zero-trust evaluation
        mcp_annotation_status = "NOT_PROVIDED"
        if mcp_tool_annotations is not None:
            claims_safe = bool(
                mcp_tool_annotations.get("readOnlyHint")
                or mcp_tool_annotations.get("idempotentHint")
                or mcp_tool_annotations.get("destructiveHint") is False
            )
            if claims_safe and not mcp_server_pinned:
                mcp_annotation_status = "UNTRUSTED_HINT_IGNORED_ENFORCE_EO1"
            elif claims_safe and mcp_server_pinned:
                mcp_annotation_status = "PINNED_SERVER_ANNOTATION_ACCEPTED"
            else:
                mcp_annotation_status = "CONSERVATIVE_MUTATING_ENFORCE_EO1"

        replay_payload = json.dumps(
            {
                "block_reason": block_reason,
                "caid": caid,
                "diagnosis_status": diagnosis_status,
                "mcp_annotation_status": mcp_annotation_status,
                "prior_intent_id": prior_intent.get("intent_id") if prior_intent else None,
                "valid_policy_fact_ids": [pf["fact_id"] for pf in valid_policy_facts],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        diagnosis_replay_sha256 = compute_sha256_prefixed(replay_payload)

        return {
            "authority": "EO1_SOLE_EXECUTION_AUTHORITY",
            "hypersu_role": "READ_ONLY_PROVENANCE_EXPLANATION",
            "caid": caid,
            "block_reason": block_reason,
            "reconciliation_required": reconciliation_required,
            "diagnosis_status": diagnosis_status,
            "abstention_reasons": abstention_reasons,
            "diagnosis_replay_sha256": diagnosis_replay_sha256,
            "mcp_annotation_status": mcp_annotation_status,
            "prior_intent_record": prior_intent,
            "policy_facts": policy_facts,
            "supporting_hyperedges": hyperedges,
        }
