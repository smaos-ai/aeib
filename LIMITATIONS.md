# AEIB v0.2 — Known Limitations

This is a synthetic prototype for engineering review. It is not a production system.

## What is implemented
- Deterministic UUIDv5 idempotency key derivation
- JCS-subset canonicalization (not RFC 8785 validated)
- Ed25519 receipt signing with hash-chain
- 7-state disposition taxonomy
- Transport-to-disposition mapping contract (YAML)
- Offline verifier (`aeib_verify.py`)
- 7 synthetic fault scenarios with signed receipts

## What is not implemented
- Real socket-level transport interception
- Real out-of-band ledger probes
- Physical retry suppression in a live runtime
- RFC 8785 JCS compliance
- COSE_Sign1 envelope format
- SCITT transparency service integration
- Hardware attestation (TRACE, TDX, SEV-SNP)
- DORA `incident_class` mapping
- MCP sidecar integration
- HSM/KMS key management

## What this prototype does not claim
- Regulatory compliance with DORA, EU AI Act, or any other framework
- Production readiness
- Resistance to adversarial tampering beyond the demonstrated hash-chain and Ed25519 signature
- Correctness against real-world APIs or ledgers

## What it demonstrates
- The invariant: an ambiguous transport outcome can be represented as a verifiable, signed disposition rather than a speculative retry
- The mapping contract: transport observations can deterministically produce dispositions
- The evidence chain: receipt signatures, evidence hashes, and mapping contract hash are all verifiable offline
