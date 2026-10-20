# AEIB Stripe Sandbox Test-Mode Proxy Wire-Level Latch Test Plan

```text
Specification Version : 1.0.0-rc.5-plan
Status                : Wire-Level Latch & Reconciliation Evaluation Plan
Target Rail           : Stripe Test-Mode API (https://api.stripe.com/v1) & Stripe Connect
Execution Model       : Host-Side Proxy with Agent Credential Starvation
```

---

## 1. Scope and Architecture Overview

This test plan defines the wire-level validation procedure for evaluating the AEIB Station 2 egress proxy against the real Stripe test-mode sandbox (`https://api.stripe.com/v1`).

The evaluation focuses on three core invariants:
1. **Host-Side Credential Starvation:** The untrusted agent runtime process holds zero Stripe bearer keys (`sk_test_...`) or webhook signing secrets (`whsec_...`). All secrets reside strictly in the host-side egress gateway.
2. **Deterministic Idempotency Key Derivation:** Every mutating HTTP request derives an operation-bound `Idempotency-Key` formatted per RFC draft (`draft-ietf-httpapi-idempotency-key-header`):
   ```text
   Idempotency-Key: aeib-idem-v1-<sha256(operation_id:action_caid)[:32]>
   ```
3. **Wire-Level Transport Latching & Single-Flight Reconciliation:** When transport ambiguity occurs (e.g., HTTP 504 Gateway Timeout, TCP RST, or dropped connection), the proxy transitions the operation to `EFFECT_INDETERMINATE`, blocks blind retries fail-closed, and executes a bounded single-flight reconciliation probe (`ProbeBudget: 1`).

---

## 2. Wire Architecture & Trust Boundary

```text
┌────────────────────────────────────────────────────────┐
│ Untrusted Agent Runtime (Guest / Sandbox)              │
│  - Proposes structured mutation (operation_id, amount) │
│  - Zero knowledge of sk_test_* or whsec_*              │
└───────────────────────────┬────────────────────────────┘
                            │ Unix Domain Socket / VSOCK
                            ↓
┌────────────────────────────────────────────────────────┐
│ Host-Side AEIB Station 1 Boundary                      │
│  - Computes and binds exact action CAID                │
│  - Verifies spend limit against local budget escrow    │
│  - Appends intent record to atomic WAL                 │
│  - Issues Ed25519-signed dispatch warrant              │
└───────────────────────────┬────────────────────────────┘
                            │
                            ↓
┌────────────────────────────────────────────────────────┐
│ Station 2 Host Egress Proxy                            │
│  - Validates Station 1 Ed25519 signature & CAID        │
│  - Injects host-held 'Authorization: Bearer sk_test_*' │
│  - Derives and injects deterministic 'Idempotency-Key' │
│  - Transmits payload over TLS to Stripe Sandbox        │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS (TLS 1.3)
                            ↓
┌────────────────────────────────────────────────────────┐
│ Stripe Sandbox Test Rail (https://api.stripe.com/v1)   │
└────────────────────────────────────────────────────────┘
```

---

## 3. Test Scenarios and Evaluation Procedures

### Scenario 1: Nominal Test-Mode Mutation Dispatch
- **Preconditions:** Valid Station 1 budget allocation; valid Ed25519 warrant.
- **Action:** Host-side proxy dispatches `POST /v1/refunds` with injected `Idempotency-Key` and `Bearer sk_test_...`.
- **Expected Outcome:** Stripe sandbox responds with HTTP 200 and a valid refund object (`re_...`). Station 1 commits spend to `CONFIRMED` and issues an RFC 8785 Ed25519 continuity receipt.

### Scenario 2: Transport Ambiguity Latch (HTTP 504 / TCP Reset)
- **Preconditions:** Wire fault injected between proxy and Stripe (or simulated via Toxiproxy / loopback listener).
- **Action:** Upstream HTTP 504 Gateway Timeout or TCP connection reset received after dispatch.
- **Expected Outcome:**
  1. Proxy records `EFFECT_INDETERMINATE`.
  2. The budget remains held in escrow (neither released nor confirmed).
  3. A subsequent dispatch attempt with the same `operation_id` or `caid` is rejected immediately with `HALT_REPLAY_DETECTED` or `LATCHED_INDETERMINATE`.

### Scenario 3: Bounded Status Probe Reconciliation
- **Preconditions:** Operation latched in `EFFECT_INDETERMINATE`.
- **Action:** Station 2 initiates a read-only query: `GET /v1/refunds?charge=ch_...` using `ProbeBudget: 1`.
- **Expected Outcome:**
  - If the refund is found in Stripe test records: Proxy transitions state to `SETTLED_CONFIRMED` with target record evidence digest.
  - If the charge has no corresponding refund: Proxy verifies terminal absence, releases escrowed budget, and transitions state to `SETTLED_REFUTED`.
  - Max probe attempts: strictly 1. No continuous polling loops.

### Scenario 4: Webhook Ingestion & Signature Verification
- **Preconditions:** Ingress webhook endpoint active on host gateway.
- **Action:** Ingest `charge.refunded` webhook payload with `Stripe-Signature` header (`t=...,v1=...`).
- **Expected Outcome:**
  1. Real HMAC-SHA256 signature verification over `f"{timestamp}.{payload}"` matching `whsec_...`.
  2. Rejection of signatures older than `tolerance_sec: 300` (`ERR_WEBHOOK_TIMESTAMP_EXPIRED`).
  3. Rejection of tampered payloads or forged `v1` signatures (`ERR_INVALID_WEBHOOK_SIGNATURE`).
  4. Duplicate webhook events matching an already settled `operation_id` are acknowledged without double-settlement.

### Scenario 5: Process Memory Credential Starvation Audit
- **Preconditions:** Agent runtime actively executing test tasks.
- **Action:** Inspect agent process memory (`/proc/<pid>/maps` or heap dump) for strings matching `sk_test_` or `whsec_`.
- **Expected Outcome:** Zero occurrences observed. The agent environment contains no external payment credentials.

---

## 4. Verification Harness Commands

The test suite executing this plan is located in `tests/test_stripe_connect_reconciliation_adapter.py`:

```bash
# Execute unit and wire-latching test suite
pytest tests/test_stripe_connect_reconciliation_adapter.py -v

# Verify AST purity and zero-mock enforcement
python3 compliance/ast_purity.py tests/test_stripe_connect_reconciliation_adapter.py
python3 compliance/no_mock_enforcer.py
```

*Observed Status:* 5/5 tests passing locally.
