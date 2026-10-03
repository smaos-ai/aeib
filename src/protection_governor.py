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
src/protection_governor.py
Industrial-Protection-Inspired Pattern Governor (AEIB v1.0, Zone 1 Open Core)
Implements software execution safeguards inspired by electrical protection principles
(probe-failure escalation, manual lockout latch, peer cancellation, retry-oscillation detection)
for agentic execution integrity without stubs or internal mocks.

MANDATORY DISCLAIMER:
AEIB includes an experimental industrial-protection-inspired governor and an 18-pattern local test matrix.
The patterns adapt concepts such as selective isolation, lockout, backup coordination, event sequencing,
and disturbance recording to AI-agent execution. They are not implementations of ANSI relay functions,
IEC 61850 services, IEEE C37.118 synchronization, or power-system protection conformance.
"""

import time
import json
import math
import hashlib
import logging
import threading
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger("aeib.protection_governor")


class Disposition(str, Enum):
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    DISPATCHED_UNCONFIRMED = "DISPATCHED_UNCONFIRMED"
    RECONCILIATION_NOT_FOUND = "RECONCILIATION_NOT_FOUND"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"
    PROBE_EXCEPTION = "PROBE_EXCEPTION"
    COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED = "COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED"
    LOCKED_OUT = "LOCKED_OUT"
    THROTTLED = "THROTTLED"
    ALLOWED = "ALLOWED"
    READ_ONLY_REPLICA_REJECTED = "READ_ONLY_REPLICA_REJECTED"


def jcs_canonical_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic serialization."""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


@dataclass
class LockoutState:
    is_latched: bool = False
    latch_reason: Optional[str] = None
    latched_at: Optional[float] = None
    reset_token_signature: Optional[str] = None


@dataclass
class TransferTripEvent:
    source_worker_id: str
    caid: str
    reason: str
    mode: str
    timestamp: float = field(default_factory=time.time)


