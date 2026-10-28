# smaos-ai — Sovereign Multi-Agent OS & Trust Infrastructure

<p align="center">
  <img src="https://raw.githubusercontent.com/smaos-ai/.github/main/profile/avatar.jpg" width="180" height="180" alt="smaos-ai logo" style="border-radius: 50%; box-shadow: 0 4px 20px rgba(0, 229, 255, 0.3);">
</p>

<p align="center">
  <strong>Sovereign, local-first, zero-dependency trust and governance infrastructure for autonomous AI agents.</strong>
</p>

<p align="center">
  <a href="https://github.com/smaos-ai"><img src="https://img.shields.io/badge/license-Apache%202.0%20%7C%20MIT-blue.svg" alt="License"></a>
  <a href="https://github.com/smaos-ai"><img src="https://img.shields.io/badge/standard-RFC%208785%20JCS-green.svg" alt="RFC 8785 JCS"></a>
  <a href="https://github.com/smaos-ai"><img src="https://img.shields.io/badge/IETF-draft--sharif--aat--03-purple.svg" alt="IETF AAT"></a>
  <a href="https://github.com/smaos-ai"><img src="https://img.shields.io/badge/compliance-DORA%20Art.%2017(3)%20%7C%2028(3)-orange.svg" alt="DORA Compliance"></a>
  <a href="https://github.com/smaos-ai"><img src="https://img.shields.io/badge/verification-sub--millisecond%20WASM-brightgreen.svg" alt="WASM Verifier"></a>
</p>

---

## 🏛️ Executive Summary & Core Thesis

Enterprise AI adoption faces a fundamental governance crisis: **Record Reproducibility vs. Decision Reproducibility**.

While closed-model cloud APIs can only offer post-hoc summary logs (*Container Presence*), **smaos-ai** establishes an unbridgeable architectural moat through **Decision Reproducibility via Attestation Closure** (IETF `draft-sharif-agent-audit-trail-03`) and **Relying-Party Evidence Sufficiency** (IETF `draft-schrock-ep-action-evidence-graph-00`). 

By sealing the execution environment with cryptographic bindings (`tokenizer_digest`, `chat_template_digest`, `engine_build_digest`, `numeric_environment_digest`) and evaluating claims against wire-socket truth in pure WebAssembly, **smaos-ai** guarantees zero evidence contamination, zero false positives, and 100% fail-closed safety.

---

## 🛡️ The 8 Moats Architecture

| # | Moat | Standard / Specification | Technical Scope & Code Implementation |
|---|------|--------------------------|---------------------------------------|
| **1** | **Decision Reproducibility** | IETF AAT `draft-sharif-agent-audit-trail-03` §13.6 | **`ReceiptPayload v1.1`**: Sealed with `tokenizer_digest`, `chat_template_digest`, `engine_build_digest`, and `numeric_environment_digest`. |
| **2** | **Evidence Sufficiency** | IETF EP-AEG `draft-schrock-ep-action-evidence-graph-00` §4.2 | **Relying-Party Layer**: Evaluates sufficiency from the auditor's perspective (`admissible`, `missing_evidence`, `stale`, `conflicted`, `unverifiable`). |
| **3** | **Evidence-Path Correctness** | GroundEval (*arXiv:2606.22737*) | **Fuzzer Suite**: Deterministic verification against Silence, Perspective, and Counterfactual edge cases. |
| **4** | **Runtime Data-Quality Gating** | SARC-DQ (*arXiv:2607.26313*) | **Pre-Retrieval Gate**: Classifies evidence as `valid`, `stale`, `malformed`, or `out_of_scope` prior to execution. |
| **5** | **Sub-Millisecond Verification** | CCS (*draft-wang-ccs-runtime-verification*) | **`smaos_verify.wasm`**: Sub-millisecond (<1ms) pure Rust WebAssembly verifier enforcing RFC 9162 Merkle tree proofs and Ed25519 signatures. |
| **6** | **Hardware-Rooted Attestation** | IETF RATS / TPM 2.0 (*arXiv:2608.00801*) | **Enclave Binding**: Cryptographic anchoring into hardware root-of-trust (`tpm_quote`, `sev_snp_measurement`). |
| **7** | **Economic Incentive Alignment** | AIGA `draft-00` | **Continuous Verification Engine**: Real-time streaming drift detection replacing expensive, unrepeatable one-off manual audits. |
| **8** | **Pre-Access Compliance Handshake** | ACD `draft-03` | **PreToolUse Gate**: Machine-to-machine compliance negotiation and policy enforcement before tool execution occurs. |

