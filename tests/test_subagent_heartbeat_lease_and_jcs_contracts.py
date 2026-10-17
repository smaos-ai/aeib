#!/usr/bin/env python3
"""
tests/test_subagent_heartbeat_lease_and_jcs_contracts.py

Python Unit Test Harness for the 4-Step Multi-Agent Orchestration Execution Plan
under the stated model:
- Move 1: Disjoint File Ownership & Shared-Nothing Worktree Partition Interlock
  (halts on overlapping file write-sets or dirty worktree state).
- Move 2: Frozen Contract Validation (`schemas/operation.schema.json`, `refund_status_v1`)
  & RFC 8785 JCS `spec_caid` cryptographic binding.
- Move 3: Context Cartography (phi, sigma) Hand-Back Validator enforcing a strict
  250-word ceiling and JSON schema check to prevent parent context compaction cliffs.
- Move 4: Temporal-style 90-second Heartbeat Lease Monitor (`HEARTBEAT_TIMEOUT = 90s`)
  that reaps stalled subagent tasks, latches `status: "INDETERMINATE"`, trips the
  circuit breaker without blind retry, and emits an Ed25519-signed Merkle receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Support execution from either repository root or aeib-native-runtime/ subdirectory
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT.parent))

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Returns sha256:<hex> digest."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ============================================================================
# MOVE 1: Disjoint File Ownership & Shared-Nothing Worktree Partition Interlock
# ============================================================================


@dataclass(frozen=True)
class SubagentWorktreePartition:
    """Declares a subagent's isolated git worktree and owned file write-set."""

    subagent_id: str
    worktree_branch: str
    declared_write_set: FrozenSet[str]
    actual_modified_files: FrozenSet[str]
    worktree_clean_exit: bool


class SharedNothingPartitionCoordinator:
    """
    Move 1 Coordinator: Verifies that parallel subagents operate in disjoint
    file ownership partitions (`A_i intersect A_j == empty_set` for i != j),
    only modify files inside their declared write-set, and exit with a clean
    git worktree (`worktree_clean_exit: True`).
    """

    def evaluate_partitions(
        self, partitions: List[SubagentWorktreePartition]
    ) -> Dict[str, Any]:
        seen_files: Dict[str, str] = {}
        seen_branches: Dict[str, str] = {}

        for part in partitions:
            if not part.worktree_clean_exit:
                return {
                    "verdict": "HALTED",
                    "rejection_code": "HALT_DIRTY_WORKTREE_EXIT",
                    "offending_subagent": part.subagent_id,
                }

            if part.worktree_branch in seen_branches:
                return {
                    "verdict": "HALTED",
                    "rejection_code": "HALT_SHARED_WORKTREE_BRANCH_COLLISION",
                    "offending_subagents": [
                        seen_branches[part.worktree_branch],
                        part.subagent_id,
                    ],
                }
            seen_branches[part.worktree_branch] = part.subagent_id

            undeclared = part.actual_modified_files - part.declared_write_set
            if undeclared:
                return {
                    "verdict": "HALTED",
                    "rejection_code": "HALT_UNDECLARED_FILE_MUTATION",
                    "offending_subagent": part.subagent_id,
                    "undeclared_files": sorted(undeclared),
                }

            for file_path in sorted(part.declared_write_set):
                if file_path in seen_files:
                    return {
                        "verdict": "HALTED",
                        "rejection_code": "HALT_OVERLAPPING_WRITE_SET_COLLISION",
                        "colliding_file": file_path,
                        "offending_subagents": [
                            seen_files[file_path],
                            part.subagent_id,
                        ],
                    }
                seen_files[file_path] = part.subagent_id

        return {
            "verdict": "MERGE_AUTHORIZED",
            "partition_count": len(partitions),
            "total_owned_files": len(seen_files),
            "worktree_clean_exit": True,
        }


# ============================================================================
# MOVE 2: Contract Freeze & RFC 8785 JCS `spec_caid` Schema Binding
# ============================================================================


