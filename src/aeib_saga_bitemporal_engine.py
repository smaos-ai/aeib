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
aeib_saga_bitemporal_engine.py — Bitemporal Saga Compensating Ledger Engine
Part of the Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.

Solves the multi-day asynchronous banking settlement reality:
1. SEPA R-transactions (returns, recalls, refunds) and chargebacks arrive 5 to 60 days later.
2. Rather than breaking hash-chain continuity or triggering contradiction alarms,
   reversals are recorded as forward-compensating entries with distinct bitemporal coordinates:
   - system_time: Immutable monotonic boundary recording epoch.
   - valid_time: Real-world economic reference epoch.
3. Cryptographically verifiable query slices:
   - as_of_system_time(t) -> Exact historical audit state known at boundary clock t.
   - as_of_valid_time(t) -> Economically effective settlement state at real-world time t.
"""

import base64
import hashlib
import time
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs


class BitemporalLedgerEntry:
    def __init__(
        self,
        entry_id: str,
        entry_type: str,  # "DISPATCH_COMMIT", "COMPENSATING_REVERSAL", "CHARGEBACK_DEBIT"
        operation_id: str,
        action_caid: str,
        amount_minor: int,
        system_time: int,
        valid_time: int,
        prev_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.entry_id = entry_id
        self.entry_type = entry_type
        self.operation_id = operation_id
        self.action_caid = action_caid
        self.amount_minor = amount_minor
        self.system_time = system_time
        self.valid_time = valid_time
        self.prev_hash = prev_hash
        self.metadata = metadata or {}

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type,
            "operation_id": self.operation_id,
            "action_caid": self.action_caid,
            "amount_minor": self.amount_minor,
            "system_time": self.system_time,
            "valid_time": self.valid_time,
            "prev_hash": self.prev_hash,
            "metadata": self.metadata,
        }

    def compute_hash(self) -> str:
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        return hashlib.sha256(canonical_bytes).hexdigest()


class BitemporalSagaEngine:
    """
    Append-only bitemporal ledger supporting forward saga compensations,
    asynchronous chargebacks, and dual-clock time-travel queries.
    """

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, signer_privkey: Optional[ed25519.Ed25519PrivateKey] = None):
        self._signer = signer_privkey or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self._signer.public_key()
        self._entries: List[BitemporalLedgerEntry] = []
        self._chain_tip: str = self.GENESIS_HASH

        # Fast lookup indices
        self._op_to_entries: Dict[str, List[BitemporalLedgerEntry]] = {}
        self._committed_amounts: Dict[str, int] = {}
        self._compensated_amounts: Dict[str, int] = {}

    @property
    def chain_tip(self) -> str:
        return self._chain_tip

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    def append_dispatch_commit(
        self,
        operation_id: str,
        action_caid: str,
        amount_minor: int,
        system_time: Optional[int] = None,
        valid_time: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Appends an authorized dispatch mutation to the bitemporal ledger.
        """
        now = int(time.time())
        sys_ts = system_time if system_time is not None else now
        val_ts = valid_time if valid_time is not None else sys_ts

        if operation_id in self._committed_amounts:
            return {"valid": False, "error": "ERR_DUPLICATE_OPERATION_DISPATCH"}

        entry_id = f"entry-{len(self._entries) + 1:06d}"
        entry = BitemporalLedgerEntry(
            entry_id=entry_id,
            entry_type="DISPATCH_COMMIT",
            operation_id=operation_id,
            action_caid=action_caid,
            amount_minor=amount_minor,
            system_time=sys_ts,
            valid_time=val_ts,
            prev_hash=self._chain_tip,
            metadata=metadata,
        )

        entry_hash = entry.compute_hash()
        sig = self._signer.sign(entry_hash.encode("utf-8"))

        self._entries.append(entry)
        self._chain_tip = entry_hash
        self._op_to_entries.setdefault(operation_id, []).append(entry)
        self._committed_amounts[operation_id] = amount_minor
        self._compensated_amounts[operation_id] = 0

        return {
            "valid": True,
            "entry_id": entry_id,
            "entry_hash": entry_hash,
            "signature_b64": base64.b64encode(sig).decode("ascii"),
            "chain_tip": self._chain_tip,
        }

    def append_compensating_reversal(
        self,
        operation_id: str,
        reversal_amount_minor: int,
        reversal_reason: str,  # e.g. "SEPA_RECALL_R04", "CHARGEBACK_DISPUTE", "SAGA_TIMEOUT"
        system_time: Optional[int] = None,
        valid_time: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Appends an asynchronous forward-compensating transaction (SEPA recall / chargeback).
        Preserves hash-chain continuity without overwriting historical records.
        """
        now = int(time.time())
        sys_ts = system_time if system_time is not None else now

        # Validation 1: Original operation must exist
        if operation_id not in self._committed_amounts:
            return {"valid": False, "error": "ERR_UNKNOWN_OPERATION_REVERSAL"}

        orig_amount = self._committed_amounts[operation_id]
        already_compensated = self._compensated_amounts.get(operation_id, 0)

        # Validation 2: Cannot compensate more than the original committed amount
        if already_compensated + reversal_amount_minor > orig_amount:
            return {
                "valid": False,
                "error": "ERR_COMPENSATION_EXCEEDS_ORIGINAL_AMOUNT",
                "original_amount": orig_amount,
                "already_compensated": already_compensated,
                "requested_reversal": reversal_amount_minor,
            }

        orig_entries = self._op_to_entries[operation_id]
        orig_caid = orig_entries[0].action_caid
        # valid_time defaults to the original transaction's valid_time or caller-provided effective date
        val_ts = valid_time if valid_time is not None else orig_entries[0].valid_time

        meta = dict(metadata or {})
        meta["reversal_reason"] = reversal_reason
        meta["original_entry_id"] = orig_entries[0].entry_id

        entry_id = f"entry-{len(self._entries) + 1:06d}"
        entry = BitemporalLedgerEntry(
            entry_id=entry_id,
            entry_type="COMPENSATING_REVERSAL",
            operation_id=operation_id,
            action_caid=orig_caid,
            amount_minor=reversal_amount_minor,
            system_time=sys_ts,
            valid_time=val_ts,
            prev_hash=self._chain_tip,
            metadata=meta,
        )

        entry_hash = entry.compute_hash()
        sig = self._signer.sign(entry_hash.encode("utf-8"))

        self._entries.append(entry)
        self._chain_tip = entry_hash
        self._op_to_entries[operation_id].append(entry)
        self._compensated_amounts[operation_id] += reversal_amount_minor

        return {
            "valid": True,
            "entry_id": entry_id,
            "entry_hash": entry_hash,
            "signature_b64": base64.b64encode(sig).decode("ascii"),
            "chain_tip": self._chain_tip,
            "net_remaining_minor": orig_amount - self._compensated_amounts[operation_id],
        }

    def verify_ledger_continuity(self) -> Dict[str, Any]:
        """
        Cryptographically verifies the entire bitemporal hash chain from genesis to tip.
        """
        current_hash = self.GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            if entry.prev_hash != current_hash:
                return {
                    "valid": False,
                    "error": "ERR_CHAIN_LINK_CORRUPTED",
                    "entry_idx": idx,
                    "expected_prev": current_hash,
                    "observed_prev": entry.prev_hash,
                }
            current_hash = entry.compute_hash()

        return {
            "valid": True,
            "verified_entries": len(self._entries),
            "final_tip": current_hash,
        }

    def query_net_balance_as_of_system_time(self, system_ts: int) -> int:
        """
        Time-travel query: What was the net settled balance known to the boundary at system_ts?
        """
        net_balance = 0
        for entry in self._entries:
            if entry.system_time <= system_ts:
                if entry.entry_type == "DISPATCH_COMMIT":
                    net_balance += entry.amount_minor
                elif entry.entry_type == "COMPENSATING_REVERSAL":
                    net_balance -= entry.amount_minor
        return net_balance

    def query_net_balance_as_of_valid_time(self, valid_ts: int) -> int:
        """
        Economic time query: What was the net settled balance for all events effective at valid_ts?
        """
        net_balance = 0
        for entry in self._entries:
            if entry.valid_time <= valid_ts:
                if entry.entry_type == "DISPATCH_COMMIT":
                    net_balance += entry.amount_minor
                elif entry.entry_type == "COMPENSATING_REVERSAL":
                    net_balance -= entry.amount_minor
        return net_balance
