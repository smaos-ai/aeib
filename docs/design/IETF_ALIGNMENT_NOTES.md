# IETF Alignment & Conceptual Mapping Notes

**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Status:** Research Note & Conceptual Profile Specification  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Scope:** Conceptual translation between AEIB's 7-state disposition model and emerging IETF agent compliance receipt drafts.

---

## 📜 1. Target IETF Specifications Under Review

This analysis maps AEIB against three actively developing IETF standards and draft tracks:

1. **`draft-marques-asqav-compliance-receipts`**:
   - Focus: Cryptographic compliance receipts for automated systems subject to EU regulatory oversight (DORA Article 17/28, EU AI Act Article 14).
   - Core Fields: `payload_digest`, `action_ref`, `policy_digest`, `verdict`, `risk_class`, `incident_class`.
   - Anchoring: Cryptographic timestamping (RFC 3161 or OpenTimestamps).

2. **IETF SCITT Architecture (`draft-ietf-scitt-architecture`)**:
   - Focus: Supply Chain Integrity, Transparency, and Trust.
   - Core Primitive: Signed statements wrapped in COSE_Sign1 envelopes and registered in an append-only Transparency Service (verifiable via Merkle inclusion proofs).

3. **AER-1 (Agent Execution Receipts Drafts)**:
   - Focus: Uniform envelope definitions for multi-agent delegation chains and action receipts.

---

## 🗺️ 2. Field-by-Field Conceptual Mapping

The current prototype format (`AEIB_JSON_ED25519_PROTOTYPE`) uses a vendor extension namespace (`org.smaos.aeib`). Below is the normative mapping showing how this structure fits into a future COSE_Sign1 compliance envelope:

| IETF Compliance Draft Field | AEIB Prototype Path | Conceptual Alignment & Semantics |
| :--- | :--- | :--- |
| `action_ref` | `payload.action_id` | Unique URI identifying the invoked agent session, step, and tool method (`mcp://...`). |
| `payload_digest` | `payload.unsigned_payload_hash` | SHA-256 digest of the canonicalized request arguments. |
| `idempotency_handle` | `payload.idempotency_key` | Deterministic UUIDv5 key injected prior to wire dispatch. |
| `verdict` | `payload.org.smaos.aeib.disposition` | Direct mapping of the 7-state disposition (see taxonomy below). |
| `policy_digest` | `payload.org.smaos.aeib.transport_evidence.transport_evidence_hash` | Digest binding the observed transport network trace. |
| `evidence_ref` | `payload.org.smaos.aeib.outcome_probe.record_id` | URI pointing to the out-of-band probe observation in `evidence/probe.jsonl`. |
| `remediation_advisory` | `payload.org.smaos.aeib.retry_policy` | Cryptographically signed retry constraint (`retry_permitted: false`). |

---

## 🚦 3. Disposition to Verdict & Incident Class Mapping

How AEIB's 7-state disposition taxonomy conceptually translates into standard audit verdicts:

| AEIB Disposition | Conceptual IETF Verdict | Conceptual DORA Incident Class | Operational Meaning |
| :--- | :---: | :---: | :--- |
| `OUTCOME_VERIFIED` | `PASS` | `NONE` | Downstream ledger confirmed committed; retry locked. |
| `DISPATCHED_UNCONFIRMED` | `INDETERMINATE` | `MAJOR_ICT_SUSPECTED` | Wire dropped (HTTP 504 / RST); retry strictly prohibited. |
| `RECONCILIATION_NOT_FOUND` | `FAIL` | `HANDLED_FAIL_SAFE` | Probe confirmed transaction never persisted; safe to retry. |
| `RECONCILIATION_FAILED` | `FAIL` | `INTEGRITY_BREACH_SUSPECTED` | Downstream state mismatch or payload corruption detected. |
| `RECONCILIATION_CONFLICT` | `FAIL` | `DOUBLE_MUTATION_SUSPECTED` | Conflicting transaction found under same idempotency handle. |
| `CONTEXT_POLICY_VIOLATION`| `REFUSED` | `POLICY_BLOCKED` | Request lacked necessary authorization context before wire dispatch. |
| `AUTHORITY_NOT_BOUND` | `REFUSED` | `SECURITY_TOKEN_EXPIRED` | Signing token or delegation authority expired prior to dispatch. |

---

## ⚖️ 4. Explicit Non-Claims & Compliance Boundaries

To maintain complete scientific and commercial honesty:

1. **No Claims of Compliance**: AEIB v0.2 does **not** implement `draft-marques-asqav-compliance-receipts`. The mapping above is a conceptual blueprint for future iterations.
2. **No Native CBOR/COSE**: All receipts in v0.2 use a deterministic JSON subset, not binary RFC 9052 COSE_Sign1.
3. **No Active SCITT Registration**: Receipts are stored locally in append-only JSONL; they are not registered to a public or private SCITT Transparency Service.
4. **No Retention Guarantees**: DORA Article 28(3) five-year retention floors must be provided by the deploying enterprise's archival infrastructure; AEIB v0.2 provides no storage retention SLA.
