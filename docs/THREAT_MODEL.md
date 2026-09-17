# AEI Threat Model

**Version:** 0.2.0  
**Scope:** Agent-Effect Integrity (AEI) — Wire-Level Evidence Contamination

---

## 1. The Core Threat: Evidence Contamination

When an AI agent dispatches a mutating tool call (payment, database
write, API state change) and the downstream system responds ambiguously
(HTTP 504 timeout, TCP RST, partial write), the agent's SDK must
decide what to record.

**The Fatal Assumption:**
> *"If the Ed25519 signature is valid and the sandbox ran cleanly,
> the receipt is true."*

**The Reality:**  WASM sandboxes and MicroVMs isolate local compute,
but when the downstream payment gateway times out, the agent's SDK
emits a cryptographically valid receipt asserting `verdict: "executed"`.

The signature is mathematically correct.  The receipt is operationally
false.

---

## 2. Threat Categories

### T1 — Fabricated Confirmation

| Property | Detail |
|:---------|:-------|
| **Trigger** | HTTP 504 / TCP RST during tool call |
| **Failure** | Harness signs `CONFIRMED` without downstream ACK |
| **Impact** | Duplicate payments, phantom inventory, audit trail corruption |
| **Detection** | AEIB `TIMEOUT` + `DROP` fault modes |

### T2 — Signature-Without-Substance

| Property | Detail |
|:---------|:-------|
| **Trigger** | Valid Ed25519/ES256 signature on unverified payload |
| **Failure** | Downstream auditors accept signature as proof of effect |
| **Impact** | False compliance under DORA Art. 17(3) |
| **Detection** | Property-level sufficiency check (AEI pipeline) |

### T3 — In-Transit Payload Modification

| Property | Detail |
|:---------|:-------|
| **Trigger** | MITM, compromised proxy, or faulty middleware |
| **Failure** | Amount, counterparty, or terms silently edited |
| **Impact** | Financial loss (see: €50K skimming demo) |
| **Detection** | JCS digest comparison (`HALT:digest_mismatch`) |

### T4 — Timestamp Rollback / Replay

| Property | Detail |
|:---------|:-------|
| **Trigger** | Stale SCITT timestamp re-injected |
| **Failure** | Old receipt accepted as current |
| **Impact** | Replay attacks, regulatory timeline falsification |
| **Detection** | AEIB `EXPIRE_TIMESTAMP` fault mode |

---

## 3. Container Presence vs. Property-Level Sufficiency

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  CONTAINER PRESENCE VS. PROPERTY SUFFICIENCY                │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTAINER PRESENCE (Commoditized / Existing 50+ Tools)                      │
│   "Is a JSON trace file present? Is an Ed25519 signature attached?"         │
│   → Merely proves a log string was written and signed.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ PROPERTY-LEVEL SUFFICIENCY (The AEI Architectural Focus)                    │
│   "Does the receipt prove downstream settlement or merely dispatch?"        │
│   "Did the harness preserve UNKNOWN on a 504 timeout?"                      │
│   → Evaluates whether the claimed disposition is justified by wire evidence.│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Mitigation: The AEI Verification Pipeline

The `toxic_receipt_detector.py` implements a 5-stage pipeline that
addresses all four threat categories:

1. **JCS Digest Integrity** → mitigates T3
2. **Signature Envelope Presence** → mitigates T2
3. **Canonicalization Guard** → mitigates T3
4. **Timestamp Freshness** → mitigates T4
5. **Effect-Integrity Classification** → mitigates T1

The pipeline enforces a strict order of precedence:

```
INVALID_INPUT → MISSING_EVIDENCE → CONFLICT → REFUSED → CONFIRMED → UNKNOWN
```

`UNKNOWN` is the fail-safe terminus.  If no affirmative evidence
confirms the external effect, the receipt MUST remain `UNKNOWN`.
