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
macp — Multi-Agent Coordination Primitives
================================================================================
Foundational distributed systems invariants for multi-agent LLM systems:
- Gap 1: Heartbeat & Lease-Timeout Management (HeartbeatLeaseTracker)
- Gap 2: Per-Profile Circuit Breakers (CircuitBreaker)
- Gap 3: Idempotent Task Dispatch & Disk Persistence (IdempotentTaskDispatcher)
- Gap 4: Zero-LLM Deterministic BFT Provenance Verification (BFTProvenanceValidator)
- Gap 5: Quorum Consensus Resolution with Indeterminate Fallback (QuorumConsensusResolver)
- Gap 6: Bounded Semaphore Backpressure & Fsync'd Ledger (BackpressureLimiter)
"""

from macp.backpressure import BackpressureLimiter
from macp.bft import BFTProvenanceValidator, SemanticValidationError
from macp.consensus import QuorumConsensusResolver
from macp.coordinator import HardenedCoordinator
from macp.idempotency import IdempotentTaskDispatcher, encode_jcs
from macp.resilience import CircuitBreaker, HeartbeatLeaseTracker

__version__ = "0.1.0"
__all__ = [
    "BackpressureLimiter",
    "BFTProvenanceValidator",
    "CircuitBreaker",
    "HardenedCoordinator",
    "HeartbeatLeaseTracker",
    "IdempotentTaskDispatcher",
    "QuorumConsensusResolver",
    "SemanticValidationError",
    "encode_jcs",
]
