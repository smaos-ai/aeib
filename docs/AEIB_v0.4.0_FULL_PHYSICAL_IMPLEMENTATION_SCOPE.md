# 🚀 Full Physical Implementation Scope & Execution Verification Delivery
### AEIB (Agentic Execution-Integrity & Boundary) v0.4.0
**Bounded Synthetic Benchmark and Local Runtime Reference for Agent Effect-Integrity Evidence**

---

## 🏛️ 1. Physical Software Engines & Executable Verifiers

```text
                                PHYSICAL RUNTIME ARCHITECTURE
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  AEIB GATEWAY ADAPTER & DISPATCH ENGINE (dispatcher.py, pipeline_runner.py)            │
│  • RFC 8785 JCS Candidate Action ID Binder (candidate_caid)                            │
│  • Pre-Dispatch Standing Check (Tn) immediately before wire emission                   │
│  • Memory-Digest Binding Interlock (AT29 / AT42)                                       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ZERO-DEPENDENCY OFFLINE WASM VERIFIER (smaos_verify.wasm / verifier/verify_attestation.py) │
│  • 195 KB standalone Rust/WASM binary | 10.4µs p99 Latency | 212,710 Receipts/sec          │
│  • Evaluates 14/14 release-blocking cryptographic & schema tamper checks offline       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PHYSICAL TEST HARNESSES & FAULT INJECTORS                                             │
│  1. Track B Web-Mutation Harness (B01–B11): HTTP 504, TCP RST, socket drops            │
│  2. Extended Edge Harness (BT12–BT18): Process crash recovery, dual-probe traps         │
│  3. Container & Sidecar Bypass Battery (AT41): Loopback, hostNetwork, CAP_NET_RAW      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Zero-Dependency WASM Verifier (`verifier/verify_attestation.py` & `smaos_verify.wasm`)**:
  * **Size & Performance**: 195 KB (199,770 bytes) standalone Rust/WASM binary executing in **10.4µs p99 latency** at **212,710 receipts/sec**.
  * **Tamper Verification**: Offline verification passing **14/14 release-blocking tamper checks** on Ed25519 signatures, Merkle roots, and JCS canonical payloads without network access.
  * *Note: Designed for offline verification; network isolation must be verified in the execution environment.*
* **Track B Web Mutation Finality Engine (`src/track_b_harness.py` & `tests/test_track_b_scenarios.py`)**:
  * Simulates 11 core wire fault scenarios (**B01–B11**) under physical transport drops (`HTTP 504 Gateway Timeout`, `TCP RST`, socket cuts).
  * Evaluates against **100% target-side backend ledger ground-truth verification** (independent oracle).
* **Extended Edge & Decisive Demo Harness (`src/decisive_demo_harness.py` & `tests/test_decisive_demo.py`)**:
  * Evaluates edge matrix **BT12–BT18** (speculative retry blocks, dual-probe conflict traps, gateway process crash recovery, browser profile isolation).
  * Confirms **Target `commit_count = 1`** with **0 duplicate retries** across 500 deterministic test episodes.
* **Container & Sidecar Bypass Battery (`AT41`)**:
  * Evaluates container-level escape attempts: `localhost` loopback bypasses, `hostNetwork` sharing, privileged `CAP_NET_RAW` socket creation, init container race conditions, DNS bypasses, and dual-stack IPv4/IPv6 socket attempts.

---

## 📋 2. Machine-Readable Schemas & Verification Contracts

```text
schemas/
├── aeib_bench_v0.1_spec.json           # Master Specification (AT15–AT45 & GOD-01–GOD-06)
├── aeib-bench-web-v0.1.schema.json      # Track B Web Mutation JSON Schema
└── zenodo.json                          # DOI Registration Deposit Manifest
```

### Master Acceptance Test Specification (`AT15`–`AT45` & `GOD-01`–`GOD-06`)
The specification (`schemas/aeib_bench_v0.1_spec.json`) formally defines **37 physical acceptance scenarios**:

| Test Group | Test IDs | Focus Vector & Verification Mechanics | Target Disposition |
| :--- | :--- | :--- | :--- |
| **Core & Epochs** | `AT15`–`AT25` | Cryptographic grant chains (`AT16`), TOCTOU policy epoch re-checks (`AT23`), JCS schema pinning (`AT24`), and COSE receipt verification (`AT25`). | `STALE_STANDING` / `EVIDENCE_LATCHED` |
| **Egress & Memory** | `AT26`–`AT29` | `ProxyToolAbuseGuard` URI allowlisting (`AT26`), Anonymous A2A model shrouding (`AT27`), prototype eBPF Ring-0 kernel intercept scaffold (`AT28`), and Memory-Digest Binding (`AT29`). | `PROXY_EGRESS_VIOLATION` / `C4_QUARANTINE` |
| **Federation & Audience**| `AT30`–`AT36` | Credential Audience Binding (`AT30`), Redirect Chains (`AT31`), DNS Rebinding (`AT32`), Cross-Protocol Instructions (`AT33`), Token Passthrough (`AT34`), Agent Card Mutation (`AT35`), and Secret Leakage (`AT36`). | `AUDIENCE_MISMATCH` / `SECRET_LEAKAGE_BLOCKED` |
| **Handshake & Transport**| `AT37`–`AT39` | OAuth discovery SSRF in `WWW-Authenticate` headers (`AT37`), Agent Card prompt sanitization (`AT38`), and Per-Hop 302/307 Redirect Re-resolution (`AT39`). | `HANDSHAKE_DISCOVERY_BLOCKED` |
| **Cross-Layer & K8s** | `AT40`–`AT45` | Infrastructure Identity Mismatches (`AT40`), Sidecar Direct Socket Bypass (`AT41`), Un-provenanced Memory Writes (`AT42`), Cross-Protocol Delegation Handoffs (`AT43`), Control Degradation Fallbacks (`AT44`), and Governance Version Staleness (`AT45`). | `EGRESS_INTERCEPTED` / `CONTAINMENT_ENGAGED` |
| **GOD Operator Suite** | `GOD-01`–`GOD-06`| Intervention Binding (`GOD-01`), Replay Immutability (`GOD-02`), Ask/Intervene Split (`GOD-03`), Target Primacy Divergence (`GOD-04`), Export Tamper Check (`GOD-05`), and Operator RBAC (`GOD-06`). | `STALE_STANDING` / `EFFECT_INDETERMINATE` |

---

## 📜 3. Regulated Evidence Export Kit

* **DORA Article 17 Incident Exporter (`scripts/export_dora_incident.py` / `dora_art17_gap_report.json`)**:
  * Produces evidence that may support incident detection, timeline reconstruction, classification, and investigation workflows. Timing expectations (<=4h initial, 24h/72h intermediate, 1 month final per RTS 2025/301) derive from applicable standards; AEIB records local timestamps and wire telemetry (`bytes_sent`, `socket_state`, `fault_phase`), but does not determine when legal clocks start or whether an incident is major.
* **DORA Article 28(3) Register of Information (`scripts/validate_dora_register.py` / `2_DORA_Register_of_Information.csv`)**:
  * Reference evidence-mapping workflow for selected ICT third-party relationship fields (`RT.01.01`–`RT.02.03` xBRL-CSV); completeness and regulatory sufficiency require institution-specific legal, contractual, and supervisory review.
* **EU AI Act & MAS Attestation Receipts**:
  * Emits append-only, tamper-evident `COSE_Sign1` Ed25519 receipts aligned with SCITT-compatible evidence architectures (RFC 9943). Human oversight records require an identified reviewer, review timestamp, reviewed raw evidence, action digest, decision, and authority to intervene/reverse.

---

## 🧪 4. Multi-Agent & Simulator Integrations

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  OWASP FINBOT MULTI-AGENT TESTBED ("DEFENDED MODE")                                    │
│  • Inline proxy between orchestrators and MCP tool servers                             │
│  • Intercepts lateral prompt injections, cross-agent task handoffs (AT43), & SSRF      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  GOD (GOVERN · OBSERVE · DIRECT) CONTROL ROOM INTEGRATION (GOD-01 to GOD-06)          │
│  • GOD-01 (Intervention Binding)   : Binds steering to (step_id, policy_epoch, CAID)  │
│  • GOD-02 (Replay Immutability)    : Replays force dry_run; blocks live dispatches      │
│  • GOD-03 (Ask/Intervene Split)    : Read-only queries produce zero state drift        │
│  • GOD-04 (Target Primacy)         : Target ledger evidence overrides simulation state  │
│  • GOD-05 (Export Tamper Check)    : WASM verifier invalidates altered replay packs    │
│  • GOD-06 (Operator Authority)     : Observation RBAC cannot release held actions      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  OAGMM EMPIRICAL BENCHMARK MAPPING                                                     │
│  • Maps Dr. Tamsolja's Operational AI Governance Maturity Model (Levels 1–4)           │
│    directly to physical fault-injection test profiles (AT15–AT45).                      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 5. Distribution Bundles & Verified Checksums

The release is packaged in standalone archives located in `dist/`:

1. **`aeib-v0.4.0-cleanroom.tar.gz`** (371,213 bytes / 363 KB):
   * SHA-256: `6d52b322aeee795e445db4d8692f0ce3ca71157f718128746a1e8264faf61363`
   * Contains clean-room verification harness (`cleanroom/verify_from_scratch.py`), AST purity scanner, assurance profiles, and runnable source trees.
2. **`smaos_verify.wasm`** (199,770 bytes / 195 KB):
   * SHA-256: `6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041`
   * Standalone WebAssembly verifier compiled from Rust source.
3. **`verifier.html`** (7,844 bytes):
   * SHA-256: `11a3cb753a634b78ab83f1a6f0705c19d54d029424953eef8af3056e0a3dd11b`
   * In-browser drag-and-drop receipt and attestation verifier.

---

## 📁 6. Master Executive & Regulatory Dossiers

* **`AEIB_BENCHMARK_REPORT-v5.md`**: Master technical dossier incorporating the 5-layer threat model, the ELIAS/HARMONIC/AEIB triad, the AT15–AT45 and GOD-01–GOD-06 specifications, and bounded claim rules.
* **`CISO_BRIEFING_PACK_v2.md`**: Executive brief for CISOs and risk committees, framing AEIB as the dispatch-time interlock in a defense-in-depth architecture.
* **`CAS_PRE_SUBMISSION_PACK.md`**: Formal regulatory inquiry and sandbox consultation dossier for ČAS (TNK 156) and CzechInvest FinTech Sandbox II.
* **`AEIB_v0.4.0_ZENODO_AND_CZECHINVEST_SUBMISSION_PACK.md`**: Complete submission and deposit pack with verified contacts and staging API commands.

---

## 🔒 7. The Approved 5-Fact Empirical Claim Boundary

All technical documentation, briefings, and regulatory filings adhere strictly to these **5 empirical assertions**:

1. *"No duplicate retry was issued by the controlled gateway in the tested scenario."*
2. *"The gateway preserved an ambiguous outcome after the tested transport fault."*
3. *"The verifier detected tampering in the tested tamper cases."*
4. *"The benchmark grades against target-side state rather than agent self-report."*
5. *"The adapter is designed to integrate with existing identity and gateway controls."*

---

### 🏁 Execution Invariant & Epistemic Boundaries

> **The Sovereign Invariant of Execution Integrity:**  
> **"AEIB is a cross-layer execution-integrity boundary, not a complete cross-layer security platform. It consumes identity, delegation, memory, infrastructure, and governance claims; binds them to a specific operation via JCS hashing; rejects stale or mismatched standing before dispatch; preserves transport ambiguity; and emits evidence for reconciliation, containment, and separately authorized release.**  
>  
> **Permissions are time-indexed claims; execution requires current standing plus effect evidence. If standing no longer holds at the millisecond of wire dispatch ($T_{\text{dispatch}}$), the action does not execute."**

```text
Status Classification:
- Package: AEIB v0.4.0 — Bounded Synthetic Benchmark and Local Runtime Reference for Agent Effect-Integrity Evidence
- Synthetic Track B: reported complete
- Local physical socket test: reported complete
- Real third-party API: pending
- Real TinyFish cloud session: pending
- Independent reproduction: pending
- PAP interoperability: pending
- CzechInvest consultation: non-certifying inquiry only
- CNB submission: separate via official specialized FinTech web form
- ČAS submission: official contact route (agentura@agenturacas.gov.cz / Datová schránka 4htvpem)
- Regulatory certification: not claimed
```

> **Mandatory Epistemic Disclaimer:**  
> **All claims refer to the declared synthetic or local physical harness and do not establish remote exactly-once behavior, universal security, deployment readiness, or regulatory compliance.**
