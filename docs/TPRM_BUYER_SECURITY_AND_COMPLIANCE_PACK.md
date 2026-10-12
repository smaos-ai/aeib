# AEIB / SMAOS — TPRM Buyer Security, Competitive & Regulatory Alignment Dossier

**Document Version:** `1.0.0-rc.1`  
**Epistemic Boundary (`AGENTS.md` §1):** All properties in this dossier are framed strictly around **observed**, **tested**, **evaluated**, and **configured** runtime behavior under the stated fault and threat models. This document makes no claim of out-of-the-box regulatory certification or model-level cognitive safety.

---

## 1. Honest Competitive Comparison Matrix (Gap 1)

Signed, hash-chained receipts for AI agent tool calls are an active 2026 category. AEIB does **not** claim to have invented agent receipts or MCP proxies. Instead, AEIB focuses on **transport-layer execution finality (`EFFECT_INDETERMINATE`)**, **out-of-band target state reconciliation**, and **cross-language offline verifier parity**.

| Framework / Project | Primary Mechanism | Signature / Framing | Post-Dispatch Drop (`HTTP 504` / `TCP RST`) Handling | Offline Verifier Parity | DORA EBA DPM 4.0 Mapping |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AEIB (`v1.0.0-rc.1`)** | 4-Station Wire Boundary + Out-of-Band Reconciler | RFC 8785 JCS + Ed25519 (`ContinuityReceipt`), WASM & JVM CLI | Explicit **`EFFECT_INDETERMINATE`** state latch (`retry_safe: false`) + bounded `ProbeBudget` target reconciliation + signed `RESOLUTION_RECEIPT` | **Observed**: Java 21 (`ReceiptVerifier`) + Python 3 (`jvm_native_diff_engine.py`) + Rust/WASM (`smaos-verify.html`) (`14/14` vector parity) | Deterministic `RT.01.01`–`RT.01.03` xBRL-CSV export (`DoraIts2024ZipExporter`) |
| **Obsigna / AgentReceipts** | MCP Proxy + W3C Verifiable Credentials | Ed25519 + Hash Chain | Records proxy call completion/error; no dedicated out-of-band target semantic state reconciler | TypeScript / CLI verifier | Not included |
| **AER-1** | Portable Execution Receipt Spec | Ed25519 + Hosted Verify Endpoint | Standard success/failure receipt states | Public verification endpoint | Not included |
| **Pipelock / Signet** | Mediator-Signed / Bilateral Co-Signed Receipts | Ed25519 | Bilateral co-signing prior to or upon response; does not reconcile severed post-dispatch sockets | Single-runtime SDK | Not included |
| **Asqav** | Post-Quantum Agent Action Signing | ML-DSA-65 (FIPS 204) | Cryptographic signing focus; no `EFFECT_INDETERMINATE` target state probe loop | Single-runtime verifier | Not included |
| **AgentMint** | Signed Receipts + RFC 3161 Timestamping | Ed25519 + RFC 3161 TSA | Timestamped action receipts; no target-side semantic reconciliation | Python CLI | Not included |
| **Microsoft Agent Governance Toolkit** | Policy / Identity Guardrails | Cloud / Entra ID Integration | Pre-invocation policy enforcement; relies on application SDK retry behavior on wire drops | Cloud telemetry | Not included |

---

## 2. IETF SCITT (`COSE_Sign1`) Mapping & HTTP `Idempotency-Key` Citation Accuracy (Gaps 2 & 3)

### 2.1 Receipt $\rightarrow$ IETF SCITT `COSE_Sign1` Equivalence Mapping (Gap 2)
AEIB `v1.0.0-rc.1` emits JSON receipts canonicalized via **RFC 8785 (JCS)** so that security teams can inspect raw UTF-8 receipt files without binary CBOR tooling. For environments integrating with IETF SCITT transparency services (`draft-ietf-scitt-architecture`, `draft-emirdag-scitt-ai-agent-execution` `[UNVERIFIED draft status]`), AEIB fields map deterministically to RFC 9052 `COSE_Sign1` structures:

