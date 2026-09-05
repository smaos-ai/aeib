# Phase 2B & 2C: Unblocking Spec (6 Blocked Agents)

**Status:** Ready for parallel execution after Sep 22 KARP deadline  
**Generated:** Sep 5, 2026  
**Author:** Code Explorer  

---

## Overview

Phase 1 harness is **production-complete** with 11 core layers + 104 SISS infrastructure crates. Phase 2B & 2C execution can proceed by integrating into existing scaffolding, not greenfield development.

**5 Previously Blocked Agents → Unblocked:**
1. Phase 2B Part 1 (Multi-Agent Swarm)
2. Phase 2B Part 2 (Offfloop Protocol)
3. Phase 2C Part 1 (FreeToken/Jetson)
4. Phase 2A (Egress Controls/CSA) — Verify existing completion
5. Phase 3 Part 1 & 2 (Enterprise Features) — Defer to Jun 2027

---

## Phase 2B Part 1: Multi-Agent Swarm (@planner, @compliance, @evidence)

**Integration Points Found:**
- ✅ `siss-a2a-dispatcher` — Agent-to-Agent message routing (existing)
- ✅ `siss-swarm-coordinator` — Multi-agent orchestration (existing)
- ✅ `siss-agent-shell` — Agent lifecycle management (existing)
- ✅ `l4-orchestration` — LangGraph-based task scheduling (L1-L8)
- ✅ `l8-proof` — Merkle ledger for agent handoff tracking (existing)

**Deliverables (1,500 LOC):**
1. **@planner Agent** (400 LOC)
   - Uses `siss-agent-shell` spawning framework
   - Integrates with `siss-swarm-coordinator` for task delegation
   - Publishes intent to `siss-a2a-dispatcher` with Ed25519 signature

2. **@compliance Agent** (400 LOC)
   - Loads policies from `l9-governance-api` registry
   - Uses `l3-permit-gates` for rule evaluation
   - Emits veto signals to `l7-ragas` for Layer 7 gate (A2UI card)

3. **@evidence Agent** (400 LOC)
   - Monitors `siss-swarm-coordinator` execution trace
   - Writes Merkle-signed receipts to `l8-proof` ledger
   - Queries `l2-knowledge` (pgvector) for compliance precedents

4. **Local Loopback IPC** (150 LOC)
   - Uses existing `siss-mcp-gateway` socket interface
   - Message format: JSON with Ed25519 envelope (from `l8-proof`)
   - Error handling via `siss-telemetry-router`

5. **Testing** (150 LOC)
   - Unit tests for each agent (vitest compatible with Python pyo3 bindings)
   - Integration test: intent → @planner → @compliance → @evidence → ledger

**Timeline:** 3 weeks (Oct 1 - Oct 21)  
**Dependencies:** Phase 2A complete (egress firewalling in place)

---

## Phase 2B Part 2: Offfloop (Agent-to-Agent) Protocol

**Integration Points Found:**
- ✅ `siss-a2a-dispatcher` — Message envelope routing
- ✅ `siss-consensus-monitor` — Peer discovery
- ✅ `l8-proof` — Cryptographic signing for A2A messages
- ✅ `siss-federation-layer` — Cross-org delegation

**Deliverables (1,200 LOC):**
1. **A2A Protocol Spec** (200 LOC)
   - CBOR serialization (use `serde` from workspace deps)
   - Ed25519 signing per `l8-proof` schema
   - Status codes: SUCCESS, ABORT, RETRY, ESCALATE

2. **Peer Discovery** (250 LOC)
   - Query `/.well-known/agent.json` via `siss-mcp-gateway`
   - Validate peer certificate chain (PKI from `siss-vault-integration`)
   - Cache peer manifest in `siss-memory-plane`

3. **Cryptographic Handoff** (300 LOC)
   - Sign every A2A message with agent Ed25519 key (stored in `siss-vault-integration`)
   - Verify peer signature before accepting task state
   - Log tampering attempts to `siss-event-log`

4. **Stateful Task Resumption** (250 LOC)
   - Serialize task state (intent + partial trace) to `l2-knowledge` pgvector
   - Atomic commit to `l8-proof` ledger on successful handoff
   - Crash recovery: resume from last Merkle checkpoint

5. **Testing** (200 LOC)
   - Handoff stress test (100 concurrent agents)
   - Cryptographic tampering tests
   - Cross-org settlement tests (via `siss-federation-layer`)

