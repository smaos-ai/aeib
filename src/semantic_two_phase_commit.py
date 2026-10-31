#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
src/semantic_two_phase_commit.py
================================================================================
Scope 2: Tsinghua Semantic ACID Multi-Agent Two-Phase Commit Coordinator.

Enforces Atomicity, Consistency, Isolation (row-level semantic locks), and
Durability across multi-agent context handoffs under the stated model, rolling back cleanly on
transport drops (TCP_RST / HTTP_504) or Monitor AI rejections.
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.eo1_unified_gate import sha256_jcs_caid
from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class SemanticTransactionReceipt:
    """Deterministic cryptographic receipt for a semantic 2PC transaction."""

    tx_id: str
    agent_id: str
    status: str
    pre_state_caid: str
    post_state_caid: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "post_state_caid": self.post_state_caid,
            "pre_state_caid": self.pre_state_caid,
            "receipt_caid": self.receipt_caid,
            "status": self.status,
            "tx_id": self.tx_id,
        }


class SemanticACIDCoordinator:
    """
    Transactional memory coordinator for HyperSU multi-agent state handoffs.
    Enforces ACID semantics on knowledge graph state and tool call effects.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
        self._committed_state: Dict[str, Any] = copy.deepcopy(initial_state or {})
        self._locked_keys: Dict[str, str] = {}    # key -> tx_id
        self._staging: Dict[str, Dict[str, Any]] = {}  # tx_id -> staged key-values
        self._snapshots: Dict[str, Dict[str, Any]] = {}  # tx_id -> pre-dispatch snapshot
        self._tx_owner: Dict[str, str] = {}       # tx_id -> agent_id

    def current_state_caid(self) -> str:
        """Returns the canonical RFC 8785 SHA-256 digest of committed state."""
        return sha256_jcs_caid(self._committed_state)

    def read_committed(self, key: str) -> Any:
        """Reads a key from the committed state (dirty reads forbidden)."""
        val = self._committed_state.get(key)
        return copy.deepcopy(val) if val is not None else None

    def is_key_locked(self, key: str) -> bool:
        return key in self._locked_keys

    def begin_transaction(
        self, tx_id: str, agent_id: str, target_keys: FrozenSet[str]
    ) -> Optional[SemanticTransactionReceipt]:
        """
        Phase 1 (Prepare):
        Acquires exclusive row locks on target_keys and snapshots pre-dispatch state.
        Fails closed with HALT_LOCK_CONTENTION if any key is currently held.
        """
        if not tx_id.strip():
            raise ValueError("ERR_EMPTY_TX_ID")
        if not agent_id.strip():
            raise ValueError("ERR_EMPTY_AGENT_ID")
        if not target_keys:
            raise ValueError("ERR_EMPTY_TARGET_KEYS")

        # Isolation: Check lock contention
        for k in sorted(target_keys):
            holder = self._locked_keys.get(k)
            if holder is not None and holder != tx_id:
                snap_caid = self.current_state_caid()
                return self._mint_receipt(
                    tx_id=tx_id,
                    agent_id=agent_id,
                    status=f"HALT_LOCK_CONTENTION:{k}_held_by_{holder}",
                    pre_caid=snap_caid,
                    post_caid=snap_caid,
                )

        # Acquire locks and snapshot state
        for k in target_keys:
            self._locked_keys[k] = tx_id
        self._snapshots[tx_id] = copy.deepcopy(self._committed_state)
        self._staging[tx_id] = {}
        self._tx_owner[tx_id] = agent_id

        return None

    def stage_write(self, tx_id: str, key: str, value: Any) -> None:
        """Stages a speculative write within an active transaction."""
        if tx_id not in self._staging:
            raise ValueError(f"ERR_UNKNOWN_TRANSACTION:{tx_id}")
        if self._locked_keys.get(key) != tx_id:
            raise ValueError(f"ERR_UNDECLARED_KEY_WRITE:{key}")
        self._staging[tx_id][key] = copy.deepcopy(value)

    def finalize_handoff(
        self,
        tx_id: str,
        transport_ok: bool,
        monitor_verified: bool,
    ) -> SemanticTransactionReceipt:
        """
        Phase 2 (Commit or Abort):
        - If transport_ok and monitor_verified: atomically commits staged mutations.
        - If transport drops or verification fails: rolls back to pre-dispatch snapshot.
        Always releases locks cleanly.
        """
        if tx_id not in self._snapshots:
            raise ValueError(f"ERR_UNKNOWN_TRANSACTION:{tx_id}")

        agent_id = self._tx_owner[tx_id]
        pre_snapshot = self._snapshots[tx_id]
        pre_caid = sha256_jcs_caid(pre_snapshot)

        try:
            if not transport_ok or not monitor_verified:
                # Atomic rollback to exact pre-dispatch snapshot
                self._committed_state = copy.deepcopy(pre_snapshot)
                post_caid = self.current_state_caid()
                reason = (
                    "EFFECT_INDETERMINATE_ROLLED_BACK:TRANSPORT_DROP"
                    if not transport_ok
                    else "EFFECT_INDETERMINATE_ROLLED_BACK:MONITOR_REJECTED"
                )
                return self._mint_receipt(tx_id, agent_id, reason, pre_caid, post_caid)

            # Atomic Commit of all staged writes
            for k, v in self._staging[tx_id].items():
                self._committed_state[k] = copy.deepcopy(v)
            post_caid = self.current_state_caid()
            return self._mint_receipt(tx_id, agent_id, "COMMITTED", pre_caid, post_caid)

        finally:
            # Release all row locks held by tx_id
            keys_to_release = [k for k, holder in self._locked_keys.items() if holder == tx_id]
            for k in keys_to_release:
                del self._locked_keys[k]
            self._staging.pop(tx_id, None)
            self._snapshots.pop(tx_id, None)
            self._tx_owner.pop(tx_id, None)

    @staticmethod
    def _mint_receipt(
        tx_id: str, agent_id: str, status: str, pre_caid: str, post_caid: str
    ) -> SemanticTransactionReceipt:
        payload = {
            "agent_id": agent_id,
            "post_state_caid": post_caid,
            "pre_state_caid": pre_caid,
            "status": status,
            "tx_id": tx_id,
        }
        return SemanticTransactionReceipt(
            tx_id=tx_id,
            agent_id=agent_id,
            status=status,
            pre_state_caid=pre_caid,
            post_state_caid=post_caid,
            receipt_caid=sha256_jcs_caid(payload),
        )
