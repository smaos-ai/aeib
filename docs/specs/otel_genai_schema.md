# OpenTelemetry GenAI v1.43 Privacy-Split Span & Event Schema

## 1. Architectural Purpose
Defines the telemetry schema enforced by `tools/scitt_ap2_x402_otel_engine.py` and `src/observability/otel_genai_evidence_chain.py` under the OpenTelemetry GenAI Semantic Conventions (`v1.43`).

## 2. Two-Tier Privacy Split
To reconcile EU AI Act Article 12 traceability with GDPR data minimization:
1. **Standard Telemetry Spans (`execute_tool <tool_name>`)**:
   - Exported to observability backends without raw PII, IBANs, or secret payloads.
   - Required attributes:
     - `gen_ai.operation.name`: `"execute_tool"`
     - `gen_ai.provider.name`: Model provider identifier
     - `gen_ai.tool.name`: Registered tool identifier
     - `gen_ai.tool.type`: `"function"`
     - `gen_ai.agent.name`: Logical agent identifier
     - `aeib.operation_id`: Pre-dispatch idempotency key
     - `aeib.action.caid`: `sha256:` RFC 8785 JCS digest of the canonical arguments
     - `aeib.receipt.sha256`: `sha256:` digest of the Station 3 SCITT receipt
     - `aeib.boundary.verdict`: `"AUTHORIZED"`, `"DENIED"`, or `"HOLD"`
2. **Vault-Restricted Inference Detail Events (`gen_ai.client.inference.operation.details`)**:
   - Routed strictly to the encrypted local evidence vault.
   - Binds `gen_ai.tool.call.arguments_redacted_digest` (`action_caid`) to the raw arguments for authorized forensic inspection.
