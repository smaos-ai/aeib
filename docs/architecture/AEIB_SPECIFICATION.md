# Agent Execution Integrity Boundary (AEIB) — Architectural Specification

**Version:** 0.2.1  
**Status:** Synthetic prototype for engineering review  
**Author:** Andrii Leukhin, Independent Researcher, SovereignNexus project  

---

## The Structural Fault: Why "Retry or Else" Fails in Agentic Architectures

```text
Traditional Deterministic Retry (Safe Failure):
[ POST /wire ] ──(504 Drop)──> [ Retry Handler ] ──(Exact Payload Replay + Same UUID)──> [ Target API ]

Autonomous Agentic Retry (Silent Double-Mutation):
[ POST /wire ] ──(504 Drop)──> [ LLM ReAct Loop ] ──(Semantic Re-reasoning: Mutated JSON)──> [ Target API (Double Spend) ]
```

In traditional infrastructure, automated retry loops relied on three invariants:

* **Byte-Level Determinism:** The client resends the identical serialized payload with the exact same `Idempotency-Key`.
* **Strict Protocol Semantics:** Retries were limited to safe HTTP methods or controlled within distributed transactions, sagas, and dead-letter queues.
* **Bounded Failure States:** After $N$ attempts, the thread failed closed, surfaced a stack trace, and triggered an on-call human.

Autonomous agents destroy these invariants through three distinct failure modes:

* **Semantic Drift Overrides Idempotency:** When an agent receives an error like `HTTP 504 Gateway Timeout`, that raw string re-enters its prompt context. Instead of replaying raw packets, the model re-reasons, frequently altering whitespace, numbers, phrasing, or regenerating internal UUIDs. Because the payload digest changes, downstream deduplication fails, resulting in duplicate ledger entries, double-booked ERP updates, or corrupted state.
* **The "Error = Not Done" Fallacy (The 504 Trap):** A transport dropout (HTTP 504, TCP RST) only proves that the socket severed, not that the backend aborted. The reverse proxy dropped the connection while the database may have committed the write milliseconds later. To an LLM, an error semantically means "my goal was not accomplished." It interprets transport ambiguity as permission to re-execute, transforming a lost ACK into duplicate real-world side effects.
* **Multi-Tool Chains Without Two-Phase Commits (2PC):** Agents chain heterogeneous APIs (e.g., Stripe charge → internal database write → Slack dispatch). If step 2 drops at the socket layer and the agent re-executes its reasoning loop from step 1, uncoordinated external systems mutate multiple times.

---

## The 6-Stage Core Implementation Pipeline

> **Implementation status:** Stages 1, 3, 5, 6 are implemented in the v0.2 synthetic prototype. Stages 2 and 4 are simulated via fixture scenarios. A future sidecar interceptor will implement Stages 2 and 4 against real networks and real ledgers.

```text
[Tool Call Request] 
         │
         ▼
[ 1. Pre-Dispatch Binding ] ──> Recursive key-sort, canonical serialization, SHA-256 digest, UUIDv5 derivation
         │
         ▼
[ 2. Socket-Level Trap ]    ──> Intercepts 504, ECONNRESET, pipe EOF before client runtime masks the error
         │
         ▼
[ 3. Hard Policy Lock ]     ──> Sets retry_permitted = false; transitions state to DISPATCHED_UNCONFIRMED
         │
         ▼
[ 4. Out-of-Band Prober ]   ──> Queries authoritative ledger via UUIDv5 handle:
         │                      ├── Found: OUTCOME_VERIFIED (Halt retry; record exists)
         │                      ├── Absent: RECONCILIATION_NOT_FOUND (Safe to redispatch)
         │                      └── Mismatch: RECONCILIATION_FAILED (Quarantine for audit)
         │
         ▼
[ 5. Receipt Emission ]     ──> Binds action ID, payload hash, evidence hashes; signs via Ed25519
         │
         ▼
[ 6. Offline Verification ] ──> Zero-dependency script validates signature, hash chain, and disposition
```

