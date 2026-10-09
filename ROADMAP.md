# AEIB Architecture Roadmap

## v1.0 (Current Release Candidate)
- Java 21 LTS runtime baseline.
- Station 0: Manifest integrity gating with local pin verification.
- Station 1: Dispatch interlock with RFC 8785 canonical CAID generation.
- Station 2: Effect reconciler with bounded probe budgets and single-flight coalescing.
- Station 3: Continuous ledger with Ed25519 hash-chain receipts.
- Station 4: Standalone CLI verifier for offline verification.
- Zero-network runtime container verification harness.

## v1.1 Candidate Backlog

### Specification Candidates
- Upstream context-decision reference (contextDecisionRef = SHA-256(canonical signed decision))
- Diagnostic interlock decision fields (interlockDecisionReason constrained enum)
- Multi-tier memory binding
- Procedural-memory write admission
- External transparency registration (e.g., SCITT profile)
- Hybrid signature profile (Ed25519 + ML-DSA-65)

### Research Workstreams
- Harness evolution from diagnosed failure corpora
- External benchmark integration (e.g., HaluMem adapter review)
- Independent examination pathway
- Interoperability review (TRACE, VET, AEGIS)

### Explicitly Out of Scope for v1.0
All items above are unimplemented, unspecified, and untested.
They do not alter v1.0 claims or release criteria.
