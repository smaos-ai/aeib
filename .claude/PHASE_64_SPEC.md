# PHASE 64 SPECIFICATION — $\pi^{++}$ Ontology + Proof Objects

**Status:** SPECIFICATION DRAFT (Pre-RED Phase)  
**Timestamp:** 2026-05-23T00:00:00Z  
**Gate:** Phase 63 GREEN (Cross-Node Attestation) VERIFIED ✓  
**Next Gate:** Phase 64 RED (Failing Test Specification)

---

## 1. THE $\pi^{++}$ OPERATOR (Real-Time Ranking & Projection)

### 1.1 Mathematical Definition

The $\pi^{++}$ operator is a **structural dimensionality reduction function** that accelerates knowledge graph queries by projecting high-dimensional context onto lower-dimensional subspaces while preserving decision-relevant features.

**Signature:**
```
π++: (Graph × Query × Budget) → (RankedResults × Confidence)
```

Where:
- **Graph**: The local knowledge graph (siss-graph-core)
- **Query**: A constraint or decision question (e.g., "Is agent A authorized for resource X?")
- **Budget**: Latency and memory constraints from the hot-path
- **RankedResults**: Ordered result set with relevance scores
- **Confidence**: Statistical confidence metric (0.0–1.0)

### 1.2 Operational Semantics

The $\pi^{++}$ operator executes in **three phases**:

#### Phase 1: Structural Filtering ($\pi^+$)
- Extract **entity types** relevant to the query (e.g., agents, resources, policies)
- Filter the knowledge graph to subgraph containing only relevant edges
- Time budget: <0.2ms (graph traversal only)

#### Phase 2: Dimensional Projection (++)
- Apply **lossy compression** to multi-dimensional entity attributes
- Project onto decision-relevant dimensions:
  - For authorization queries: [capability_level, temporal_window, resource_category]
  - For ranking queries: [relevance_score, freshness, trust_weight]
- Time budget: <0.3ms (projection computation)

#### Phase 3: Ranking & Confidence Scoring
- Sort projected results by relevance using **pre-computed ranking weights**
- Compute confidence via **Bayesian uncertainty quantification**:
  ```
  confidence = 1.0 - (missing_facts / total_relevant_facts)
  ```
- Time budget: <0.5ms (sorting + scoring)

**Total π++ Latency Budget: <1.0ms**

### 1.3 API Contract

```rust
pub fn project_and_rank(
    graph: &KnowledgeGraph,
    query: &OntologyQuery,
    budget_ms: f64,
) -> Result<ProjectionResult, OntologyError> {
    // Structural filtering phase
    let subgraph = graph.filter_relevant_entities(&query)?;
    
    // Dimensional projection phase
    let projected = subgraph.project_onto_basis(&query.dimensions)?;
    
    // Ranking and confidence scoring
    let ranked = projected.rank_and_score()?;
    
    Ok(ranked)
}

pub struct ProjectionResult {
    pub results: Vec<RankedEntity>,
    pub confidence: f64,
    pub latency_ms: f64,
    pub proof_root: String,  // Hash of projection computation (for Proof Objects)
}
```

---

## 2. PROOF OBJECTS (Cryptographically Signed Artifacts)

### 2.1 Definition

A **Proof Object** is a deterministic, cryptographically signed JSON document that **cryptographically binds**:
1. The **ontology transformation** (e.g., a knowledge graph update)
2. The **π++ projection** that justified the transformation
3. The **node's attestation** (from Phase 63 cross-node trust layer)

Proof Objects are the fundamental **currency of proof** in the swarm—they prove that a state change was legitimate before it enters `swarm_state`.

### 2.2 Deterministic JSON Schema

