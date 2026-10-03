# Copyright 2026 SovereignNexus Project
#
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

r"""Saga Compensation & Reconciliation Engine

Resolves `verdict: UNKNOWN` receipts by executing bitemporal ledger checks and
issuing idempotent compensating transactions to preserve the net ledger invariant
(\sum \Delta_{net} = 0.00).
"""

import hashlib
import json
import time
from typing import Any, Dict, Tuple


class SagaReconciler:
    def __init__(self, sla_timeout_sec: float = 300.0):
        self.sla_timeout_sec = sla_timeout_sec
        self.ledger_state: Dict[str, float] = {}

    def reconcile_receipt(
        self, receipt: Dict[str, Any], wire_proof: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        capsule = receipt.get("capsule", {})
        txid = capsule.get("txid") or capsule.get("payload_hash") or "tx-unknown"
        idempotency_key = capsule.get("idempotency_key", f"idem-{str(txid)[:16]}")
        timestamp = capsule.get("timestamp", time.time())
        amount = float(capsule.get("amount", 0.0))

        # 1. Bitemporal Verification
        valid_time_ok = wire_proof.get("valid_time_confirmed", False)
        target_committed = wire_proof.get("target_committed", False)

        if target_committed and valid_time_ok:
            # Transition -> CONFIRMED
            self.ledger_state[txid] = amount
            return "CONFIRMED", {
                "txid": txid,
                "status": "CONFIRMED",
                "delta_net": 0.0,
                "timestamp": time.time(),
            }

        # 2. SLA Timeout / Irreconcilable Conflict Check -> MANUAL_ESCALATION
        if (
            time.time() - timestamp > self.sla_timeout_sec
            or wire_proof.get("conflict_detected", False)
        ):
            return "MANUAL_ESCALATION", {
                "txid": txid,
                "status": "MANUAL_ESCALATION",
                "reason": "SLA timeout or cryptographic state conflict",
                "requires_dual_control_signoff": True,
                "timestamp": time.time(),
            }

        # 3. Uncommitted Wire Drop -> Execute Idempotent COMPENSATED_ROLLBACK
        compensation_txid = f"revert-{hashlib.sha256(f'{txid}:{idempotency_key}'.encode()).hexdigest()[:16]}"

        # Enforce Net Ledger Invariant (\sum \Delta_net = 0.00)
        self.ledger_state[txid] = 0.0

        return "COMPENSATED_ROLLBACK", {
            "original_txid": txid,
            "compensation_txid": compensation_txid,
            "idempotency_key": idempotency_key,
            "action": "REVERT_TRANSFER",
            "delta_net": 0.00,
            "status": "COMPENSATED_ROLLBACK",
            "timestamp": time.time(),
        }
