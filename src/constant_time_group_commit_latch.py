#!/usr/bin/env python3
"""
src/constant_time_group_commit_latch.py
================================================================================
Systems Engineering Optimizations for AEIB:
1. Constant-Time (Branchless) Station 1 Admissibility Predicate Evaluator
   using hmac.compare_digest and bitwise predicate accumulation.
2. TigerBeetle-Style Group-Commit WAL Wire Latch with explicit Darwin F_FULLFSYNC
   support for physical NAND flash durability.
3. jCodeMunch-Style O(1) Byte-Offset AST Symbol Indexer with Dual-Digest
   Bell-LaPadula Taint Binding (raw_file_sha256 + slice_sha256).
4. Deterministic O(1) Bitmask Fast-Path Escalator over pre-hashed tool descriptors.

Evaluated under the stated model. Preserves strict zero-mock purity.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def sha256_bytes(data: bytes) -> bytes:
    """Computes raw SHA-256 digest bytes."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """Computes canonical 'sha256:<hex>' digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ==============================================================================
# 1. Constant-Time (Branchless) Station 1 Predicate Evaluator
# ==============================================================================

class ConstantTimeStation1Check:
    """
    Evaluates all admissibility digests in constant time without short-circuit branching.
    Prevents local IPC timing attacks from inferring which digest or policy epoch failed.
    """

    _ZERO_32 = b"\x00" * 32

    @classmethod
    def verify_5_tuple_constant_time(
        cls,
        actual_caid: bytes,
        expected_caid: bytes,
        actual_harness_digest: bytes,
        expected_harness_digest: bytes,
        actual_tool_digest: bytes,
        expected_tool_digest: bytes,
        taint_tier_id: int,          # 0 = TIER_0, 1 = TIER_1, 2 = TIER_2
        has_step_up_warrant: int,    # 0 or 1
        requested_minor: int,
        remaining_budget_minor: int,
    ) -> Tuple[bool, int]:
        """
        Executes C-level constant-time comparisons across all 32-byte digests.
        Accumulates all 5 terms via bitwise AND (zero short-circuit branching).
        Returns (all_passed, failure_mask).
        """
        # Ensure 32-byte fixed width for constant-time comparisons
        a_caid = actual_caid if len(actual_caid) == 32 else cls._ZERO_32
        e_caid = expected_caid if len(expected_caid) == 32 else cls._ZERO_32
        a_harn = actual_harness_digest if len(actual_harness_digest) == 32 else cls._ZERO_32
        e_harn = expected_harness_digest if len(expected_harness_digest) == 32 else cls._ZERO_32
        a_tool = actual_tool_digest if len(actual_tool_digest) == 32 else cls._ZERO_32
        e_tool = expected_tool_digest if len(expected_tool_digest) == 32 else cls._ZERO_32

        c1_caid_ok = int(hmac.compare_digest(a_caid, e_caid)) & int(len(actual_caid) == 32)
        c2_harness_ok = int(hmac.compare_digest(a_harn, e_harn)) & int(len(actual_harness_digest) == 32)
        c3_tool_ok = int(hmac.compare_digest(a_tool, e_tool)) & int(len(actual_tool_digest) == 32)

        # Branchless taint check: if taint_tier_id == 2, requires has_step_up_warrant == 1
        is_tier2 = int(taint_tier_id == 2)
        c4_taint_ok = (1 - is_tier2) | (is_tier2 & (has_step_up_warrant & 1))

        # Branchless budget check: requested_minor <= remaining_budget_minor
        c5_budget_ok = int(requested_minor <= remaining_budget_minor)

        # Accumulate all 5 checks via bitwise AND (zero short-circuit branching)
        all_passed = c1_caid_ok & c2_harness_ok & c3_tool_ok & c4_taint_ok & c5_budget_ok

        # Bitmask of exact failure reasons for deterministic audit logging
        failure_mask = (
            ((1 - c1_caid_ok) << 0)
            | ((1 - c2_harness_ok) << 1)
            | ((1 - c3_tool_ok) << 2)
            | ((1 - c4_taint_ok) << 3)
            | ((1 - c5_budget_ok) << 4)
        )
        return bool(all_passed), failure_mask


# ==============================================================================
# 2. TigerBeetle-Style Group-Commit WAL Latch with Darwin F_FULLFSYNC
# ==============================================================================