---

## 🛠️ The 5-Stage OCR Hybrid Audit Pipeline

To solve the **Signal-to-Noise Ratio (SNR) Crisis** in enterprise trace auditing, we implement the **Open Code Review (OCR) paradigm** (*arXiv:2608.09290*):

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                        5-STAGE OCR HYBRID AUDIT PIPELINE                                  │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│ Stage 1: Deterministic Dispatcher  ──► Filters 83–95% healthy read logs in Python ($0)    │
│ Stage 2: Smart Action Bundler      ──► Clusters trace cascades by action_id (±5s window)  │
│ Stage 3: Forensic Interrogator     ──► Executes read-only status and JCS tools            │
│ Stage 4: Wire-Truth Reflector      ──► Socket facts override model opinions (Zero FP)     │
│ Stage 5: Deterministic Anchor      ──► Programmatically binds findings to line offsets    │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

- **`dispatcher.py` (Stage 1)**: Pre-filters read-only telemetry in Python in <15ms at **$0 token cost**.
- **`bundler.py` (Stage 2)**: Groups mutating operations into isolated, sub-2,000 token `ActionBundle` contexts (±5s cascade window) to eliminate the context window compaction cliff.
- **`interrogator.py` (Stage 3)**: Uses scenario-tuned forensic read-only tools (`GetWireStatus`, `CompareJCSDigest`, `CheckRetryPolicy`, `InspectDisbursementLineage`).
- **`reflector.py` (Stage 4)**: Resolves the DEMM-Bench Container Fallacy (*arXiv:2606.20634*). Physical wire socket facts strictly override LLM speculation, freezing unhedged retry loops at `verdict: UNKNOWN`.
- **`anchor.py` (Stage 5)**: Binds findings to byte-exact JSONL line offsets with **0.00% line drift** and SHA-256 evidence digests.

---

## 📦 Core Ecosystem Repositories

| Repository | Purpose | Key Artifacts & Standards |
| :--- | :--- | :--- |
| [**`smaos-verify`**](https://github.com/smaos-ai/smaos-verify) | Zero-dependency cryptographic verifier | `smaos_verify.wasm` (195 KB release, pure Rust, RFC 9162 Merkle + Ed25519) |
| [**`ocr-audit-engine`**](https://github.com/smaos-ai/ocr-audit-engine) | 5-stage deterministic hybrid audit pipeline | Python 3.10+ stdlib, $0 token pre-filter, 0.00% line drift |
| [**`aeib`**](https://github.com/smaos-ai/aeib) | Agent External Invariant Benchmark | 10 canonical scenarios, 15 CCS test vectors, 6-disposition precedence cascade |
| [**`smaos-dora-kit`**](https://github.com/smaos-ai/smaos-dora-kit) | Regulatory filing generator | DORA Art. 28(3) Register of Information (RT.01.01–RT.02.03) under EBA DPM 4.0 |
| [**`ghost-audit-scanner`**](https://github.com/smaos-ai/ghost-audit-scanner) | 60-second read-only CLI diagnostic | Governance Intensity Index (GII) mapped to OWASP LLM Top 10 risks |

---

## 🇪🇺 Regulatory & Institutional Alignment

- **Regulation (EU) 2022/2554 (DORA)**: Article 17 (ICT-related incident management) & Article 28(3) (Register of Information on third-party ICT service providers).
- **Regulation (EU) 2024/1689 (EU AI Act)**: Article 12 (Automatic record-keeping / logging) & Article 14 (Human oversight and Jidoka line-stop halts).
- **Czech Fintech Sandbox**: Pre-registered under [fintechsandbox.cz](https://fintechsandbox.cz) for supervisory engagement with the Czech National Bank (ČNB) and Czech Fintech Association (ČAS).

---

## 🔒 Security & Privacy Invariants

- **100% Local-First & Air-Gapped**: Runs offline with zero external cloud API dependencies.
- **Zero Credential Sharing**: Uses ephemeral signing keys and local hardware enclave quotes.
- **Fail-Closed by Design**: Never coerces transport ambiguity (HTTP 504) into false confirmation.

**Security Disclosures & Institutional Inquiries**: [`andrejlo123@gmail.com`](mailto:andrejlo123@gmail.com)
