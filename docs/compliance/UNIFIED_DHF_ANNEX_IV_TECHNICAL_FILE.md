# EU AI Act Annex IV Unified Technical File & ISO 13485 DHF Addendum
## Integrated Compliance Architecture: ISO 42001 + EN 18286 + ISO 13485 + ECMA-424 CBOM

> **EPISTEMIC & REGULATORY NOTICE:** EPISTEMIC BOUNDARY NOTICE: All technical assertions, standards alignments, and hazard mitigations in this dossier are observed, tested, and evaluated under the stated model using deterministic prototype and verification scaffolds. AEIB produces verifiable technical evidence to support deployer compliance; it does not confer legal certification.

---

### Section 1: Executive Identity & Cryptographic Anchor
* **Document Title:** Unified High-Risk AI Technical Documentation & ISO 13485 DHF Addendum
* **Schema Version:** `aeib.unified.technical.file.annex_iv.v1`
* **Package Digest (SHA-256):** `2ac088b24f7a51e77e25f318810d11ea3a9c8482babf856b06848c71e1950370`
* **Signature Hex:** `72242bf8416b7c5724b6567ddf2dca6a...`

---

### Section 2: Statutory Timelines & Target Deadlines
| High-Risk Classification | Mandatory Enforcement Deadline | Target Technical File Deliverable |
|---|---|---|
| **ANNEX III STANDALONE HIGH RISK** | `2027-12-02` | Standalone EU AI Act Annex IV Technical File + EN 18286 QMS Conformity File |
| **ANNEX I EMBEDDED HIGH RISK** | `2028-08-02` | Unified Design History File (DHF) Addendum bridging ISO 13485 & AI Act Annex IV |

---

### Section 3: The 4-Layer Integrated Compliance Architecture
| Compliance Layer | Governing Standard | Technical Runtime Enforcement Mechanism |
|---|---|---|
| **LAYER_1_ORGANIZATIONAL_AIMS** | `ISO/IEC 42001:2023` | System inventory, root sponsor identity binding, policy epoch monotonic versioning, and high-level risk treatment classification. |
| **LAYER_2_EU_AI_ACT_HARMONIZED_QMS** | `CEN-CENELEC EN 18286:2026` | Pre-dispatch TCC escrow, fail-closed human release gates, RFC 8785 JCS CAID derivation, and continuous hash-chained execution receipt generation. |
| **LAYER_3_PRODUCT_SAFETY_AND_MEDICAL_DHF** | `ISO 13485:2016 / ISO 14971:2019 / ISO 9001:2015 & EU MDR 2017/745 / IVDR 2017/746` | Fail-closed socket mediation for consequential actions (clinical dosage, physical actuators, financial disbursement), hazard event logging, and hardware-level container isolation. |
| **LAYER_4_SUPPLY_CHAIN_AND_CBOM** | `EU AI Act Art. 28 / ISO 42001 Annex A.8 / CycloneDX 1.6 / ECMA-424` | Pinned MCP tool descriptors, SHA-256 model weight digests, and Ed25519-signed ECMA-424 CBOM receipts mapping cryptographic algorithm agility. |

---

### Section 4: ISO 14971 Clinical & Financial Hazard Log
| Hazard ID & Title | Clinical / Operational Risk | AEIB Technical Mitigation Control | Residual Risk Level |
|---|---|---|---|
| **HZD-01-TRANSPORT-AMBIGUITY**<br>*Layer 7 Transport Ambiguity & Duplicate Consequential Mutation* | Network timeout (HTTP 504) or TCP reset causes unhedged agent retry, executing duplicate patient medication disbursement, double financial transfer, or redundant physical actuator cycle. | Station 3 Wire Latch traps state to EFFECT_INDETERMINATE (retry_safe: false). Automated retries blocked; single out-of-band probe (ProbeBudget: 1) verifies downstream state. | `ACCEPTABLE_UNDER_STATED_MODEL` |
| **HZD-02-PARALLEL-RESOURCE-DEPLETION**<br>*Concurrent Multi-Agent Budget & Resource Overrun* | Concurrent subagents read unreserved balance simultaneously and execute parallel dispatches, overrunning institutional budget ceilings or physical medication reservoirs. | Pre-socket TCC (Try-Confirm-Cancel) atomic reservation in SQLite WAL with BEGIN IMMEDIATE. Subagents cannot dispatch until budget is locked; excess requests rejected fail-closed. | `ACCEPTABLE_UNDER_STATED_MODEL` |
| **HZD-03-CONTEXT-POISONING**<br>*Memory Poisoning & Prompt Injection Parameter Tampering (AT57)* | Adversary manipulates working memory or RAG context to alter destination IBAN, clinical dosage value, or actuator threshold without operator consent. | Station 1 Context Integrity Gate evaluates candidate action CAID against ingestion-time commitment manifest. Tampered parameters trigger HALT_CONTEXT_INTEGRITY_FAILURE (0 socket bytes emitted). | `ACCEPTABLE_UNDER_STATED_MODEL` |
| **HZD-04-EVIDENTIARY-TAMPERING**<br>*Audit Log Tampering & Forensic Repudiation* | Malicious insider or compromised operating system alters local audit rows to conceal fraudulent transactions or lethal clinical dosage modifications. | RFC 8785 JCS + Ed25519 hash-chained Continuity Receipts registered into RFC 9942 / RFC 9943 SCITT Merkle tree transparent statements. Any in-place bit flip triggers InvalidSignature. | `ACCEPTABLE_UNDER_STATED_MODEL` |

---

### Section 5: Annex IV Mandatory Execution Controls (§1–§6)
* **Article 11 / Annex IV §1 (General Description):** Deterministic interception, pre-dispatch transactional reservation (TCC), uncertain-outcome wire latching (HTTP 504 / TCP RST), and continuous cryptographic receipt emission for autonomous AI tool dispatches.
* **Article 12 / Annex IV §4 (Automatic Logging):** Every external dispatch intent and resulting outcome is committed to an append-only hash-chained ledger prior to and immediately following socket I/O.
* **Article 14 / Annex IV §6 (Human Oversight):** Safety policy decoupled from model weights; enforced at pre-socket gate. Prohibition of [APPROVE OVERRIDE] without authenticated target evidence.
* **Article 15 / Annex IV §3 (Robustness & Accuracy):** Five-term pre-dispatch predicate: `GrantValid and PolicyEpochFresh and SourceEpochFresh and CAIDMatch and TicketUnburned`
* **Article 28 / Annex IV §2 (Supply Chain / CBOM):** CycloneDX 1.6 / ECMA-424 bound in `evidence/cbom.json`.

---

### Section 6: Verified Artifact Manifest
| Artifact Path | File Present | SHA-256 Digest |
|---|---|---|
| `evidence/cbom.json` | Verified Present | `43e0a056ca87ced4...` |
| `compliance/iso_42001_soa_report.json` | Verified Present | `afeb7614e432608a...` |
| `docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md` | Verified Present | `d8ec3537f2a6c850...` |
| `docs/compliance/ANNEX_IV_TECHNICAL_DOSSIER.md` | Verified Present | `d2b75418d87e9018...` |
| `src/jcs_canonicalizer.py` | Verified Present | `2be49725bf6af150...` |
| `src/eo1_write_before_execute.py` | Verified Present | `2437ede45bae1b82...` |
| `aeib-native-runtime/src/sqlite_acid_tcc_boundary.py` | Verified Present | `9c77db758a7b9140...` |
