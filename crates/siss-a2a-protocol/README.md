# siss-a2a-protocol: Agent-to-Agent Protocol Layer

**Phase 2B Part 2 Deliverable**  
**Timeline:** Oct 22 - Nov 4, 2026 (2 weeks after Phase 2B Part 1)  
**Status:** Design & Scaffolding (awaiting Phase 2B Part 1 completion for integration)

---

## Overview

The A2A Protocol provides cryptographically-signed, stateful handoff semantics for agent-to-agent communication in the SMAOS system. It integrates:

- **CBOR message envelopes** with Ed25519 signatures
- **Peer discovery** via `/.well-known/agent.json` + `siss-consensus-monitor`
- **Cryptographic handoff** of task state with signature verification
- **Stateful task resumption** via pgvector storage + atomic ledger commits
- **Joint ledger anchoring** with git digests for regulatory audit trails

---

## Architecture

### Deliverables (1,200 LOC total)

1. **A2A Protocol Spec** (200 LOC)
   - File: `src/protocol.rs`
   - Types: `A2AMessage`, `A2AEnvelope`, `MessageType`, `MessageStatus`
   - CBOR serialization + Ed25519 signature verification
   - Status codes: 200/202 (success), 400/401/403 (errors), 500/503 (peer errors)

2. **Peer Discovery** (250 LOC)
   - File: `src/discovery.rs`
   - In-memory cache: `PeerCache` (thread-safe via `DashMap`)
   - Discovery backend trait: `DiscoveryBackend`
   - Capability-based discovery: agents publish capabilities, peers query by name
   - Integration point: `siss-consensus-monitor` (peer health) + `siss-vault-integration` (cert validation)

3. **Cryptographic Handoff** (300 LOC)
   - File: `src/handoff.rs`
   - Manager: `CryptographicHandoff` (Ed25519 signing/verification)
   - State snapshot: `TaskState` (intent + trace + checkpoint + pgvector context)
   - Methods: `prepare_handoff()`, `accept_handoff()`, `reject_handoff()`
   - Ledger integration: Task state digest → L8 ledger entry

4. **Stateful Task Resumption** (250 LOC)
   - File: `src/ledger.rs`
   - Immutable ledger: `JointLedger` (Merkle-linked entries)
   - Anchor: `LedgerAnchor` (git commit + merkle root + Ed25519 signature)
   - Recovery: Ledger persists in `/tmp/agentacct.db` (local-first invariant)
   - Chain verification: `ledger.verify_integrity()` checks all prev_digest links

5. **Testing & Validation** (200 LOC)
   - File: `src/tests.rs`
   - Protocol conformance: message serialization, envelope lifecycle, status codes
   - Cryptographic: signature generation/verification, tampering detection
   - Handoff stress: 10 concurrent agents signing + message passing
   - Ledger anchoring: chain integrity, Merkle root consistency

---

## Message Flow

### Peer Discovery

```
Agent A                     Consensus Monitor            Vault Integration
   |                               |                            |
   +------ Query capability ------>|                            |
   |                    Fetch peer list                        |
   |                               |------ Validate cert ----->|
   |                               |<----- Valid? True --------|
   |<----- PeerManifest (B) -------|
   |      pubkey, uri, caps
```

### Handoff with Signature

```
Agent A (Source)          Agent B (Target)            Ledger (L8 + L2)
   |                           |                           |
   |-- Prepare task state ----->|                           |
   |   + intent + trace         |                           |
   |   + sign(ED25519)          |                           |
   |                            |                           |
   |<----- Accept (signed) ------|                           |
   |                            |                           |
   |-- Commit to ledger ------->|                           |
   |   + handoff digest         |-- Write ledger entry ---->|
   |   + git commit hash        |   + Merkle chain link     |
   |                            |   + timestamp             |
```

---

## Integration Points

