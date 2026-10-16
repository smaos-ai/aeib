# `macp` — Multi-Agent Coordination Primitives

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Determinism](https://img.shields.io/badge/provenance-RFC_8785_JCS-green.svg)](https://www.rfc-editor.org/rfc/rfc8785)

> *"Multi-Agent Systems Have a Distributed Systems Problem"*  
> — Christopher Meiklejohn (March 2026)

Existing multi-agent frameworks (LangChain, CrewAI, AutoGen, LangGraph) excel at prompt chaining, router selection, and graph definitions, but lack core distributed systems coordination primitives. When subagents stall, crash mid-dispatch, or return ungrounded responses, naive orchestrators burn tokens on duplicate dispatches, hallucinate consensus, or deadlock on lost heartbeats.

`macp` provides standalone, lightweight distributed systems primitives for multi-agent LLM systems with **zero mandatory external runtime dependencies**.

---

## 🏛️ The 6 Primitives

| Primitive | Class | Operational Invariant & Failure Mode Prevention |
| :--- | :--- | :--- |
| **Gap 1: Heartbeats** | `HeartbeatLeaseTracker` | Detects hung/crashed subagents; transitions stalled dispatches to `INDETERMINATE` (`HEARTBEAT_TIMEOUT`). |
| **Gap 2: Circuit Breakers** | `CircuitBreaker` | Tracks per-profile failure counts; short-circuits repeated failures (`CIRCUIT_BREAKER_OPEN:<profile>`) to protect token budgets. |
| **Gap 3: Idempotency (EO-1)** | `IdempotentTaskDispatcher` | Persists task intent prior to dispatch; computes RFC 8785 JCS `spec_caid`; serves cached disk results on re-dispatch. |
| **Gap 4: BFT Provenance** | `BFTProvenanceValidator` | Zero-LLM deterministic disk verification: validates file existence, line bounds, and SHA-256 digests without extra LLM token burn. |
| **Gap 5: Quorum Consensus** | `QuorumConsensusResolver` | Computes strict 2-of-3 majority over JCS finding digests; split ties latch to `INDETERMINATE` (`NO_CONSENSUS_QUORUM`). |
| **Gap 6: Backpressure** | `BackpressureLimiter` | Bounded semaphore concurrency control and tamper-evident append-only telemetry synchronized via `os.fsync`. |

---

## 🚀 Quickstart

```python
from pathlib import Path
from macp import HardenedCoordinator

# Initialize coordinator with persistent disk storage and bounded concurrency
coordinator = HardenedCoordinator(
    state_dir=Path("./runtime_state"),
    repo_root=Path("."),
    max_concurrent=4,
    heartbeat_timeout_sec=90.0,
)

# Define worker callback
def run_researcher(task_id: str, spec: dict) -> str:
    # Subagent executes work and returns strictly formatted JSON
    return '''{
        "status": "COMPLETED",
        "scope_reviewed": ["config/ownership.yaml"],
        "verified_findings": [
            {"claim": "Depth-1 enforced", "source": "config/ownership.yaml:10"}
        ],
        "not_established": [],
        "summary_for_orchestrator": "Observed Depth-1 nesting rule."
    }'''

# Dispatch task with automatic idempotency, circuit breakers, and BFT verification
result = coordinator.dispatch_task(
    profile="aeib-researcher",
    task_id="task-001",
    spec={"scope": "ownership"},
    worker_fn=run_researcher,
)

print(f"Status: {result['status']}")
```

---

## 🛡️ Standalone Modules

* `macp.resilience`: `CircuitBreaker` and `HeartbeatLeaseTracker`.
* `macp.idempotency`: `encode_jcs` (RFC 8785) and `IdempotentTaskDispatcher`.
* `macp.bft`: `BFTProvenanceValidator` and `SemanticValidationError`.
* `macp.consensus`: `QuorumConsensusResolver`.
* `macp.backpressure`: `BackpressureLimiter`.
* `macp.coordinator`: `HardenedCoordinator`.

---

## 📄 License

Apache License 2.0. See LICENSE for details.
