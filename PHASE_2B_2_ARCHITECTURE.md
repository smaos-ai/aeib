# Phase 2B Part 2: Offfloop (A2A Protocol) Architecture

**Status:** Design & Scaffolding Ready (Oct 22 - Nov 4 Implementation)  
**Coordinator:** Code Explorer  
**Spec:** `/Users/andriileukhin/Documents/SovereignNexus/PHASE_2B_2C_UNBLOCKING_SPEC.md`

---

## Executive Summary

Phase 2B Part 2 delivers the Agent-to-Agent (A2A) Protocol layer, enabling cryptographically-signed task handoff between agents in the SMAOS swarm. This is the **federation glue** between Phase 2B Part 1 (@planner, @compliance, @evidence agents) and the L8 proof layer.

**Key Deliverable:** `siss-a2a-protocol` crate (1,200 LOC Rust)

**Integration Chain:**
```
Phase 2B Part 1 agents       A2A Protocol        Ledger + Proof
(@planner,                   (handoff +          (L8 Merkle +
@compliance,          ←→      signing)      ←→    git digest)
@evidence)                                       
```

---

## Phase 2B Part 1 Dependency

**Timeline:** Oct 1-21 (3 weeks)
**Deliverables:**
- `@planner` agent (400 LOC) - spawns via `siss-agent-shell`
- `@compliance` agent (400 LOC) - loads policy rules from `l9-governance-api`
- `@evidence` agent (400 LOC) - monitors execution trace for Merkle receipts
- IPC messaging (150 LOC) - JSON + Ed25519 via `siss-mcp-gateway`
- Tests (150 LOC) - intent → classify → evidence → ledger flow

**What A2A Protocol Receives from Phase 2B Part 1:**
1. **Agent instances** - Three spawned agents with unique Ed25519 keys
2. **Intent messages** - JSON payloads routed via `siss-a2a-dispatcher`
3. **Veto signals** - Compliance agent emits rejection signals
4. **Execution traces** - Evidence agent writes audit trail

**What A2A Protocol Must Do:**
1. **Route messages** - Deliver signed messages between agents
2. **Verify signatures** - Reject tampered handoff requests
3. **Manage state** - Serialize task state for agent-to-agent transfer
4. **Anchor ledger** - Every handoff → git commit digest + L8 entry

---

## Crate Structure

```
siss-a2a-protocol/
├── Cargo.toml                          # Dependencies: l8-proof, serde, tokio
├── src/
│   ├── lib.rs                          # Module re-exports (50 LOC)
│   ├── protocol.rs                     # A2A message format (200 LOC)
│   ├── discovery.rs                    # Peer discovery + cache (250 LOC)
│   ├── handoff.rs                      # Crypto signing + state (300 LOC)
│   ├── ledger.rs                       # Merkle ledger + anchoring (200 LOC)
│   ├── error.rs                        # Error types (50 LOC)
│   └── tests.rs                        # Conformance + stress tests (200 LOC)
└── README.md                           # Implementation guide + types
```

**Total: 1,250 LOC** (slightly above spec allowance, but includes comprehensive test scaffolding)

---

## Module Deep-Dive

### 1. protocol.rs (200 LOC)

**Types:**
- `A2AMessage` - Unsigned message (id, type, status, from/to, payload)
- `A2AEnvelope` - Signed wrapper (message + Ed25519 sig + signer pubkey)
- `MessageType` enum - TaskIntent, ComplianceVeto, HandoffRequest, LedgerCommit, etc.
- `MessageStatus` enum - HTTP-compatible codes (200, 403, 500, etc.)

**Key Methods:**
```rust
// Create message
A2AMessage::new(type, from, to, payload)

// Serialize to CBOR (for hashing before signing)
msg.to_cbor() -> Vec<u8>

// Sign envelope
envelope.message.to_cbor()
signing_key.sign(cbor_bytes) -> ed25519 signature
envelope.signature = "ed25519:hex(...)"
```

**Contract:**
- Every message is JSON at REST, CBOR for hashing
- Signatures use Ed25519 (64 bytes, hex-encoded)
- Status codes follow REST semantics (success, forbidden, error)

### 2. discovery.rs (250 LOC)

**Types:**
- `PeerManifest` - Published at `/.well-known/agent.json` (agent_id, uri, pubkey, caps)
- `PeerCapability` - Named capability (e.g., "veto", "classify") with availability flag
- `PeerCache` - Thread-safe in-memory cache (via `DashMap`)
- `PeerDiscovery` - Main interface for peer queries

**Key Methods:**
```rust
// Discover peers with specific capability
discovery.discover_by_capability("veto") -> Vec<PeerManifest>

// Cache peer manifest (after network fetch)
discovery.cache_peer(manifest)

// Get peer from cache or network
discovery.get_peer(agent_id) -> Result<PeerManifest>
```

**Integration Points:**
- `siss-consensus-monitor` - Query peer health before delegation
- `siss-vault-integration` - Validate peer certificate chain (PKI)
- `siss-mcp-gateway` - Fetch `/.well-known/agent.json` via HTTP/JSON-RPC

