# MCP Sidecar Interceptor — Research Architecture Specification (v0.2.1)

**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0 / v0.2.1-design)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Target Milestone:** P0 Research Prototype (Local Staging & Testing)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Status:** Design Document (Strict Research Scope)

---

## 🎯 1. Goals

The primary goal of the AEIB Sidecar Interceptor is to provide an out-of-process boundary guard that transparently enforces post-dispatch execution integrity between an agent orchestrator and downstream MCP tool servers.

1. **Transparent Protocol Interception**: Observe standard MCP `stdio` (stdin/stdout pipe) and loopback `HTTP/SSE` JSON-RPC tool calls without modifying agent or tool server application code.
2. **Pre-Dispatch Idempotency Binding**: Intercept mutating `tools/call` requests, serialize payload arguments into a deterministic JSON subset (sorted keys, compact separators), compute the SHA-256 digest, and inject a deterministic UUIDv5 idempotency key.
3. **Transport Fault Trapping**: Detect post-dispatch transport anomalies (HTTP 504 Gateway Timeout, TCP RST, connection drops, pipe EOFs) and prevent them from being masked as generic client-side execution errors.
4. **Normative Contract Evaluation**: Dynamically evaluate observed transport failures against `mapping/transport-to-disposition-mapping.yaml`, automatically assigning normative dispositions (`DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, etc.).
5. **Deterministic Retry Suppression**: Emit client-facing error responses containing cryptographically signed receipts that enforce `retry_policy.retry_permitted: false`.
6. **Verifiable Receipt Emission**: Generate append-only `AEIB_JSON_ED25519_PROTOTYPE` receipts verifiable offline by `verifier/aeib_verify.py`.

---

## 🚫 2. Non-Goals (Strict Research Boundaries)

To prevent overreach and maintain scientific rigor as an independent researcher, the following capabilities are **explicitly out of scope**:

* **No Production Hardening**: No multi-tenant concurrency tuning, zero high-availability failover clustering, and no enterprise SLAs.
* **No Full RFC 9052 (COSE_Sign1) / RFC 8785 (JCS) Certification**: Uses the proven `AEIB_JSON_ED25519_PROTOTYPE` deterministic JSON subset format; does not claim formal IETF standards certification.
* **No IETF SCITT Transparency Service Submission**: Receipts are saved to local append-only JSONL files; they are not registered to a live public SCITT ledger.
* **No Hardware Attestation / TRACE Integration**: Operates purely at the software protocol and cryptographic signature layer without requiring confidential enclaves (SGX/SEV-SNP).
* **No Re-implementation of Pre-Dispatch Governance**: Does not perform prompt sanitization, user authentication, or model fine-tuning; relies on upstream governance tools (e.g., WitnessAI, Safeguard) for authorization decisions.

---

## 🏗️ 3. Architecture Sketch

### Sits Between Agent and Tool Server

```text
┌────────────────────────┐                   ┌──────────────────────────────────────┐                   ┌────────────────────────┐
│    AGENT / CALLER      │                   │          AEIB SIDECAR PROXY          │                   │    DOWNSTREAM SERVER   │
│  (Claude, Cursor,      │                   │        (transport_observer.py)       │                   │ (Database, ERP, Core   │
│   LangChain Agent)     │                   │                                      │                   │  Banking, MCP Tool)    │
└───────────┬────────────┘                   └──────────────────┬───────────────────┘                   └───────────┬────────────┘
            │                                                   │                                                   │
            │ 1. tools/call {method, args}                      │                                                   │
            ├──────────────────────────────────────────────────►│                                                   │
            │                                                   │ 2. Canonicalize JSON & Compute Digest             │
            │                                                   │ 3. Inject X-Idempotency-Key (UUIDv5)              │
            │                                                   │ 4. Record Dispatch Event in transport.jsonl       │
            │                                                   │                                                   │
            │                                                   │ 5. Forward Mutating Call                          │
            │                                                   ├──────────────────────────────────────────────────►│
            │                                                   │                                                   │
            │                                                   │ ⚠️ TRANSPORT FAULT OCCURS                         │
            │                                                   │    (HTTP 504 / Connection Reset / Socket Abort)   │
            │                                                   │◄··················································┤
            │                                                   │                                                   │
            │                                                   │ 6. Evaluate Rule Contract:                        │
            │                                                   │    -> RULE-02A-504-AMBIGUOUS                      │
            │                                                   │    -> disposition: DISPATCHED_UNCONFIRMED         │
            │                                                   │    -> retry_permitted: false                      │
            │                                                   │                                                   │
            │                                                   │ 7. Invoke OutcomeProbeAdapter (Optional/Sync):    │
            │                                                   │    - Query target ledger via UUIDv5               │
            │                                                   │                                                   │
            │                                                   │ 8. Emit & Sign AEIB Ed25519 Receipt               │
            │                                                   │ 9. Record Observation in probe.jsonl              │
            │                                                   │                                                   │
            │ 10. Return JSON-RPC Error with Bound Receipt      │                                                   │
            │◄──────────────────────────────────────────────────┤                                                   │
```

### Traffic Observation Mechanics
1. **stdio Proxy Mode**:
   - The sidecar acts as a parent process to the target MCP tool server (`child_process` / Python `subprocess.Popen`).
   - Listens on `sys.stdin` for incoming requests from the agent host.
   - Pushes requests down the child's `stdin` and reads responses from the child's `stdout`.
2. **HTTP Middleware Mode**:
   - Runs a lightweight loopback `asyncio` HTTP server on `127.0.0.1:<port>`.
   - Reverse-proxies JSON-RPC POST requests to upstream MCP server endpoints.

### Metadata & Evidence Capture
* **Pre-Dispatch Metadata**: `agent_id`, `session_id`, `step_sequence`, `tool_name`, `timestamp_utc`.
* **Dispatch Evidence**: Bytes sent across the pipe, TCP connection state, timestamp of outbound flush.
* **Transport Observation**: Raw HTTP status code, socket error code (e.g., `ECONNRESET`, `ETIMEDOUT`), latency delta ($\Delta t$).

### Abstract Reconciliation Interface (`OutcomeProbeAdapter`)
```python
class OutcomeProbeAdapter:
    """Abstract base interface for verifying downstream state post-transport drop."""
    def probe(self, idempotency_key: str, payload_hash: str) -> dict:
        """
        Queries the authoritative downstream register.
        Returns:
            {
                'status': 'COMMITTED' | 'NOT_FOUND' | 'CONFLICT' | 'UNREACHABLE',
                'record_id': str | None,
                'ledger_timestamp': str | None
            }
        """
        raise NotImplementedError
```

---

## 📄 4. Data Model & Receipt Structure

### Receipt Format (`AEIB_JSON_ED25519_PROTOTYPE`)
Receipts are assembled in the established v0.2 structure to guarantee compatibility with `verifier/aeib_verify.py`:

```json
{
  "receipt_id": "rcpt_20260930_sidecar_02a",
  "format": "AEIB_JSON_ED25519_PROTOTYPE",
  "created_at": "2026-09-30T15:30:00Z",
  "signer": {
    "key_id": "ed25519-local-sidecar-01",
    "public_key_pem": "-----BEGIN PUBLIC KEY-----\n..."
  },
  "payload": {
    "action_id": "mcp://sess_local/101/rpc_call_01/payment.settle",
    "unsigned_payload_hash": "a1b2c3d4...",
    "idempotency_key": "59812455-88ea-52ae-8e45-130787a478ee",
    "org.smaos.aeib": {
      "version": "0.2.0",
      "disposition": "DISPATCHED_UNCONFIRMED",
      "transport_evidence": {
        "record_id": "evidence/transport.jsonl#obs-sidecar-01",
        "transport_evidence_hash": "e3b0c442..."
      },
      "outcome_probe": {
        "record_id": "evidence/probe.jsonl#prb-sidecar-01",
        "outcome_probe_hash": "f4c1d2e3..."
      },
      "retry_policy": {
        "rule_id": "RULE-02A-504-AMBIGUOUS",
        "retry_permitted": false,
        "action_required": "OUT_OF_BAND_RECONCILIATION_REQUIRED"
      }
    }
  },
  "signature": "3045022100..."
}
```

### Conceptual IETF / COSE Envelope Mapping (Future Reference)
In future iterations conforming to emerging IETF drafts (`draft-marques-asqav-compliance-receipts`), the payload maps into standard COSE header buckets:
* `action_ref` ← `payload.action_id`
* `payload_digest` ← `payload.unsigned_payload_hash`
* `verdict` ← `org.smaos.aeib.disposition`
* `vendor_extensions` ← `org.smaos.aeib` namespace

---

## ❓ 5. Open Engineering Questions

1. **Concurrent Request Multiplexing**: How should the sidecar manage in-flight request tracking across multiplexed stdio JSON-RPC streams when an upstream server handles asynchronous concurrent tool calls?
2. **Probe Exception Handling**: When the out-of-band probe itself encounters a timeout (`PROBE_EXCEPTION`), how long should the transaction remain quarantined in `DISPATCHED_UNCONFIRMED` before escalating to human operator intervention?
3. **Integration with Upstream Governance PDPs**: What is the cleanest lightweight protocol for the sidecar to consume permit/deny tokens from upstream MCP gateways (e.g., WitnessAI, Safeguard) without introducing latency overhead?

---

## 🗓️ 6. Implementation Plan & Milestones

| Milestone | Target Scope | Deliverables & Verification Criteria |
| :--- | :--- | :--- |
| **M1: Minimal stdio Proxy** | Stdio pipe interceptor, 1 test tool, synthetic fault injection | • Python wrapper reading `stdin`/`stdout`<br>• Injects UUIDv5 header<br>• Injects simulated 504 drop<br>• Emits valid v0.2 receipt verified by `aeib_verify.py` |
| **M2: Dynamic Rule Contract Binding** | Dynamic YAML loader | • Evaluates `mapping/transport-to-disposition-mapping.yaml`<br>• Correctly assigns all 7 normative dispositions based on transport input |
| **M3: Loopback HTTP & Probe Hook** | Async HTTP proxy on `127.0.0.1` + local SQLite probe adapter | • Handles HTTP/SSE JSON-RPC calls<br>• Executes real out-of-band query against local SQLite mock database<br>• Resolves `DISPATCHED_UNCONFIRMED` → `OUTCOME_VERIFIED` |
| **M4: Evaluation & Research Release** | Packaging & verification report | • Comprehensive test suite running 8/8 automated scenarios<br>• Released under SovereignNexus research repository with full limitations disclaimers |