```json
{
  "proof_version": "1.0",
  "proof_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_id": "550e8400-e29b-41d4-a716-446655440001",
  "proof_type": "ontology_transformation",
  "transformation": {
    "operation": "add_edge|remove_edge|update_entity|assert_fact",
    "timestamp_utc": "2026-05-23T00:00:00Z",
    "source_entity": "550e8400-e29b-41d4-a716-446655440010",
    "target_entity": "550e8400-e29b-41d4-a716-446655440011",
    "edge_type": "authorized_for|delegates_to|trusts|rate_limited_by",
    "metadata": {
      "reason": "User requested resource access",
      "trace_id": "550e8400-e29b-41d4-a716-446655440020"
    }
  },
  "justification": {
    "pi_projection": {
      "query": "SELECT * FROM graph WHERE agent_id=? AND resource_id=?",
      "filtered_subgraph_size": 42,
      "projected_dimensions": ["capability_level", "temporal_window"],
      "top_k_results": 5,
      "confidence": 0.95,
      "latency_ms": 0.67
    },
    "decision_rule": "IF confidence > 0.9 AND capability_level >= REQUIRED THEN allow",
    "decision_outcome": "allow"
  },
  "attestation": {
    "node_attestation": {
      "node_id": "550e8400-e29b-41d4-a716-446655440001",
      "state_hash": "sha256:abc123...",
      "signature": "ed25519:deadbeef...",
      "timestamp": 1234567890
    }
  },
  "cryptography": {
    "proof_hash": "sha256:def456...",
    "proof_signature": "ed25519:cafebabe...",
    "signer_public_key": "ed25519:publickey...",
    "timestamp_signed": "2026-05-23T00:00:01Z"
  }
}
```

### 2.3 Schema Constraints (Fail-Closed)

**INVARIANT 1: Determinism**
- All timestamp fields must be RFC3339 formatted (no microsecond variance)
- `transformation` must be JSON-serialized with sorted keys (canonical form)
- `pi_projection` must be included in full (proof is worthless without justification)

**INVARIANT 2: Cryptographic Binding**
- `proof_hash` = SHA256(transformation || justification || attestation)
- `proof_signature` = Ed25519Sign(proof_hash, node_private_key)
- Any modification to nested fields invalidates the signature

**INVARIANT 3: Temporal Coherence**
- `timestamp_utc` must be <= `timestamp_signed` (proof cannot be signed before transformation)
- `timestamp_signed` must be <= current node's wall-clock time (no future-dated proofs)

**INVARIANT 4: Attestation Binding**
- `node_id` in proof must match `node_id` in attestation
- Attestation must be valid (verified via Phase 63 swarm_state)

### 2.4 Fail-Closed Rejection Rules

A Proof Object MUST be rejected if:
1. `proof_signature` fails Ed25519 verification
2. `proof_hash` does not equal SHA256(transformation || justification || attestation)
3. `confidence` < 0.8 (low-confidence projections cannot justify state changes)
4. `latency_ms` > 1.0 (π++ execution exceeded budget)
5. Attestation node is not in the verified swarm peer list
6. Temporal ordering violated

---

## 3. INTEGRATION: MCP Contract Routing

### 3.1 Data Flow

```
Client Request
    ↓
[siss-task-router] — Routes to decision pipeline
    ↓
[siss-behavioral-firewall] — Evaluates ReBAC/AP2/Temporal
    ↓
[π++ Projection] — Queries graph, generates ranking + confidence
    ↓
[Proof Object Generation] — Wraps decision in cryptographic proof
    ↓
[MCP Contract: validate_proof_object()] — Verifies signature + schema
    ↓
[siss-swarm-attestation] — append_state(proof) → ledger
    ↓
[SSE Broadcast] — Real-time cockpit update (Phase 2)
    ↓
Client Response + Proof Receipt
```

### 3.2 New MCP Contracts

#### Contract 1: `validate_proof_object()`

**Input Schema:**
```rust
pub struct ValidateProofObjectInput {
    pub proof_json: String,  // Full Proof Object as JSON
}
```

**Output Schema:**
```rust
pub struct ValidateProofObjectOutput {
    pub valid: bool,
    pub proof_id: String,
    pub confidence: f64,
    pub rejection_reason: Option<String>,
}
```

