# Reference Audit: mcp-shield (DainoJung/mcp-shield)

**Document Type:** Vendor & Open-Source Research Audit  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Target Repository:** `https://github.com/DainoJung/mcp-shield.git`  
**Commit Inspected:** HEAD (September 2026)  
**License:** MIT License (Copyright (c) 2026 mcp-shield contributors)  
**Purpose:** Technical assessment of existing MCP proxy architecture to inform the AEIB v0.2.1 minimal sidecar design.

---

## 🔍 1. Executive Summary

`mcp-shield` is an open-source TypeScript reverse proxy and middleware harness designed to protect MCP servers from runaway agent calls, excessive latency, and unhandled crashes.

### Key Capabilities Provided
* **Transport Modes**: `StdioProxy` (spawning downstream tools via `child_process.spawn` with piped stdio) and `MultiServerProxy`.
* **Middleware Chain**:
  - `timeout.ts`: Configurable per-tool invocation timeouts using `Promise.race`.
  - `retry.ts`: Configurable retry loops (exponential, linear, fixed backoff with jitter).
  - `circuit-breaker.ts`: Standard circuit breaking (CLOSED $\to$ OPEN $\to$ HALF_OPEN).
  - `rate-limiter.ts`: Token bucket / window-based request throttling.
  - `tool-filter.ts`: Allowlist / denylist filtering of exposed MCP tools.

---

## 🔬 2. Deep Dive: Failure Handling & The Ambiguity Gap

An audit of `mcp-shield`'s core failure handling modules reveals the exact industry blindspot that AEIB addresses:

### A. The Timeout Blindspot (`src/middleware/timeout.ts`)
When an MCP tool invocation exceeds the configured timeout deadline:
```typescript
// src/middleware/timeout.ts:24-31
if (timedOut) {
  return makeErrorResponse(
    ctx.request.id,
    ErrorCodes.TIMEOUT,
    `Tool '${ctx.toolName}' timed out after ${timeoutMs}ms`,
    { type: "timeout", tool: ctx.toolName, timeout_ms: timeoutMs },
  );
}
```
* **The Vulnerability**: The proxy aborts waiting for the child process and emits a generic `ErrorCodes.TIMEOUT` (-32000). 
* **State Blindness**: The proxy does **not** know whether the child process committed a database write, dispatched an external wire payment, or died before execution. 
* **Agent Fallback**: The client agent receives a standard JSON-RPC error. If the calling framework or orchestrator is configured to handle errors, it risks assuming failure and issuing an unhedged duplicate call.

### B. The Retry Logic (`src/middleware/retry.ts`)
```typescript
// src/middleware/retry.ts:4-9
const NON_RETRYABLE_CODES: ReadonlySet<number> = new Set([
  ErrorCodes.TIMEOUT,
  ErrorCodes.INVALID_PARAMS,
  ErrorCodes.METHOD_NOT_FOUND,
  ErrorCodes.CIRCUIT_OPEN,
]);
```
* **Observation**: `mcp-shield` correctly marks `ErrorCodes.TIMEOUT` as non-retryable inside its *own* internal proxy loop to avoid compounding gateway load.
* **The Missing Link**: It does not provide any reconciliation mechanism for the caller. The transaction is simply abandoned in an unknown state.

---

## ⚖️ 3. Architectural Comparison: mcp-shield vs. AEIB Sidecar

| Dimension | `mcp-shield` | AEIB Sidecar (`MINIMAL_MCP_SIDECAR_DESIGN`) |
| :--- | :--- | :--- |
| **Primary Goal** | Runtime stability & fault tolerance | **Post-dispatch execution integrity & auditability** |
| **Transport Handling**| Pipe stdio, forward JSON-RPC | Pipe stdio, forward JSON-RPC + loopback HTTP |
| **Idempotency** | None (no payload hashing or header injection) | **Pre-dispatch deterministic UUIDv5 injection** |
| **504 / Timeout Verdict**| Generic `ErrorCodes.TIMEOUT` | **Normative `DISPATCHED_UNCONFIRMED` disposition** |
| **Retry Enforcement** | Internal flag, no verifiable caller constraint | **Signed `retry_permitted: false` policy receipt** |
| **Reconciliation** | None (caller must manually handle) | **Out-of-band `OutcomeProbeAdapter` query** |
| **Audit Artifact** | Ephemeral console / file logs | **Append-only Ed25519 cryptographic receipts** |

---

## 🛠️ 4. What to Learn vs. What to Re-Implement

### Valuable Patterns to Learn From
1. **JSON-RPC Framing (`message-parser.ts`)**: Clean handling of both Content-Length headers (LSP/MCP specification) and raw newline-delimited JSON.
2. **Process Lifecycle Management (`stdio-proxy.ts`)**: Graceful handling of child process crashes (`SERVER_CRASH`), process signal propagation, and pending request map cleanup.
3. **Middleware Pipeline Composition (`chain.ts`)**: Standard onion-style middleware pipeline (`next()` passing) for composable tool intercepts.

### What AEIB Must Implement Uniquely
1. **Canonical JSON Normalization**: Sorting keys and formatting compact separators prior to wire egress.
2. **Pre-Dispatch Digest Binding**: Generating `unsigned_payload_hash` before passing the message to the downstream tool.
3. **AEIB Mapping Contract Evaluation**: Direct dynamic evaluation of `transport-to-disposition-mapping.yaml`.
4. **Cryptographic Receipt Signing**: Asymmetric Ed25519 signing of the resulting disposition receipt.

---

## 📜 5. Licensing & Clean-Room Governance

* **License**: MIT License.
* **Governance**: Because AEIB’s core prototype is implemented in Python and targets verifiable deterministic state machines, we will maintain a **clean-room implementation** in Python for `transport_observer.py`.
* Any conceptual structure borrowed from `mcp-shield`'s stdio lifecycle will be properly attributed in compliance with the MIT license.
