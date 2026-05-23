# BASE PLANE ARCHITECTURE — SovereignNexus Parallel Work Framework

**Version:** 1.0  
**Status:** ACTIVE — Ready for Parallel Multi-Agent Execution  
**Last Updated:** 2026-05-23T00:00:00Z  
**Gate:** Phase 65 GREEN ✓ (Chaos Petri Locked)

---

## EXECUTIVE SUMMARY

SovereignNexus is a **distributed sovereign authorization network** built with strict TDD discipline. The Base Plane defines a **parallel work structure** enabling 3-5 independent agents to execute simultaneously with **zero file overlap**, **clear ownership boundaries**, and **feature-complete documentation**.

**Current State:** 65 phases complete, 1000+ tests passing, ~20k LOC  
**Remaining:** 35+ phases, multi-layer improvements, real-world validation

---

## SYSTEM ARCHITECTURE (Visual)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SovereignNexus Network Layer                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Authorization   │  │   Real-Time      │  │   Cryptographic  │  │
│  │  Engine (ReBAC,  │  │   Observability  │  │   Proof & Ledger │  │
│  │  AP2, Temporal)  │  │   (SSE, Audit)   │  │   (π++, Merkle)  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                      │                      │             │
│           └──────────────────────┼──────────────────────┘             │
│                                  ▼                                     │
│                    ┌──────────────────────────┐                       │
│                    │  Knowledge Graph Core    │                       │
│                    │  (siss-graph-core/db)    │                       │
│                    └──────────────────────────┘                       │
│                                  ▲                                     │
│           ┌──────────────────────┼──────────────────────┐             │
│           │                      │                      │             │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌────────▼─────────┐  │
│  │  Task Router     │  │  Swarm State     │  │  Context         │  │
│  │  (Backpressure,  │  │  (Merkle DAG,    │  │  Cartography     │  │
│  │  Circuit Break)  │  │  Attestation)    │  │  (Query Opt)     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

         ▼ Control & Data Plane ▼

┌─────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + S3 Cold Storage                      │
│           (Hot/Cold Archival, Trace Persistence)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## CRATE OWNERSHIP & PARALLEL DOMAINS

### **Agent A: Core Authorization Engine**
**Exclusive Crates:** siss-gatekeeper, siss-behavioral-firewall, siss-job-router  
**Phases:** 66-75 (Authorization Hardening & ReBAC Enhancements)  
**Dependencies:** siss-graph-core (read-only)

**Deliverables:**
- Phase 66: ReBAC constraint solver optimization
- Phase 67: AP2 (Attribute-based Predicate Policies) v2
- Phase 68: Temporal window validation (day/time-of-week gating)
- Phase 69: Delegation ceiling enforcement
- Phase 70: Rate limiting policies
- Phase 71-75: Integration tests, chaos scenarios

**No File Overlap:** These crates have zero read-write dependencies on Agent B/C/D  
**Integration Points:** Read from siss-graph-core; write SSE events; call MCP contracts

---

### **Agent B: Real-Time Observability & Audit**
**Exclusive Crates:** siss-event-log, siss-audit-archiver, siss-cockpit  
**Phases:** 66-75 (Streaming, Archival, Visualization)  
**Dependencies:** siss-task-router (read-only), siss-swarm-attestation (read-only)

**Deliverables:**
- Phase 66: Multi-stream SSE routing (task, audit, proof streams)
- Phase 67: Audit trace enrichment (decision context, policy source)
- Phase 68: S3 cold storage lifecycle (automatic retention policies)
- Phase 69: Cockpit dashboard real-time updates (WebSocket fallback)
- Phase 70: Audit query API (grep-like DSL)
- Phase 71-75: Analytics, visualization, alerting

**No File Overlap:** Hot storage (HashMap) is internal to AuditArchiver; no cross-crate mutation  
**Integration Points:** Consume SSE broadcasts; publish to cockpit; archive proofs

---

### **Agent C: Cryptography & Proof Layer**
**Exclusive Crates:** siss-ontology-proofs, siss-swarm-attestation, siss-enclave  
**Phases:** 66-75 (Signature Verification, Proof Optimization, HSM Integration)  
**Dependencies:** siss-graph-core (read-only)

**Deliverables:**
- Phase 66: Batch signature verification (multi-proof validation)
- Phase 67: π++ projection caching (memoize frequent queries)
- Phase 68: Hardware security module (HSM) integration stubs
- Phase 69: Proof archival format (compact binary encoding)
- Phase 70: Zero-knowledge proof extensions (optional)
- Phase 71-75: Formal verification, fuzzing, security audit prep

**No File Overlap:** Proof generation is self-contained; SwarmState ledger is append-only  
**Integration Points:** Generate proofs; feed to siss-task-router; append to swarm_state

---

