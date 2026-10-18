# AEIB Production Deployment & Operational Hardening Runbook

> [!IMPORTANT]
> **Canonical Epistemic & Operational Notice:**
> **AEIB is a governed execution boundary for consequential AI actions: it binds exact action and authority before dispatch, preserves uncertainty (`EFFECT_INDETERMINATE`) after transport ambiguity, reconciles through bounded authoritative evidence, and produces operation-bound verifiable receipts.**
> All mechanisms documented in this runbook are **observed**, **tested**, **evaluated**, and **configured** **under the stated model** of our **prototype** and **scaffold** deployment baselines.

---

## 1. Grounded Deployment Architecture

AEIB deploys as an out-of-process network sidecar or container appliance strictly interposed between the untrusted agent runtime and protected core enterprise services (payment rails, transactional databases, and ERP APIs).

```
+-------------------------------------------------------------------------------+
| AGENT HOST / CONTAINER (Zone 1: Untrusted Execution Domain)                   |
|   - Agent / LLM Orchestration Framework (e.g., OpenCode 2.0, Claude, AutoGen)|
|   - Zero credentials held (API keys, mTLS certs, bearer tokens starved)       |
|   - Outbound HTTP tool mutations directed to 127.0.0.1:<GATEWAY_PORT>         |
+---------------------------------------+---------------------------------------+
                                        | HTTP POST /v1/dispatch
                                        v
+-------------------------------------------------------------------------------+
| AEIB SIDECAR APPLIANCE (Zone 2: Deterministic Boundary Runtime)               |
|   - Station 0: Typing admission and parameter bounds validation               |
|   - Station 1: Root Sponsor Quota Tree (AT56), Context Taint Gate (AT57a/b),  |
|                MCP Code Mode Taint Interlock (AT67), Mid-Session Hot-Reload   |
|                Rejection (AT68), and Zero-Token System-1 Governance (AT69)    |
|   - Station 2: Socket Forwarding, HTTP 504 Wire Latching, and Out-of-Band     |
|                Probe Reconciler (ProbeBudget: 1)                              |
|   - Station 3: Append-Only Hash-Chained Ledger & RFC 9942 SCITT Receipt Export|
+---------------------------------------+---------------------------------------+
                                        | Authenticated Wire Request
                                        v
+-------------------------------------------------------------------------------+
| CORE ENTERPRISE SYSTEMS (Zone 3: Protected Primary Ledger / Payment Rails)   |
|   - Target payment endpoints (e.g., Google AP2, LF x402, Stripe ACP)          |
|   - Read-only authoritative status receiver (e.g., refund_status_v1)          |
+-------------------------------------------------------------------------------+
```

---

## 2. Operational Health & Readiness Endpoints

The AEIB gateway daemon exposes lightweight, zero-allocation HTTP endpoints for container orchestrators (Kubernetes, Nomad, Systemd):

### Liveness Probe (`GET /healthz`)
* **Path:** `/healthz`
* **Success Status:** `200 OK`
* **Response Payload:**
  ```json
  {
    "boundary_mode": "FAIL_CLOSED",
    "status": "HEALTHY",
    "uptime_seconds": 1420
  }
  ```
* **Failure Condition:** If internal worker threads deadlock or unhandled process exceptions occur, the socket fails to respond and the orchestrator restarts the pod.

### Readiness Probe (`GET /readyz`)
* **Path:** `/readyz`
* **Success Status:** `200 OK` (when ledger is mounted, unbroken chain tip is verified, and pinned tool manifests are active)
* **Degraded Status:** `503 Service Unavailable` (if the ledger volume is missing, chain tip verification fails, or an unresolved continuity halt is latched)
* **Response Payload:**
  ```json
  {
    "chain_tip": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
    "indeterminate_escrow_count": 0,
    "ledger_exists": true,
    "pinned_plugins_count": 4,
    "ready": true
  }
  ```

---