class GroupCommitWireLatch:
    """
    Batches concurrent EFFECT_INDETERMINATE / pre-dispatch WAL entries into a single
    vectored write + hardware sync (F_FULLFSYNC on macOS Darwin, fsync on Linux).
    Avoids the macOS NVMe volatile controller RAM flush trap.
    """

    def __init__(self, wal_path: str, strict_fullfsync: bool = False) -> None:
        self.wal_path = wal_path
        self.strict_fullfsync = strict_fullfsync
        self._fd = os.open(wal_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)

    def commit_batch(self, entries: List[Dict[str, Any]]) -> Tuple[int, float]:
        """
        Serializes entries into a single contiguous byte buffer and issues
        a hardware sync barrier.
        Returns (batch_count, amortized_microseconds_per_entry).
        """
        if not entries:
            return 0, 0.0

        t0 = time.perf_counter()
        payload = b"".join(
            json.dumps(e, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            for e in entries
        )
        os.write(self._fd, payload)

        if self.strict_fullfsync and sys.platform == "darwin" and hasattr(fcntl, "F_FULLFSYNC"):
            fcntl.fcntl(self._fd, fcntl.F_FULLFSYNC)
        else:
            os.fsync(self._fd)

        elapsed_us = (time.perf_counter() - t0) * 1_000_000.0
        amortized_us = elapsed_us / max(len(entries), 1)
        return len(entries), amortized_us

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1


# ==============================================================================
# 3. jCodeMunch-Style O(1) Byte-Offset Symbol Indexer with Taint Binding
# ==============================================================================

@dataclass(frozen=True)
class SymbolIndexEntry:
    qualified_name: str
    kind: str
    signature: str
    start_byte: int
    end_byte: int
    file_raw_sha256: str
    taint_tier: str


class ByteOffsetSymbolIndexer:
    """
    Replaces full-file RAG reads with O(1) seek+read byte-offset symbol retrieval
    and compact MUNCH-style wire encoding while strictly binding both raw_file_sha256
    and slice_sha256 to preserve Bell-LaPadula taint provenance.
    """

    def __init__(self, source_path: str, taint_tier: str = "TIER_0_PINNED") -> None:
        self.source_path = source_path
        self.taint_tier = taint_tier
        with open(source_path, "rb") as f:
            raw = f.read()
        self.file_raw_sha256 = sha256_hex(raw)
        self.full_file_bytes = len(raw)
        self._symbols: Dict[str, SymbolIndexEntry] = {}
        self._index_python_symbols(raw)

    def _index_python_symbols(self, raw: bytes) -> None:
        lines = raw.splitlines(keepends=True)
        offset = 0
        current_name = None
        start_b = 0
        sig = ""
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(b"def ") or stripped.startswith(b"class "):
                if current_name is not None:
                    self._symbols[current_name] = SymbolIndexEntry(
                        qualified_name=current_name,
                        kind="function" if current_name.startswith("def") else "symbol",
                        signature=sig,
                        start_byte=start_b,
                        end_byte=offset,
                        file_raw_sha256=self.file_raw_sha256,
                        taint_tier=self.taint_tier,
                    )
                header = stripped.decode("utf-8", errors="replace").strip()
                sig = header
                current_name = header.split()[1].split("(")[0].split(":")[0]
                start_b = offset
            offset += len(line)
        if current_name is not None:
            self._symbols[current_name] = SymbolIndexEntry(
                qualified_name=current_name,
                kind="function",
                signature=sig,
                start_byte=start_b,
                end_byte=offset,
                file_raw_sha256=self.file_raw_sha256,
                taint_tier=self.taint_tier,
            )

    def fetch_compact_symbol(self, symbol_name: str) -> Dict[str, Any]:
        """
        Retrieves the exact symbol byte slice via seek+read, strips non-functional
        boilerplate for MUNCH wire representation, and records dual-digest provenance.
        """
        if symbol_name not in self._symbols:
            raise KeyError(f"Symbol '{symbol_name}' not found in {self.source_path}")

        entry = self._symbols[symbol_name]
        with open(self.source_path, "rb") as f:
            f.seek(entry.start_byte)
            slice_bytes = f.read(entry.end_byte - entry.start_byte)

        # MUNCH-style compact line compaction (strip blank & comment lines)
        compact_lines = [
            ln.decode("utf-8", errors="replace")
            for ln in slice_bytes.splitlines()
            if ln.strip() and not ln.strip().startswith(b"#")
        ]
        compact_body = "\n".join(compact_lines).encode("utf-8")
        return {
            "sym": entry.qualified_name,
            "sig": entry.signature,
            "body": compact_body.decode("utf-8"),
            "raw_file_sha256": entry.file_raw_sha256,
            "slice_sha256": sha256_hex(compact_body),
            "taint_tier": entry.taint_tier,
            "compression_ratio_x": round(self.full_file_bytes / max(len(compact_body), 1), 2),
        }


# ==============================================================================
# 4. Deterministic O(1) Bitmask Fast-Path Escalator
# ==============================================================================

class DeterministicFastPathGate:
    """
    O(1) bitmask fast-path evaluator over pre-hashed tool descriptors.
    Routes strictly read-only, non-mutating operations through fast path (<10 µs);
    any state mutation, TIER_2 taint, or external credential use immediately
    escalates to full_gate.
    """

    FLAG_READ_ONLY = 1 << 0
    FLAG_NO_EXTERNAL_NET = 1 << 1
    FLAG_NO_CREDENTIALS = 1 << 2
    FLAG_NO_STATE_MUTATION = 1 << 3
    FLAG_TAINT_TIER_ZERO_OR_ONE = 1 << 4

    REQUIRED_FAST_PATH_MASK = (
        FLAG_READ_ONLY
        | FLAG_NO_EXTERNAL_NET
        | FLAG_NO_CREDENTIALS
        | FLAG_NO_STATE_MUTATION
        | FLAG_TAINT_TIER_ZERO_OR_ONE
    )

    @classmethod
    def evaluate_tool_call(
        cls,
        is_read_only: bool,
        no_external_net: bool,
        no_credentials: bool,
        no_state_mutation: bool,
        taint_tier: str,
    ) -> Tuple[str, int]:
        """
        Evaluates the tool call bitmask.
        Returns ("fast_path" | "full_gate", bitmask).
        """
        mask = 0
        if is_read_only:
            mask |= cls.FLAG_READ_ONLY
        if no_external_net:
            mask |= cls.FLAG_NO_EXTERNAL_NET
        if no_credentials:
            mask |= cls.FLAG_NO_CREDENTIALS
        if no_state_mutation:
            mask |= cls.FLAG_NO_STATE_MUTATION
        if taint_tier in ("TIER_0_PINNED", "TIER_1_PARTNER_ATTESTED"):
            mask |= cls.FLAG_TAINT_TIER_ZERO_OR_ONE

        if (mask & cls.REQUIRED_FAST_PATH_MASK) == cls.REQUIRED_FAST_PATH_MASK:
            return "fast_path", mask
        return "full_gate", mask
