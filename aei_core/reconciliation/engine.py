#!/usr/bin/env python3
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

"""
aei_core/reconciliation/engine.py
Reconciliation Engine implementing probe-failure escalation pattern and manual lockout latch
(conceptually inspired by breaker failure and lockout relay patterns).
"""

from typing import Dict, Any, Optional
from aei_core.model.evidence import EvidenceRecord, EvidenceType
from aei_core.model.state import DispositionState, ReconciliationState


class ReconciliationEngine:
    """
    State-machine reconciliation engine with probe-failure escalation pattern
    and terminal manual lockout latch protection.
    """

    def __init__(
        self,
        max_probe_attempts: int = 3,
        probe_backoff_ms: int = 0,
        terminal_state: str = DispositionState.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    ):
        self.max_probe_attempts = max_probe_attempts
        self.probe_backoff_ms = probe_backoff_ms
        self.terminal_state = terminal_state
        self._state_store: Dict[str, ReconciliationState] = {}

    def process_evidence(
        self,
        caid: str,
        current_context: Any,
        evidence: EvidenceRecord
    ) -> ReconciliationState:
        # Retrieve or initialize state
        if isinstance(current_context, ReconciliationState):
            state = current_context
            self._state_store[caid] = state
        elif caid in self._state_store:
            state = self._state_store[caid]
        else:
            ctx = current_context if isinstance(current_context, dict) else {}
            state = ReconciliationState(
                caid=caid,
                disposition=DispositionState.DISPATCHED_UNCONFIRMED,
                probe_attempts=0,
                requires_further_probing=True,
                is_terminal=False,
                context=ctx
            )
            self._state_store[caid] = state

        # ANSI 86 Lockout Guard: If terminal, reject all further automated processing
        if state.is_terminal:
            return state

        # Process Probe Failure
        if evidence.evidence_type == EvidenceType.PROBE_RESULT and self._is_failure(evidence):
            state.probe_attempts += 1

            if state.probe_attempts >= self.max_probe_attempts:
                # ANSI 50BF Cascade Exhausted -> ANSI 86 Lockout
                state.disposition = self.terminal_state
                state.requires_further_probing = False
                state.is_terminal = True
            else:
                # Escalate to next probe
                state.disposition = getattr(DispositionState, f"PROBE_{state.probe_attempts}_FAILED", f"PROBE_{state.probe_attempts}_FAILED")
                state.requires_further_probing = True
        elif evidence.evidence_type == EvidenceType.PROBE_RESULT and not self._is_failure(evidence):
            state.disposition = DispositionState.OUTCOME_VERIFIED
            state.requires_further_probing = False
            state.is_terminal = False

        self._state_store[caid] = state
        return state

    def _is_failure(self, evidence: EvidenceRecord) -> bool:
        """Deterministic failure check based on payload (e.g., 5xx codes, connection refused)."""
        payload = evidence.payload
        if not isinstance(payload, dict):
            return True
        http_code = payload.get("http_code", 200)
        status = str(payload.get("status", "")).lower()
        return (
            http_code >= 500
            or status in ("connection_refused", "timeout", "service_unavailable", "failed", "error")
            or payload.get("error") is not None
        )