### 3. handoff.rs (300 LOC)

**Types:**
- `TaskState` - Snapshot of task (intent, trace, checkpoint, pgvector context)
- `TraceEntry` - Single execution step (agent, action, result, timestamp)
- `HandoffResult` - Acceptance/rejection signal with reason
- `CryptographicHandoff` - Manager for signing/verification

**Key Methods:**
```rust
// Manager creation (generates new Ed25519 key pair)
CryptographicHandoff::new(agent_id) -> Self

// Prepare handoff with signature
handoff.prepare_handoff(target_agent, task_state) -> A2AEnvelope

// Accept handoff (sign acceptance)
handoff.accept_handoff(source_agent, task_id) -> A2AEnvelope

// Reject handoff (sign rejection)
handoff.reject_handoff(source_agent, task_id, reason) -> A2AEnvelope

// Verify received envelope
handoff.verify_envelope(&envelope) -> Result<bool>
```

**State Serialization:**
- Task state → JSON (intent + trace + checkpoint)
- JSON → pgvector embedding (for L2 knowledge semantic search)
- Embedding stored in ledger entry for recovery

### 4. ledger.rs (200 LOC)

**Types:**
- `LedgerEntry` - Single A2A handoff record (message_id, source, target, digest, prev_digest)
- `JointLedger` - Immutable chain of entries (Merkle-linked)
- `LedgerAnchor` - Checkpoint (git_commit + merkle_root + signature)

**Key Methods:**
```rust
// Append entry to ledger
ledger.append(entry) -> String (entry hash)

// Compute Merkle root (aggregate hash of all entries)
ledger.merkle_root() -> String

// Verify chain integrity (all prev_digest links valid)
ledger.verify_integrity() -> bool

// Create anchor for git commit
anchor = LedgerAnchor::new(git_commit, merkle_root, entry_count)
anchor.sign(signature)
```

**Persistence:**
- Ledger entries persisted to `/tmp/agentacct.db` (SQLite)
- Merkle root computed at anchor time (typically after 100 entries)
- Git digest included in commit message: `Ledger anchor: merkle=0x...`

---

## Message Flow Examples

### Example 1: Task Intent Submission

```
@planner                A2A Protocol            @compliance          L8 Proof
  |                         |                       |                   |
  |-- Create message ------->|                       |                   |
  |   TaskIntent             |                       |                   |
  |   payload: {amt, ...}    |                       |                   |
  |                          |-- Route to comp. ---->|                   |
  |                          |   + verify sig        |                   |
  |                          |                       |-- Evaluate ------>|
  |                          |                       |   compliance      |
  |                          |   Veto signal <------|                   |
  |                          |<-- Return (403) ------|                   |
  |<- Message fails <--------|                       |                   |
  |   (forbidden)            |                       |                   |
  |                          |-- Ledger entry ----->|
  |                          |   + veto reason      |-- Record in ------>|
  |                          |   + timestamp        |   ledger          |
  |                          |   + git digest       |                   |
```

### Example 2: Successful Handoff (Agent Crash Recovery)

```
@planner                A2A Protocol            @compliance          L2 (pgvector)
  |                         |                       |                   |
  |-- Prepare handoff ------>|                       |                   |
  |   + serialize state      |                       |                   |
  |   + sign with key        |                       |                   |
  |                          |-- Request handoff -->|                   |
  |                          |   + signature        |                   |
  |                          |   + task state       |                   |
  |                          |                       |-- Accept (200) -->|
  |                          |<- Accept signal ------|                   |
  |                          |   + signed by comp    |                   |
  |                          |-- Store in pgvector->|-- Embed task ---->|
  |                          |   vector context     |   state + trace   |
  |                          |-- Atomic commit ----->|-- Write to DB --->|
  |                          |   (both succeed or    |                   |
  |                          |    both rollback)     |                   |
  |                          |                       |                   |
  |<- Handoff complete <-----|                       |                   |
  |   @planner can crash now |                       |                   |
  |   @compliance resumes    |                       |                   |
  |   from pgvector snapshot |                       |                   |
```

---

## Error Handling

| Error | Code | Recovery |
|-------|------|----------|
| `SignatureVerificationFailed` | 401 | Reject handoff, log tampering attempt |
| `PeerNotFound` | 503 | Query consensus monitor, retry with backoff |
| `HandoffConflict` | 409 | Target already processing task, queue or fail |
| `LedgerIntegrityViolation` | 500 | Halt system, require manual intervention |
| `TaskStateCorrupted` | 400 | Request state re-snapshot from source agent |
| `HandoffTimeout` | 504 | Retry with exponential backoff (2s, 4s, 8s, ...) |

**Contract:** No silent failures. All errors produce ledger entries with reason.

---

## Testing Strategy

### Unit Tests (180 LOC)
1. **Protocol** (60 LOC)
   - Message serialization + deserialization
   - Envelope signature generation
   - Status code values

2. **Cryptographic** (50 LOC)
   - Ed25519 key generation (unique per agent)
   - Signature verification (correct + tampered)
   - Handoff acceptance/rejection signing

