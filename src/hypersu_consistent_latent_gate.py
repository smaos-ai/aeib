#!/usr/bin/env python3
"""
src/hypersu_consistent_latent_gate.py — SovereignNexus Tri-Core Invariant Engine

Implements three decoupled execution-plane governors:
1. RawHistoryPointerCache (HyperSU Raw-RAG + Context Compaction via Pointer Refs).
2. LatentStateInterceptor (Defends against unverified Prefill-Free KV-Cache / Tensor telepathy).
3. ConsistentHistoryLedger (Robert B. Griffiths Consistent Histories joint-sequence verifier).

Under the stated model, all state transitions and digests are RFC 8785 single-source JCS compliant.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Compute canonical content-addressed identifier (CAID) using RFC 8785 JCS and SHA-256."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


# ==============================================================================
# ENGINE 1: Raw-History Pointer Cache (LUD Raw-RAG + Token Compaction)
# ==============================================================================
@dataclass(frozen=True)
class RawSpanPointer:
    ref_id: str
    source_path: str
    start_line: int
    end_line: int
    raw_byte_len: int
    pointer_token_str: str
    content_caid: str


class RawHistoryPointerCache:
    """Stores loss-free raw history spans in SQLite FTS5 indexed storage.

    Injects compact pointer tokens into the active context window, dereferencing
    with SHA-256 byte integrity checks on retrieval.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_spans (
                ref_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                content_caid TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS raw_spans_fts USING fts5(
                ref_id UNINDEXED,
                source_path,
                raw_text
            )
            """
        )
        self._conn.commit()

    def ingest_raw_span(
        self, source_path: str, start_line: int, end_line: int, raw_text: str
    ) -> RawSpanPointer:
        if not source_path.strip() or not raw_text:
            raise ValueError("ERR_EMPTY_RAW_SPAN")
        if start_line <= 0 or end_line < start_line:
            raise ValueError("ERR_INVALID_LINE_RANGE")

        content_caid = sha256_jcs_caid(raw_text.encode("utf-8"))
        short_hash = content_caid.split(":")[1][:10]
        ref_id = f"ref_{short_hash}"
        pointer_str = f"[REF:{ref_id} path={source_path} L{start_line}-L{end_line} caid={short_hash}]"

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO raw_spans
                (ref_id, source_path, start_line, end_line, raw_text, content_caid)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ref_id, source_path, start_line, end_line, raw_text, content_caid),
            )
            self._conn.execute("DELETE FROM raw_spans_fts WHERE ref_id = ?", (ref_id,))
            self._conn.execute(
                "INSERT INTO raw_spans_fts (ref_id, source_path, raw_text) VALUES (?, ?, ?)",
                (ref_id, source_path, raw_text),
            )

        return RawSpanPointer(
            ref_id=ref_id,
            source_path=source_path,
            start_line=start_line,
            end_line=end_line,
            raw_byte_len=len(raw_text.encode("utf-8")),
            pointer_token_str=pointer_str,
            content_caid=content_caid,
        )

    def fetch_reference(self, ref_id: str) -> str:
        row = self._conn.execute(
            "SELECT raw_text, content_caid FROM raw_spans WHERE ref_id = ?", (ref_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"HALT_UNKNOWN_POINTER_REF:{ref_id}")
        raw_text, stored_caid = row
        actual_caid = sha256_jcs_caid(raw_text.encode("utf-8"))
        if actual_caid != stored_caid:
            raise ValueError(f"HALT_RAW_SPAN_TAMPER_DETECTED:{ref_id}")
        return str(raw_text)

    def search_raw_fts5(self, query: str, limit: int = 5) -> Tuple[RawSpanPointer, ...]:
        rows = self._conn.execute(
            """
            SELECT r.ref_id, r.source_path, r.start_line, r.end_line, r.raw_text, r.content_caid
            FROM raw_spans_fts f
            JOIN raw_spans r ON f.ref_id = r.ref_id
            WHERE raw_spans_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        results: List[RawSpanPointer] = []
        for ref_id, spath, sline, eline, rtext, ccaid in rows:
            short_h = ccaid.split(":")[1][:10]
            p_str = f"[REF:{ref_id} path={spath} L{sline}-L{eline} caid={short_h}]"
            results.append(
                RawSpanPointer(
                    ref_id=ref_id,
                    source_path=spath,
                    start_line=sline,
                    end_line=eline,
                    raw_byte_len=len(rtext.encode("utf-8")),
                    pointer_token_str=p_str,
                    content_caid=ccaid,
                )
            )
        return tuple(results)


# ==============================================================================
# ENGINE 2: Latent State Interceptor (KV-Cache / Swarm Telepathy Defense)
# ==============================================================================
@dataclass(frozen=True)
class LatentStatePacket:
    sender_agent_id: str
    receiver_agent_id: str
    model_backbone_id: str
    kv_cache_raw_bytes: bytes
    semantic_projection: Optional[Dict[str, Any]]
    projection_fidelity_bps: int  # 0..10000 bps
    bound_tensor_caid: str


@dataclass(frozen=True)
class LatentInterceptionVerdict:
    allowed: bool
    status_code: str
    projected_intent_caid: str
    verdict_caid: str


class LatentStateInterceptor:
    """Defends against unverified Prefill-Free KV-Cache Transfer blind spots.

    Forbids raw binary tensor/KV-Cache handoffs unless accompanied by:
    1. A deterministic `semantic_projection` JSON dictionary (action, target_scope, risk_tier).
    2. Cryptographic hash binding (`bound_tensor_caid == sha256(kv_cache_raw_bytes)`).
    3. Homogeneous model backbone verification and fidelity >= 9000 bps (90.00%).
    4. Zero forbidden side-effect escalation inside the projected intent.
    """

    MIN_PROJECTION_FIDELITY_BPS: int = 9000  # claim: config
    REQUIRED_PROJECTION_KEYS: FrozenSet[str] = frozenset(
        {"action", "risk_tier", "target_scope"}
    )
    FORBIDDEN_LATENT_ACTIONS: FrozenSet[str] = frozenset(
        {"bypass_eo1", "modify_tests", "exfiltrate_secret", "exec_shell"}
    )

    def __init__(self, allowed_model_backbones: FrozenSet[str]) -> None:
        if not allowed_model_backbones:
            raise ValueError("ERR_EMPTY_ALLOWED_BACKBONES")
        self.allowed_backbones = allowed_model_backbones

    def inspect_kv_cache_transfer(
        self, packet: LatentStatePacket
    ) -> LatentInterceptionVerdict:
        # 1. Reject empty or unprojected raw KV-Cache tensors
        if not packet.kv_cache_raw_bytes:
            return self._mint(False, "HALT_EMPTY_KV_CACHE_PAYLOAD", "NONE")

        if packet.semantic_projection is None:
            return self._mint(
                False, "HALT_LATENT_TRANSFER_UNVERIFIABLE:MISSING_PROJECTION", "NONE"
            )

        # 2. Verify cryptographic binding between raw KV-Cache bytes and declared hash
        actual_tensor_caid = sha256_jcs_caid(packet.kv_cache_raw_bytes)
        if packet.bound_tensor_caid != actual_tensor_caid:
            return self._mint(
                False,
                "HALT_LATENT_TENSOR_HASH_MISMATCH",
                actual_tensor_caid,
            )

        # 3. Verify model backbone homogeneity
        if packet.model_backbone_id not in self.allowed_backbones:
            return self._mint(
                False,
                f"HALT_UNTRUSTED_LATENT_BACKBONE:{packet.model_backbone_id}",
                actual_tensor_caid,
            )

        # 4. Verify schema completeness of semantic projection
        missing_keys = self.REQUIRED_PROJECTION_KEYS - set(packet.semantic_projection.keys())
        if missing_keys:
            return self._mint(
                False,
                f"HALT_INCOMPLETE_SEMANTIC_PROJECTION:{sorted(missing_keys)}",
                actual_tensor_caid,
            )

        # 5. Verify projection decoding fidelity floor (>= 9000 bps)
        if packet.projection_fidelity_bps < self.MIN_PROJECTION_FIDELITY_BPS:
            return self._mint(
                False,
                f"HALT_LATENT_PROJECTION_LOW_FIDELITY:{packet.projection_fidelity_bps}",
                actual_tensor_caid,
            )

        # 6. Inspect projected action for forbidden latent side effects
        projected_action = str(packet.semantic_projection.get("action", "")).strip()
        if projected_action in self.FORBIDDEN_LATENT_ACTIONS:
            return self._mint(
                False,
                f"HALT_FORBIDDEN_LATENT_INTENT:{projected_action}",
                actual_tensor_caid,
            )

        intent_caid = sha256_jcs_caid(
            {
                "projection": packet.semantic_projection,
                "receiver": packet.receiver_agent_id,
                "sender": packet.sender_agent_id,
                "tensor_caid": actual_tensor_caid,
            }
        )
        return self._mint(True, "OK_LATENT_TRANSFER_VERIFIED", intent_caid)

    @staticmethod
    def _mint(
        allowed: bool, status_code: str, intent_caid: str
    ) -> LatentInterceptionVerdict:
        payload = {
            "allowed": allowed,
            "projected_intent_caid": intent_caid,
            "status_code": status_code,
        }
        return LatentInterceptionVerdict(
            allowed=allowed,
            status_code=status_code,
            projected_intent_caid=intent_caid,
            verdict_caid=sha256_jcs_caid(payload),
        )


# ==============================================================================
# ENGINE 3: Griffiths Consistent Histories Execution Ledger
# ==============================================================================
@dataclass(frozen=True)
class HistoryEventStep:
    step_id: str
    cycle_phase: str       # "CYCLE_1_BRAINSTORM" | "CYCLE_2_GO_NOGO" | "CYCLE_3_EXECUTE"
    target_file: str
    spend_minor_units: int
    step_caid: str


@dataclass(frozen=True)
class ConsistentHistoryReceipt:
    consistent: bool
    status_code: str
    cumulative_spend_minor: int
    chain_length: int
    history_chain_caid: str


class ConsistentHistoryLedger:
    """Implements Robert B. Griffiths Consistent Histories joint-sequence verification.

    A candidate event is only appended if the entire trajectory satisfies:
    1. Cumulative Budget Conservation: sum(spend_minor_units) <= max_budget_minor.
    2. Monotonic Cycle Ordering: CYCLE_1_BRAINSTORM <= CYCLE_2_GO_NOGO <= CYCLE_3_EXECUTE
       (and CYCLE_3_EXECUTE is forbidden unless a prior CYCLE_2_GO_NOGO step was recorded).
    3. Scope Non-Amplification: target_file must remain inside authorized_files.
    """

    PHASE_ORDER: Dict[str, int] = {
        "CYCLE_1_BRAINSTORM": 1,
        "CYCLE_2_GO_NOGO": 2,
        "CYCLE_3_EXECUTE": 3,
    }

    def __init__(
        self, max_budget_minor: int, authorized_files: FrozenSet[str]
    ) -> None:
        if max_budget_minor < 0 or not authorized_files:
            raise ValueError("ERR_INVALID_HISTORY_CONSTRAINTS")
        self.max_budget_minor = max_budget_minor
        self.authorized_files = authorized_files
        self._history: List[HistoryEventStep] = []
        self._chain_caid: str = "GENESIS_HISTORY_FAMILY"

    @property
    def cumulative_spend_minor(self) -> int:
        return sum(e.spend_minor_units for e in self._history)

    def append_and_verify_consistency(
        self,
        step_id: str,
        cycle_phase: str,
        target_file: str,
        spend_minor_units: int,
    ) -> ConsistentHistoryReceipt:
        if spend_minor_units < 0:
            return self._reject("HALT_INCONSISTENT_HISTORY:NEGATIVE_SPEND")

        # Projector 1: Valid Cycle Phase & Monotonic Progression
        if cycle_phase not in self.PHASE_ORDER:
            return self._reject(f"HALT_INCONSISTENT_HISTORY:UNKNOWN_PHASE:{cycle_phase}")

        new_rank = self.PHASE_ORDER[cycle_phase]
        if self._history:
            last_rank = self.PHASE_ORDER[self._history[-1].cycle_phase]
            if new_rank < last_rank:
                return self._reject(
                    f"HALT_INCONSISTENT_HISTORY:PHASE_REGRESSION:{self._history[-1].cycle_phase}_to_{cycle_phase}"
                )

        # Cannot enter CYCLE_3_EXECUTE without passing through CYCLE_2_GO_NOGO
        if cycle_phase == "CYCLE_3_EXECUTE":
            has_gonogo = any(e.cycle_phase == "CYCLE_2_GO_NOGO" for e in self._history)
            if not has_gonogo:
                return self._reject(
                    "HALT_INCONSISTENT_HISTORY:MISSING_CYCLE_2_GO_NOGO_GATE"
                )

        # Projector 2: Scope Non-Amplification
        if target_file not in self.authorized_files:
            return self._reject(
                f"HALT_INCONSISTENT_HISTORY:SCOPE_AMPLIFICATION:{target_file}"
            )

        # Projector 3: Joint Trajectory Budget Conservation
        projected_total = self.cumulative_spend_minor + spend_minor_units
        if projected_total > self.max_budget_minor:
            return self._reject(
                f"HALT_INCONSISTENT_HISTORY:BUDGET_DECOHERENCE:{projected_total}_exceeds_{self.max_budget_minor}"
            )

        step_payload = {
            "cycle_phase": cycle_phase,
            "prev_chain_caid": self._chain_caid,
            "spend_minor_units": spend_minor_units,
            "step_id": step_id,
            "target_file": target_file,
        }
        step_caid = sha256_jcs_caid(step_payload)
        event = HistoryEventStep(
            step_id=step_id,
            cycle_phase=cycle_phase,
            target_file=target_file,
            spend_minor_units=spend_minor_units,
            step_caid=step_caid,
        )
        self._history.append(event)
        self._chain_caid = sha256_jcs_caid(
            {
                "chain_length": len(self._history),
                "latest_step_caid": step_caid,
                "total_spend": projected_total,
            }
        )
        return ConsistentHistoryReceipt(
            consistent=True,
            status_code="OK_CONSISTENT_HISTORY_APPENDED",
            cumulative_spend_minor=projected_total,
            chain_length=len(self._history),
            history_chain_caid=self._chain_caid,
        )

    def _reject(self, reason: str) -> ConsistentHistoryReceipt:
        return ConsistentHistoryReceipt(
            consistent=False,
            status_code=reason,
            cumulative_spend_minor=self.cumulative_spend_minor,
            chain_length=len(self._history),
            history_chain_caid=self._chain_caid,
        )