### Phase 2B Part 1: Multi-Agent Swarm
- **Dependency:** Phase 2B Part 1 spawns @planner, @compliance, @evidence agents
- **Integration:** A2A Protocol routes messages between agents
- **Messaging:** Use `siss-a2a-dispatcher` + A2AEnvelope for inter-agent RPC

### L8: Proof Layer
- **Dependency:** `l8-proof` crate (Ed25519 keys + KMS signing)
- **Integration:** Every handoff creates signed `LedgerEntry` in `JointLedger`
- **Verification:** `ProofLayer.sign_ledger_entry()` used in `LedgerAnchor.sign()`

### L2: Knowledge (pgvector)
- **Dependency:** Task state stored as vector embeddings
- **Integration:** `TaskState.context_vector` → pgvector for semantic search
- **Recovery:** On resumption, query pgvector for similar past tasks

### L3: Permit Gates
- **Dependency:** Compliance rules from `l9-governance-api`
- **Integration:** `PeerDiscovery.discover_by_capability("veto")` finds compliance agents
- **Enforcement:** Handoff rejected if target lacks required capability

### Consensus Monitor
- **Dependency:** Health monitoring + Byzantine fault detection
- **Integration:** Query peer health before handoff (skip unhealthy peers)
- **Signals:** `HealthStatus::Unhealthy` → exponential backoff + retry

---

## Core Types

### A2AMessage (40 LOC)
```rust
pub struct A2AMessage {
    pub id: String,                    // UUID v4
    pub msg_type: MessageType,         // TaskIntent, ComplianceVeto, ...
    pub status: MessageStatus,         // 200, 403, 500, ...
    pub from_agent: String,            // Source
    pub to_agent: Option<String>,      // Target (None = broadcast)
    pub timestamp: DateTime<Utc>,
    pub payload: serde_json::Value,
    pub trace_id: Option<String>,
    pub request_id: Option<String>,
}
```

### A2AEnvelope (30 LOC)
```rust
pub struct A2AEnvelope {
    pub message: A2AMessage,
    pub signature: String,             // "ed25519:hex(...)"
    pub signer_pubkey: String,         // Hex-encoded Ed25519 pubkey
    pub prev_digest: Option<String>,   // Ledger chain link
}
```

### TaskState (50 LOC)
```rust
pub struct TaskState {
    pub task_id: String,
    pub intent: serde_json::Value,
    pub trace: Vec<TraceEntry>,
    pub checkpoint: Option<String>,    // For resumption
    pub context_vector: Option<Vec<f32>>, // pgvector
    pub captured_at: DateTime<Utc>,
}
```

### JointLedger (60 LOC)
```rust
pub struct JointLedger {
    entries: Vec<LedgerEntry>,
    last_digest: Option<String>,       // Chain tip
}

impl JointLedger {
    fn append(&mut self, entry: LedgerEntry) -> String { /* ... */ }
    fn merkle_root(&self) -> String { /* ... */ }
    fn verify_integrity(&self) -> bool { /* ... */ }
}
```

---

## Test Coverage

| Category | File | LOC | Test Cases |
|----------|------|-----|-----------|
| Protocol Conformance | `src/tests.rs` | 60 | Message creation, serialization, status codes |
| Cryptographic | `src/tests.rs` | 50 | Signature gen/verify, tampering detection |
| Handoff Stress | `src/tests.rs` | 40 | 10 concurrent agents, key uniqueness |
| Ledger Anchoring | `src/tests.rs` | 30 | Chain integrity, Merkle root, anchor creation |
| **Total** | — | **180** | **16+ tests** |

**Run tests:**
```bash
cd crates/siss-a2a-protocol
cargo test --lib
```

---

## Error Handling

```rust
pub enum A2AError {
    PeerNotFound(String),
    SignatureVerificationFailed,
    MessageTampering,
    HandoffConflict(String),
    TaskStateCorrupted(String),
    LedgerIntegrityViolation,
    CryptoError(String),
    TaskNotFound(String),
    HandoffTimeout,
    // ... 5+ more
}
```

All errors propagate via `Result<T> = std::result::Result<T, A2AError>`.

