# AEIB Architecture Roadmap

## v1.0 (Current Release Candidate)
- Java 21 LTS runtime baseline.
- Station 0: Manifest integrity gating with local pin verification.
- Station 1: Dispatch interlock with RFC 8785 canonical CAID generation.
- Station 2: Effect reconciler with bounded probe budgets and single-flight coalescing.
- Station 3: Continuous ledger with Ed25519 hash-chain receipts.
- Standalone CLI verifier for offline verification.
- Zero-network runtime container verification harness.

## v1.1 Candidate: Memory and Retrieval Provenance

### Threat model
- Agent memory may change between authorization and dispatch.
- Retrieved context may originate from an untrusted or poisoned source.
- A self-improving agent may attempt to modify its manifest, policy context, or identity material.

### Candidate controls
- Bind each candidate action to a content-addressed memory digest.
- Record the memory digest in the manifest and receipt.
- Reject actions whose current memory digest differs from the authorized digest.
- Validate retrieval provenance through a declared trust policy.
- Record retrieval-source identity, content digest, retrieval timestamp, and policy decision.

### Required evidence
- Memory mutation test.
- Stale-memory rejection test.
- Poisoned-retrieval rejection test.
- Receipt binding test.
- Independent verifier test.
