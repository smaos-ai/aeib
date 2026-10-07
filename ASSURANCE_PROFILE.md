# AEIB Assurance Profile

**Specification:** Agent Evidence Interlock Boundary (AEIB v0.4.0)  
**Status:** Review Candidate & Reproducibility Package  
**Epistemic Scope:** Evaluated under declared synthetic fault conditions. Does not claim universal exactly-once execution or turnkey regulatory compliance.

---

## 1. Operational Invariants & Fail-Closed Behavior

The following matrix documents observed system behavior under anomalous operating conditions:

| System Subsystem | Disturbance / Failure Condition | Interlock Reaction | Resulting State |
| :--- | :--- | :--- | :--- |
| **Transport Layer (L7a)** | HTTP 504 Gateway Timeout / TCP RST | Drops speculation; sets `retry_safe: false` | `DISPATCHED_UNCONFIRMED` |
| **Probe Layer (L7b)** | Probe unavailable or replica lag mismatch | Refuses speculative clearance; halts retries | `PROBE_OUTAGE_HOLD` |
| **Disposition Engine (L7c)** | Upstream model hypothesis contradicts wire fact | Wire observation overrides model claim | `ImmutableFactViolationError` |
| **Schema Gatekeeper** | Tool parameter mutated post-approval | Rejects dispatch; halts execution | `MCP_SCHEMA_MUTATION_REJECTED` |
| **Tycho Structural Gate** | Structural verdict absent or un-evaluated | ANSI 86 latch engaged; execution halted | `StructuralVerificationError` |
| **Cryptographic Layer (L8)** | Corrupted payload byte or signature bit | Rejects receipt; raises verification exception | `InvalidSignature` |
| **State Continuity** | Ambiguous transport followed by process restart | Out-of-context store preserves lockout | `retry_safe: false` latched |
| **Reconciliation Engine** | Authoritative probe reports missing side effect | Classifies transaction as unfulfilled | `RECONCILIATION_NOT_FOUND` |
| **Dual-Control Gate** | Missing multi-party release authorization | Releases hold token; blocks settlement | `release_auth: not_provided` |
| **Concurrent Stampede** | 50 concurrent workers hit HTTP 504 on same effect | Coalesces to 1 upstream probe request | Coalesced resolution |

---

## 2. Defined Boundaries of Proof

1. **Probe Concurrency**: Tests prove exactly one upstream probe request was issued per effect in the tested concurrency scenario. They do not prove that upstream provider databases are uncompromised or bug-free.
2. **Duplicate Suppression**: A local ledger and retry lockout confirm that no duplicate retry was issued by the controlled gateway in the tested scenario. They do not prove that remote APIs did not experience duplicate side effects prior to gateway observation.
3. **Regulatory Context**: AEIB provides immutable evidence logs, timestamps, and schema definitions. It serves as technical evidence input; it does not itself constitute regulatory certification or compliance under DORA Article 17 or EU AI Act Article 50.