| AEIB `ContinuityReceipt` JSON Field | RFC 9052 `COSE_Sign1` / SCITT Equivalent | Encoding & Verification Rule |
| :--- | :--- | :--- |
| `signatureAlgorithm: "Ed25519"` | Protected Header `1` (`alg`): `-8` (`EdDSA`) | Pinned to Ed25519 in `v1.0`; reserved `-49` (`ML-DSA-65`) for `v1.2` PQC agility |
| `signature.keyId` | Protected Header `4` (`kid`): `bstr` | UTF-8 bytes of `keyId` |
| `epoch` / `chainTip` | Protected Header SCITT `CWT_Claims` (`15`) / Unprotected `receipts` | 32-byte SHA-256 sequential hash-chain tip |
| `signedStatement` (Base64 RFC 8785 JCS) | `COSE_Sign1.payload` (`bstr`) | Exact UTF-8 bytes of the RFC 8785 JCS canonical statement |
| `signature.ed25519Signature` | `COSE_Sign1.signature` (`bstr`, 64 bytes) | 64-byte Ed25519 signature |
| `org.agentactioncapsule.otel` (`v1.1`) | Custom Protected Header / Payload Claim | W3C `traceparent` (`00-{traceId}-{spanId}-01`) per `draft-palanisamy-scitt-aac-otel-00` |

> **Epistemic Note:** AEIB `v1.0.0-rc.1` verifies RFC 8785 JCS JSON envelopes natively and does **not** claim out-of-the-box IETF SCITT CBOR/COSE wire conformance.

### 2.2 Expired IETF `Idempotency-Key` Draft Citation (Gap 3)
All references to `Idempotency-Key` (`draft-ietf-httpapi-idempotency-key-header`) across AEIB documentation and code are cited strictly as an **expired IETF Individual/WG draft and de facto HTTP industry practice** (used by Stripe, Adyen, and AWS), not a finalized IETF RFC.

---

## 3. MCP `2025-11-25` Authorization & OWASP Agentic Top 10 (`ASI01`–`ASI10`) Coverage (Gaps 4 & 5)

### 3.1 MCP `2025-11-25` OAuth 2.1 & No-Token-Passthrough Enforcement (Gap 4)
Per the Model Context Protocol (`2025-11-25`) authorization specification:
1. **Mandatory RFC 8707 Resource Audience Binding:** `McpOAuth21ResourceAudienceGate` (`v1.1-roadmap/unified_governance_stack.py`) verifies that the token's `aud` (resource indicator) exactly matches the canonical target resource URI (`https://...`), alongside non-empty `sub`, `client_id`, and `scope` claims.
2. **Forbidden Token Passthrough (Anti-Confused-Deputy):** The proxy gate explicitly scans outbound tool arguments and headers and halts (`GovernanceHaltError`) if an upstream OAuth access token or raw `Bearer` credential is passed through to a downstream tool server.

### 3.2 OWASP Top 10 for Agentic Applications 2026 (`ASI01`–`ASI10`) Coverage Matrix (Gap 5)

