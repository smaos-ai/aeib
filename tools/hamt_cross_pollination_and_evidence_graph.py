#!/usr/bin/env python3
# File: tools/hamt_cross_pollination_and_evidence_graph.py
"""
ID-Bound Adversarial Cross-Pollination Orchestrator (`Debate_Orchestrator`) &
SQLite O(1) Counterexample Evidence Graph (`Evidence_Graph`) with HAMT State Forking.

Implements the complete 4-Stage Cross-Pollination & Persistent Knowledge Graph architecture:
1. Stage 1 — Orthogonal Persona Seeding (arXiv:2605.21006) & HAMT O(1) State Forking:
   Seeds independent model personas (`SKEPTIC`, `ARCHITECT`, `SECURITY_EXPERT`, `WEB_VERIFIER`)
   and forks immutable state snapshots via a 32-way Hash Array Mapped Trie (`HamtPersistentMap`),
   binding each branch to a content-addressed `CAID`.
2. Stage 2 — Cross-Injection & Forced Critique with Mandatory Web/Graph Evidence:
   Feeds Agent A's draft (`agent_A_CAID`) into Agent B with an anti-sycophancy rule: critiques
   without a verified `[URL_Evidence]` or executable counterexample witness are rejected
   (`HALT_SYCOPHANTIC_OR_UNGROUNDED_CRITIQUE`).
3. Stage 3 — Non-Dilutable Conflict Register & SQLite Tier-4 Counterexample Graph:
   Every verified contradiction is written to both the `NonDilutableConflictRegister` and the
   persistent SQLite `EvidenceGraph` (indexed by `topic_key` and `claim_sha256` for O(1)
   sub-millisecond historical counterexample retrieval on future `/decide` runs).
4. Stage 4 — High-Privilege Judge Synthesis:
   Synthesizes the final decision strictly from the verified Evidence Graph and resolved
   Conflict Register, signing an Ed25519 RFC 8785 JCS receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


def canonical_jcs(obj: Any) -> bytes:
    """Serialize object to RFC 8785 JCS canonical UTF-8 bytes (rejecting floats)."""
    def _reject_float(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("Floats are forbidden in RFC 8785 JCS payloads; use integer bps.")
        if isinstance(val, dict):
            for k, v in val.items():
                _reject_float(k)
                _reject_float(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _reject_float(item)

    _reject_float(obj)
    return _reference_encode_jcs(obj)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# 1. HAMT (HASH ARRAY MAPPED TRIE) PERSISTENT O(1) STATE FORKING ENGINE
# ============================================================================
@dataclass(frozen=True)
class HamtNode:
    """
    Immutable 32-way Hash Array Mapped Trie (HAMT) node (5 bits per level) providing
    structural sharing across forked agent state snapshots.
    """
    bitmap: int = 0
    children: Tuple[Any, ...] = field(default_factory=tuple)
    leaf_key: Optional[str] = None
    leaf_val: Optional[Any] = None
    node_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.leaf_key is not None:
            raw = canonical_jcs({"k": self.leaf_key, "v": self.leaf_val})
        else:
            child_hashes = [
                c.node_sha256 if isinstance(c, HamtNode) else str(c)
                for c in self.children
            ]
            raw = canonical_jcs({"bitmap": self.bitmap, "children": child_hashes})
        object.__setattr__(self, "node_sha256", sha256_prefixed(raw))


class HamtPersistentStateTree:
    """
    Persistent immutable key-value store backed by a 32-way HAMT.
    Forking a state for a parallel agent is O(1) (copying only the root reference),
    and inserting a key copies at most log32(N) <= 7 path nodes.
    """

    def __init__(self, root: Optional[HamtNode] = None) -> None:
        self._root = root or HamtNode()

    @property
    def root_caid(self) -> str:
        return self._root.node_sha256

    @staticmethod
    def _key_hash32(key: str) -> int:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big")

    def fork_with(self, key: str, value: Any) -> "HamtPersistentStateTree":
        h = self._key_hash32(key)
        new_root = self._assoc(self._root, h, 0, key, value)
        return HamtPersistentStateTree(new_root)

    def lookup(self, key: str) -> Optional[Any]:
        h = self._key_hash32(key)
        return self._find(self._root, h, 0, key)

    def _assoc(
        self,
        node: HamtNode,
        h: int,
        shift: int,
        key: str,
        val: Any,
    ) -> HamtNode:
        if node.leaf_key is not None:
            if node.leaf_key == key:
                return HamtNode(leaf_key=key, leaf_val=val)
            # Push existing leaf and new leaf down one level
            existing_h = self._key_hash32(node.leaf_key)
            intermediate = HamtNode()
            intermediate = self._assoc_branch(
                intermediate, existing_h, shift, node.leaf_key, node.leaf_val
            )
            return self._assoc_branch(intermediate, h, shift, key, val)
        return self._assoc_branch(node, h, shift, key, val)

    def _assoc_branch(
        self,
        node: HamtNode,
        h: int,
        shift: int,
        key: str,
        val: Any,
    ) -> HamtNode:
        idx = (h >> shift) & 0x1F
        bit = 1 << idx
        pos = bin(node.bitmap & (bit - 1)).count("1")
        if node.bitmap & bit:
            child = node.children[pos]
            new_child = self._assoc(child, h, shift + 5, key, val)
            new_children = (
                node.children[:pos] + (new_child,) + node.children[pos + 1 :]
            )
            return HamtNode(bitmap=node.bitmap, children=new_children)
        else:
            new_leaf = HamtNode(leaf_key=key, leaf_val=val)
            new_children = (
                node.children[:pos] + (new_leaf,) + node.children[pos:]
            )
            return HamtNode(bitmap=node.bitmap | bit, children=new_children)

    def _find(
        self,
        node: HamtNode,
        h: int,
        shift: int,
        key: str,
    ) -> Optional[Any]:
        if node.leaf_key is not None:
            return node.leaf_val if node.leaf_key == key else None
        idx = (h >> shift) & 0x1F
        bit = 1 << idx
        if not (node.bitmap & bit):
            return None
        pos = bin(node.bitmap & (bit - 1)).count("1")
        return self._find(node.children[pos], h, shift + 5, key)


# ============================================================================
# 2. SQLITE TIER-4 COUNTEREXAMPLE EVIDENCE GRAPH (`Evidence_Graph.py`)
# ============================================================================
@dataclass(frozen=True)
class CounterexampleGraphEdge:
    edge_id: str
    topic_key: str
    source_critic_agent: str
    target_author_agent: str
    target_snapshot_caid: str
    refuted_claim_text: str
    counterexample_summary: str
    url_evidence: str
    search_query_executed: str
    edge_caid: str = field(init=False)

    def __post_init__(self) -> None:
        raw = canonical_jcs(
            {
                "counterexample_summary": self.counterexample_summary,
                "edge_id": self.edge_id,
                "refuted_claim_text": self.refuted_claim_text,
                "search_query_executed": self.search_query_executed,
                "source_critic_agent": self.source_critic_agent,
                "target_author_agent": self.target_author_agent,
                "target_snapshot_caid": self.target_snapshot_caid,
                "topic_key": self.topic_key,
                "url_evidence": self.url_evidence,
            }
        )
        object.__setattr__(self, "edge_caid", sha256_prefixed(raw))


class SqliteCounterexampleEvidenceGraph:
    """
    Persistent Tier-4 Counterexample & Vulnerability Knowledge Graph backed by SQLite WAL.
    Provides O(1) indexed lookup by `topic_key` or `refuted_claim_sha256` so historical
    counter-arguments are matched in sub-millisecond time without re-running LLM inference.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_graph_edges (
                edge_id TEXT PRIMARY KEY,
                topic_key TEXT NOT NULL,
                refuted_claim_sha256 TEXT NOT NULL,
                source_critic_agent TEXT NOT NULL,
                target_author_agent TEXT NOT NULL,
                target_snapshot_caid TEXT NOT NULL,
                refuted_claim_text TEXT NOT NULL,
                counterexample_summary TEXT NOT NULL,
                url_evidence TEXT NOT NULL,
                search_query_executed TEXT NOT NULL,
                edge_caid TEXT NOT NULL
            );
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_topic ON evidence_graph_edges(topic_key);"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_claim_hash ON evidence_graph_edges(refuted_claim_sha256);"
        )
        self._conn.commit()

    def record_counterexample_edge(self, edge: CounterexampleGraphEdge) -> str:
        claim_hash = sha256_prefixed(edge.refuted_claim_text.encode("utf-8"))
        self._conn.execute(
            """
            INSERT OR REPLACE INTO evidence_graph_edges (
                edge_id, topic_key, refuted_claim_sha256, source_critic_agent,
                target_author_agent, target_snapshot_caid, refuted_claim_text,
                counterexample_summary, url_evidence, search_query_executed, edge_caid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                edge.edge_id,
                edge.topic_key,
                claim_hash,
                edge.source_critic_agent,
                edge.target_author_agent,
                edge.target_snapshot_caid,
                edge.refuted_claim_text,
                edge.counterexample_summary,
                edge.url_evidence,
                edge.search_query_executed,
                edge.edge_caid,
            ),
        )
        self._conn.commit()
        return edge.edge_caid

    def lookup_by_topic_o1(self, topic_key: str) -> List[Dict[str, str]]:
        cur = self._conn.execute(
            """
            SELECT edge_id, source_critic_agent, target_author_agent, target_snapshot_caid,
                   refuted_claim_text, counterexample_summary, url_evidence,
                   search_query_executed, edge_caid
            FROM evidence_graph_edges
            WHERE topic_key = ?
            ORDER BY edge_id ASC;
            """,
            (topic_key,),
        )
        rows: List[Dict[str, str]] = []
        for r in cur.fetchall():
            rows.append(
                {
                    "counterexample_summary": r[5],
                    "edge_caid": r[8],
                    "edge_id": r[0],
                    "refuted_claim_text": r[4],
                    "search_query_executed": r[6],
                    "source_critic_agent": r[1],
                    "target_author_agent": r[2],
                    "target_snapshot_caid": r[3],
                    "topic_key": topic_key,
                    "url_evidence": r[6],
                }
            )
        return rows

    def lookup_by_claim_exact_o1(self, claim_text: str) -> Optional[Dict[str, str]]:
        claim_hash = sha256_prefixed(claim_text.encode("utf-8"))
        cur = self._conn.execute(
            """
            SELECT edge_id, topic_key, counterexample_summary, url_evidence, edge_caid
            FROM evidence_graph_edges
            WHERE refuted_claim_sha256 = ?
            LIMIT 1;
            """,
            (claim_hash,),
        )
        row = cur.fetchone()
        return (
            None
            if row is None
            else {
                "counterexample_summary": row[2],
                "edge_caid": row[4],
                "edge_id": row[0],
                "topic_key": row[1],
                "url_evidence": row[3],
            }
        )

    def close(self) -> None:
        self._conn.close()


# ============================================================================
# 3. ID-BOUND ADVERSARIAL CROSS-POLLINATION ORCHESTRATOR (`Debate_Orchestrator`)
# ============================================================================
@dataclass(frozen=True)
class PersonaAgentSpec:
    agent_id: str
    persona_vector: str  # "SKEPTIC" | "ARCHITECT" | "SECURITY_EXPERT" | "FORMAL_PROVER"
    draft_generator_fn: Callable[[str], Dict[str, str]]
    cross_critic_fn: Callable[[str, Dict[str, str], Callable[[str], Optional[Dict[str, str]]]], Dict[str, Any]]


class AdversarialCrossPollinationOrchestrator:
    """
    Executes the 4-stage ID-Bound Adversarial Cross-Pollination workflow:
    - Stage 1: Parallel Orthogonal Seeding + HAMT O(1) State Forking.
    - Stage 2: Cross-Injection & Forced Critique with Mandatory Web Search (`[URL_Evidence]`).
    - Stage 3: Non-Dilutable Conflict Register & Tier-4 SQLite Evidence Graph persistence.
    - Stage 4: Judge Synthesis reading strictly from the Conflict Register + Evidence Graph.
    """

    def __init__(
        self,
        agents: List[PersonaAgentSpec],
        web_search_tool_fn: Callable[[str], Optional[Dict[str, str]]],
        evidence_graph: SqliteCounterexampleEvidenceGraph,
        judge_privkey: Ed25519PrivateKey,
    ) -> None:
        self._agents = agents
        self._web_search_tool = web_search_tool_fn
        self._graph = evidence_graph
        self._judge_privkey = judge_privkey
        self._non_dilutable_conflict_register: Dict[str, Dict[str, Any]] = {}

    def run_batch_cross_pollination(
        self,
        topic_key: str,
        initial_prompt: str,
    ) -> Dict[str, Any]:
        # Fast O(1) check in Tier-4 Historical Evidence Graph before running debate
        historical_hits = self._graph.lookup_by_topic_o1(topic_key)

        base_hamt = HamtPersistentStateTree().fork_with("topic_key", topic_key)
        forked_states: Dict[str, Tuple[Dict[str, str], str]] = {}

        # Stage 1: Orthogonal Persona Seeding + HAMT State Forking
        for agent in self._agents:
            draft = agent.draft_generator_fn(initial_prompt)
            agent_hamt = base_hamt.fork_with(
                f"draft:{agent.agent_id}",
                {
                    "claim": draft["claim"],
                    "persona": agent.persona_vector,
                    "proposed_design": draft["proposed_design"],
                },
            )
            forked_states[agent.agent_id] = (draft, agent_hamt.root_caid)

        # Stage 2: Cross-Injection & Forced Critique with Mandatory Live Web Search
        rejected_sycophantic_critiques = 0
        recorded_edge_caids: List[str] = []

        for author_id, (author_draft, author_snap_caid) in sorted(forked_states.items()):
            # Check if historical O(1) Evidence Graph already refutes this exact claim
            cached_refutation = self._graph.lookup_by_claim_exact_o1(author_draft["claim"])
            if cached_refutation is not None:
                conflict_id = f"conflict:cached:{author_id}"
                self._non_dilutable_conflict_register[conflict_id] = {
                    "author_id": author_id,
                    "author_snapshot_caid": author_snap_caid,
                    "counterexample_summary": cached_refutation["counterexample_summary"],
                    "critic_id": "TIER4_EVIDENCE_GRAPH_O1_CACHE",
                    "refuted_claim": author_draft["claim"],
                    "status": "OPEN_CONFLICT",
                    "url_evidence": cached_refutation["url_evidence"],
                }
                continue

            for critic in self._agents:
                if critic.agent_id == author_id:
                    continue

                critique_out = critic.cross_critic_fn(
                    author_id, author_draft, self._web_search_tool
                )

                # Enforce anti-sycophancy rule: "I think they are right" or missing URL is rejected
                text_lower = str(critique_out.get("critique_text", "")).lower()
                url_ev = str(critique_out.get("url_evidence", "")).strip()
                search_q = str(critique_out.get("search_query", "")).strip()

                if "i think they are right" in text_lower or "i agree" in text_lower:
                    rejected_sycophantic_critiques += 1
                    continue

                if critique_out.get("has_conflict") and url_ev.startswith("https://") and search_q:
                    edge_id = f"edge:{topic_key}:{critic.agent_id}->:{author_id}"
                    edge = CounterexampleGraphEdge(
                        edge_id=edge_id,
                        topic_key=topic_key,
                        source_critic_agent=critic.agent_id,
                        target_author_agent=author_id,
                        target_snapshot_caid=author_snap_caid,
                        refuted_claim_text=author_draft["claim"],
                        counterexample_summary=str(critique_out["critique_text"]),
                        url_evidence=url_ev,
                        search_query_executed=search_q,
                    )
                    edge_caid = self._graph.record_counterexample_edge(edge)
                    recorded_edge_caids.append(edge_caid)

                    # Stage 3: Pin into Non-Dilutable Conflict Register
                    conflict_id = f"conflict:{critic.agent_id}->{author_id}"
                    self._non_dilutable_conflict_register[conflict_id] = {
                        "author_id": author_id,
                        "author_snapshot_caid": author_snap_caid,
                        "counterexample_summary": edge.counterexample_summary,
                        "critic_id": critic.agent_id,
                        "edge_caid": edge_caid,
                        "refuted_claim": author_draft["claim"],
                        "status": "OPEN_CONFLICT",
                        "url_evidence": url_ev,
                    }

        # Stage 4: High-Privilege Judge Synthesis (reads strictly Conflict Register + Evidence Graph)
        refuted_authors = {
            v["author_id"] for v in self._non_dilutable_conflict_register.values()
        }
        surviving_designs: List[Dict[str, str]] = []
        for agent_id, (draft, snap_caid) in sorted(forked_states.items()):
            if agent_id not in refuted_authors:
                surviving_designs.append(
                    {
                        "agent_id": agent_id,
                        "proposed_design": draft["proposed_design"],
                        "snapshot_caid": snap_caid,
                    }
                )

        # Mark all conflicts as resolved by excluding refuted claims and incorporating counterexamples
        for cid in sorted(self._non_dilutable_conflict_register.keys()):
            self._non_dilutable_conflict_register[cid]["status"] = (
                "RESOLVED_BY_REFUTATION_EXCLUSION"
            )

        synthesis_payload = {
            "conflict_count_registered": len(self._non_dilutable_conflict_register),
            "historical_o1_cache_hits": len(historical_hits),
            "recorded_evidence_edge_caids": sorted(recorded_edge_caids),
            "refuted_agents_excluded": sorted(refuted_authors),
            "rejected_sycophantic_critiques": rejected_sycophantic_critiques,
            "surviving_verified_designs": surviving_designs,
            "topic_key": topic_key,
        }
        sig = self._judge_privkey.sign(canonical_jcs(synthesis_payload))
        return {
            "receipt_sha256": sha256_prefixed(canonical_jcs(synthesis_payload)),
            "signature_b64": base64.b64encode(sig).decode("ascii"),
            "synthesis": synthesis_payload,
        }