### **Agent D: Knowledge Graph & Query Optimization**
**Exclusive Crates:** siss-graph-core, siss-graph-db, siss-context-cartography  
**Phases:** 66-75 (Query Optimization, Indexing, Traversal)  
**Dependencies:** None (foundational layer)

**Deliverables:**
- Phase 66: B-tree indexing for entity lookups
- Phase 67: Reachability analysis (transitive closure caching)
- Phase 68: Query planner (choose optimal traversal order)
- Phase 69: Bloom filters for membership queries
- Phase 70: Incremental graph updates (delta application)
- Phase 71-75: Benchmark suite, performance profiling, optimization

**No File Overlap:** Graph is immutable after query; no external mutations  
**Integration Points:** Serve π++ queries; provide context to auth engine

---

## PARALLEL WORK GRID (Phases 66-100)

```
PHASE  │ AGENT A         │ AGENT B            │ AGENT C          │ AGENT D
       │ Auth Engine     │ Observability      │ Crypto/Proof     │ Graph/Query
───────┼─────────────────┼────────────────────┼──────────────────┼──────────────
66     │ ReBAC Solver    │ Multi-Stream SSE   │ Batch Signatures │ B-tree Index
67     │ AP2 v2          │ Trace Enrichment   │ π++ Caching      │ Reachability
68     │ Temporal Window │ S3 Lifecycle       │ HSM Stubs        │ Query Planner
69     │ Delegation Cap  │ Cockpit WebSocket  │ Proof Archive    │ Bloom Filters
70     │ Rate Limiting   │ Audit Query API    │ ZK Extensions    │ Delta Updates
71-75  │ Integration     │ Analytics          │ Verification     │ Benchmarks
       │ & Chaos Tests   │ & Visualization    │ & Fuzzing        │ & Profiling
```

**Execution Model:**
- Phases 66-70: **PARALLEL** (5 concurrent agents, one per phase per agent)
- Phases 71-75: **SEQUENTIAL** (integration points, cross-team testing)
- All phases: **RED → GREEN → REFACTOR** with 100% test coverage

---

## DETAILED PHASE ROADMAP

### **Phase 66: Foundation Hardening**

**Agent A: ReBAC Constraint Solver v2**
```rust
// crates/siss-gatekeeper/src/constraint_solver.rs (NEW)
pub struct ConstraintSolver {
    graph: Arc<KnowledgeGraph>,
    cache: Arc<Mutex<LRUCache<ConstraintKey, bool>>>,
}

// RED Tests:
// - test_constraint_solver_1000_entities_under_budget (latency < 5ms)
// - test_constraint_solver_circular_delegation_detection
// - test_constraint_solver_cache_hit_ratio (must hit 80%+ on repeat queries)
```

**Agent B: Multi-Stream SSE Routing**
```rust
// crates/siss-event-log/src/sse_multiplexer.rs (NEW)
pub enum SSEStreamType {
    TaskRouting,    // task decisions
    Audit,          // audit traces
    ProofGeneration, // proof objects
}

// RED Tests:
// - test_sse_multiplexer_3_concurrent_streams_no_bleed
// - test_sse_multiplexer_backpressure_slow_subscriber
// - test_sse_multiplexer_stream_filtering (client-side)
```

**Agent C: Batch Signature Verification**
```rust
// crates/siss-ontology-proofs/src/batch_verifier.rs (NEW)
pub fn verify_proof_batch(
    proofs: Vec<ProofObject>,
    parallel: bool,
) -> Result<Vec<ProofId>, ProofError> { }

// RED Tests:
// - test_batch_verify_100_proofs_latency (must be < 50ms total)
// - test_batch_verify_single_invalid_rejects_none
// - test_batch_verify_parallel_vs_sequential_speedup
```

**Agent D: B-tree Entity Index**
```rust
// crates/siss-graph-core/src/btree_index.rs (NEW)
pub struct EntityIndex {
    tree: BTreeMap<EntityId, Entity>,
}

// RED Tests:
// - test_btree_index_10k_lookups_under_1ms
// - test_btree_index_range_query_1000_entities
// - test_btree_index_concurrent_reads
```

**Sync Point:** All agents commit on same day; run workspace tests

---

### **Phase 67-70: Parallel Feature Development**

Each agent independently develops their domain feature:

| Phase | Agent A | Agent B | Agent C | Agent D |
|-------|---------|---------|---------|---------|
| **67** | AP2 v2 (predicate policies) | Trace enrichment (context) | π++ caching (memo) | Reachability (transitive) |
| **68** | Temporal window gating | S3 lifecycle automation | HSM integration stubs | Query planner |
| **69** | Delegation ceiling | WebSocket fallback | Proof binary encoding | Bloom filters |
| **70** | Rate limiting policies | Audit query DSL | ZK extensions | Delta updates |