| OWASP ID | Category Title (Dec 2025 Release) | AEIB Coverage Disposition | Technical Anchor / Scope Boundary |
| :--- | :--- | :--- | :--- |
| **ASI01** | **Agent Goal Hijacking** (Indirect Prompt Injection) | **NOT COVERED / OUT OF SCOPE** | AEIB operates at the post-reasoning wire boundary and does not inspect or filter LLM prompts or model weights. |
| **ASI02** | **Tool Misuse & Unbounded Parameter Execution** | **COVERED (Pre-Dispatch Gate + Evidence)** | `Station0AdmissionGate`, `Station1DispatchInterlock`, and `TypedOwaspPreDispatchGate` enforce schema, URI allowlist, and parameter bounds prior to socket I/O. |
| **ASI03** | **Identity & Privilege Abuse (Confused Deputy)** | **COVERED (Vault + Audience Binding)** | `CredentialVaultGate` and `McpOAuth21ResourceAudienceGate` block raw credential exposure and token passthrough (`RFC 8707`). |
| **ASI04** | **Agentic Supply Chain & Unpinned Tool Manifests** | **COVERED (Manifest Pinning + SBOM/SLSA)** | `GhostAtrDiagnosticScanner` (`ATR-2026-01932`) rejects unpinned MCP servers; releases include CycloneDX 1.6 SBOMs and SLSA Build L3 provenance. |
| **ASI05** | **Unexpected Code Execution (RCE via Tooling)** | **PARTIAL (Policy Gate Only; eBPF is Scaffold)** | Pre-dispatch allowlists block unapproved tool verbs; `ebpf/` kernel enforcement is structural scaffolding unless deployed on a locked Linux CVM host. |
| **ASI06** | **Memory & Context Poisoning** | **PARTIAL (Epoch Staleness Only; Semantic Poisoning Out of Scope)** | `TemporalMemoryDigest` and `TripartiteKvBlockAdmissibilityGate` halt on stale epochs (`STALE_DONT_TRUST_YET`), but do not detect adversarial falsehoods inside valid epochs. |
| **ASI07** | **Insecure Inter-Agent Communication** | **PARTIAL (Signed Receipts)** | Inter-agent handoffs can verify Ed25519 `ContinuityReceipt` envelopes offline. |
| **ASI08** | **Cascading Failures & Retry Storms** | **COVERED (Core Differentiator)** | `EFFECT_INDETERMINATE` latching halts blind retries on HTTP 504 / TCP RST; `Station2EffectReconciler` enforces a bounded `ProbeBudget`. |
| **ASI09** | **Human-Agent Trust Exploitation** | **NOT COVERED / OUT OF SCOPE** | AEIB does not govern human UI persuasion or social engineering by model outputs; it provides raw JSON receipts for human/auditor inspection. |
| **ASI10** | **Rogue Agents & Repudiation of Actions** | **COVERED (Non-Repudiation Evidence)** | `Station3ContinuousLedger` binds every lifecycle transition into an Ed25519-signed RFC 8785 JCS hash chain (`ContinuityReceipt`). |

---

## 4. NIST AI RMF, ISO/IEC 42001 & SOC 2 Design Alignment Matrix (Gaps 6, 7 & Action 24)

> **Important Disclaimer:** The mappings below represent **architectural design alignment** to assist deployer compliance teams and auditors. AEIB is a software component and is **not** independently certified under ISO/IEC 42001, ISO/IEC 27001, or AICPA SOC 2.

| Standard / Framework | Control / Function | AEIB Runtime / Verifier Artifact | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **NIST AI RMF 1.0 / CAISI** | **GOVERN 1.2 /MANAGE 2.4** (Runtime disengagement & override) | `Station1DispatchInterlock` epoch revocation & `EFFECT_INDETERMINATE` freeze | `Gate4IntegrationTest.java`, `MandatoryNegativeTestSuite.java` |
| **NIST AI RMF 1.0 / CAISI** | **MEASURE 2.6 / 2.7** (Independent evaluation & auditability) | Standalone offline `ReceiptVerifier` (Java 21) & `jvm_native_diff_engine.py` (Python 3) | `14/14` vector parity in `.github/workflows/aeib-ci.yml` |
| **ISO/IEC 42001:2023** | **Clause 9.1 / Annex A.6.2.6** (AI system operation & event logging) | `Station3ContinuousLedger` sequential SHA-256 hash chain + Ed25519 signature | `EVIDENCE_MANIFEST.md` (`NEG-01`–`NEG-08` negative ledger) |
| **ISO/IEC 42001:2023** | **Annex A.8.4 / A.9.3** (Technical documentation & provenance) | CycloneDX 1.6 SBOM (`bom.json`) + SLSA Build L3 provenance | `VERIFY_RELEASE.md` |
| **SOC 2 TSC** | **CC6.1** (Logical access & credential isolation) | `CredentialVaultGate` + `McpOAuth21ResourceAudienceGate` | `tests/test_unified_governance_stack.py` |
| **SOC 2 TSC** | **CC7.2 / CC7.4** (Anomaly detection & incident response) | `Station2EffectReconciler` (`CONFLICT` / `EFFECT_INDETERMINATE` detection) | `Gate4IntegrationTest.java` |
| **SOC 2 TSC** | **CC8.1** (Change management & build integrity) | 40-char SHA-pinned GitHub Actions + reproducible JAR build check | `.github/workflows/aeib-ci.yml` |

---

## 5. Regulatory Timelines & Applicability Boundaries (Gaps 8, 9, 10, 11, 12)

