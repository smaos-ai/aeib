# AEIB v0.2 – Delivered Scope Checklist (Research Prototype)

> **Operational Boundary & Promise Standard**  
> Use this document as a literal checklist. If a box is not ticked, it is **not in scope to promise** in any email, call, proposal, or repository documentation.

---

### 1. Core Artifact

- [x] **Synthetic conformance bundle**  
  - File: `aeib-0.2-synthetic-prototype-conformance-run.zip`  
  - SHA-256: `5c9a5a9f2d4871d177bc20aaa7282b326aea9450080616ab3544abfec091be9c`  
  - Contents:
    - [x] 8 receipt JSON files (one per canonical scenario).
    - [x] `evidence/transport.jsonl` (8 records).
    - [x] `evidence/probe.jsonl` (8 records).
    - [x] `mapping/transport-to-disposition-mapping.yaml`.
    - [x] `verifier/aeib_verify.py`.
    - [x] `public-keys/key-registry.json`.
    - [x] `manifest.json`.
    - [x] `README.md`, `LIMITATIONS.md`, `FOR_REVIEWERS.md`.

---

### 2. Cryptographic & Mapping Guarantees

- [x] **Ed25519-signed receipts**  
  - Signature covers `{unsigned_payload, unsigned_payload_hash}`.  
  - Verifier checks signature with public key from registry.

- [x] **Deterministic JSON subset**  
  - Sorted keys, compact separators.  
  - Explicitly **not** claimed as RFC 8785 / JCS compliant.

- [x] **Mapping contract enforcement**  
  - `transport-to-disposition-mapping.yaml` defines:
    - [x] Dispositions (`OUTCOME_VERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_FAILED`, `RECONCILIATION_CONFLICT`, `CONTEXT_POLICY_VIOLATION`, `AUTHORITY_NOT_BOUND`).
    - [x] Retry policies (`CLOSE_NO_RETRY`, `PROBE_REQUIRED_NO_ORIGINAL_RETRY`, `FRESH_AUTHORITY_REQUIRED`, `RETRY_WITH_CONTEXT_REPAIR`).
  - Verifier:
    - [x] Loads YAML dynamically.
    - [x] Checks that each receipt’s disposition and retry policy match the matched rule.
    - [x] Verifies mapping contract hash consistency (file ↔ manifest ↔ receipts).

---

### 3. Evidence Binding

- [x] **Transport evidence**  
  - Each receipt references `evidence/transport.jsonl#obs-{scenario}`.  
  - Verifier:
    - [x] Finds the record by ID.
    - [x] Recomputes hash and compares to `transport_evidence_hash`.
    - [x] Checks `dispatch` and `obs` fields match the receipt’s extension.

- [x] **Probe evidence**  
  - Each receipt references `evidence/probe.jsonl#prb-{scenario}`.  
  - Verifier:
    - [x] Finds the record by ID.
    - [x] Recomputes hash and compares to `outcome_probe_hash`.
    - [x] Checks `result` field matches the receipt’s extension.

---

### 4. Test Coverage & Reproducibility

- [x] **Verifier passes cleanly**  
  - Command: `python3 verifier/aeib_verify.py`  
  - Output: 8 `[+] VALID` lines, exit code 0.

- [x] **Idempotent generator**  
  - Running generator scripts:
    - [x] Recreates the bundle directory cleanly.
    - [x] Produces exactly 8 transport records and 8 probe records (no duplicates).

- [x] **Tamper detection**  
  - Modifying `transport-to-disposition-mapping.yaml` or `manifest.json` causes verifier to fail.  
  - Restoring the original file makes verifier pass again.

---

### 5. Documentation & Reviewer Onboarding

- [x] **README.md**  
  - Explains:
    - [x] Purpose (research prototype, synthetic data).
    - [x] How to run the verifier.
    - [x] What is verified (signatures, evidence, mapping).
    - [x] What is not verified (RFC 8785, COSE, SCITT, production guarantees).

- [x] **LIMITATIONS.md**  
  - Explicitly states:
    - [x] Not RFC 8785 / JCS compliant.
    - [x] Not COSE_Sign1 / SCITT compliant.
    - [x] Synthetic data only.
    - [x] No production or compliance claims.
    - [x] Ephemeral keys, no HSM/KMS.

- [x] **FOR_REVIEWERS.md**  
  - Provides:
    - [x] 30-second verifier command.
    - [x] 5-minute tour (which receipts and files to inspect).
    - [x] 4 open engineering questions (idempotency, 7-state fit, probe failures, deployment model).

---

### 6. Integration Scope (What You Can Honestly Discuss)

- [x] **Offline review**  
  - You can send the ZIP + SHA-256 and walk a reviewer through:
    - [x] One ambiguous scenario (e.g., `02a-504-ambiguous.json`).
    - [x] The mapping YAML.
    - [x] The verifier output.

- [x] **Conceptual integration patterns** (future roadmap)  
  - You can discuss:
    - [x] Sidecar proxy pattern (Mode 2).
    - [x] In-process filter pattern (Mode 3, e.g., `ProofOrStopFilter.java` as a reference).
  - But you do **NOT** promise:
    - [ ] A working sidecar today.
    - [ ] A supported SDK.
    - [ ] Integration with their real systems.

- [x] **Research collaboration**  
  - You can explore:
    - [x] Whether the 7-state taxonomy matches their real failure modes.
    - [x] How this primitive might complement their existing saga/orchestration/retry logic.
  - You do **NOT** promise:
    - [ ] Custom development.
    - [ ] Production pilots.
    - [ ] Compliance certifications.

---

## 📌 One-Paragraph Scope Statement (Copy/Paste Ready)

> “AEIB v0.2 is a synthetic research prototype. It delivers a conformance bundle with 8 scenarios, Ed25519-signed receipts, and an offline verifier that checks signatures, evidence bindings, and mapping-rule consistency. It uses a deterministic JSON subset (not RFC 8785 validated) and operates entirely on synthetic data. It is not a production system, not integrated with real banking or physical systems, and not a compliance solution. Current scope is limited to offline review, engineering feedback, and conceptual discussions about future integration patterns (sidecar proxy or in-process filter).”