### Phase 1: Pre-Dispatch Normalization & Idempotency Injection

* **Deterministic Serialization:** Recursively sort all payload object keys and format with compact separators (`,`, `:`) to ensure byte-exact cross-platform hashes.
* **Payload Digest Binding:** Calculate:

$$\text{unsigned\_payload\_hash} = \text{SHA-256}(\text{canonical\_json})$$

* **Deterministic UUIDv5 Generation:** Derive an RFC 4122 UUIDv5 using an established fixed namespace and the `unsigned_payload_hash`.
* **Parameter Injection:** Inject the deterministic UUIDv5 into outgoing headers (`X-Idempotency-Key`) or tool-call arguments before opening the network socket.

### Phase 2: Socket-Level Wire-Fault Interception

* **Fault Detection:** Intercept post-write transport dropouts (`HTTP 504`, `ECONNRESET`, `ETIMEDOUT`, pipe EOF).
* **State Isolation:** Mark the action state immediately as `DISPATCHED_UNCONFIRMED`.
* **Trap Masking Prevention:** Prevent underlying HTTP/client libraries from swallowing ambiguous socket drops or wrapping them in generic retryable network exceptions.

### Phase 3: Hard Policy Lock (Retry Suppression)

* **Execution Suspension:** Set `retry_permitted: false` in the signed receipt and mapping contract. In the v0.2 synthetic prototype, this is enforced logically: the mapping contract declares no permitted retry, and the verifier rejects any receipt whose retry policy contradicts the transport-probe tuple. A future sidecar interceptor will enforce this physically by intercepting retry attempts at the transport layer and returning a fail-closed error before the request reaches the network.
* **Structured Return:** Return a fail-closed JSON-RPC error containing the quarantine receipt ID and instruction:
```json
{
  "status": "HOLD",
  "disposition": "DISPATCHED_UNCONFIRMED",
  "error": "ACTION_REQUIRED: OUT_OF_BAND_RECONCILIATION_REQUIRED"
}
```

### Phase 4: Out-of-Band State Reconciliation Probe

* **Probe Interface:** Implement an authoritative check interface:

$$\text{probe}(\text{idempotency\_key}, \text{payload\_hash})$$

* **Authoritative Register Query:** Probe the target datastore/ledger using the deterministic UUIDv5 key:
* **State Present:** Resolve disposition to `OUTCOME_VERIFIED` (halt retry; transaction completed).
* **State Absent:** Resolve disposition to `RECONCILIATION_NOT_FOUND` (unlock retry; safe to redispatch).
* **Payload Conflict:** Resolve disposition to `RECONCILIATION_FAILED` (quarantine for operator inspection).

### Phase 5: Cryptographic Receipt Emission

* **Payload Assembly:** Bind `action_id`, `unsigned_payload_hash`, `idempotency_key`, transport evidence hash, and probe evidence hash under the `org.smaos.aeib` namespace schema.
* **Asymmetric Signing:** Sign the canonical JSON digest using an Ed25519 private key.
* **Append-Only Evidence Storage:** Write the structured signed record to a local append-only ledger (`receipts.jsonl`).

### Phase 6: Offline Verifier Conformance

* **Zero-Dependency Verifier:** Maintain an offline verification runner (`aeib_verify.py`) that:
1. Validates the Ed25519 signature against the public key registry.
2. Recomputes SHA-256 hashes of the captured request and transport evidence.
3. Confirms that the disposition matches the recorded transition conditions.

---

## The Minimal Sufficient Deliverable

The core execution boundary consists of six components:

1. **Idempotency Key Derivation Engine** (UUIDv5 derived from canonical JSON payload).
2. **Transport Fault Interceptor** (Trapping 504, connection resets, read timeouts).
3. **Disposition State Machine** (Enforcing EXECUTE → HOLD → BLOCK transitions).
4. **Authoritative Out-of-Band Prober** (Target state verification via UUIDv5).
5. **Ed25519 Receipt Signer** (Hash-chained, tamper-evident JSON records).
6. **Offline Verifier Script** (Self-contained, deterministic audit validation).

