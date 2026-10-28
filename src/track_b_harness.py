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

r"""
src/track_b_harness.py — AEIB Track B (Web Mutation Finality) Benchmark Harness

Implements the physical simulation harness for Track B:
- MockTargetLedger: Independent target-side oracle tracking actual committed state.
- FaultInjector: Simulates wire faults across 7 execution phases.
- AEIBWebGateway: Implements uncertainty latching and single-flight out-of-band target probing.
"""

import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.jcs_canonicalizer import encode_jcs


class MockTargetLedger:
    """
    Independent target-side ledger oracle.
    Records mutations by business_key and tracks commits, idempotency suppressions,
    and ground truth state strictly independent of client/agent assertions.
    """
    def __init__(self):
        self.ledger_records: Dict[str, Dict[str, Any]] = {}
        self.commit_counts: Dict[str, int] = {}
        self.seen_idempotency_keys: Dict[str, str] = {}  # idempotency_key -> business_key

    def commit_mutation(self, business_key: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Executes a commit on the target database."""
        if idempotency_key and idempotency_key in self.seen_idempotency_keys:
            # Idempotent replay: record already committed, suppress duplicate
            return {
                "status": "DEDUPLICATED",
                "business_key": business_key,
                "commit_count": self.commit_counts[business_key],
            }

        self.commit_counts[business_key] = self.commit_counts.get(business_key, 0) + 1
        record = {
            "business_key": business_key,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "COMMITTED"
        }
        self.ledger_records[business_key] = record
        if idempotency_key:
            self.seen_idempotency_keys[idempotency_key] = business_key

        return {
            "status": "COMMITTED",
            "business_key": business_key,
            "commit_count": self.commit_counts[business_key]
        }

    def probe_state(self, business_key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Out-of-band authoritative target query endpoint.
        Oracle independence invariant: strictly queries by business_key string only.
        Cannot access gateway state, expected dispositions, fault labels, test assertions, or retry decisions.
        """
        if not isinstance(business_key, str):
            raise TypeError(f"Oracle independence violation: query must be string business_key, got {type(business_key)}")
        forbidden_context_keys = {"gateway_state", "expected_disposition", "fault_label", "test_assertion", "retry_decision"}
        for k in kwargs:
            if k in forbidden_context_keys:
                raise ValueError(f"Oracle independence violation: forbidden key '{k}' passed to target ledger probe")
        rec = self.ledger_records.get(business_key)
        if rec:
            return {
                "status": rec["status"],
                "commit_count": self.commit_counts.get(business_key, 0),
                "timestamp": rec["timestamp"]
            }
        return None

    def get_commit_count(self, business_key: str) -> int:
        return self.commit_counts.get(business_key, 0)


@dataclass
class FaultInjector:
    """Simulates wire-level fault injection across the 7 execution phases."""
    phase: str
    wire_event: str

    VALID_PHASES = frozenset([
        "pre_dispatch",
        "pre_body",
        "mid_body",
        "post_commit",
        "post_click",
        "post_response",
        "probe"
    ])

    def should_fault(self, current_phase: str) -> bool:
        return self.phase == current_phase and self.wire_event != "HTTP_200_OK"


@dataclass
class WireTelemetry:
    bytes_sent: int = 0
    request_started: Optional[str] = None
    request_body_complete: Optional[str] = None
    target_received: Optional[str] = None
    target_commit_time: Optional[str] = None
    response_received: bool = False


@dataclass
class GatewayExecutionResult:
    scenario_id: str
    gateway_disposition: str
    wire_event: str
    retry_safe: bool
    latch_engaged: bool
    probe_reconciliation: Optional[str] = None
    target_ground_truth: str = "NOT_FOUND"
    commit_count: int = 0
    attributes: Dict[str, Any] = field(default_factory=dict)
    telemetry: Optional[WireTelemetry] = None
    outcome: str = "OUTCOME_UNSPECIFIED"
    effect_status: str = "UNKNOWN"
    retry_reason: str = "unspecified"
    release_authorization: str = "not_provided"


class AEIBWebGateway:
    """
    AEIB Web Gateway Adapter for browser and HTTP-driven mutations.
    Enforces candidate binding, uncertainty latching, and single-flight out-of-band reconciliation.
    """
    def __init__(self, target_ledger: MockTargetLedger, durable_store: Optional[Dict[str, Any]] = None):
        self.target_ledger = target_ledger
        self.durable_store = durable_store if durable_store is not None else {}
        if "latches" not in self.durable_store:
            self.durable_store["latches"] = {}
        self.latched_caids: Dict[str, bool] = self.durable_store["latches"]
        self.probe_flights: Dict[str, int] = {}  # caid -> flight count
        self.session_contexts: Dict[str, Dict[str, Any]] = {}

    def execute_transaction(
        self,
        scenario_id: str,
        noun: str,
        verb: str,
        business_key: str,
        payload: Dict[str, Any],
        fault_injector: FaultInjector,
        idempotency_key: Optional[str] = None,
        validate_schema: bool = True,
        probe_override_fn: Optional[Any] = None,
        session_id: Optional[str] = None,
        context_profile_id: Optional[str] = None,
        origin_allowlist: Optional[list] = None
    ) -> GatewayExecutionResult:
        # Session context isolation
        if session_id:
            if session_id not in self.session_contexts:
                self.session_contexts[session_id] = {
                    "context_profile_id": context_profile_id or "default",
                    "origin_allowlist": origin_allowlist or ["https://trusted.example"],
                    "session_tokens": {}
                }

        # Derive CAID: CAID = H(Noun || Verb || JCS(Payload))
        canonical_bytes = encode_jcs(payload)
        hasher = hashlib.sha256()
        hasher.update(noun.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(verb.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(canonical_bytes)
        caid = f"caid:sha256:{hasher.hexdigest()}"

        # Initialize physical wire telemetry (0 bytes sent prior to durable latch fsync)
        now_iso = datetime.now(timezone.utc).isoformat()
        telemetry = WireTelemetry(
            bytes_sent=0,
            request_started=now_iso,
        )

        # Latch check: If CAID is already latched, block duplicate retry fail-closed
        if self.latched_caids.get(caid, False):
            target_record = self.target_ledger.probe_state(business_key)
            target_status = target_record.get("status", "NOT_FOUND") if target_record else "NOT_FOUND"
            return GatewayExecutionResult(
                scenario_id=scenario_id,
                gateway_disposition="EFFECT_INDETERMINATE",
                wire_event="UNCERTAINTY_LATCHED_RETRY_BLOCKED",
                retry_safe=False,
                latch_engaged=True,
                probe_reconciliation="BLOCKED_PREVIOUSLY_LATCHED",
                target_ground_truth=target_status,
                commit_count=self.target_ledger.get_commit_count(business_key),
                attributes={"aeib.caid": caid, "block_reason": "UNCERTAINTY_LATCHED_RETRY_BLOCKED"},
                telemetry=telemetry,
                outcome="OUTCOME_BLOCKED",
                effect_status=target_status,
                retry_reason="uncertainty_latched_retry_blocked",
                release_authorization="not_provided"
            )

        # 1. Phase: pre_dispatch (Schema validation & durable latch journal write)
        # Invariant ordering: latch journal write -> durable commit/fsync -> only then network dispatch.
        # If storage or schema validation fails, dispatch is rejected fail-closed (0 bytes dispatched).
        if fault_injector.should_fault("pre_dispatch"):
            return GatewayExecutionResult(
                scenario_id=scenario_id,
                gateway_disposition="DISPATCH_REJECTED",
                wire_event=fault_injector.wire_event,
                retry_safe=True,
                latch_engaged=False,
                probe_reconciliation="PROBE_NOT_ATTEMPTED",
                target_ground_truth="NOT_FOUND",
                commit_count=self.target_ledger.get_commit_count(business_key),
                attributes={"aeib.caid": caid},
                telemetry=telemetry,
                outcome="OUTCOME_REJECTED",
                effect_status="NOT_FOUND",
                retry_reason="clean_rejection_no_effect",
                release_authorization="not_provided"
            )

        # Durable latch committed: now proceed to wire dispatch
        telemetry.bytes_sent = len(canonical_bytes)
        telemetry.request_body_complete = datetime.now(timezone.utc).isoformat()

        # 2. Phase: pre_body (Connection drop / TCP RST before body reaches target)
        if fault_injector.should_fault("pre_body"):
            # Target never received the body; state not committed
            self.latched_caids[caid] = True
            probe_result = self._execute_single_flight_probe(business_key, caid, probe_override_fn)
            return GatewayExecutionResult(
                scenario_id=scenario_id,
                gateway_disposition="EFFECT_INDETERMINATE",
                wire_event=fault_injector.wire_event,
                retry_safe=False,
                latch_engaged=True,
                probe_reconciliation=probe_result,
                target_ground_truth="NOT_FOUND",
                commit_count=self.target_ledger.get_commit_count(business_key),
                attributes={"aeib.caid": caid},
                telemetry=telemetry,
                outcome="OUTCOME_INDETERMINATE",
                effect_status="NOT_FOUND",
                retry_reason="uncertainty_latched",
                release_authorization="not_provided"
            )

        # 3. Phase: mid_body (Connection drops mid-stream)
        if fault_injector.should_fault("mid_body"):
            self.latched_caids[caid] = True
            probe_result = self._execute_single_flight_probe(business_key, caid, probe_override_fn)
            return GatewayExecutionResult(
                scenario_id=scenario_id,
                gateway_disposition="EFFECT_INDETERMINATE",
                wire_event=fault_injector.wire_event,
                retry_safe=False,
                latch_engaged=True,
                probe_reconciliation=probe_result,
                target_ground_truth="NOT_FOUND",
                commit_count=self.target_ledger.get_commit_count(business_key),
                attributes={"aeib.caid": caid},
                telemetry=telemetry,
                outcome="OUTCOME_INDETERMINATE",
                effect_status="NOT_FOUND",
                retry_reason="uncertainty_latched",
                release_authorization="not_provided"
            )

        # Target processes and commits mutation
        telemetry.target_received = datetime.now(timezone.utc).isoformat()
        self.target_ledger.commit_mutation(business_key, payload, idempotency_key=idempotency_key)
        telemetry.target_commit_time = datetime.now(timezone.utc).isoformat()

        # 4. Phase: post_commit / post_click / post_response (Transport drop after commit)
        for post_phase in ("post_commit", "post_click", "post_response"):
            if fault_injector.should_fault(post_phase):
                self.latched_caids[caid] = True
                probe_result = self._execute_single_flight_probe(business_key, caid, probe_override_fn)
                attributes = {"aeib.caid": caid}
                disposition = "EFFECT_INDETERMINATE"
                outcome = "OUTCOME_INDETERMINATE"
                retry_reason = "uncertainty_latched"
                if probe_result == "RECONCILIATION_CONFLICT":
                    disposition = "RECONCILIATION_CONFLICT"
                    outcome = "OUTCOME_CONFLICT"
                    retry_reason = "probe_conflict_frozen"
                    attributes["release_status"] = "frozen_dual_control"
                elif probe_result == "PROBE_TIMEOUT":
                    disposition = "EFFECT_INDETERMINATE"
                    outcome = "OUTCOME_INDETERMINATE"
                    retry_reason = "probe_timeout_unresolved"
                    attributes["escalation"] = "operator_intervention_required"

                return GatewayExecutionResult(
                    scenario_id=scenario_id,
                    gateway_disposition=disposition,
                    wire_event=fault_injector.wire_event,
                    retry_safe=False,
                    latch_engaged=True,
                    probe_reconciliation=probe_result,
                    target_ground_truth="COMMITTED",
                    commit_count=self.target_ledger.get_commit_count(business_key),
                    attributes=attributes,
                    telemetry=telemetry,
                    outcome=outcome,
                    effect_status="COMMITTED",
                    retry_reason=retry_reason,
                    release_authorization="not_provided"
                )

        # Nominal Success (HTTP 200 / Confirmed)
        telemetry.response_received = True
        return GatewayExecutionResult(
            scenario_id=scenario_id,
            gateway_disposition="OUTCOME_CONFIRMED",
            wire_event="HTTP_200_OK",
            retry_safe=False,
            latch_engaged=False,
            probe_reconciliation="PROBE_NOT_ATTEMPTED",
            target_ground_truth="COMMITTED",
            commit_count=self.target_ledger.get_commit_count(business_key),
            attributes={"aeib.caid": caid},
            telemetry=telemetry,
            outcome="OUTCOME_CONFIRMED",
            effect_status="COMMITTED",
            retry_reason="effect_already_committed",
            release_authorization="not_provided"
        )

    def _execute_single_flight_probe(self, business_key: str, caid: str, probe_override_fn: Optional[Any] = None) -> str:
        """
        Executes exactly 1 single-flight out-of-band reconciliation probe
        against the target-side ledger.
        """
        # Programmatic isolation assertion: strictly query using business key string
        assert isinstance(business_key, str), "Probe query must strictly use business key string"
        self.probe_flights[caid] = self.probe_flights.get(caid, 0) + 1
        if probe_override_fn is not None:
            return probe_override_fn(business_key)
        record = self.target_ledger.probe_state(business_key)
        if record and record.get("status") == "COMMITTED":
            return "EFFECT_CONFIRMED_VIA_PROBE"
        return "EFFECT_ABSENT_VIA_PROBE"
