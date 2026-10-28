# Automated Saga Compensation & Reconciliation Protocol
## Technical Specification: Resolving `verdict: UNKNOWN` & Preserving the Net Ledger Invariant

**Standard Alignment:** IETF SCITT Agent Action Capsules · DORA RTS 2024/1772 · Proof-or-Stop (arXiv:2607.14890)  
**Component Reference:** `ocr_audit/saga_reconciler.py`  
**Classification:** Technical Architectural Specification  

---

### 1. The Core Operational Problem: The 504 Timeout Dilemma

When an autonomous AI agent initiates a mutating action (such as an external SEPA credit transfer or database update) and the remote transport layer experiences a network partition, dropped socket, or **HTTP 504 Gateway Timeout**, standard agent harnesses suffer from a structural vulnerability:

1. **The Blind Retry Hazard:** The agent assumes failure and initiates an immediate retry. If the remote core banking system *did* process the initial request before the connection severed, the blind retry results in a **duplicate payout** (double spend).
2. **The Hallucinated Confirmation:** The agent LLM catches the exception, infers success from its conversational prompt context, and records `status: CONFIRMED` in the cold log. Downstream audit logs become contaminated with false claims.

To resolve this, the **Sovereign Multi-Agent OS (`smaos-ai`)** enforces a two-tier defense:
* **Ex-Ante Reflector:** Immediately freezes unconfirmed transport events at **`verdict: UNKNOWN`** ($\Delta = 0$).
* **Saga Compensation Engine:** An out-of-band asynchronous worker deterministically resolves `UNKNOWN` transactions into either `CONFIRMED` or `COMPENSATED_ROLLBACK`.

---

### 2. The Deterministic Saga State Machine

```text
                     [ Mutating Tool Call Dispatched ]
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
             [ HTTP 200 OK ]                 [ HTTP 504 / RST ]
             Target Committed                Connection Dropped
                     │                               │
                     ▼                               ▼
             [ CONFIRMED ]                   [ Freeze: UNKNOWN ]
             (Δ_net = +Amount)               (Freeze State: Δ = 0)
                                                     │
                                                     ▼
                                      [ Bitemporal Wire Query ]
                                      Query by Idempotency Key & TxID
                                                     │
                     ┌───────────────────────────────┼───────────────────────────────┐
                     ▼                               ▼                               ▼
           [ Commit Proven ]               [ Uncommitted / Dropped ]       [ Conflict / SLA Expiry ]
           valid_time confirmed            target_committed = False        elapsed > 300s
                     │                               │                               │
                     ▼                               ▼                               ▼
             [ CONFIRMED ]               [ COMPENSATED_ROLLBACK ]          [ MANUAL_ESCALATION ]
             Transition to               Idempotent REVERT_TRANSFER        Requires Dual-Control
             Settled State               Net Ledger Invariant:             Cryptographic Sign-Off
             (Δ_net = +Amount)           \sum \Delta_net = 0.00            Account/Tool Locked
```

---

### 3. Mathematical Invariants & State Transitions

#### Invariant 1: Net Ledger Invariant
At all times, the net effect of an unresolved or rolled-back transaction on the host ledger must be zero:
$$\sum \Delta_{\text{net}} = 0.00$$

#### Invariant 2: Bitemporal Determinism
A transaction state transition from `UNKNOWN` to `CONFIRMED` requires independent proof across two temporal dimensions:
1. **Valid Time ($T_v$):** The timestamp when the business event occurred in the real world.
2. **System / Transaction Time ($T_s$):** The physical timestamp when the database commit log or wire packet recorded the mutation.

A confirmation is only valid if $T_s \ge T_v$ and $|T_s - T_v| \le \delta_{\text{max}}$ ($\delta_{\text{max}} = 50\,\text{ms}$).

#### Invariant 3: Idempotent Compensation Derivation
The compensating transaction identifier must be cryptographically derived from the original transaction identifier and idempotency key to prevent double reversal:
$$\text{TxID}_{\text{comp}} = \text{"revert-"} \parallel \text{Trunc}_{16}\Big(\text{SHA-256}\big(\text{TxID}_{\text{orig}} \parallel \text{":"} \parallel \text{IdempotencyKey}\big)\Big)$$

---

### 4. Wire Schema & Data Structures

#### A. Input Unresolved Receipt Capsule
```json
{
  "capsule": {
    "action_id": "act-wire-042",
    "txid": "tx-payment-1001",
    "idempotency_key": "idem-9f6f8a1c6d7ec419",
    "amount": 420000.0,
    "currency": "EUR",
    "timestamp": 1758414000.0,
    "harness_verdict": "UNKNOWN",
    "wire_fault": "HTTP_504_GATEWAY_TIMEOUT"
  }
}
```

#### B. Compensated Rollback Output Capsule
```json
{
  "original_txid": "tx-payment-1001",
  "compensation_txid": "revert-a1b2c3d4e5f67890",
  "idempotency_key": "idem-9f6f8a1c6d7ec419",
  "action": "REVERT_TRANSFER",
  "delta_net": 0.00,
  "status": "COMPENSATED_ROLLBACK",
  "timestamp": 1758414025.12,
  "signature": "sig:ed25519:5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f..."
}
```

#### C. Manual Escalation Output Capsule (Dual-Control Lock)
```json
{
  "txid": "tx-payment-1001",
  "status": "MANUAL_ESCALATION",
  "reason": "SLA timeout or cryptographic state conflict",
  "requires_dual_control_signoff": true,
  "lock_scope": ["payments:sepa:initiate", "account:4801924"],
  "timestamp": 1758414300.00
}
```

---

### 5. Implementation Verification Protocol

The Saga Reconciler is evaluated against a 3-scenario falsifiability matrix:
1. **Scenario A (Downstream Settled):** Remote banking database confirms commit. Engine transitions `UNKNOWN` $\to$ `CONFIRMED`.
2. **Scenario B (Downstream Uncommitted):** Remote socket shows connection reset with no commit ID. Engine dispatches idempotent `REVERT_TRANSFER` with `delta_net = 0.00` transitioning to `COMPENSATED_ROLLBACK`.
3. **Scenario C (SLA Exceeded / Conflict):** Remote system unreachable past 300 seconds SLA or conflicting ledger records found. Engine transitions to `MANUAL_ESCALATION` and initiates an RCE Cockpit interrupt requiring dual-control Ed25519 signatures.
