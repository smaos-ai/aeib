# Identity Ingestion Schema

```json
{
  "action_id": {
    "type": "action_ref",
    "value": "urn:action_ref:sha256:82a0d91efec675c9d0092305db3a846f4817a3a3026f8d3c52e85a539ebf8f01"
  },
  "aeib_operation_id": "op_wire_8f21e0a4",
  "attempt_id": "atm_9a8b7c6d",
  "disposition": "DISPATCHED_UNCONFIRMED",
  "retry_policy": "PROBE_REQUIRED_NO_ORIGINAL_RETRY",
  "transport_observation": {
    "status": 504,
    "type": "TCP_RST"
  },
  "probe_evidence": null
}
```

* **Consumption Rules**: `action_id.value` is treated as an opaque, externally supplied string. AEIB does not validate or recompute the preimage. Permitted retries must preserve the original `action_id` and `aeib_operation_id`; payload mutations yield a new `action_id` upstream and constitute a novel action.
