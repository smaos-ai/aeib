# Zenodo Deposit Metadata & Abstract: AEIB v0.4.0
## Track B Web Mutation Finality & Execution-Integrity Benchmark Report

- **Target Repository**: [Zenodo (CERN / OpenAIRE)](https://zenodo.org/)
- **Release Version**: `v0.4.0`
- **Release Date**: `2026-10-07`
- **Licenses**: Dual-licensed under `Apache-2.0` (Open Core Software & Harness) and `CC-BY-4.0` (Specifications & Documentation)
- **Status**: AEIB v0.4.0 is a bounded synthetic benchmark and execution-evidence proposal, with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction.
- **Offline Verifier**: `dist/smaos_verify.wasm` (199,770 bytes)

---

## 1. Zenodo Upload Form Fields

| Field | Value |
|:---|:---|
| **Resource Type** | Software |
| **Title** | AEIB v0.4.0: Track B Web Mutation Finality & Execution-Integrity Benchmark Report |
| **DOI** | *(Generated automatically by Zenodo upon record publication; note that a reserved DOI is not final until published)* |
| **Publication Date** | `2026-10-07` |
| **Authors / Creators** | Leukhin, Andrej (Affiliation: SovereignNexus, ORCID: `0009-0004-9543-8263`, Email: `andrejlo123@gmail.com`) |
| **Description / Abstract** | *(See Section 2 below for exact text)* |
| **License** | Apache License 2.0 (Code) / Creative Commons Attribution 4.0 International (CC-BY-4.0, Docs) |
| **Keywords** | `Agentic AI`, `Autonomous Systems`, `Execution Finality`, `GIRAI 2026`, `LIMBO Prior Art`, `DORA Regulation (EU) 2022/2554`, `EU AI Act Article 50`, `RFC 8785 JCS`, `IETF SCITT RFC 9943`, `OpenTelemetry GenAI`, `Retry Suppression`, `Uncertainty Latching`, `Target-Side Ledger Benchmark`, `WebAssembly Verifier`, `Personal Agent Protocol` |
| **Communities** | `computer-science`, `open-science`, `ai-governance` |
| **Related Identifiers** | `arXiv:2608.09290` (references), `arXiv:2609.29095` (references), `arXiv:2609.35928` (references), `https://datatracker.ietf.org/doc/draft-schrock-canonical-action-identifier/` (references), `https://github.com/sovreignnexus/smaos` (isSupplementTo) |

---

## 2. Zenodo Description / Abstract (Exact Copy-Paste Text)

```text
AEIB v0.4.0 is a bounded synthetic benchmark and execution-evidence proposal, with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction. AEIB is a vendor-neutral execution-evidence integration layer for state-changing agent actions. It binds a unique operation to an exact request, records transport ambiguity as a typed disposition, removes retry authority until reconciliation, and preserves evidence for separately authorized review and release.

Grounded in the principle that "Permissions are time-indexed claims; execution requires current standing plus effect evidence" (Capability ≠ Authority ≠ Standing ≠ Execution), the package bridges the GIRAI 2026 governance gap ("adoption outpaces self-constraint") by establishing millisecond self-constraint at the wire boundary.

### Key Deliverables in AEIB v0.4.0
1. aeib-bench v0.1 (Synthetic Benchmark):
   Evaluates agent runtime behavior against an independent target-side ledger oracle across 12 Layer 7 wire-fault scenarios (AT01–AT12), 11 extended governance boundary tests (AT15–AT25), 11 web mutation finality scenarios (B01–B11), 7 extended physical execution edge cases (BT12–BT18), and 10 operational integration tests (AT26–AT35). Total: 50 automated scenario tests.

2. Identity Triad Specification:
   Separates unique intent instance (operation_id) from exact request hash (request_digest) and target idempotency identity (business_idempotency_key), overcoming the collision flaws of payload-only content identifiers.

3. Prior-Art Adjusted Integration:
   Explicitly positioned against LIMBO (arXiv:2609.29095), RFC 9110 HTTP semantics, and OpenTelemetry GenAI semantic conventions (proposing gen_ai.effect_disposition event projection).

4. AEIB Gateway Adapter & Personal Agent Protocol (PAP) Adapter Proposal:
   A reference control-plane adapter sitting beneath agent identity (Microsoft Entra Agent ID, AWS IAM) and gateway prompt firewalls. Features RFC 8785 JSON Canonicalization Scheme (JCS) payload binding, fail-closed uncertainty latching (retry_safe: false), single-flight out-of-band target probe coalescing against declared target-side oracles, real Ed25519 cryptographic receipts, and decoupled human release separation.

5. Regulated Evidence Export Reference:
   Supporting telemetry generation designed to inform DORA (Regulation (EU) 2022/2554) Article 17 incident timeline logs (initial <=4h/24h, intermediate 72h, final 1 month per RTS 2025/301), Article 28(3) Register of Information templates (RT.01.01–RT.02.03 xBRL-CSV), EU AI Act Article 50 (C2PA metadata), and IETF SCITT RFC 9943 continuity receipts.

### Locked Milestone Claim
"Under the declared synthetic Track B scenarios, the harness matched gateway dispositions to an independent target-side ledger and issued no speculative retry in the tested ambiguous cases (11/11 reported synthetic scenarios matched the declared oracle)."

### Strategic Framing
"Hyperscalers and GRC frameworks define what an agent is permitted to attempt. AEIB provides the execution-integrity plane that enforces real-time self-constraint at the wire boundary—verifying target-side ground truth, preventing speculative retries, and proving that authority still stands before consequence binds."

### Strict 5 Approved Empirical Observations
1. No duplicate retry was issued by the controlled gateway in the tested scenario.
2. The gateway preserved an ambiguous outcome after the tested transport fault.
3. The verifier detected tampering in the tested tamper cases against trusted anchors.
4. The benchmark grades against target-side state rather than agent self-report.
5. The adapter is configured to integrate with existing identity and gateway controls.

### Status & Approved Scope Text
AEIB v0.4.0 is a bounded synthetic benchmark and execution-evidence proposal, with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction.

The package reports target-ledger-grounded disposition matching, retry suppression, schema/CAID invalidation, probe coalescing, and restart-latch behavior under declared synthetic scenarios.

Independent reproduction, external target validation, real TinyFish execution, PAP interoperability, deployment-specific egress testing, and regulatory assessment remain pending.

The package does not establish universal exactly-once execution across arbitrary distributed networks, absence of remote duplicate effects, complete prompt-injection prevention, or regulatory compliance.
```

---

## 3. Mandatory Pre-Publication Checklist

Before publishing on Zenodo, ensure every item below is audited and verified:

- [x] **Release Version**: Tagged `v0.4.0` in git.
- [x] **Source Commit**: Exact git commit hash recorded in distribution metadata (`e02b1ef7`).
- [x] **Archive SHA-256**: Computed from the final archive immediately before deposit (do not use unverified claimed digests).
- [x] **Dependency Lockfile**: Fully vendored or locked with zero unvetted runtime dependencies.
- [x] **Runtime Manifest**: Complete file list and checksums in `compliance/aeib_manifest.json`.
- [x] **Test Transcript**: Clean-room test run output verified across all scenarios.
- [x] **Scope and Limitations**: Explicitly states synthetic harness scope and lack of universal consensus claims.
- [x] **Public Verification Key**: Embedded in `keys/` and verifier source.
- [x] **Offline Verifier**: `dist/smaos_verify.wasm` (199,770 bytes) and `dist/verifier.html`.
- [x] **Negative-Test Outputs**: Tamper test outputs from `test_tampered_receipt_signature_fails_verification` and `test_corrupted_ledger_state_fails_closed`.
- [x] **Licenses**: Dual-licensed: Apache-2.0 (Code) / CC-BY-4.0 (Specifications & Docs).
- [x] **Author ORCID**: `0009-0004-9543-8263` (Andrej Leukhin).
- [x] **Contact Address**: `andrejlo123@gmail.com`.