**Validation Logic:**
1. Parse JSON to typed Proof Object
2. Verify `proof_signature` (Ed25519)
3. Verify `proof_hash` matches computed hash
4. Validate temporal ordering
5. Verify attestation is in swarm_state
6. Check confidence threshold (>= 0.8)
7. Return `valid=true` only if all checks pass

#### Contract 2: `generate_proof_object()`

**Input Schema:**
```rust
pub struct GenerateProofObjectInput {
    pub transformation: TransformationRecord,
    pub pi_projection_result: ProjectionResult,
    pub decision_outcome: String,  // "allow" | "deny"
}
```

**Output Schema:**
```rust
pub struct GenerateProofObjectOutput {
    pub proof_object: String,  // Full JSON
    pub proof_id: String,
    pub proof_signature: String,
}
```

**Generation Logic:**
1. Serialize transformation + projection + attestation to canonical JSON
2. Compute `proof_hash` = SHA256(canonical JSON)
3. Sign with node's Ed25519 private key
4. Wrap in Proof Object envelope
5. Return complete JSON

### 3.3 Integration Points

**Point A: After π++ Projection**
- The projection result (`confidence`, `latency_ms`, `proof_root`) flows directly into Proof Object generation
- Failed π++ queries (latency > 1.0ms) cannot be proven

**Point B: Before swarm_state Append**
- Proof Objects are validated before entering the Merkle DAG
- Invalid proofs trigger fail-closed rejection (decision reverted to deny)

**Point C: Cockpit SSE Stream**
- Each proof appended to swarm_state emits an SSE event (Phase 2 integration)
- Cockpit displays proof confidence + decision outcome in real-time

---

## 4. STRUCTURAL INVARIANTS (RED Phase Constraints)

### INVARIANT 1: π++ Latency Budget
The structural filtering + projection + ranking must execute **strictly < 1.0ms**.

**Test:** Submit query spanning 10,000-node graph; measure end-to-end latency.
**Expected:** Latency < 1.0ms OR query rejection (graceful degradation).

### INVARIANT 2: Proof Object Determinism
Two nodes projecting the **same query** on the **same graph state** must generate **identical proof_hash values**.

**Test:** Replicate query on two nodes; compare computed `proof_hash`.
**Expected:** Hashes match bit-for-bit (no random variance in sorting, scoring).

### INVARIANT 3: Confidence-Gated Proofs
Proof Objects with `confidence < 0.8` must be **unconditionally rejected** by `validate_proof_object()`.

**Test:** Generate proof with artificially low confidence; verify rejection.
**Expected:** `valid=false`, rejection_reason includes confidence threshold.

### INVARIANT 4: Cryptographic Binding
Modifying any field in a Proof Object (except timestamp_signed) must **invalidate the signature**.

**Test:** Flip one bit in `transformation` field; verify signature fails.
**Expected:** Ed25519 verification returns error (cannot forge signatures).

### INVARIANT 5: Temporal Coherence
A Proof Object signed at time T1 cannot have a transformation timestamp > T1.

**Test:** Attempt to create proof with `timestamp_utc` > `timestamp_signed`.
**Expected:** Fail-closed rejection (temporal ordering violated).

---

## 5. PHASE 64 ROADMAP

### RED Phase (This Document)
- Write 5 failing tests that lock the above invariants
- Verify all tests fail (proof infrastructure is stubbed)

### GREEN Phase
- Implement π++ projection engine (siss-context-cartography integration)
- Implement Proof Object generation + schema validation
- Wire MCP contracts into decision pipeline
- Verify all 5 tests pass

### REFACTOR Phase
- Optimize π++ latency (target: <0.5ms average case)
- Add confidence uncertainty quantification (Bayesian inference)
- Integrate with cockpit real-time proof visualization

---

**Standing by for PHASE 64 RED Phase authorization.**