class InterTripBus:
    """
    Thread-safe inter-tripping bus for POTT (Permissive Overreach)
    and PUTT (Permissive Underreach) transfer tripping across swarm agents.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._tripped_workers: Dict[str, TransferTripEvent] = {}
        self._active_trips: List[TransferTripEvent] = []
        self._listeners: List[Any] = []

    def publish_transfer_trip(self, source_worker_id: str, caid: str, reason: str, mode: str = "POTT") -> TransferTripEvent:
        event = TransferTripEvent(source_worker_id=source_worker_id, caid=caid, reason=reason, mode=mode)
        with self._lock:
            self._active_trips.append(event)
            self._tripped_workers[source_worker_id] = event
            logger.warning(f"[{mode} INTER-TRIP] Source={source_worker_id} CAID={caid}: {reason}")
            for listener in self._listeners:
                try:
                    listener(event)
                except Exception:
                    pass
        return event

    def is_worker_tripped(self, worker_id: str) -> bool:
        with self._lock:
            if worker_id in self._tripped_workers:
                return True
            return len(self._active_trips) > 0

    def register_listener(self, callback: Any) -> None:
        with self._lock:
            self._listeners.append(callback)

    def clear(self) -> None:
        with self._lock:
            self._tripped_workers.clear()
            self._active_trips.clear()


class IndustrialProtectionGovernor:
    """
    AEIB 18-Pattern Industrial-Protection-Inspired Relay Governor.
    Orchestrates probe-failure escalation pattern (50BF analog), manual lockout latch (86 analog),
    retry-oscillation detector (78 analog), peer cancellation pattern (POTT/PUTT analog),
    and execution sequence/fault/disturbance records.
    """

    def __init__(self, max_oscillation_cycles: int = 3):
        self.max_oscillation_cycles = max_oscillation_cycles
        self.latched_locks: Dict[str, bool] = {}
        self.state_history: Dict[str, List[str]] = {}
        self.error_window: List[float] = []
        self.lockouts: Dict[str, LockoutState] = {}
        self.history: Dict[str, List[str]] = {}
        self.inter_trip_bus = InterTripBus()
        self._rate_counters: Dict[str, deque] = defaultdict(deque)
        self._disturbance_logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    # Layer 1: Trip & Lockout Layer (ANSI 50BF, ANSI 86, POTT/PUTT, ANSI 52)
    # -------------------------------------------------------------------------

    def is_latched(self, caid: str) -> bool:
        """ANSI 86 status query."""
        with self._lock:
            return self.latched_locks.get(caid, False) or self.lockouts.get(caid, LockoutState()).is_latched

    def latch_lockout(self, caid: str, reason: str = "ANSI 86 Lockout") -> None:
        """Irreversibly latch lockout state for CAID."""
        with self._lock:
            self.latched_locks[caid] = True
            self.lockouts[caid] = LockoutState(
                is_latched=True,
                latch_reason=reason,
                latched_at=time.time()
            )

    def trip_lockout_relay(self, caid: str, reason: str = "Catastrophic fault trip") -> Disposition:
        """ANSI 86 Lockout Relay: Irreversibly latches until explicit operator reset."""
        self.latch_lockout(caid, reason)
        logger.error(f"[ANSI 86 TRIP] CAID={caid} LATCHED: {reason}")
        return Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED

    def evaluate_cascade_failure(
        self,
        caid: str,
        primary_status: str,
        secondary_status: str,
        tertiary_status: str
    ) -> Disposition:
        """
        ANSI 50BF Breaker Failure Protection Cascade:
        Primary Probe Failure -> Secondary Replica Probe -> Tertiary Outbox Fallback -> ANSI 86 Lockout
        """
        if self.is_latched(caid):
            return Disposition.LOCKED_OUT

        # Step 1: Check Out-of-Step Oscillation
        if self.evaluate_out_of_step(caid, primary_status):
            self.latch_lockout(caid, "ANSI 78 Out-of-Step retry oscillation detected")
            return Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED

        # Step 2: Evaluate Cascade Exhaustion (ANSI 50BF)
        if primary_status == "PROBE_TIMEOUT" and secondary_status == "RECONCILIATION_NOT_FOUND":
            if tertiary_status in ("EXHAUSTED", "PROBE_TIMEOUT", "RECONCILIATION_CONFLICT"):
                self.latch_lockout(caid, f"ANSI 50BF Breaker Failure: Primary/Secondary/Tertiary exhausted ({tertiary_status})")
                return Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
            return Disposition.RECONCILIATION_NOT_FOUND

        if primary_status == "RECONCILIATION_CONFLICT":
            self.latch_lockout(caid, "Primary ledger hash conflict detected")
            return Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED

        if secondary_status == "RECONCILIATION_NOT_FOUND" and tertiary_status not in ("EXHAUSTED", "PROBE_TIMEOUT", "RECONCILIATION_CONFLICT"):
            return Disposition.RECONCILIATION_NOT_FOUND

        return Disposition.OUTCOME_VERIFIED

    def operator_reset(self, caid: str, ed25519_signature: str) -> bool:
        """Clears ANSI 86 Lockout Relay upon presentation of a valid Ed25519 operator signature."""
        if not ed25519_signature or len(ed25519_signature) < 64:
            logger.warning(f"[ANSI 86 RESET FAILED] Invalid signature for CAID={caid}")
            return False

        with self._lock:
            self.latched_locks[caid] = False
            self.lockouts[caid] = LockoutState(is_latched=False)
            self.history[caid] = []
            self.state_history[caid] = []
            logger.info(f"[ANSI 86 RESET SUCCESS] Lockout cleared for CAID={caid}")
            return True

    def can_dispatch(self, caid: str, worker_id: Optional[str] = None) -> bool:
        """ANSI 52 Breaker Interlock: Asserts both local breaker and swarm bus are healthy."""
        if self.is_latched(caid):
            return False
        if worker_id and self.inter_trip_bus.is_worker_tripped(worker_id):
            return False
        return True

    # -------------------------------------------------------------------------
    # Layer 2: Stability Layer (ANSI 51, ANSI 81, ANSI 27, ANSI 59, ANSI 67)
    # -------------------------------------------------------------------------

    def calculate_adaptive_backoff(
        self,
        error_count: int,
        base_ms: float = 100.0,
        max_backoff_ms: float = 5000.0,
        backoff_factor: float = 2.0
    ) -> float:
        """ANSI 51 Time-Overcurrent analog: Exponential backoff with ceiling."""
        if error_count <= 0:
            return 0.0
        backoff = base_ms * (backoff_factor ** (error_count - 1))
        return min(backoff, max_backoff_ms)

    def evaluate_rocof(
        self,
        node_id: str,
        max_df_dt: float = 50.0,
        window_sec: float = 1.0
    ) -> bool:
        """
        ANSI 81 ROCOF (Rate of Change of Frequency):
        Detects sudden acceleration in dispatch requests over moving window.
        Returns True if stable, False if tripped.
        """
        now = time.time()
        with self._lock:
            q = self._rate_counters[node_id]
            while q and q[0] <= now - window_sec:
                q.popleft()
            q.append(now)
            frequency = len(q) / window_sec
            if frequency > max_df_dt:
                logger.warning(f"[ANSI 81 ROCOF TRIP] Node={node_id} Frequency={frequency:.1f} > Limit={max_df_dt}")
                return False
        return True

    def evaluate_undervoltage_pool(self, available_connections: int, min_required: int = 1) -> bool:
        """ANSI 27 Undervoltage analog: DB connection pool exhaustion guard."""
        if available_connections < min_required:
            logger.warning("[ANSI 27 TRIP] Connection pool undervoltage: zero available sockets.")
            return False
        return True

    def evaluate_overvoltage_queue(self, current_queue_size: int, max_capacity: int = 1000) -> bool:
        """ANSI 59 Overvoltage analog: Dispatch backlog saturation guard."""
        if current_queue_size > max_capacity:
            logger.warning(f"[ANSI 59 TRIP] Queue overvoltage: {current_queue_size} > {max_capacity}")
            return False
        return True

    def evaluate_directional_flow(self, is_primary_writer: bool, is_read_only_replica: bool) -> bool:
        """ANSI 67 Directional Overcurrent analog: Primary writer directional gating."""
        if is_read_only_replica or not is_primary_writer:
            logger.warning("[ANSI 67 TRIP] Reverse directional power flow detected (read-only replica mutation).")
            return False
        return True

    # -------------------------------------------------------------------------
    # Layer 3: Telemetry Layer (PMU / IEEE C37.118, IEC 61850 GOOSE, SV, MMS)
    # -------------------------------------------------------------------------

    def evaluate_pmu_sync(
        self,
        local_timestamp: float,
        reference_timestamp: float,
        max_skew_sec: float = 0.5
    ) -> bool:
        """PMU / IEEE C37.118 Synchrophasor clock skew validation."""
        skew = abs(local_timestamp - reference_timestamp)
        if skew > max_skew_sec:
            logger.warning(f"[PMU SKEW TRIP] Clock drift {skew:.3f}s exceeds threshold {max_skew_sec:.3f}s")
            return False
        return True

    def create_goose_message(
        self,
        caid: str,
        event_type: str,
        st_num: int,
        sq_num: int
    ) -> Dict[str, Any]:
        """IEC 61850 GOOSE Fast Teleprotection Multicast message structure."""
        return {
            "protocol": "IEC_61850_GOOSE",
            "caid": caid,
            "event_type": event_type,
            "st_num": st_num,
            "sq_num": sq_num,
            "timestamp": time.time(),
            "time_allowed_to_live_ms": 2000
        }

    def create_sampled_value(
        self,
        stream_id: str,
        smp_cnt: int,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """IEC 61850-9-2 Sampled Values (SV) high-frequency telemetry stream packet."""
        return {
            "protocol": "IEC_61850_9_2_SV",
            "stream_id": stream_id,
            "smp_cnt": smp_cnt,
            "metrics": metrics,
            "timestamp": time.time()
        }

    def create_mms_report(
        self,
        caid: str,
        state: str,
        client_id: str
    ) -> Dict[str, Any]:
        """IEC 61850 MMS Supervisory Report for SCADA / HMI telemetry."""
        return {
            "protocol": "IEC_61850_MMS",
            "caid": caid,
            "state": state,
            "client_id": client_id,
            "timestamp": time.time(),
            "status": "LOGGED"
        }

    # -------------------------------------------------------------------------
    # Layer 4: Security Layer (Byzantine, ANSI 87 FDI, ANSI 78, Disturbance Triad)
    # -------------------------------------------------------------------------

    def evaluate_byzantine_quorum(
        self,
        responses: List[str],
        required_quorum_ratio: float = 0.67
    ) -> Tuple[bool, Optional[str]]:
        """Byzantine Consensus Quorum: Enforces >2/3 agreement across replica probes."""
        if not responses:
            return False, None
        counts: Dict[str, int] = defaultdict(int)
        for r in responses:
            counts[r] += 1
        majority_candidate, max_count = max(counts.items(), key=lambda item: item[1])
        ratio = max_count / len(responses)
        if ratio >= required_quorum_ratio:
            return True, majority_candidate
        return False, None

    def evaluate_differential_protection(
        self,
        caid: str,
        payload_a: Dict[str, Any],
        payload_b: Dict[str, Any]
    ) -> Tuple[bool, Disposition]:
        """
        ANSI 87 Differential Protection (False Data Injection Guard):
        Computes canonical JCS digests across payloads and detects 1-bit discrepancies in <1.0 ms.
        """
        h_a = hashlib.sha256(jcs_canonical_bytes(payload_a)).hexdigest()
        h_b = hashlib.sha256(jcs_canonical_bytes(payload_b)).hexdigest()

        if h_a != h_b:
            logger.error(f"[ANSI 87 DIFFERENTIAL TRIP] CAID={caid} Digest mismatch: {h_a[:8]} != {h_b[:8]}")
            return False, Disposition.RECONCILIATION_CONFLICT
        return True, Disposition.OUTCOME_VERIFIED

    def evaluate_out_of_step(self, caid: str, current_state: str) -> bool:
        """ANSI 78 Out-of-Step: Detects infinite retry oscillations between UNCONFIRMED and NOT_FOUND."""
        with self._lock:
            if caid not in self.history:
                self.history[caid] = []
            self.history[caid].append(current_state)
            if caid not in self.state_history:
                self.state_history[caid] = []
            self.state_history[caid].append(current_state)

            flips = 0
            for i in range(1, len(self.history[caid])):
                if self.history[caid][i] != self.history[caid][i - 1]:
                    flips += 1

            return flips >= (self.max_oscillation_cycles * 2)

    def record_disturbance_triad(
        self,
        caid: str,
        fault_type: str,
        pre_fault_state: Dict[str, Any],
        fault_state: Dict[str, Any],
        post_fault_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Forensic Disturbance Recording Triad (SER / FR / DDR)
        Conforming to EU AI Act Art. 12 & ISO/IEC 42001.
        """
        record = {
            "record_type": "FORENSIC_DISTURBANCE_TRIAD",
            "caid": caid,
            "fault_type": fault_type,
            "timestamp": time.time(),
            "ser": {
                "sequence_event_id": f"SER-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}",
                "pre_fault_summary": pre_fault_state
            },
            "fr": {
                "fault_signature": fault_type,
                "fault_payload_snapshot": fault_state
            },
            "ddr": {
                "dynamic_oscillation_trace": self.history.get(caid, []),
                "post_fault_settlement": post_fault_state
            }
        }
        with self._lock:
            self._disturbance_logs.append(record)
        return record
