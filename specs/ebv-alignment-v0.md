# Effectuation-Boundary Verification (EBV) — Alignment Specification v0

```text
Status       : Informational Vocabulary Alignment (Candidate Reference Implementation)
Reference    : IETF Internet-Draft draft-das-agent-execution-finality-00
Legal Notice : Internet-Drafts possess no formal IETF standing and are not endorsed by the IETF.
```

---

## 1. Scope & Informational Alignment

This specification outlines the conceptual and architectural alignment between AEIB and the terminology proposed in `draft-das-agent-execution-finality-00` (*Protected Execution-Finality Architecture for AI and Autonomous Systems*).

AEIB serves as a candidate reference implementation evaluating selected EBV concepts under declared simulation and local testbed models. This document defines the terminology mapping, operational state machine, and invariants governing dispatch-time boundary checks.

---

## 2. Terminology Mapping & Architectural Caveats

| Internet-Draft Term | AEIB Architecture Primitive | Operational Meaning | System Boundary Caveat |
|---|---|---|---|
| **Protected Enforcement Domain (PED)** | Host-Side AEIB Authorization & Escrow Service | The isolated boundary where state, permissions, and budgets are evaluated prior to execution. | Isolation boundary is deployment-specific (UDS, process jail, or microVM). |
| **Candidate Act** | Signed Proposed Action / Pre-Dispatch Intent | The agent's proposed tool invocation or mutation before wire transmission. | The act is non-effective until authorized, staged, and dispatched. |
| **Finality Sink** | Authorized External Target System & Downstream Rails | The external service where consequential side-effects occur. | A local WAL or database commit is not external-rail finality. |
| **Protected Evidence Store** | Local Durable Ledger (`DirectIoWal` / WAL) | The append-only, durable evidence log recording intents, escrows, and receipts. | Stores local causal proof; does not force external side-effects to commit. |
| **Non-Effective State** | `PROPOSED`, `DISPATCHED`, `EFFECT_INDETERMINATE`, `REFUTED` | States where the external outcome is pending, unconfirmed, or denied. | An action in `DISPATCHED` may still be in-flight or externally effective on downstream rails. |
| **Finality** | Authoritative External Confirmation / Refutation | The definitive settlement of an action via downstream status lookup or idempotency probe. | AEIB cannot create external payment-rail finality; it reconciles local uncertainty against target evidence. |

---

## 3. Normative Architectural Thesis

```text
AEIB local durable ledger is the protected validation-evidence store.
The external payment rail or target system is the finality sink.
AEIB reconciles local uncertainty against authoritative target evidence.
```

---

## 4. Governed Invariants

The state machine evaluates six core invariants across all candidate acts:

1. **`exact_act_binding`**: Every candidate act must be deterministically bound to a Canonical Action Identifier (CAID) computed via RFC 8785 JSON Canonicalization Scheme (JCS).
2. **`authority_before_effect`**: Execution credentials and wire dispatch must remain inaccessible to the agent runtime; credentials are injected strictly at the host proxy upon presentation of an authorized warrant.
3. **`durable_evidence_before_or_with_dispatch`**: Pre-dispatch escrow and intent records must be persisted to the durable evidence store (`O_DIRECT` / `F_FULLFSYNC`) before or concurrently with wire transmission.
4. **`no_blind_retry_after_uncertainty`**: Ambiguous wire timeouts (e.g., HTTP 504) must transition the state to `EFFECT_INDETERMINATE`, latching further retry attempts until status is authoritatively reconciled.
5. **`bounded_reconciliation`**: Uncertainty states must initiate bounded, progressive probing (idempotency replay or authoritative status query) or escalate to supervisory oversight.
6. **`fail_closed`**: Any schema malformation, epoch expiration, or signature mismatch must immediately halt dispatch and reject the candidate act.