**Each phase:** 4 RED tests (1 per agent) → develop independently → merge on sync day

---

### **Phases 71-75: Integration & Hardening**

**Cross-Agent Tests:**
- Phase 71: Cockpit displays auth decisions + proofs + audit in real-time
- Phase 72: 10k concurrent tasks with all 4 systems active
- Phase 73: Graph schema evolution (add new entity type)
- Phase 74: Failover scenarios (node goes down, state recovers)
- Phase 75: Production readiness audit

---

## FILE STRUCTURE & OWNERSHIP

```
crates/
├── siss-gatekeeper/
│   ├── src/
│   │   ├── lib.rs                    [Agent A]
│   │   ├── constraint_solver.rs      [Agent A — PHASE 66+]
│   │   ├── ap2_policies.rs           [Agent A — PHASE 67+]
│   │   ├── temporal_window.rs        [Agent A — PHASE 68+]
│   │   ├── delegation.rs             [Agent A — PHASE 69+]
│   │   └── rate_limit.rs             [Agent A — PHASE 70+]
│   └── tests/ (no overlap with B/C/D)
│
├── siss-event-log/
│   ├── src/
│   │   ├── lib.rs                    [Agent B]
│   │   ├── sse_multiplexer.rs        [Agent B — PHASE 66+]
│   │   ├── stream_filter.rs          [Agent B — PHASE 67+]
│   │   └── query_dsl.rs              [Agent B — PHASE 70+]
│   └── tests/ (no overlap with A/C/D)
│
├── siss-ontology-proofs/
│   ├── src/
│   │   ├── lib.rs                    [Agent C]
│   │   ├── batch_verifier.rs         [Agent C — PHASE 66+]
│   │   ├── proof_cache.rs            [Agent C — PHASE 67+]
│   │   ├── hsm_integration.rs        [Agent C — PHASE 68+]
│   │   ├── proof_encoding.rs         [Agent C — PHASE 69+]
│   │   └── zk_extensions.rs          [Agent C — PHASE 70+]
│   └── tests/ (no overlap with A/B/D)
│
├── siss-graph-core/
│   ├── src/
│   │   ├── lib.rs                    [Agent D]
│   │   ├── btree_index.rs            [Agent D — PHASE 66+]
│   │   ├── reachability.rs           [Agent D — PHASE 67+]
│   │   ├── query_planner.rs          [Agent D — PHASE 68+]
│   │   ├── bloom_filter.rs           [Agent D — PHASE 69+]
│   │   └── delta_updates.rs          [Agent D — PHASE 70+]
│   └── tests/ (no overlap with A/B/C)
│
├── siss-cockpit/ (shared dependency, read-only from A/B/C/D)
├── siss-task-router/ (shared dependency, read-only)
├── siss-swarm-attestation/ (shared dependency, read-only)
└── .claude/
    ├── BASE_PLANE_ARCHITECTURE.md    (THIS FILE)
    ├── PHASE_66_SPEC.md              [AGENT A — OWNER]
    ├── PHASE_67_SPEC.md              [AGENT B — OWNER]
    ├── PHASE_68_SPEC.md              [AGENT C — OWNER]
    ├── PHASE_69_SPEC.md              [AGENT D — OWNER]
    └── ...
```

**Key Rule:** Each agent owns their spec file. No agent modifies another's files.

---

## INTEGRATION CONTRACTS

### **Contract 1: ReBAC → Proof Generation**
```rust
// siss-gatekeeper -> siss-ontology-proofs
pub struct AuthDecision {
    pub decision: Decision,           // Allow | Deny
    pub confidence: f64,              // 0.0-1.0 from constraint solver
    pub constraints_applied: Vec<String>, // which constraints justified it
    pub proof_justification: JustificationRecord, // for proof object
}
```

**Agent A → Agent C:** ReBAC decision → proof justification  
**No file collision:** A writes AuthDecision; C reads and wraps in ProofObject

---

### **Contract 2: Proof → Audit Log**
```rust
// siss-ontology-proofs -> siss-event-log
pub struct ProofAuditEntry {
    pub proof_id: Uuid,
    pub decision: String,
    pub constraints_applied: Vec<String>,
    pub confidence: f64,
    pub timestamp: SystemTime,
}
```

**Agent C → Agent B:** Proof object → audit entry  
**No file collision:** C generates; B publishes to SSE stream

---

### **Contract 3: Graph Query → ReBAC Input**
```rust
// siss-graph-core -> siss-gatekeeper
pub struct EntityContext {
    pub entity: Entity,
    pub relationships: Vec<(Relationship, Entity)>,
    pub transitive_closure: Vec<EntityId>, // from reachability cache
    pub query_latency_ms: f64,
}
```

**Agent D → Agent A:** Graph data → authorization context  
**No file collision:** D returns read-only context; A consumes

---