---

## Implementation Plan (Oct 22 - Nov 4)

### Week 1: Protocol + Discovery
- [ ] Complete `protocol.rs` message serialization + envelope signing
- [ ] Implement `discovery.rs` peer caching + capability queries
- [ ] Unit tests: protocol conformance (60 LOC, 6+ tests)
- [ ] Integration: Mock peer manifest endpoints

### Week 2: Handoff + Ledger
- [ ] Complete `handoff.rs` cryptographic state preparation
- [ ] Implement `ledger.rs` Merkle chaining + git digest anchoring
- [ ] Stress tests: 100 concurrent handoffs, signature verification
- [ ] End-to-end: Agent A → handoff → Agent B → ledger write

### Checkpoint: Oct 28
- All 5 modules compile without warnings
- 16+ tests pass with >80% code coverage
- Documentation complete (this README + inline comments)

### Final: Nov 4
- Phase 2B Part 1 integration (agents spawned)
- Handoff stress test (100 agents, <5ms per signature)
- Ledger audit trail verified (git digests in /tmp/agentacct.db)
- MMV Protocol: Manual click-through of handoff flow in browser

---

## Verification (Hands-On-Silicon Invariant)

Before claiming completion, execute in browser:

1. **Physical Isolation:** Open DevTools → Network tab
   - Confirm A2A messages routed locally (no external HTTP)
   - Verify signatures computed on local machine

2. **Click-Every-Button Sweep**
   - Start handoff → Observe message envelope
   - Accept handoff → Verify signature in console
   - Reject handoff → Confirm error code propagates
   - Query ledger → Display Merkle root + git digest

3. **Visual State Validation**
   - Message status (200/403/500) renders distinctly
   - Signature verification shows green/red badge
   - Ledger entries appear in real-time

4. **End-to-End Journey**
   - Intent submission → Classification → Execution → Authorization → Ledger
   - Confirm all 5 steps produce signed audit trail

5. **Console Hygiene**
   - No errors, no warnings
   - Document any acceptable warnings

---

## Regulatory Audit Trail

Every A2A handoff creates:

```json
{
  "message_id": "uuid",
  "signature": "ed25519:hex(...)",
  "ledger_entry": {
    "prev_digest": "sha256(...)",
    "git_commit": "abc123def456...",
    "timestamp": "2026-10-31T14:00:00Z",
    "trace": [
      {"agent": "@planner", "action": "submit_intent", "result": "success"},
      {"agent": "@compliance", "action": "evaluate_rules", "result": "veto"},
      {"agent": "@evidence", "action": "log_receipt", "result": "success"}
    ]
  }
}
```

Regulatory post-mortem: "Prove this handoff was authorized" → Check ledger entry signature + git digest.

---

## Dependencies

- `l8-proof`: Ed25519 signing, Merkle ledger
- `serde_json`: Message serialization
- `tokio`: Async runtime (for phase 2B part 1 integration)
- `ed25519-dalek`: Cryptography
- `sha2`: Digest generation
- `uuid`: Message IDs
- `chrono`: Timestamps
- `dashmap`: Thread-safe peer cache

**No external HTTP:** All communication local (IPC).

---

## Success Criteria (May 31, 2027)

- ✅ Protocol spec: 200 LOC, all 5 message types supported
- ✅ Discovery: 250 LOC, capability-based peer query
- ✅ Handoff: 300 LOC, signature + state serialization
- ✅ Ledger: 250 LOC, Merkle chain + git anchoring
- ✅ Tests: 200 LOC, 16+ tests, >80% coverage
- ✅ MMV: Manual handoff flow tested end-to-end in browser
- ✅ Docs: Architecture + integration points + error codes

---

**Document Status:** Ready for Oct 22 Implementation  
**Code Scaffolding:** Complete (1,200 LOC of Rust source)  
**Next Step:** Phase 2B Part 1 completes (Oct 21) → Merge A2A Protocol (Oct 22-Nov 4)
