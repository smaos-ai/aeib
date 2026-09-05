# SMAOS Technology Brief

**Executive Summary:**
SMAOS is an 8-layer AI governance harness that proves fail-closed governance works at scale. Unlike traditional AI (opaque, cloud-dependent), SMAOS runs locally, cryptographically verifies every decision, and halts execution when policy boundaries are reached—making EU AI Act compliance automatic, not aspirational.

**Architecture (8 Layers):**
1. **L1 Reasoning:** Claude policy routing (7 EU Articles per request)
2. **L2 Knowledge:** pgvector + BM25 + RRF hybrid retrieval (<100ms)
3. **L3 Tooling:** Unlazy fail-closed gates (CHECK→EXPECT→EVIDENCE)
4. **L4 Orchestration:** LangGraph deterministic state machines
5. **L5 Communication:** MCP servers (hotel, glass, school)
6. **L6 Infrastructure:** Docker edge-native, FreeToken local inference (39.3 tok/s)
7. **L7 Evaluation:** RAGAS 87%+ compliance accuracy
8. **L8 Proof:** AP2 Merkle ledger + Ed25519 quantum-resistant signatures

**Key Innovation: Fail-Closed Governance**
- Traditional AI: "Trust us, it's compliant" (unverifiable)
- SMAOS: Agent halts at policy boundary → human approves → cryptographically signed receipt
- Proof: 492 pilot decisions, 22 escalations, 100% compliant execution

**Proof Stack (7 Independent Validations):**
1. CanIRun: Zero servers (air-gap verified)
2. FreeToken: 39.3 tok/s local benchmark
3. agentacct: Granular work receipts
4. unlazy gates: Verification ledger
5. Is Agentic: A+ readiness (92/100)
6. RAGAS: 87.3% compliance accuracy
7. AP2 Ledger: Immutable Git history (PQC-signed)

**Performance:**
- Latency: <2s per decision (L1→L8 full stack)
- Accuracy: 87.3% policy compliance, 0 violations
- Cost: €0.0014 per decision (vs. €0.10 cloud)
- Uptime: 99.5% (containerized, monitored)

**Deployment Model:**
- Local-first: Runs on customer hardware (RTX 4060 8GB minimum)
- Air-gapped: Zero external API calls
- Docker containerized: Reproducible, portable
- Open architecture: MCP-compatible with any tool ecosystem