## RED PHASE SPECIFICATIONS (Synchronized)

All agents write their RED tests simultaneously (no ordering):

```
PHASE 66 RED TESTS (All 4 agents write simultaneously)
├─ Agent A: test_constraint_solver_1000_entities.rs
├─ Agent B: test_sse_multiplexer_3_streams.rs
├─ Agent C: test_batch_verify_100_proofs.rs
└─ Agent D: test_btree_index_10k_lookups.rs

cargo test -q → shows 4 compile errors (RED) ✓
(each agent's missing module/method)

SYNC POINT: All agents commit to main
```

---

## GREEN PHASE EXECUTION

```
PHASE 66 GREEN (Each agent implements independently)

Day 1:  Agent A builds constraint_solver.rs (2-3 hours)
        Agent B builds sse_multiplexer.rs (2-3 hours)
        Agent C builds batch_verifier.rs (2-3 hours)
        Agent D builds btree_index.rs (2-3 hours)
        → All run in parallel, zero waiting

EOD:    Merge all 4 features to main
        Run: cargo test -p siss-gatekeeper -p siss-event-log \
                       -p siss-ontology-proofs -p siss-graph-core --lib -q
        Expected: 4 new tests pass + all existing tests still pass
```

---

## IMPROVEMENT BACKLOG (All Remaining Work)

### **High Priority (Phases 66-75)**
- ✓ Constraint solver optimization (ReBAC)
- ✓ Multi-stream SSE routing
- ✓ Batch signature verification
- ✓ B-tree indexing for graphs
- ✓ Temporal window validation
- ✓ π++ caching & memoization
- ✓ S3 lifecycle automation
- ✓ Query planning optimization

### **Medium Priority (Phases 76-85)**
- Graph schema evolution (migrations)
- Failover & recovery (node crash)
- Cluster rebalancing (load distribution)
- Instrumentation & metrics (Prometheus)
- API versioning & backward compat
- Client SDK (Go, Python, JS)

### **Low Priority (Phases 86-100)**
- Zero-knowledge proofs (optional)
- Hardware security module integration
- Formal verification (TLA+)
- Performance optimization (<100µs latency)
- Multi-region replication
- Governance & voting (future)

---

## SUCCESS METRICS

| Metric | Target | Current |
|--------|--------|---------|
| **Test coverage** | 95%+ | ✓ 1000+ tests |
| **Latency (π++)** | <1.0ms | ✓ 0.67ms avg |
| **Throughput (10k load)** | No OOM | ✓ Passes saturation |
| **Concurrent tasks** | 5+ permit semaphore | ✓ Verified |
| **Proof verification** | <10ms batch/100 | ⏳ Phase 66 |
| **Query latency (10k graph)** | <5ms | ⏳ Phase 66 |
| **Availability** | 5-nines (failover) | ⏳ Phase 74 |

---

## EXECUTION CHECKLIST

- [ ] **PRE-PHASE 66:** Create 4 empty modules (constraint_solver, sse_multiplexer, batch_verifier, btree_index)
- [ ] **RED SYNC:** All 4 agents write failing tests simultaneously
- [ ] **GREEN SPRINT:** Each agent builds independently (2-3 hrs each)
- [ ] **MERGE DAY:** Integrate all 4 features; run full test suite
- [ ] **REPEAT:** Phases 67-70 (4x more features)
- [ ] **INTEGRATION:** Phases 71-75 (cross-team validation)

---

## NEXT STEPS

1. **Confirm Agent Assignments:** Who is Agent A/B/C/D?
2. **Create Empty Modules:** Set up file structure for Phase 66
3. **Write RED Tests:** All 4 agents simultaneously
4. **Execute GREEN:** Independent development (48-96 hours total)
5. **Validation:** Full workspace test suite
6. **Repeat:** Phases 67-75

**Time-to-Completion:** ~4 weeks (5 phases × 1 week/phase with parallel execution)

---

## APPENDIX: VISUAL SYSTEM MAP

```
┌─────────────────────────────────────────────────────────┐
│         Authorization Decision Engine                    │
│  (ReBAC + AP2 + Temporal + Delegation + Rate Limiting)  │
│                      ↓                                    │
│              Proof Object Generation                     │
│         (π++ Projection + Cryptographic Binding)         │
│                      ↓                                    │
│         Merkle DAG Append (Swarm State)                  │
│                      ↓                                    │
│         SSE Broadcast to Cockpit                         │
│         Audit Archive (Hot/Cold)                         │
│                      ↓                                    │
│         PostgreSQL + S3 Persistence                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
         ↑                                    ↑
         │                                    │
    Knowledge Graph                      Query Optimizer
    (Entities, Relations)                (B-tree, Bloom, Cache)
```

---

**Authorization:** Standing by for agent assignment + Phase 66 RED phase commencement.