class FrozenJCSContractValidator:
    """
    Move 2 Validator: Enforces the frozen `schemas/operation.schema.json`
    contract and binds `spec_caid = sha256(encode_jcs(contract_core))`.
    """

    ALLOWED_ACTIONS = frozenset(
        {
            "POST /v1/refunds",
            "POST /v1/loyalty-credits",
            "POST /v1/vouchers",
            "POST /v1/payouts",
        }
    )
    ALLOWED_CURRENCIES = frozenset({"EUR", "USD", "GBP"})
    ALLOWED_REFUND_STATUS = frozenset({"CONFIRMED", "REFUTED", "PENDING"})
    SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def compute_spec_caid(cls, payload: Dict[str, Any]) -> str:
        core = {
            k: v
            for k, v in payload.items()
            if k not in ("spec_caid", "refund_status_v1")
        }
        return sha256_prefixed(encode_jcs(core))

    @classmethod
    def validate_operation_contract(
        cls, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        required_keys = {
            "operation_id",
            "action_type",
            "amount_minor",
            "currency",
            "recipient",
            "policy_epoch",
            "spec_caid",
        }
        allowed_keys = required_keys | {"refund_status_v1"}

        if not required_keys.issubset(payload.keys()):
            missing = sorted(required_keys - set(payload.keys()))
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": f"Missing required keys: {missing}",
            }

        extra_keys = set(payload.keys()) - allowed_keys
        if extra_keys:
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": f"Additional properties forbidden: {sorted(extra_keys)}",
            }

        # Reject booleans or floats disguised as amount_minor / policy_epoch
        if (
            isinstance(payload["amount_minor"], bool)
            or not isinstance(payload["amount_minor"], int)
            or payload["amount_minor"] < 1
        ):
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": "amount_minor must be a positive integer in minor units",
            }

        if (
            isinstance(payload["policy_epoch"], bool)
            or not isinstance(payload["policy_epoch"], int)
            or payload["policy_epoch"] < 1
        ):
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": "policy_epoch must be a positive integer",
            }

        if payload["action_type"] not in cls.ALLOWED_ACTIONS:
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": f"Unsupported action_type: {payload['action_type']}",
            }

        if payload["currency"] not in cls.ALLOWED_CURRENCIES:
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": f"Unsupported currency: {payload['currency']}",
            }

        spec_caid = payload.get("spec_caid", "")
        if not isinstance(spec_caid, str) or not cls.SHA256_RE.match(spec_caid):
            return {
                "valid": False,
                "rejection_code": "HALT_CONTRACT_SCHEMA_VIOLATION",
                "detail": "spec_caid must match ^sha256:[0-9a-f]{64}$",
            }

        expected_caid = cls.compute_spec_caid(payload)
        if spec_caid != expected_caid:
            return {
                "valid": False,
                "rejection_code": "HALT_SPEC_CAID_MISMATCH",
                "expected_spec_caid": expected_caid,
                "observed_spec_caid": spec_caid,
            }

        if "refund_status_v1" in payload:
            probe = payload["refund_status_v1"]
            probe_req = {
                "operation_id",
                "recipient",
                "amount_minor",
                "currency",
                "status_enum",
            }
            if not isinstance(probe, dict) or set(probe.keys()) != probe_req:
                return {
                    "valid": False,
                    "rejection_code": "HALT_REFUND_STATUS_V1_SCHEMA_VIOLATION",
                }
            if (
                probe["operation_id"] != payload["operation_id"]
                or probe["recipient"] != payload["recipient"]
                or probe["amount_minor"] != payload["amount_minor"]
                or probe["currency"] != payload["currency"]
                or probe["status_enum"] not in cls.ALLOWED_REFUND_STATUS
            ):
                return {
                    "valid": False,
                    "rejection_code": "HALT_REFUND_STATUS_V1_BINDING_MISMATCH",
                }

        return {
            "valid": True,
            "spec_caid": expected_caid,
            "jcs_bytes": encode_jcs(payload),
        }


# ============================================================================
# MOVE 3: Context Cartography (phi, sigma) Strict Hand-Back Ceiling Validator
# ============================================================================


