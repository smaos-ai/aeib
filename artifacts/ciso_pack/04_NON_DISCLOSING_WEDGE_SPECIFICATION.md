# Non-Disclosing Commercial Wedge Specification

### 1. Dual-Tier Distribution Architecture
To enable viral enterprise adoption without exposing proprietary data plane source code to competitors:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        ONE CORE, TWO DOORS                             │
├───────────────────────────────────┬────────────────────────────────────┤
│ DOOR 1: Public Audit Wedge        │ DOOR 2: Enterprise Core Plane       │
│ • smaos_verify.wasm (195 KB)      │ • Rust/Python/Swift data plane     │
│ • ghost_audit_scanner.py (CLI)    │ • Station 1–3 pre-dispatch gates   │
│ • Read-only discovery             │ • Zero-egress hardware attestation │
│ • Discloses 0 execution code      │ • Paid enterprise deployment       │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 2. Standalone WASM Receipt Verifier
- **Binary:** `dist/smaos_verify.wasm`
- **SHA-256 Digest:** `sha256:6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041`
- **Capabilities:** Verifies RFC 8785 JCS canonicalization, Ed25519 signatures, Merkle inclusion proofs, and policy epoch validity in browsers or serverless edge runtimes without server-side dependencies.