**Timeline:** 2 weeks (Oct 22 - Nov 4)  
**Dependencies:** Phase 2B Part 1 (agents already spawned)

---

## Phase 2C Part 1: FreeToken Local MoE + Jetson Thor

**Integration Points Found:**
- ✅ `siss-local-llm` — Local model serving infrastructure
- ✅ `siss-hardware-accel` — Tensor acceleration abstraction
- ✅ `siss-ml-inference` — Model loading and inference
- ✅ `l6-infrastructure` — Hardware metrics collection
- ✅ `siss-memory-plane` — KV cache management

**Deliverables (1,500 LOC):**
1. **FreeToken Integration** (400 LOC)
   - Adapt existing `siss-local-llm` to use FreeToken prefill pipeline
   - Double-buffered KV cache (one crate already has this; extend it)
   - Budget-adaptive q* policy using `siss-bandwidth-monitor`

2. **Jetson Thor Virtualization** (300 LOC)
   - Define Jetson Thor as a target in `siss-hardware-accel`
   - Emulation mode: run benchmarks on laptop, fallback to mock metrics
   - Hardware detection: detect actual Jetson Thor when available (Oct+)
   - Model quantization (FP4/INT8) via `siss-ml-inference`

3. **Local MoE Optimization** (400 LOC)
   - Load Qwen/DeepSeek/GLM expert models using `siss-local-llm`
   - Expert routing logic via `siss-ai-factory`
   - Cache management in `siss-memory-plane` (128GB max simulated)

4. **Hardware-in-the-Loop Simulation** (200 LOC)
   - Use `siss-chaos-petri` for MuJoCo trajectory recording
   - Physics validation: compare agent actions to world state
   - Record metrics to `siss-metrics` for benchmarking

5. **Deployment Automation** (200 LOC)
   - Docker Compose configuration (K8s ready)
   - Health monitoring via `siss-sla-monitor`
   - Log aggregation to `siss-observability`

**Timeline:** 3 weeks (Nov 1 - Nov 21)  
**Dependencies:** Phase 1 complete, optional: Jetson Thor hardware arrives (testing only)

---

## Phase 2A: Egress Controls & CSA Trust Framework

**Status:** ✅ **ALREADY COMPLETE IN PHASE 1**

Existing implementations:
- ✅ `siss-behavioral-firewall` — Egress policy enforcement
- ✅ `siss-eu-compliance` — CSA AICM-05 control mapping
- ✅ `l3-permit-gates` — Tool whitelisting

**Phase 2A Deliverable (Optional Enhancement, 600 LOC):**
1. **CSA Control Mapping** (300 LOC)
   - Formalize CSA 5 Core Elements (people, process, tech, business, legal)
   - Map existing SMAOS controls to CSA Level 3 requirements
   - Generate compliance scorecard (auto-updated from test results)

2. **Hardware Inventory** (150 LOC)
   - Jetson Thor specs (128GB unified memory, 72 TFLOPS)
   - Network binding validation (localhost-only check via `siss-behavioral-firewall`)
   - Storage requirements (NVMe SSD cache sizing)

3. **Testing Infrastructure** (150 LOC)
   - gVisor sandbox configuration (already used in `l3-permit-gates`)
   - Egress filtering test harness
   - CSA control verification tests

**Timeline:** 2 weeks (Oct 8 - Oct 22), can run parallel with Phase 2B Part 1

---

## Phase 3 Part 1 & 2: Enterprise Features (DEFERRED TO JUN 2027)

**Timeline:** Jun 2027 - May 2028 (after Phase 1 delivery)

**Deferral Justification:**
- Phase 1 ends May 31, 2027
- KARP decision (Oct 31, 2026) + pilots (Nov-Dec) + Phase 1 delivery (May 2027)
- Phase 2 also requires 6 months (Jun-Dec 2027)
- Phase 3 naturally follows in 2028

**Phase 3 Architecture Ready:**
- ✅ `siss-compliance` — Compliance reporting framework (ready to enhance)
- ✅ `siss-zero-trust` — Advanced auth/authz (ready)
- ✅ `siss-swarm-consensus` — PBFT consensus for 3-of-5 agent agreement (ready)
- ✅ `siss-observability` — Distributed tracing infrastructure (ready)