1. **EU AI Act Re-Dated Timeline & Article Grounding (Gaps 8 & 9):**
   * **Primary Articles:** Grounded in **Article 12 (Record-Keeping / Automatic Logging)**, **Article 14 (Human Oversight — preventing blind automated retries on ambiguous wire states)**, and **Article 15 (Accuracy, Robustness, and Cybersecurity)**.
   * **Digital Omnibus Timeline Update (`[UNVERIFIED - Confirm EUR-Lex Official Journal text prior to legal reliance]`):** Reported omnibus amendments shift Annex III high-risk application to **2 December 2027** and Annex I product safety integration to **2 August 2028** (with Article 50 transparency obligations from **2 August 2026**).
   * **`prEN 18282` Status:** CEN-CENELEC JTC 21 `prEN 18282` remains a **draft under enquiry** and is not cited in the Official Journal of the European Union; it confers **no presumption of conformity**.
2. **DORA RTS `2025/301`, ITS `2025/302` & RTS `2024/1772` Incident Reporting (Gap 10):**
   * **Reporting Windows:** Initial notification within **4 hours** of classification as a major ICT-related incident (and $\le 24\text{ hours}$ of detection), intermediate report within **72 hours**, and final report within **1 month**.
   * **Responsibility Boundary:** DORA Article 19 regulatory submission is strictly the **regulated financial entity's responsibility**. AEIB provides deterministic forensic timeline reconstruction (`ContinuityReceipt` timestamps, `CAID`, and `EFFECT_INDETERMINATE` vs. `CONFLICT` dispositions) plus an automated EBA DPM 4.0 xBRL-CSV Register of Information (`RT.01.01`–`RT.01.03`) export (`DoraIts2024ZipExporter`).
3. **Czech AI Regulatory Sandbox Status (Gap 11):**
   * **Status:** **`[UNVERIFIED - Pending primary confirmation from ČNB / MPO / ČTÚ]`**. No specific Czech national sandbox application window or deadline is claimed.
