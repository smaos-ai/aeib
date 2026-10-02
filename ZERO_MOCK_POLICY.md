# Zero-Mock Architectural Invariant (AEIB v0.2.4)

## 1. The Core Invariant
In the AEIB execution boundary, mock usage is not merely discouraged; it is structurally prevented from passing the build. The system enforces a strict "Zero-Mock Policy" for all post-dispatch state tracking, cryptographic signing, and database reconciliation paths. 

## 2. Epistemic Justification
Permitting mock objects in agentic state-machine testing introduces "researcher degrees of freedom" analogous to p-hacking. Mocks allow the test to be reshaped to match the implementation, generating false positive passing grades for LLM-generated code. To guarantee Semantic Atomicity and Isolation (arXiv:2608.13900), the testing substrate must be deterministically hostile to synthetic approximations.

## 3. Structural Enforcement (Poka-Yoke & Jidoka)
* **Banned Libraries:** The AST validation gate (`ghost_audit_scanner.py`) will throw a fatal `IllegalSubstrateException` if `unittest.mock`, `MagicMock`, `@patch`, or equivalent interceptors are detected in the verification logic.
* **Database Probing:** All ledger reconciliation tests must execute against a live, ephemeral PostgreSQL connection (e.g., `postgres:16-alpine` via Docker) or a physical SQLite WAL file. In-memory dummy stores (`:memory:`) are rejected for transport-fault testing.
* **Cryptographic Purity:** All AEIB SCITT receipts must be generated using real RFC 8785 JSON Canonicalization Scheme (JCS) payloads and Ed25519 signatures. Fallback strings (e.g., `b"dummy"`) will fail the receipt parser's strict mode.
* **The Agentic Andon Cord:** If an LLM agent attempts to bypass a complex integration by writing a mock or a hollow assertion (`assert True`), the Continuous Integration pipeline triggers a Jidoka halt. The main thread is suspended, the tool call authority is revoked, and the system demands a real execution proof before proceeding.

## 4. Alignment
This policy implements the deterministic boundaries described in Alibaba's *OpenCodeReview* (arXiv:2608.09290) and the *Deterministic AI Operating Systems* framework (DAIOS), ensuring that execution permission relies on physical substrate truth, not probabilistic model confidence.
