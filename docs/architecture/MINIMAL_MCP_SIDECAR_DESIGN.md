# Minimal MCP Sidecar Interceptor — Research Architecture Specification

**Status:** Research Prototype Design (v0.2.1 Target Milestone)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Scope:** Research prototype design for local stdio/HTTP MCP proxying. Not a production security gateway or supported enterprise SDK.

---

## 🎯 1. Design Objective & Scope Boundary

The purpose of this minimal sidecar interceptor is to prove that the **AEIB 7-state disposition model and retry constraints** can be enforced transparently between an MCP client (e.g., Claude Desktop, Cursor, local agent orchestrator) and an MCP server without requiring changes to agent code or tool implementations.

### What It Delivers (Research Scope)
* Transparent stdio pipe interceptor (stdin/stdout JSON-RPC proxy).
* Transparent local HTTP/SSE reverse proxy on `127.0.0.1:<port>`.
* Deterministic UUIDv5 idempotency key injection into mutating requests.
* Wire-fault detection (HTTP 504, timeout exception, abrupt EOF/reset).
* Automated assignment of `DISPATCHED_UNCONFIRMED` on transport drops.
* Enforcement of `retry_permitted: false` in the client response receipt.
* Local append-only JSONL receipt emission signed with local Ed25519 key.

### What It Explicitly Does NOT Deliver (Non-Scope)
* No distributed consensus or multi-node clustering.
* No HSM / KMS cloud key integration (uses local PEM key pairs).
* No full RFC 8785 (JCS) or RFC 9052 (COSE_Sign1) certification.
* No production enterprise SLA, multi-tenancy, or high-throughput tuning.

---

## 🏗️ 2. Architectural Pipeline

```text
┌────────────────┐           ┌──────────────────────────────────────┐           ┌────────────────┐
│   MCP CLIENT   │           │          AEIB LOCAL SIDECAR          │           │   MCP SERVER   │
│ (Claude/Agent) │           │     (Minimal Python / Rust Proxy)    │           │ (Tools/Backend)│
└───────┬────────┘           └──────────────────┬───────────────────┘           └───────┬────────┘
        │                                       │                                       │
        │ 1. tools/call (JSON-RPC)              │                                       │
        ├──────────────────────────────────────►│                                       │
        │                                       │ 2. Canonicalize & Mint UUIDv5         │
        │                                       │ 3. Log Pre-Dispatch Hash              │
        │                                       │ 4. Inject X-Idempotency-Key           │
        │                                       ├──────────────────────────────────────►│
        │                                       │                                       │
        │                                       │ 5. Transport Ambiguity (504 / RST)   │
        │                                       │    ⚠️ Socket Drops / Timeout          │
        │                                       │◄······································┤
        │                                       │                                       │
        │                                       │ 6. Evaluate Rule Contract:            │
        │                                       │    -> DISPATCHED_UNCONFIRMED          │
        │                                       │    -> retry_permitted = false         │
        │                                       │ 7. Emit Ed25519 Signed Receipt        │
        │ 8. Return JSON-RPC Error with Receipt │                                       │
        │◄──────────────────────────────────────┤                                       │
```

---

## ⚙️ 3. Core Component Modules

### Module A: Transport Observer (`transport_observer.py`)
1. **stdio Mode**: Spawns the downstream MCP server as a subprocess, piping `stdin`, `stdout`, and `stderr`. Reads newline-delimited JSON-RPC messages.
2. **HTTP/SSE Mode**: Listens on a local loopback port (`127.0.0.1:8080`) and forwards requests to the upstream server endpoint.
3. **Fault Interception**: Wraps socket reads in an explicit timeout block. If an upstream response exceeds the deadline or returns HTTP 504 / connection reset:
   - Traps the raw transport event.
   - Prevents the exception from being masked as a generic connection failure.
   - Dispatches the observation to the rule engine.

### Module B: Normalization & Idempotency Injector (`idempotency_injector.py`)
1. Filters incoming JSON-RPC calls for state-mutating methods (`tools/call`).
2. Sorts parameter keys recursively and formats with compact delimiters (`,`, `:`).
3. Computes `unsigned_payload_hash = sha256(canonical_json)`.
4. Derives `uuidv5(NAMESPACE_OID, unsigned_payload_hash)`.
5. Injects the derived key into the tool request arguments or HTTP header (`X-Idempotency-Key`).

### Module C: Disposition Rule Engine (`disposition_engine.py`)
1. Loads `mapping/transport-to-disposition-mapping.yaml` at startup.
2. Evaluates the observed transport event against the normative rule hierarchy:
   - Policy context / authority expired $\to$ fail-closed before wire dispatch.
   - 504 timeout / socket drop $\to$ rule `RULE-02A-504-AMBIGUOUS`.
3. Outputs:
   - `disposition`: `DISPATCHED_UNCONFIRMED`
   - `retry_policy.retry_permitted`: `false`
   - `retry_policy.rule_id`: `RULE-02A-504-AMBIGUOUS`

### Module D: Receipt Signer & Storage (`receipt_signer.py`)
1. Assembles receipt payload under the `org.smaos.aeib` namespace.
2. Signs using local Ed25519 private key (`public-keys/ed25519-private.pem`).
3. Appends the complete signed record to `audit_out/receipts.jsonl`.
4. Appends transport observation to `evidence/transport.jsonl`.

---

## 🚦 4. Client Response Format

When an ambiguous timeout is trapped, the sidecar returns a structured JSON-RPC error response to the client containing the receipt metadata:

```json
{
  "jsonrpc": "2.0",
  "id": "call_12345",
  "error": {
    "code": -32000,
    "message": "AEIB_DISPATCHED_UNCONFIRMED: Transport timed out post-dispatch. Automated retry prohibited.",
    "data": {
      "aeib_receipt_id": "rcpt_20260930_02a",
      "disposition": "DISPATCHED_UNCONFIRMED",
      "retry_permitted": false,
      "idempotency_key": "59812455-88ea-52ae-8e45-130787a478ee",
      "action_required": "AUTHORITATIVE_OUT_OF_BAND_PROBE_REQUIRED"
    }
  }
}
```

---

## 🗓️ 5. Implementation Roadmap (Research Prototype)

| Milestone | Deliverable | Scope / Caveats |
| :--- | :--- | :--- |
| **M1: Minimal stdio Interceptor** | Python script wrapping a sample stdio MCP server | Local testing with simulated 504 injection |
| **M2: Mapping YAML Integration** | Dynamic evaluation of existing AEIB rule contract | Validates compatibility with v0.2 verifier |
| **M3: Loopback HTTP Proxy** | Async HTTP reverse proxy with timeout trapping | Handles SSE / streaming tool responses |
| **M4: Public Research Release** | Documented prototype repository under SovereignNexus | Marked clearly as experimental independent research |