Every external wrapper—MCP sidecars, SCITT registration, COSE envelopes, or compliance report generators—depends strictly on this primitive. With this core operational, an unknown outcome ceases to be a trigger for speculative retries and becomes a deterministic, auditable state.

---

## Known Limitations (v0.2 Synthetic Prototype)

- **No real socket interception:** Transport faults are simulated, not captured from live networks.
- **No real ledger probes:** Reconciliation outcomes are synthetic, not queried from actual databases or payment systems.
- **No production retry enforcement:** The prototype demonstrates the invariant but does not physically block retries in live orchestrators.
- **No compliance certification:** Receipts are designed for engineering review, not regulatory submission.

---

## 3-Layer Evolution Architecture (v0.3+ Target Roadmap)

The 10 acknowledged limitations of the v0.2 synthetic prototype map into three distinct production layers:

### 1. Layer A: Kernel & Physical Wire Enforcement (Items 1, 2, 3, 9)
* **Real Socket Interception & Retry Suppression:** Replaces userspace Python middleware with eBPF XDP/TC driver-level hooks (`xdp_drop.c`) and BPF LSM (`bprm_check_security`). When a transport socket drops (HTTP 504, TCP RST, or stdio broken pipe), the kernel driver physically drops unhedged retry packets before they reach userspace, freezing the loop at $T_0$.
* **Real Out-of-Band Ledger Probes:** Replaces synthetic adapter mocks with direct queries to downstream registers (PostgreSQL/DuckDB bitemporal ledgers, core banking reconciliation APIs, or target OS accessibility trees) using the `idempotency_key_uuidv5` to confirm true state before releasing retries.
* **MCP Sidecar Integration:** Embeds the pre-dispatch $\text{Admissible}(a)$ gate directly into an MCP proxy sidecar wrapping stdio and HTTP transports (`mcp://...`), evaluating context lineage and blast radius before tool execution.

### 2. Layer B: Cryptographic & Standards Conformance (Items 4, 5, 6, 10)
* **RFC 8785 JCS Compliance:** Implements strict, byte-exact JSON Canonicalization Scheme parsers to ensure UTF-16 code-unit key sorting and numeric normalization derive identical hashes across Python, Rust, WASM, and Go.
* **RFC 9052 COSE_Sign1 Envelope:** Transitions the receipt format from plain JSON into CBOR-encoded `application/scitt-statement+cose` objects containing protected header parameters (`alg`, `cty`, `iss`, `sub`).
* **IETF SCITT Integration (RFC 9943):** Registers COSE_Sign1 statements with an append-only Transparency Service (Rekor or CCF), returning an `application/scitt-receipt+cose` inclusion receipt (RFC 9942) with Merkle tree proofs.
* **HSM / KMS Key Management:** Binds signing keys to PKCS#11 Hardware Security Modules or FIPS 140-2 Level 3 KMS endpoints, ensuring Ed25519 and post-quantum ML-DSA-65 root keys remain non-exportable.

### 3. Layer C: Substrate Attestation & Statutory Binding (Items 7, 8)
* **Hardware Attestation (TRACE, TDX, SEV-SNP):** Runs the verification engine inside a Confidential Virtual Machine (CVM). The CPU generates a hardware quote (Intel TDX `TDREPORT` or AMD SEV-SNP report) binding the 64-byte `REPORTDATA` nonce directly to the receipt payload hash, proving execution integrity even if the host OS is compromised.
* **DORA Incident Class Mapping:** Connects execution receipts directly to the 7 materiality criteria of Commission Delegated Regulation (EU) 2024/1772, pre-filling mandatory DORA Article 17 incident notifications and EBA DPM 4.0 Register of Information tables (`RT.01.01`–`RT.02.01`).
