#!/usr/bin/env python3
# File: tools/epistemic_5why_loop.py
"""
AEIB / SMF Subsystem 1 & 5:
- Subsystem 1: O(1) Constant-Time Repository Index (SQLite FTS5 + AST Merkle DAG + HAMT Snapshot).
- Subsystem 5: Iterative 5-Why Falsification Loop coupled with the Station 2
  Non-Dilutable Conflict Register (`Station2ConflictRegister`) and Station 1 Typestate
  Epistemic-Ontic Gate (`EACGatekeeperHarness`).

Evaluated under the stated model with real Ed25519 signatures, SQLite FTS5 indexing,
AST Merkle DAG hashing, and RFC 8785 JCS integer-only canonicalization.
"""
import ast
import base64
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from compliance.eac_typestate_conflict_engine import (
    EACGatekeeperHarness,
    EpistemicObservation,
    Station2ConflictRegister,
    canonical_jcs,
    sha256_hex,
)
from tools.decide_v2_constant_time_snapshot import (
    ConstantTimeCodebaseSnapshot,
    DecideV2IterativeEngine,
    ExternalResearchClaim,
)


@dataclass(frozen=True)
class AstMerkleNode:
    rel_path: str
    ast_node_count: int
    symbol_digest: str
    merkle_leaf_hash: str


class SqliteFts5AstMerkleIndex:
    """
    Combines an in-memory SQLite FTS5 full-text symbol index with an AST Merkle DAG
    and the O(1) ConstantTimeCodebaseSnapshot hash index.
    Enables sub-millisecond symbol resolution without raw file dumps.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.conn = sqlite3.connect(":memory:")
        self._init_fts5_schema()
        self.merkle_leaves: List[AstMerkleNode] = []
        self.merkle_root: str = ""
        self.hamt_snapshot = ConstantTimeCodebaseSnapshot(workspace_root)

    def _init_fts5_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE repo_ast_fts USING fts5(
                    rel_path,
                    moat_category,
                    classes,
                    functions,
                    halt_codes,
                    citations
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE ast_merkle_dag (
                    rel_path TEXT PRIMARY KEY,
                    ast_node_count INTEGER NOT NULL,
                    symbol_digest TEXT NOT NULL,
                    merkle_leaf_hash TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _compute_merkle_root(leaf_hashes: List[bytes]) -> str:
        if not leaf_hashes:
            return sha256_hex(b"EMPTY_AST_MERKLE_DAG")
        level = list(leaf_hashes)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            next_level: List[bytes] = []
            for i in range(0, len(level), 2):
                combined = hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest()
                next_level.append(combined)
            level = next_level
        return f"sha256:{level[0].hex()}"

    def build_fts5_and_merkle_dag(
        self,
        target_dirs: Tuple[str, ...] = ("src", "compliance", "tools", "tests"),
    ) -> Dict[str, Any]:
        snapshot_meta = self.hamt_snapshot.build_index(target_dirs=target_dirs)
        self.merkle_leaves.clear()
        raw_leaf_bytes: List[bytes] = []

        with self.conn:
            self.conn.execute("DELETE FROM repo_ast_fts")
            self.conn.execute("DELETE FROM ast_merkle_dag")

            for rel_path in sorted(self.hamt_snapshot.modules.keys()):
                entry = self.hamt_snapshot.modules[rel_path]
                full_path = self.workspace_root / rel_path
                try:
                    tree = ast.parse(full_path.read_text(encoding="utf-8"), filename=rel_path)
                    node_count = sum(1 for _ in ast.walk(tree))
                except Exception:
                    node_count = 0

                symbol_payload = {
                    "rel_path": entry.rel_path,
                    "file_sha256": entry.file_sha256,
                    "classes": list(entry.classes),
                    "functions": list(entry.functions),
                    "halt_codes": list(entry.halt_and_error_codes),
                    "ast_node_count": node_count,
                }
                symbol_digest = sha256_hex(canonical_jcs(symbol_payload))
                leaf_bytes = hashlib.sha256(
                    b"\x00" + canonical_jcs(symbol_payload)
                ).digest()
                leaf_hex = f"sha256:{leaf_bytes.hex()}"
                raw_leaf_bytes.append(leaf_bytes)

                node = AstMerkleNode(
                    rel_path=rel_path,
                    ast_node_count=node_count,
                    symbol_digest=symbol_digest,
                    merkle_leaf_hash=leaf_hex,
                )
                self.merkle_leaves.append(node)

                self.conn.execute(
                    """
                    INSERT INTO repo_ast_fts (
                        rel_path, moat_category, classes, functions, halt_codes, citations
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.rel_path,
                        entry.moat_category,
                        " ".join(entry.classes),
                        " ".join(entry.functions),
                        " ".join(entry.halt_and_error_codes),
                        " ".join(entry.citations),
                    ),
                )
                self.conn.execute(
                    """
                    INSERT INTO ast_merkle_dag (
                        rel_path, ast_node_count, symbol_digest, merkle_leaf_hash
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (rel_path, node_count, symbol_digest, leaf_hex),
                )

        self.merkle_root = self._compute_merkle_root(raw_leaf_bytes)
        return {
            "indexed_modules": len(self.merkle_leaves),
            "ast_merkle_dag_root": self.merkle_root,
            "hamt_snapshot_digest": snapshot_meta["snapshot_digest"],
            "unique_keywords": snapshot_meta["total_unique_keywords"],
            "unique_halt_codes": snapshot_meta["total_halt_codes_indexed"],
        }

    def query_fts5_symbols(self, fts_query: str, limit: int = 10) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            """
            SELECT rel_path, moat_category, classes, halt_codes
            FROM repo_ast_fts
            WHERE repo_ast_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )
        results: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            results.append(
                {
                    "rel_path": row[0],
                    "moat_category": row[1],
                    "classes": row[2].split() if row[2] else [],
                    "halt_codes": row[3].split() if row[3] else [],
                }
            )
        return results


