# Quality Gate Architecture: Poka-Yoke & Jidoka for Autonomous Agents

## 1. Overview & Artifact Chain
This architecture formalizes the deterministic quality gate for the Sovereign Multi-Agent OS (SMAOS) and the Agent-Effect Integrity Benchmark (AEIB v0.2.4). It establishes an unbreakable artifact chain:

$$\text{Principle} \longrightarrow \text{Enforcement} \longrightarrow \text{Evidence} \longrightarrow \text{Structural Gate}$$

## 2. Pillar I: Principle (Jidoka & Poka-Yoke)
- **Jidoka (自働化):** Quality at the source. If an abnormality, socket drop, or verification ambiguity is detected, the execution line halts immediately. Unconfirmed actions are never passed downstream.
- **Poka-Yoke (ポカヨケ):** Mistake-proofing. Structural barriers make it impossible to introduce mocks, dummy fallbacks (`b"dummy"`), or hollow assertions (`assert True`) into the core verification pipeline.

## 3. Pillar II: Enforcement (The Agentic Andon Cord)
When an autonomous agent encounters deep substrate complexity (native FFI compilation, container socket isolation, live database connection pooling):
1. **The Line Halts:** The agent pulls the Andon cord, suspending linear turn progression.
2. **Task Redirection:** Work is redirected to an isolated subagent in a dedicated git worktree with a single-responsibility mandate.
3. **AST Gate:** An automated scanner parses syntax trees and aborts with `IllegalSubstrateException` if `unittest.mock` or test doubles are present in verification logic.

## 4. Pillar III: Evidence (Live Substrates & Rule of Three)
- **Zero-Mock Substrates:** All reconciliation executes against physical SQLite WAL databases or containerized PostgreSQL 16/15 instances.
- **Epistemic Precision:** Evidence is graded as `local_harness` with a Rule-of-Three 95% upper bound of 5.8% on 0/50 trials (and 15.0% on 20 negative controls).
- **Cryptographic Receipts:** Sealed using RFC 8785 JCS canonicalization and RFC 9052 COSE_Sign1 Ed25519 signatures.

## 5. Pillar IV: Structural Gate (`verify-audit-pack.py`)
Releases are locked behind an automated offline verifier that validates:
1. Manifest integrity and SHA-256 digest matching across all release files.
2. Zero-mock AST compliance across core verification modules.
3. DORA Article 17 incident classification mapping consistency.
4. Conformance across all 6 named failure gates in `test_negative_vectors.py`.

## 6. Framework Alignment
Implements the hybrid deterministic harness paradigm proven in Alibaba's *OpenCodeReview* (arXiv:2608.09290) and the *Deterministic AI Operating Systems* (DAIOS) framework.