class SubagentHandBackValidator:
    """
    Move 3 Validator: Prevents parent context compaction cliffs by enforcing:
      1. A strict 250-word ceiling (`MAX_HANDBACK_WORDS = 250`) on subagent
         hand-back `summary_text`.
      2. Context Cartography metrics (`phi` relevance density in [0.0, 1.0],
         `sigma` structural compression ratio in (0.0, 1.0]).
      3. Mandatory structured JSON hand-back fields (`subagent_id`, `status`,
         `spec_caid`, `worktree_clean_exit`, `modified_files`, `summary_text`).
    """

    MAX_HANDBACK_WORDS = 250
    REQUIRED_FIELDS = frozenset(
        {
            "subagent_id",
            "status",
            "spec_caid",
            "worktree_clean_exit",
            "modified_files",
            "summary_text",
            "context_cartography_phi",
            "context_cartography_sigma",
        }
    )

    @classmethod
    def validate_handback(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not cls.REQUIRED_FIELDS.issubset(payload.keys()):
            return {
                "accepted": False,
                "rejection_code": "HALT_HANDBACK_SCHEMA_INVALID",
                "missing_fields": sorted(cls.REQUIRED_FIELDS - set(payload.keys())),
            }

        summary_text = payload.get("summary_text", "")
        if not isinstance(summary_text, str) or not summary_text.strip():
            return {
                "accepted": False,
                "rejection_code": "HALT_HANDBACK_SCHEMA_INVALID",
            }

        words = summary_text.strip().split()
        word_count = len(words)
        if word_count > cls.MAX_HANDBACK_WORDS:
            return {
                "accepted": False,
                "rejection_code": "HALT_HANDBACK_CEILING_EXCEEDED",
                "observed_words": word_count,
                "max_words": cls.MAX_HANDBACK_WORDS,
            }

        phi = payload.get("context_cartography_phi")
        sigma = payload.get("context_cartography_sigma")
        if (
            not isinstance(phi, (int, float))
            or not isinstance(sigma, (int, float))
            or not (0.0 <= float(phi) <= 1.0)
            or not (0.0 < float(sigma) <= 1.0)
        ):
            return {
                "accepted": False,
                "rejection_code": "HALT_CARTOGRAPHY_METRICS_OUT_OF_BOUNDS",
            }

        if payload.get("worktree_clean_exit") is not True:
            return {
                "accepted": False,
                "rejection_code": "HALT_HANDBACK_DIRTY_WORKTREE",
            }

        return {
            "accepted": True,
            "observed_words": word_count,
            "handback_caid": sha256_prefixed(encode_jcs(payload)),
        }


# ============================================================================
# MOVE 4: 90s Heartbeat Lease Monitor, INDETERMINATE Latch & Merkle Receipt
# ============================================================================


class SubagentHeartbeatLeaseMonitor:
    """
    Move 4 Monitor: Enforces a Temporal-style 90-second heartbeat lease
    (`HEARTBEAT_TIMEOUT_SECONDS = 90`).
    When a subagent misses its 90s heartbeat or hits HTTP 504:
      1. Reaps the stalled subagent task (`task_reaped: True`).
      2. Latches the task state to `status: "INDETERMINATE"` (`HEARTBEAT_TIMEOUT`).
      3. Increments the circuit breaker failure counter and forbids blind retry
         (`retry_allowed: False`).
      4. Appends the transition to an RFC 9162 SHA-256 Merkle tree and signs the
         inclusion receipt with Ed25519 over RFC 8785 JCS.
    """

    HEARTBEAT_TIMEOUT_SECONDS = 90

    def __init__(
        self,
        monitor_signer: Ed25519PrivateKey,
        breaker_threshold: int = 2,
    ) -> None:
        self._signer = monitor_signer
        self._breaker_threshold = breaker_threshold
        self._leases: Dict[str, Dict[str, Any]] = {}
        self._merkle_leaves: List[bytes] = []
        self.breaker_failure_count: int = 0
        self.breaker_state: str = "CLOSED"

    def start_lease(
        self,
        *,
        task_id: str,
        subagent_id: str,
        spec_caid: str,
        start_ts: int,
    ) -> Dict[str, Any]:
        lease = {
            "last_heartbeat_ts": start_ts,
            "spec_caid": spec_caid,
            "start_ts": start_ts,
            "status": "RUNNING",
            "subagent_id": subagent_id,
            "task_id": task_id,
        }
        self._leases[task_id] = lease
        return dict(lease)

    def record_heartbeat(self, *, task_id: str, now_ts: int) -> Dict[str, Any]:
        lease = self._leases[task_id]
        if lease["status"] != "RUNNING":
            return {
                "accepted": False,
                "reason": "LEASE_ALREADY_TERMINATED",
                "status": lease["status"],
            }
        elapsed = now_ts - lease["last_heartbeat_ts"]
        if elapsed > self.HEARTBEAT_TIMEOUT_SECONDS:
            return self.evaluate_lease_at(task_id=task_id, now_ts=now_ts)

        lease["last_heartbeat_ts"] = now_ts
        return {
            "accepted": True,
            "elapsed_seconds": elapsed,
            "status": "RUNNING",
            "task_id": task_id,
        }

    def evaluate_lease_at(
        self,
        *,
        task_id: str,
        now_ts: int,
        wire_fault: Optional[str] = None,
    ) -> Dict[str, Any]:
        lease = self._leases[task_id]
        elapsed = now_ts - lease["last_heartbeat_ts"]

        if elapsed > self.HEARTBEAT_TIMEOUT_SECONDS or wire_fault == "HTTP_504":
            lease["status"] = "INDETERMINATE"
            reason = (
                "HEARTBEAT_TIMEOUT"
                if elapsed > self.HEARTBEAT_TIMEOUT_SECONDS
                else "HTTP_504_GATEWAY_TIMEOUT"
            )
            self.breaker_failure_count += 1
            if self.breaker_failure_count >= self._breaker_threshold:
                self.breaker_state = "OPEN"

            receipt_body = {
                "breaker_failure_count": self.breaker_failure_count,
                "breaker_state": self.breaker_state,
                "elapsed_seconds": elapsed,
                " evaluated_at_ts": now_ts,
                "heartbeat_timeout_seconds": self.HEARTBEAT_TIMEOUT_SECONDS,
                "reason": reason,
                "retry_allowed": False,
                "spec_caid": lease["spec_caid"],
                "status": "INDETERMINATE",
                "subagent_id": lease["subagent_id"],
                "task_id": task_id,
                "task_reaped": True,
            }
            # Fix key whitespace if any
            receipt_body.pop(" evaluated_at_ts", None)
            receipt_body["evaluated_at_ts"] = now_ts

            leaf_bytes = encode_jcs(receipt_body)
            leaf_hash = hashlib.sha256(b"\x00" + leaf_bytes).digest()
            self._merkle_leaves.append(leaf_hash)
            leaf_index = len(self._merkle_leaves) - 1
            merkle_root = self._compute_merkle_root()

            signed_envelope = {
                **receipt_body,
                "merkle_leaf_index": leaf_index,
                "merkle_root": merkle_root,
            }
            sig = self._signer.sign(encode_jcs(signed_envelope))
            signed_envelope["signature_b64"] = base64.b64encode(sig).decode("ascii")
            return signed_envelope

        return {
            "elapsed_seconds": elapsed,
            "retry_allowed": False,
            "status": lease["status"],
            "task_id": task_id,
            "task_reaped": False,
        }

    def _compute_merkle_root(self) -> str:
        if not self._merkle_leaves:
            return "sha256:" + hashlib.sha256(b"").hexdigest()
        level = list(self._merkle_leaves)
        while len(level) > 1:
            nxt: List[bytes] = []
            for i in range(0, len(level), 2):
                if i + 1 < len(level):
                    nxt.append(hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest())
                else:
                    nxt.append(level[i])
            level = nxt
        return "sha256:" + level[0].hex()


# ============================================================================
# PYTEST VERIFICATION SUITE FOR MOVES 1 - 4
# ============================================================================


def test_move1_disjoint_file_ownership_and_worktree_clean_exit() -> None:
    """
    Move 1: Verifies that disjoint subagent file write-sets in isolated worktrees
    pass pre-merge validation, while overlapping write-sets, undeclared file edits,
    or dirty worktree exits halt immediately.
    """
    coordinator = SharedNothingPartitionCoordinator()

    p_a = SubagentWorktreePartition(
        subagent_id="writer-rail-interop",
        worktree_branch="feat/subagent-a-rail",
        declared_write_set=frozenset(
            {
                "src/rail_mandate_and_mcp_taint_interlock.py",
                "tests/test_at64_rail_interop_and_mcp_tool_taint.py",
            }
        ),
        actual_modified_files=frozenset(
            {
                "src/rail_mandate_and_mcp_taint_interlock.py",
                "tests/test_at64_rail_interop_and_mcp_tool_taint.py",
            }
        ),
        worktree_clean_exit=True,
    )
    p_b = SubagentWorktreePartition(
        subagent_id="writer-scitt-cbom",
        worktree_branch="feat/subagent-b-scitt",
        declared_write_set=frozenset(
            {
                "src/cbom_and_scitt_otel_exporter.py",
                "tests/test_scitt_otel_and_pqc_cbom_agility.py",
            }
        ),
        actual_modified_files=frozenset(
            {
                "src/cbom_and_scitt_otel_exporter.py",
                "tests/test_scitt_otel_and_pqc_cbom_agility.py",
            }
        ),
        worktree_clean_exit=True,
    )

    ok = coordinator.evaluate_partitions([p_a, p_b])
    assert ok["verdict"] == "MERGE_AUTHORIZED"
    assert ok["worktree_clean_exit"] is True
    assert ok["total_owned_files"] == 4

    # Overlapping write-set collision
    p_collision = SubagentWorktreePartition(
        subagent_id="writer-colliding",
        worktree_branch="feat/subagent-c-collision",
        declared_write_set=frozenset({"src/cbom_and_scitt_otel_exporter.py"}),
        actual_modified_files=frozenset({"src/cbom_and_scitt_otel_exporter.py"}),
        worktree_clean_exit=True,
    )
    halted_overlap = coordinator.evaluate_partitions([p_a, p_b, p_collision])
    assert halted_overlap["verdict"] == "HALTED"
    assert (
        halted_overlap["rejection_code"] == "HALT_OVERLAPPING_WRITE_SET_COLLISION"
    )

    # Undeclared file modification outside write-set
    p_undeclared = SubagentWorktreePartition(
        subagent_id="writer-rogue",
        worktree_branch="feat/subagent-rogue",
        declared_write_set=frozenset({"docs/compliance/en18286_and_cbom_spec.md"}),
        actual_modified_files=frozenset(
            {
                "docs/compliance/en18286_and_cbom_spec.md",
                "src/jcs_canonicalizer.py",
            }
        ),
        worktree_clean_exit=True,
    )
    halted_undeclared = coordinator.evaluate_partitions([p_a, p_undeclared])
    assert halted_undeclared["verdict"] == "HALTED"
    assert halted_undeclared["rejection_code"] == "HALT_UNDECLARED_FILE_MUTATION"


def test_move2_frozen_jcs_contract_and_refund_status_v1_schema_binding() -> None:
    """
    Move 2: Verifies that pre-dispatch contracts and `refund_status_v1` probe
    payloads match `schemas/operation.schema.json` and bind `spec_caid` via
    RFC 8785 JCS.
    """
    schema_path = _REPO_ROOT / "schemas" / "operation.schema.json"
    if not schema_path.exists():
        schema_path = _REPO_ROOT.parent / "schemas" / "operation.schema.json"
    assert schema_path.exists(), "schemas/operation.schema.json must exist on disk"
    schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "spec_caid" in schema_doc["required"]

    contract_draft: Dict[str, Any] = {
        "action_type": "POST /v1/refunds",
        "amount_minor": 1250_00,
        "currency": "EUR",
        "operation_id": "op-move2-001",
        "policy_epoch": 12,
        "recipient": "DE89370400440532013000",
    }
    spec_caid = FrozenJCSContractValidator.compute_spec_caid(contract_draft)
    full_contract: Dict[str, Any] = {
        **contract_draft,
        "spec_caid": spec_caid,
        "refund_status_v1": {
            "amount_minor": 1250_00,
            "currency": "EUR",
            "operation_id": "op-move2-001",
            "recipient": "DE89370400440532013000",
            "status_enum": "CONFIRMED",
        },
    }

    res_ok = FrozenJCSContractValidator.validate_operation_contract(full_contract)
    assert res_ok["valid"] is True
    assert res_ok["spec_caid"] == spec_caid

    # Mutate amount_minor after spec_caid freeze -> HALT_SPEC_CAID_MISMATCH
    tampered = dict(full_contract)
    tampered["amount_minor"] = 9999_00
    res_tampered = FrozenJCSContractValidator.validate_operation_contract(tampered)
    assert res_tampered["valid"] is False
    assert res_tampered["rejection_code"] == "HALT_SPEC_CAID_MISMATCH"

    # Mismatched refund_status_v1 recipient -> HALT_REFUND_STATUS_V1_BINDING_MISMATCH
    bad_probe = dict(full_contract)
    bad_probe["refund_status_v1"] = {
        **full_contract["refund_status_v1"],
        "recipient": "FR7699999999999",
    }
    res_bad_probe = FrozenJCSContractValidator.validate_operation_contract(bad_probe)
    assert res_bad_probe["valid"] is False
    assert (
        res_bad_probe["rejection_code"] == "HALT_REFUND_STATUS_V1_BINDING_MISMATCH"
    )


def test_move3_context_cartography_handback_250_word_ceiling() -> None:
    """
    Move 3: Verifies that subagent hand-back payloads obey the 250-word ceiling
    and Context Cartography (phi, sigma) bounds, rejecting verbose raw transcripts
    that would cause parent context compaction cliffs.
    """
    concise_handback = {
        "context_cartography_phi": 0.94,
        "context_cartography_sigma": 0.18,
        "modified_files": [
            "src/rail_mandate_and_mcp_taint_interlock.py",
            "tests/test_at64_rail_interop_and_mcp_tool_taint.py",
        ],
        "spec_caid": "sha256:" + ("a" * 64),
        "status": "COMPLETED",
        "subagent_id": "writer-rail-interop",
        "summary_text": (
            "Implemented Google AP2 v0.2 Open-to-Closed SD-JWT mandate verification, "
            "Linux Foundation x402 V2 header interlock, Stripe ACP Shared Payment Token "
            "indeterminate lock, and AT63b/AT64 MCP tool taint ceiling downgrade. "
            "All 4 unit tests in test_at64_rail_interop_and_mcp_tool_taint.py passed."
        ),
        "worktree_clean_exit": True,
    }
    valid_res = SubagentHandBackValidator.validate_handback(concise_handback)
    assert valid_res["accepted"] is True
    assert valid_res["observed_words"] <= 250

    # 265-word verbose transcript dump -> rejected with HALT_HANDBACK_CEILING_EXCEEDED
    verbose_handback = {
        **concise_handback,
        "summary_text": " ".join([f"token_{i}" for i in range(265)]),
    }
    rejected_res = SubagentHandBackValidator.validate_handback(verbose_handback)
    assert rejected_res["accepted"] is False
    assert rejected_res["rejection_code"] == "HALT_HANDBACK_CEILING_EXCEEDED"
    assert rejected_res["observed_words"] == 265


def test_move4_90s_heartbeat_lease_timeout_indeterminate_latch_and_merkle_receipt() -> None:
    """
    Move 4: Verifies that when a subagent misses its 90-second heartbeat lease,
    the monitor reaps the task, latches `status: "INDETERMINATE"` (`HEARTBEAT_TIMEOUT`),
    increments the circuit breaker without blind retry (`retry_allowed: False`),
    and emits an Ed25519-signed RFC 9162 Merkle inclusion receipt.
    """
    monitor_priv = Ed25519PrivateKey.from_private_bytes(b"\x51" * 32)
    monitor = SubagentHeartbeatLeaseMonitor(
        monitor_signer=monitor_priv, breaker_threshold=2
    )
    spec_caid = "sha256:" + ("b" * 64)

    monitor.start_lease(
        task_id="task-subagent-01",
        subagent_id="worker-01",
        spec_caid=spec_caid,
        start_ts=1770002000,
    )

    # Heartbeat at +45s (within 90s lease) -> RUNNING
    hb_ok = monitor.record_heartbeat(task_id="task-subagent-01", now_ts=1770002045)
    assert hb_ok["accepted"] is True
    assert hb_ok["status"] == "RUNNING"

    # Check at +140s (95s since last heartbeat at +45s -> exceeds 90s lease!)
    reaped = monitor.evaluate_lease_at(task_id="task-subagent-01", now_ts=1770002140)
    assert reaped["status"] == "INDETERMINATE"
    assert reaped["reason"] == "HEARTBEAT_TIMEOUT"
    assert reaped["task_reaped"] is True
    assert reaped["retry_allowed"] is False
    assert reaped["elapsed_seconds"] == 95
    assert reaped["breaker_failure_count"] == 1
    assert reaped["breaker_state"] == "CLOSED"

    # Verify Ed25519 signature over the Merkle receipt envelope
    sig_bytes = base64.b64decode(reaped["signature_b64"])
    unsigned_envelope = {k: v for k, v in reaped.items() if k != "signature_b64"}
    monitor_priv.public_key().verify(sig_bytes, encode_jcs(unsigned_envelope))

    # Second task hits HTTP 504 -> trips circuit breaker to OPEN
    monitor.start_lease(
        task_id="task-subagent-02",
        subagent_id="worker-02",
        spec_caid=spec_caid,
        start_ts=1770002150,
    )
    reaped_2 = monitor.evaluate_lease_at(
        task_id="task-subagent-02",
        now_ts=1770002160,
        wire_fault="HTTP_504",
    )
    assert reaped_2["status"] == "INDETERMINATE"
    assert reaped_2["reason"] == "HTTP_504_GATEWAY_TIMEOUT"
    assert reaped_2["breaker_failure_count"] == 2
    assert reaped_2["breaker_state"] == "OPEN"
    assert reaped_2["merkle_leaf_index"] == 1