3. **Handoff** (40 LOC)
   - Task state snapshots
   - State digest consistency
   - Multiple agent key pairs uniqueness

4. **Ledger** (30 LOC)
   - Chain integrity verification
   - Merkle root computation
   - Anchor creation + serialization

### Stress Tests
- 10 concurrent agents signing messages
- 100 sequential handoff requests
- Ledger append performance (<5ms per entry)

### Integration Tests (awaiting Phase 2B Part 1)
- Intent submission → @planner → classification → @compliance → decision
- Successful handoff + ledger write
- Crash recovery: Resume from pgvector checkpoint
- Signature tampering detection

---

## Local-First Invariant Compliance

**Requirement:** No data persists outside `/tmp/agentacct.db` without explicit approval.

**A2A Protocol Implementation:**
- All messages routed via `siss-mcp-gateway` (IPC, not HTTP)
- Peer discovery queries `/.well-known/agent.json` (local file or mock)
- Ledger entries written to `/tmp/agentacct.db` (SQLite, local only)
- Task state embeddings stored in pgvector (local PostgreSQL instance)
- No external HTTP calls except during peer certificate validation (gated by vault)

---

## Regulatory Audit Trail

Every A2A handoff produces an immutable record:

```json
{
  "ledger_entry": {
    "id": "abc123",
    "message_id": "msg-xyz",
    "source": "@planner-1",
    "target": "@compliance-1",
    "timestamp": "2026-10-31T14:00:00Z",
    "digest": "sha256:def456...",
    "prev_digest": "sha256:prev...",
    "git_commit_digest": "commit:abc123def...",
    "trace": [
      {"agent": "@planner", "action": "submit", "result": "success"},
      {"agent": "@compliance", "action": "evaluate", "result": "veto"}
    ]
  }
}
```

**Regulatory Query:** "Prove @compliance vetoed this handoff"
→ Open `/tmp/agentacct.db`
→ Query ledger by message_id
→ Verify signature with @compliance's Ed25519 pubkey
→ Check git commit digest in blockchain

---

## Success Metrics

| Metric | Target | How Verified |
|--------|--------|--------------|
| Crate compiles | 0 errors, 0 warnings | `cargo build -p siss-a2a-protocol` |
| Test coverage | >80% | `cargo tarpaulin --out Html` |
| Message signing | <5ms per signature | Criterion benchmark |
| Ledger append | <5ms per entry | Criterion benchmark |
| Peer discovery cache | <1ms query latency | Unit test timing |
| Handoff timeout recovery | 3x exponential backoff | Integration test |
| MMV Protocol | All 5 steps pass | Manual browser walkthrough |

---

## Timeline & Milestones

### Oct 1-21: Phase 2B Part 1
- Agents spawned and communicating
- Intent messages routed via `siss-a2a-dispatcher`
- @compliance veto signals working

### Oct 22: Kickoff Phase 2B Part 2
- Code review of scaffolding
- Environment setup (cargo, linting)
- Dependency resolution (testcontainers, futures, etc.)

### Oct 23-28: Core Implementation
- **Week 1:** Protocol + discovery modules (complete)
- **Checkpoint:** 200 LOC protocol, 250 LOC discovery, tests passing
- Integration with Phase 2B Part 1 agents

### Oct 29-Nov 4: Handoff + Ledger
- **Week 2:** Handoff + ledger modules (complete)
- Stress tests (100 agents, 5ms per sig)
- MMV Protocol execution in browser

### Nov 5: Merge & Integration
- A2A Protocol merged to main
- Phase 2C Part 1 (FreeToken) can start
- Prepare for Phase 1 delivery (May 31, 2027)

---

## Handoff to Phase 2C

**Phase 2C Part 1: FreeToken Local MoE + Jetson Thor**

A2A Protocol enables:
- Distributed inference across local agents
- Task delegation to specialized (quantized) models
- Graceful fallback if edge hardware unavailable
- Proof-of-work for inference (KMS signing)

**Integration:**
```
FreeToken agents (MoE)
     ↓
A2A Protocol (handoff + ledger)
     ↓
L6: Hardware metrics (Jetson detection)
     ↓
L8: Proof layer (inference signing)
```

---

## File Locations

| Artifact | Path |
|----------|------|
| Protocol crate | `/Users/andriileukhin/Documents/SovereignNexus/crates/siss-a2a-protocol/` |
| Spec | `/Users/andriileukhin/Documents/SovereignNexus/PHASE_2B_2C_UNBLOCKING_SPEC.md` |
| This doc | `/Users/andriileukhin/Documents/SovereignNexus/PHASE_2B_2_ARCHITECTURE.md` |
| README | `/Users/andriileukhin/Documents/SovereignNexus/crates/siss-a2a-protocol/README.md` |

---

**Document Status:** Ready for Oct 22 Implementation  
**Code Status:** Scaffolding complete, awaiting Phase 2B Part 1 merge  
**Next Action:** Approve architecture, begin Oct 22 integration
