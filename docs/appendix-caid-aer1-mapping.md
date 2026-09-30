# Appendix: CAID and AER-1 Mapping

## 1. Receipt Schema Fragment

```json
{
  "action_id": {
    "type": "caid",
    "value": "urn:caid:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "aeib_operation_id": "op_01J8X9V2M3K4N5P6Q7R8S9T0U1",
  "disposition": "DISPATCHED_UNCONFIRMED",
  "retry_permitted": false,
  "evidence": {
    "probe_source": "postgresql",
    "status": "RECONCILIATION_NOT_FOUND"
  }
}
```

## 2. Retry Identity Constraint

A permitted retry must preserve the exact CAID; a mutated payload yields a new CAID and is a new logical action.

Specifically:
- If an agent retries an action with identical semantics, parameters, and canonical JSON structure, the derived or provided CAID remains invariant. An idempotency gateway can safely deduplicate against this invariant CAID.
- If an agent mutates the payload structure, alters fields, or introduces semantic drift ($\mathcal{C}_2$ drift), the resulting canonical digest changes, generating a novel CAID. Under CAID semantics, this is recognized as an independent action rather than a retry of the prior intent.

## 3. Scope of Definition

CAID is expected to be supplied by the upstream gateway or derived from the RFC 8785 canonical payload — AEIB does not define CAID, it consumes it.