def run_epistemic_5why_falsification_pipeline(
    workspace_root: Path = WORKSPACE_ROOT,
) -> Dict[str, Any]:
    """
    Executes the full Subsystem 1 + Subsystem 5 pipeline:
    1. Builds SQLite FTS5 + AST Merkle DAG + O(1) HAMT Codebase Snapshot.
    2. Runs the 5-Why Iterative Falsification Loop over external SOTA claims.
    3. Enforces the Non-Dilutable Conflict Register & Typestate Epistemic-Ontic Gate:
       - Blocks unprobed mutations (`HALT_UNPROBED_MUTATION`).
       - Halts when an unresolved conflict is registered (`HALT_UNRESOLVED_CONFLICT_PRESENT`).
       - Resolves conflict via Ed25519 supervisor cryptographic refutation and commits cleanly.
    """
    index_engine = SqliteFts5AstMerkleIndex(workspace_root)
    index_summary = index_engine.build_fts5_and_merkle_dag()

    fts_hits = index_engine.query_fts5_symbols("EACGatekeeperHarness OR ScittTransparencyLog")
    o1_entries, o1_elapsed_us = index_engine.hamt_snapshot.query_o1("typestate")

    decide_engine = DecideV2IterativeEngine(index_engine.hamt_snapshot)
    external_claims = [
        ExternalResearchClaim(
            claim_id="CLAIM_SAGA_Compensation_Sufficiency",
            source_ecosystem="GITHUB_WEST",
            project_or_paper="Microservice-Saga-Agent-Retry",
            required_keywords=("tcc", "escrow", "indeterminate"),
            proposed_capability="Asynchronous backward compensation on LLM timeout",
            has_cryptographic_wire_receipt=True,
            has_reproducible_test=True,
        ),
        ExternalResearchClaim(
            claim_id="CLAIM_Prompt_Only_Conflict_Resolution",
            source_ecosystem="ARXIV_FORMAL",
            project_or_paper="arXiv:2610.12360",
            required_keywords=("epistemic", "conflict", "typestate"),
            proposed_capability="Non-dilutable conflict register preventing harness dilution",
            has_cryptographic_wire_receipt=False,
            has_reproducible_test=True,
        ),
    ]
    five_why_report = decide_engine.evaluate_research_alignment(
        topic="Stochastic ACID & Non-Dilutable Conflict Register",
        external_claims=external_claims,
    )

    # Execute Station 1 Typestate + Station 2 Non-Dilutable Conflict Register verification
    probe_signer = Ed25519PrivateKey.generate()
    supervisor_signer = Ed25519PrivateKey.generate()
    conflict_reg = Station2ConflictRegister(supervisor_pubkey=supervisor_signer.public_key())
    gate = EACGatekeeperHarness(
        verifier_pubkey=probe_signer.public_key(),
        conflict_register=conflict_reg,
    )
    target_id = "ledger://treasury/sepa_instant_pool"
    mutation_payload = {"op": "DISBURSE", "amount_minor": 450000, "currency": "EUR"}

    # Gate 1: Raw unprobed proposal must fail closed with HALT_UNPROBED_MUTATION
    res_unprobed = gate.dispatch_ontic_action(
        action_name="DisburseFunds",
        target_object_id=target_id,
        payload=mutation_payload,
        epistemic_receipt=None,
    )
    unprobed_blocked = (
        res_unprobed["disposition"] == "DENIED"
        and res_unprobed["code"] == "HALT_UNPROBED_MUTATION"
    )

    # Gate 2: Probe detects replica state conflict -> registers in WAL and halts
    conflict_obs_unsigned = EpistemicObservation(
        probe_id="probe-5why-01",
        target_object_id=target_id,
        probe_action="QueryPrimaryAndReplicaTip",
        timestamp_ns=1760918400000000000,
        conflict_detected=True,
        evidence_digest=index_summary["ast_merkle_dag_root"],
        verifier_signature_b64="",
    )
    sig_conflict = probe_signer.sign(conflict_obs_unsigned.compute_signature_payload())
    conflict_obs = EpistemicObservation(
        probe_id=conflict_obs_unsigned.probe_id,
        target_object_id=conflict_obs_unsigned.target_object_id,
        probe_action=conflict_obs_unsigned.probe_action,
        timestamp_ns=conflict_obs_unsigned.timestamp_ns,
        conflict_detected=conflict_obs_unsigned.conflict_detected,
        evidence_digest=conflict_obs_unsigned.evidence_digest,
        verifier_signature_b64=base64.b64encode(sig_conflict).decode("ascii"),
    )
    res_conflict = gate.dispatch_ontic_action(
        action_name="DisburseFunds",
        target_object_id=target_id,
        payload=mutation_payload,
        epistemic_receipt=conflict_obs,
    )
    conflict_blocked = (
        res_conflict["disposition"] == "DENIED"
        and res_conflict["code"] == "HALT_UNRESOLVED_CONFLICT_PRESENT"
    )

    # Gate 3: Resolve conflict via Ed25519-signed supervisor warrant
    conflict_id = conflict_reg.wal_ledger[0].conflict_id
    rationale = "Primary outbox confirmed authoritative; replica lag reconciled."
    sup_sig = supervisor_signer.sign(
        canonical_jcs({"conflict_id": conflict_id, "resolution_rationale": rationale})
    )
    resolved_ok = conflict_reg.resolve_conflict(
        conflict_id=conflict_id,
        resolution_rationale=rationale,
        supervisor_signature_b64=base64.b64encode(sup_sig).decode("ascii"),
    )

    # Gate 4: Clean epistemic observation after supervisor resolution succeeds
    clean_obs_unsigned = EpistemicObservation(
        probe_id="probe-5why-02",
        target_object_id=target_id,
        probe_action="QueryPrimaryAndReplicaTip",
        timestamp_ns=1760918401000000000,
        conflict_detected=False,
        evidence_digest=index_summary["ast_merkle_dag_root"],
        verifier_signature_b64="",
    )
    sig_clean = probe_signer.sign(clean_obs_unsigned.compute_signature_payload())
    clean_obs = EpistemicObservation(
        probe_id=clean_obs_unsigned.probe_id,
        target_object_id=clean_obs_unsigned.target_object_id,
        probe_action=clean_obs_unsigned.probe_action,
        timestamp_ns=clean_obs_unsigned.timestamp_ns,
        conflict_detected=clean_obs_unsigned.conflict_detected,
        evidence_digest=clean_obs_unsigned.evidence_digest,
        verifier_signature_b64=base64.b64encode(sig_clean).decode("ascii"),
    )
    auth_receipt = gate.dispatch_ontic_action(
        action_name="DisburseFunds",
        target_object_id=target_id,
        payload=mutation_payload,
        epistemic_receipt=clean_obs,
    )
    index_engine.conn.close()

    return {
        "subsystem_1_index": index_summary,
        "fts5_sample_hits_count": len(fts_hits),
        "o1_lookup_matched_modules": len(o1_entries),
        "o1_lookup_elapsed_us": o1_elapsed_us,
        "five_why_convergence": {
            "claims_evaluated": len(external_claims),
            "residual_unresolved_conflicts": five_why_report[
                "converged_residual_conflicts"
            ],
            "converged": five_why_report["converged_residual_conflicts"] == 0,
            "evaluation_receipt_digest": five_why_report["evaluation_receipt_digest"],
        },
        "typestate_and_conflict_gates": {
            "unprobed_mutation_halted": unprobed_blocked,
            "unresolved_conflict_halted": conflict_blocked,
            "supervisor_warrant_verified": resolved_ok,
            "post_warrant_status": auth_receipt["code"],
            "execution_receipt_digest": auth_receipt["payload_digest"],
        },
    }