4. **EU Cyber Resilience Act (CRA, Regulation (EU) 2024/2847) Applicability Memo (Gap 12):**
   * **Effective Dates:** Mandatory manufacturer reporting of actively exploited vulnerabilities and severe incidents via the ENISA Single Reporting Platform applies from **11 September 2026** (24h early warning, 72h notification, 14-day final report after remediation), with full CE-marking and essential cybersecurity requirements applying from **11 December 2027**.
   * **AEIB Readiness:** Each release candidate generates a CycloneDX 1.6 (`ECMA-424`) JSON SBOM (`bom.json`), enforces Coordinated Vulnerability Disclosure via [`SECURITY.md`](file:///Users/andriileukhin/Documents/SovereignNexus/SECURITY.md) and [`.well-known/security.txt`](file:///Users/andriileukhin/Documents/SovereignNexus/.well-known/security.txt), and pins build provenance via SLSA v1.1 Build L3.

---

## 6. Key Custody, PQC Agility, License Audit & Scaffolding Disambiguation (Actions 22, 23, 24, 26)

### 6.1 Key Custody & Completeness Threat Model (Action 23)
A local hash chain (`chainTip`) signed by an operator-held Ed25519 private key detects post-hoc mutation of emitted receipts if the verifier holds the authentic public key, but **cannot by itself prevent a compromised operator who holds the signing key from truncating the tail of the log or re-signing a forged fork**. To mitigate operator key compromise or log omission:
* **Hardware Key Isolation:** Production deployments must bind the `Station3ContinuousLedger` signing key inside an HSM or KMS enclave (never on disk in plaintext).
* **RFC 3161 Trusted Timestamping (`Rfc3161TimestampAuthorityAnchor`):** Periodic `chainTip` checkpoints are counter-signed by an external RFC 3161 Time Stamping Authority (TSA) token binding `(chainTip, tsaEpoch, policyOid)`.
* **Transparency Log Anchoring (`WitnessedSthValidator`):** Periodic Signed Tree Heads (`STH`) are co-signed by $k$-of-$n$ external witnesses to detect split-view or tail-omission attacks.

### 6.2 Post-Quantum Cryptography (PQC) Agility (Action 22)
For banking audit logs requiring 7–10 year retention:
* `ContinuityReceipt` includes `HybridSignature(ed25519Signature, mlDsa65Signature, keyId, keyEpoch)` in [`FOUR_STATION_INTERFACES.java`](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-native-runtime/aeib-core/src/main/java/ai/sovereign/aeib/core/FOUR_STATION_INTERFACES.java#L85-L90).
* In `v1.0.0-rc.1` (JDK 21), `ed25519Signature` is active and `mlDsa65Signature` is `null`. Dual-signature hybrid signing (`Ed25519 + ML-DSA-65` per NIST FIPS 204 / OpenJDK JEP 497 in JDK 24+) is reserved for the `v1.2` roadmap.

### 6.3 Third-Party Dependency & License Audit (Action 24)
All runtime and verifier dependencies in `aeib-native-runtime` and the Python reference verifier use permissive open-source licenses compatible with Apache-2.0 distribution:

| Component | Dependency | Version | SPDX License | Scope |
| :--- | :--- | :--- | :--- | :--- |
| `aeib-verifier` / `aeib-crypto` | `io.github.erdtman:java-json-canonicalization` | `1.1` | `Apache-2.0` | RFC 8785 JCS |
| `aeib-verifier` / `aeib-runtime` | `com.fasterxml.jackson.core:jackson-databind` | `2.17.0` | `Apache-2.0` | Strict JSON parsing |
| `aeib-verifier` | `info.picocli:picocli` | `4.7.6` | `Apache-2.0` | CLI argument parsing |
| `aeib-crypto` | `org.bouncycastle:bcprov-jdk18on` | `1.77` | `MIT` | Crypto provider compatibility |
| `aeib-core` | `io.github.resilience4j:resilience4j-circuitbreaker` | `2.2.0` | `Apache-2.0` | Fault tolerance |
| `aeib-tests` | `org.junit:junit-bom` | `5.11.3` | `EPL-2.0` | Test-only (not shipped in runtime/verifier) |
| Python Verifier | `cryptography` | `44.0.0` | `Apache-2.0 OR BSD-3-Clause` | Ed25519 verification |

### 6.4 Architectural Scaffolding Disambiguation Ledger (Action 26)
To prevent any ambiguity during technical due diligence or live demonstrations:

| Component / Path | Current Operational Status | Epistemic Classification |
| :--- | :--- | :--- |
| `aeib-verifier/` (Java 21 CLI) & `benchmarks/jvm_native_diff_engine.py` | **Live Executed Code** (`14/14` vector parity in CI) | Verified under stated model |
| `aeib-runtime/` (`Station1`, `Station2`, `Station3`) & `Gate4IntegrationTest.java` | **Live Executed Code** (Real loopback TCP socket fault + HTTP status reconciliation) | Verified under stated model |
| `smaos-wasm-verifier/smaos-verify.html` | **Live Executed Code** (`ed25519-dalek` compiled to WASM, offline browser verification) | Verified under stated model |
| `ebpf/` & `TetragonTracingPolicyCompiler` | **Structural Scaffolding** (Generates policy YAML / BPF map definitions; does not load kernel programs in CI) | **Scaffold Only** (`AGENTS.md` §5) |
| `hardware_attestation/` & `HardwareAttestationReceiptBinder` | **Structural Scaffolding** (Cryptographic quote-binding schema; requires physical Intel TDX / AMD SEV-SNP silicon) | **Scaffold Only** (`AGENTS.md` §5) |
| `Ed25519BbsSelectiveRedactor` (`v1.1-roadmap/`) | **Salted SHA-256 Commitment Tree signed with Ed25519** (Selective field disclosure prototype; not pairing-based BLS12-381 BBS+) | **Prototype** |
| `R1csZeroOverclaimCircuit` (`v1.1-roadmap/`) | **Deterministic $\mathbb{F}_p$ R1CS Constraint Evaluator** (Checks witness equations directly; not a succinct zk-SNARK/STARK) | **Prototype** |
| `SagaReconciler` / `IndeterminateResolutionReceiptProtocol` | **Asynchronous Eventual Consistency** (Resolves `EFFECT_INDETERMINATE` via out-of-band probe + follow-up receipt; not atomic 2PC rollback) | **Eventual Consistency** (`AGENTS.md` §5) |
