# RFC: Idempotent Tool Execution and Effect Indeterminacy Latching in the Model Context Protocol (MCP v1.2)

- **Status:** Proposed Standard / Informational RFC
- **Working Group:** Model Context Protocol (MCP) Extensions & Conformance
- **Target Version:** MCP Specification v1.2
- **Authors:** AEIB Systems Engineering Group
- **Date:** October 2026
- **Test Suite Reference:** `conformance/mcp_golden_vectors/` (30 Golden Test Vectors)
- **Reference Implementation:** `adapters/mcp/idempotent_mcp_proxy.py`

---

## 1. Abstract & Motivation

The Model Context Protocol (MCP) standardizes how reasoning models invoke local and remote tools. However, the current specification (2025-11-25) lacks normative rules for **transactional idempotency** and **failure ambiguity handling** when tools execute state-mutating actions (e.g., database writes, financial transactions, cloud resource provisioning, or physical actuator controls).

In practice, client-server transport connections over HTTP/SSE or stdio are susceptible to network drops, gateway timeouts (HTTP 504), or process restarts. When a timeout occurs:
1. The client reasoning model cannot determine whether the tool execution completed on the server prior to the transport failure.
2. The model's natural stochastic behavior frequently leads to a prompt re-generation and tool retry, often altering parameter strings or formatting.
3. If the server does not enforce wire-level idempotency and indeterminacy latching, duplicate side-effects occur.

This RFC proposes two normative protocol extensions for MCP v1.2:
1. **Explicit Operation Identity & Canonical CAID Binding:** Standardizing `operation_id` parameter passing and RFC 8785 JSON Canonicalization Scheme (JCS) intent hashing.
2. **The `EFFECT_INDETERMINATE` Protocol State & Error Code `-32001`:** A standardized mechanism for latching ambiguous executions, preventing blind retries while preserving transaction state until authoritative reconciliation occurs.

---

## 2. Specification of Extensions

### 2.1 The `operation_id` Field
When an agent client dispatches a tool call with mutation semantics, the `CallToolRequest` parameters object SHOULD include an `operation_id`:

```json
{
  "jsonrpc": "2.0",
  "id": "req-10293",
  "method": "tools/call",
  "params": {
    "name": "disburse_funds",
    "operation_id": "op_98a7f23c_4b1a",
    "arguments": {
      "account_id": "acc_88120",
      "amount_minor": 50000,
      "currency": "EUR"
    }
  }
}
```

If the client omits `operation_id`, the server MAY fall back to computing a weak Content-Addressed Action Identifier (CAID) over the normalized arguments via RFC 8785:
$$\text{CAID} = \text{SHA-256}(\text{JCS}(\text{arguments}))$$
However, servers adhering to strict execution policies MAY reject mutating calls lacking an explicit `operation_id`.

### 2.2 Inspection of `isError` in JSON-RPC Responses
Under the current MCP specification, servers return tool execution outputs wrapped in a `CallToolResult` structure. Implementations MUST NOT interpret an HTTP 200 OK status as a successful tool mutation without inspecting the payload `isError` flag.

```json
{
  "jsonrpc": "2.0",
  "id": "req-10293",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Insufficient funds in account ledger"
      }
    ],
    "isError": true
  }
}
```

- If `isError: true`, the boundary classifies the result as `REFUTED` (definitive business failure). The mutation did not occur, and no indeterminate latch is required.
- If `isError: false` or omitted, and HTTP status is 200, the result is classified as `CONFIRMED`.

### 2.3 The `EFFECT_INDETERMINATE` State (Error Code `-32001`)
When an upstream MCP server encounters a transport drop, 504 Gateway Timeout, connection reset, or an ambiguous 5xx response during a mutating tool invocation, the boundary MUST NOT return a generic error that invites immediate re-dispatch. Instead, it MUST return error code `-32001`:

```json
{
  "jsonrpc": "2.0",
  "id": "req-10293",
  "error": {
    "code": -32001,
    "message": "Tool execution outcome is indeterminate. Blind retry blocked.",
    "data": {
      "status": "EFFECT_INDETERMINATE",
      "operation_id": "op_98a7f23c_4b1a",
      "caid": "a1b2c3d4...",
      "resolution": "authoritative_probe_required",
      "latch_timestamp": 1792576800
    }
  }
}
```

### 2.4 Latching Invariant and Blind Retry Rejection
Once an `operation_id` or `CAID` enters `EFFECT_INDETERMINATE`:
1. The boundary locks the state in local durable storage (SQLite WAL or Redis/Postgres).
2. Any subsequent tool proposal containing the identical `operation_id` or `CAID` MUST fail closed with error code `-32001` or `-32002` (`HALT_BLIND_RETRY_BLOCKED`) until an out-of-band probe or supervisor warrant resolves the state.
3. Cache TTL expiration MUST NOT discard the indeterminate state; the uncertainty latch persists until authoritative settlement.

---

## 3. Conformance Suite: The 30 Golden Test Vectors

To ensure cross-vendor interoperability across Python, Rust, Go, and TypeScript MCP gateways, we provide a suite of 30 golden test vectors located in `conformance/mcp_golden_vectors/`:

- **Vectors 1–5: Baseline Idempotency:** Validates identical argument caching, HTTP 200 OK replay, and parameter normalization.
- **Vectors 6–10: MCP `isError` Differentiation:** Validates that HTTP 200 responses with `isError: true` do not poison the cache as successful mutations.
- **Vectors 11–15: Transport Timeouts & 5xx Latching:** Validates that 504 Gateway Timeout and 502 Bad Gateway transition to `EFFECT_INDETERMINATE` and reject immediate retries.
- **Vectors 16–20: Composite Identity & Tenant Scoping:** Validates that identical `operation_id`s across different tenants or principals remain isolated.
- **Vectors 21–25: Authoritative Probe Settlement:** Validates reconciliation workflows where out-of-band status probes resolve indeterminate entries to `CONFIRMED` or `VOIDED`.
- **Vectors 26–30: Adversarial Falsification:** Validates detection of homoglyph argument tampering, timestamp spoofing, and TTL expiration attacks against unresolved states.

---

## 4. Security Considerations

1. **Denial of Service via Latch Exhaustion:** Attackers might intentionally trigger network timeouts to latch operation slots. Gateways SHOULD enforce rate limiting per tenant and client PID.
2. **Confused Deputy Attacks:** Multi-tenant MCP servers MUST bind the idempotency key to the authenticated caller's identity (`tenant_id:principal_id:operation_id`) to prevent one tenant from probing or latching another tenant's operations.
3. **Transport Security:** Because tool arguments may contain sensitive transaction details, all communication MUST occur over authenticated local Unix Domain Sockets (`0o600`) or TLS 1.3 connections.

---

## 5. Conclusion

By adopting explicit operation identifiers, payload-level `isError` verification, and stateful `EFFECT_INDETERMINATE` latching, the MCP ecosystem can bridge the divide between non-deterministic reasoning agents and mission-critical external APIs without risking duplicate side-effects.