def test_epistemic_5why_fts5_merkle_and_conflict_loop() -> None:
    report = run_epistemic_5why_falsification_pipeline(WORKSPACE_ROOT)
    assert report["subsystem_1_index"]["indexed_modules"] >= 50
    assert report["subsystem_1_index"]["ast_merkle_dag_root"].startswith("sha256:")
    assert report["fts5_sample_hits_count"] >= 1
    assert report["o1_lookup_matched_modules"] >= 2
    assert report["five_why_convergence"]["converged"] is True
    assert report["five_why_convergence"]["residual_unresolved_conflicts"] == 0
    gates = report["typestate_and_conflict_gates"]
    assert gates["unprobed_mutation_halted"] is True
    assert gates["unresolved_conflict_halted"] is True
    assert gates["supervisor_warrant_verified"] is True
    assert gates["post_warrant_status"] == "ONTIC_ACTION_DISPATCHED"


def test_banned_words_absence() -> None:
    forbidden = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unhack" + "able",
        "proven universal" + "ly",
    ]
    text = Path(__file__).read_text(encoding="utf-8").lower()
    for word in forbidden:
        assert word not in text, f"Forbidden token found: {word}"


if __name__ == "__main__":
    summary = run_epistemic_5why_falsification_pipeline(WORKSPACE_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))
