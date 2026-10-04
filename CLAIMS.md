# Claim Boundary Matrix & TEVV Evaluation Specification

**Project:** SovereignNexus / SMAOS (Sovereign Multi-Agent Operating System)  
**Specification:** Agent Execution Integrity Benchmark (AEIB) v1.0  
**Framework Alignment:** NIST AI RMF 1.0 (*Govern, Map, Measure, Manage*) | EU AI Act (Articles 12 & 14)  
**Status:** Locked & Authoritative  

---

## 1. Executive Summary & Epistemic Boundaries

This document defines the strict, mathematically falsifiable claim boundaries and Test, Evaluation, Verification, and Validation (TEVV) program for AEIB v1.0. 

All statements are evaluated under the declared in-memory simulation and local test harness models.

---

## 2. 3-Plane Architectural Boundary & TEVV Maturity Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                      3-PLANE ARCHITECTURAL MATURITY & TEVV MATRIX                           │
├───────────────────────────────┬───────────────────────────────┬─────────────────────────────┤
│ Architectural Plane           │ Current Implementation Status │ TEVV Verification Grounding │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ **Plane 1: Intent & Pre-**    │ **Conceptual / Future**       │ Payload-compatible schema;  │
│ **Dispatch Boundary (IBCTs)** │ Token parsing & Datalog rules │ Datalog evaluation engines  │
│                               │ are unbuilt in v1.0.          │ are out-of-scope for v1.0.  │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ **Plane 2: Decision Clearing**│ **Conceptual / Future**       │ Semantic alignment with     │
│ **& Obligation State (RAILS)**│ Multi-agent clearing finality;│ clearing finality; active   │
│                               │ obligations unbuilt in v1.0.  │ arbitration deferred.       │
├───────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ **Plane 3: Wire Settlement**  │ **Implemented & Audited Core**│ 32/32 zero-mock unit tests; │
│ **& Execution Finality (AEIB)│ 15+3 vector mapping contract, │ 500-episode fault harness   │
│                               │ CAID, & SCITT verifier.       │ (0/500 duplicate writes).   │
└───────────────────────────────┴───────────────────────────────┴─────────────────────────────┘
```

---

## 3. Explicit Falsifiable Invariants & TEVV Verification

1. **Deterministic Action Identity (CAID)**:
   $$\text{CAID} = H\Big(\text{Noun}_{\text{EntityID}} \parallel \text{Verb}_{\text{Action}} \parallel \text{JCS}(\text{Payload})\Big)$$
   *Verification:* Invariant against JSON key permutations, extra whitespace, and prompt rephrasings under RFC 8785 canonicalization.

2. **Zero Duplicate Mutation Invariant**:
   Under post-dispatch transport severance (`HTTP 504 Gateway Timeout`, `TCP RST`), the agent transitions to `DISPATCHED_UNCONFIRMED` and halts retry loops until out-of-band state polling confirms downstream commit state.
   *Verification:* Observed 0 duplicate writes across 500 deterministic fault-injection episodes (Arm 4; Rule-of-Three 95% CI upper bound $\le 0.60\%$ under the simulated fault model).

3. **Software Protection Safeguards (Conceptual Analogies)**:
   Software state-machine safeguards (probe-failure escalation, manual lockout latching, peer cancellation) adapt principles of selective fault isolation. They do not implement physical ANSI/IEEE/IEC relay standards or interoperate with substation hardware.

---

## 4. NIST AI RMF 1.0 Operational Mapping

* **Govern 1.2**: Explicit separation between open-core protocols (Zone 1 / Apache 2.0) and proprietary high-throughput adapters (Zone 2).
* **Map 1.5**: 18-vector physical transport fault classification mapping wire drops to unambiguous execution dispositions.
* **Measure 2.6**: Zero-mock empirical test suites enforcing exact state transitions without mock assertion shortcuts.
* **Manage 2.4**: Cryptographic SCITT receipts generating tamper-evident forensic records for post-incident auditability.
