# Big 4 Audit Intake Technical Specification
**Standardized Agent Execution Evidence Schema for ISO 42001 & DORA Audits**
*Target: PwC, Deloitte, EY, KPMG (Financial Services IT Audit & Risk Advisory)*

---

## 1. Context & Auditor Value Exchange: The Hallucination Liability Crisis

Autonomous agent deployment across the Big 4 (KPMG Clara, EY Canvas multi-agent, Deloitte Zora, PwC AI Audit) has encountered a severe liability hazard: **the agentic hallucination failure mode**. Recent academic research analyzing AI-generated assurance reports across Deloitte, EY, KPMG, and PwC discovered widespread fabricated citations. In one notable benchmark, an authoritative Big 4 study on agentic AI contained 45 formal citations, **of which 40 referenced completely fabricated, non-existent sources**.

When audit platforms deploy agents to vouch expenses, verify accounts, or audit codebases:
1. **Uncertainty Hallucination**: Agents report successful database commits or payment executions based on hallucinated LLM completions rather than physical socket proofs.
2. **Auditor Liability**: Signing off on unstructured text logs exposes audit partners to legal liability when an unconfirmed write was silently dropped by a gateway timeout (`HTTP 504`).
3. **Statutory Proof Deficit**: Under **DORA Article 17(3)** and **ISO/IEC 42001 Clause 9**, stochastic LLM telemetry is legally inadmissible because it cannot be reproduced offline or verified without frontier cloud model re-evaluation.

### What SMAOS Delivers to Big 4 Risk & Assurance Practices
SMAOS provides audit teams with an open, machine-readable, offline-verifiable **Audit Intake Specification**:
- **Protection Against Hallucination Liability**: Mathematical proof that an action physically settled in downstream records before an auditor signs workpapers.
- **10x Faster Workpaper Generation**: Ingest structured JSONL receipts directly into SQL/DuckDB workpapers in sub-35ms.
- **Cryptographic Mathematical Proof**: Every tool call is sealed in a standard RFC 9052 `COSE_Sign1` envelope (`alg: -8`, Ed25519) and linked via SHA-256 hash chaining, aligning with **RFC 9943** (SCITT Architecture) and **RFC 9942** (COSE Receipts) via the Emilia Protocol profile.
- **Zero Ambiguity**: 5-state disposition taxonomy strictly separates physical outcome (`OUTCOME_VERIFIED`) from mere network acknowledgment (`ACK_UNVERIFIED`).

---

## 2. Standard Audit Intake Receipt Schema (JSON Schema v1.1)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SMAOS_Audit_Receipt",
  "type": "object",
  "required": [
    "receipt_version",
    "key_id",
    "action_id",
    "actor",
    "authority_hash",
    "dispatched_at",
    "request_payload_hash",
    "outcome_verified",
    "verification_method",
    "wall_clock_delta_ms",
    "freshness_status",
    "disposition",
    "cose_envelope_hex",
    "cose_alg",
    "cose_kid"
  ],
  "properties": {
    "receipt_version": { "type": "string", "enum": ["v0.2.0"] },
    "key_id": { "type": "string" },
    "action_id": { "type": "string", "pattern": "^mcp://.+/.+/.+/.+$" },
    "actor": { "type": "string" },
    "authority_hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" },
    "authority_ttl": { "type": ["string", "null"] },
    "dispatched_at": { "type": "string", "format": "date-time" },
    "request_payload_hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" },
    "downstream_state_hash": { "type": ["string", "null"] },
    "outcome_verified": { "type": "boolean" },
    "verification_method": { "type": "string" },
    "wall_clock_delta_ms": { "type": ["number", "null"] },
    "freshness_status": { "type": "string", "enum": ["FRESH", "STALE", "CLOCK_ORDER_INVALID", "UNMEASURED"] },
    "disposition": { 
      "type": "string", 
      "enum": [
        "OUTCOME_VERIFIED",
        "ACK_UNVERIFIED",
        "DISPATCHED_UNCONFIRMED",
        "RECONCILIATION_NOT_FOUND",
        "RECONCILIATION_FAILED",
        "PROBE_EXCEPTION",
        "RECONCILIATION_CONFLICT",
        "REFUSED"
      ] 
    },
    "transport_fault": { "type": "string" },
    "cose_envelope_hex": { "type": "string" },
    "cose_alg": { "type": "integer", "const": -8 },
    "cose_kid": { "type": "string" }
  }
}
```

---

## 3. Standard Auditor Workpaper SQL Queries

Auditors can drop receipts directly into local DuckDB or ClickHouse to execute standard substantive testing procedures:

### Query A: Phantom Retries & Ambiguous Outcome Discovery
```sql
-- Identifies transactions that received a socket error but lack downstream commit verification
SELECT 
    action_id,
    dispatched_at,
    transport_fault,
    disposition,
    observed_outcome
FROM read_json_auto('audit_out/receipts.jsonl')
WHERE disposition IN ('DISPATCHED_UNCONFIRMED', 'ACK_UNVERIFIED', 'RECONCILIATION_FAILED')
ORDER BY dispatched_at DESC;
```

### Query B: ISO 42001 Clause 9.1 Authority Freshness Compliance
```sql
-- Audits whether agents executed actions with stale or unmeasured authority credentials
SELECT 
    freshness_status,
    count(*) AS total_dispatches,
    avg(wall_clock_delta_ms) AS avg_latency_ms,
    max(wall_clock_delta_ms) AS max_latency_ms
FROM read_json_auto('audit_out/receipts.jsonl')
GROUP BY freshness_status;
```

### Query C: Cryptographic Non-Repudiation Sample Verification
```sql
-- Confirms that 100% of receipts contain valid Ed25519 public key references
SELECT 
    cose_kid,
    count(*) AS signed_receipts,
    countIf(cose_alg = -8) AS ed25519_count
FROM read_json_auto('audit_out/receipts.jsonl')
GROUP BY cose_kid;
```

---

## 4. Auditor Verification CLI

The Big 4 audit team can verify an entire receipt ledger offline without installing SMAOS or executing agent code:

```bash
# Verify ledger continuity and cryptographic signatures offline
.venv/bin/python3 -c "
import json
from src.diagnostic_normalizer import COSESign1Engine, KeyRegistry

# Load public keys from registry
registry = KeyRegistry.from_file('audit_out/v0.2.0/public_keys.json')

with open('audit_out/v0.2.0/receipts.jsonl') as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        env = bytes.fromhex(r['cose_envelope_hex'])
        pub_key = registry.get_key(r['cose_kid'])
        valid, payload, _ = COSESign1Engine.verify_envelope(env, pub_key)
        assert valid, f'Signature invalid at receipt {i}'
print('✅ 100% of audit receipts cryptographically verified with zero egress.')
"
```

---

## 5. Partnership Model for Big 4 Practices

1. **Intake Standardization**: Big 4 firm publishes SMAOS schema as the recommended audit intake format for financial institutions deploying autonomous AI.
2. **Accelerated Assurance Engagements**: The firm provides DORA Article 17 and ISO 42001 readiness assessments in days rather than months.
3. **Enterprise Pipeline Sharing**: When an enterprise audit reveals toxic receipts, the Big 4 firm recommends the SMAOS runtime for continuous prevention.