## 3. Configuration & Parameter Hardening

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `AEIB_HOST` | string | `127.0.0.1` | Local loopback interface binding. |
| `AEIB_PORT` | integer | `8443` | Listening port for agent tool dispatch calls. |
| `AEIB_SPRINT_LIMIT_MINOR` | integer | `250000` | Rolling 5-hour sprint spend limit in minor currency units (€2,500.00). |
| `AEIB_EPOCH_LIMIT_MINOR` | integer | `1000000` | Rolling 7-day epoch spend limit in minor currency units (€10,000.00). |
| `AEIB_DOWNSTREAM_TARGET_URL` | string | *required* | Downstream transactional API endpoint (e.g., core banking gateway). |
| `AEIB_DOWNSTREAM_PROBE_URL` | string | *required* | Downstream read-only status receiver for out-of-band reconciliation. |
| `AEIB_HUMAN_PUBLISHER_KEY_ID` | string | *required* | Identifier of offline human security officer (`did:key:...`). |
| `AEIB_LEDGER_PATH` | path | `/var/log/aeib/ledger.jsonl` | Persistent append-only hash-chain volume mount. |

---

## 4. DORA Article 11 & 12 Incident Response & Recovery Runbook

When a downstream transport ambiguity occurs (such as an upstream load balancer emitting `HTTP 504 Gateway Timeout` or a TCP connection reset):

1. **Deterministic Latching (`EFFECT_INDETERMINATE`):**
   * Station 2 immediately traps the ambiguous outcome.
   * `retry_allowed` is set to `False` to prevent duplicate mutation attempts.
   * The in-flight transaction amount is locked in sprint escrow (`_indeterminate_escrow`), preventing timeout-smurfing attacks (`AT58`).
2. **Single-Flight Out-of-Band Reconciliation (`POST /v1/reconcile`):**
   * Station 2 initiates an out-of-band probe query (`ProbeBudget: 1`) to `AEIB_DOWNSTREAM_PROBE_URL`.
   * **Case A: Target confirms transaction committed (`COMMITTED` / `CONFIRMED`):**
     * State transitions to `RESOLVED_CONFIRMED`.
     * Escrowed amount is permanently deducted from the sprint and epoch window.
     * Signed continuity receipt is emitted with disposition `RESOLVED_CONFIRMED`.
   * **Case B: Target refutes transaction (`NOT_FOUND` / `REFUTED`):**
     * State transitions to `RESOLVED_REFUTED`.
     * Target returns an Ed25519-signed refutation attestation.
     * Escrowed amount is released back to the available sprint pool.
     * Signed continuity receipt is emitted with disposition `RESOLVED_REFUTED`.
3. **Continuous Auditing (`GET /v1/ledger/receipts`):**
   * Downstream SIEM and compliance systems harvest Ed25519-signed receipts.
   * External verifiers validate that `prev_chain_tip` unbroken linkages match without reading confidential agent prompt memory.

---

## 5. Architectural Scaffolding Awareness (AGENTS.md Section 5)

* **Linux eBPF & Kernel LSM (`ebpf/`):**
  * Hook definitions in `ebpf/ebpf_agent_guard.c` and `ebpf/ebpf_lsm_agent_guard.c` are structural scaffolding (`SCAFFOLD_ONLY`).
  * Live runtime enforcement is performed in userspace by AEIB Station 0–3 interlocks. Do not claim kernel-level enforcement unless deployed on a validated Linux kernel with active BPF LSM.
* **Hardware Attestation (`hardware_attestation/`):**
  * Type structures for Intel TDX and AMD SEV-SNP are structural scaffolding (`SCAFFOLD_ONLY`).
  * Full attestation requires execution inside an authenticated Confidential Virtual Machine (CVM).
* **Saga Compensation Consistency:**
  * Distributed compensation operates under *eventual consistency* via asynchronous queues, NOT atomic two-phase commit (2PC).