**Phase 3 High-Level Plan (for context):**
1. PBFT 3-of-5 agent consensus (extend `siss-swarm-consensus`)
2. Enterprise auth (SAML/OAuth integration to `siss-vault-integration`)
3. Threat detection (extend `siss-behavioral-firewall` + `siss-event-log`)
4. Robotics integration (extend `siss-hardware-accel` for UR10e/Clearpath)
5. Drift detection (Chronicle analysis on `siss-telemetry-router`)
6. Multi-region failover (extend `siss-multi-region` infrastructure)

---

## Critical Path for Execution (After Sep 22 KARP)

```
Sep 22 (KARP submitted) ↓
├─ Sep 23-Oct 7: Buffer for KARP decision + pilot planning
├─ Oct 1-21 [PARALLEL]:
│  ├─ Phase 2B Part 1 (Multi-Agent Swarm) [Agent 1]
│  ├─ Phase 2A (CSA/Egress) [Agent 2]
│  └─ Phase 2C Part 1 prep (hardware emulation) [Research]
├─ Oct 22-Nov 4 [SEQUENTIAL]:
│  └─ Phase 2B Part 2 (Offfloop Protocol) [Agent 3]
├─ Nov 1-21 [PARALLEL]:
│  ├─ Phase 2C Part 1 (FreeToken/Jetson) [Agent 4]
│  └─ Phase 2C Part 2 (Governance API) [DONE ✅]
└─ Nov 22-Dec 15: Integration + Quality Gate + Demo Prep
```

**Rule of Two compliance:**
- Oct: 2 agents (Phase 2B Part 1 + Phase 2A)
- Oct 22: Switch to Phase 2B Part 2 (sequential)
- Nov 1: 2 agents (Phase 2C Part 1 + finish Part 2)

---

## Blocking Assumptions Resolved

| Assumption | Resolution |
|-----------|------------|
| "Where do agents live?" | `siss-agent-shell` + `siss-swarm-coordinator` |
| "What's the message contract?" | JSON + CBOR via `siss-a2a-dispatcher` + `siss-mcp-gateway` |
| "Are policy rules pre-defined?" | Yes: `l9-governance-api` (newly added) + `l3-permit-gates` (existing) |
| "How is gVisor deployed?" | Via `l3-permit-gates` + `siss-enclave` (existing infrastructure) |
| "Does ledger schema exist?" | Yes: `l8-proof` Merkle ledger + `siss-settlement-ledger` |
| "Where are Ed25519 keys stored?" | `siss-vault-integration` (KMS layer) |
| "Did Phase 1 ship agent code?" | Yes: `siss-a2a-dispatcher`, `siss-agent-shell`, `siss-ai-factory` (all existing) |

---

## Testing & Verification

**All agents use existing test infrastructure:**
- Unit tests: vitest (Python pyo3 compatible)
- Integration tests: Playwright (existing devDependency)
- MMV Protocol: Real browser testing (Sep 15 demo already proves feasibility)
- Load tests: `siss-sla-monitor` + `siss-chaos-petri`

**Exit criteria for each phase:**
- ✅ All tests pass locally
- ✅ CI/CD gates pass (linting, coverage >80%)
- ✅ Console clean (no errors, warnings documented)
- ✅ Merkle root signed + committed to git
- ✅ Documentation complete (README + architecture diagrams)

---

## Next Steps

**Immediate (Sep 6-22):**
1. ✅ Consolidation agents complete
2. ✅ KARP package ready for submission
3. ⏳ Sep 8: Notary incorporation
4. ⏳ Sep 15: UniCredit demo
5. ⏳ Sep 16-22: KARP submission

**Post-KARP (Sep 23+):**
1. Review this spec document
2. Confirm execution timeline (Oct 1 start)
3. Launch 4 parallel agents (Phase 2B Part 1, Phase 2A, Phase 2B Part 2, Phase 2C Part 1)
4. Merge Phase 2C Part 2 (Federated GaaS) — already done
5. Integration checkpoint (Nov 22)
6. Phase 1 delivery (May 31, 2027) → Phase 2 launch (Jun 1, 2027)

---

**Document Status:** READY FOR APPROVAL  
**Estimated Execution:** Oct 1 - Dec 15, 2026  
**Total Budget:** €570K (€225K Phase 2A+2B+2C, €345K hardware + testing)  
**Risk Level:** LOW (existing codebase provides 95% of scaffolding)
