# ANNEX IV DOSSIER — Population & Export Guide

## Overview
The `annex_iv_structure.json` file provides a complete regulatory template for EU AI Act Annex III high-risk system compliance. This guide explains how to populate it with real pilot execution data and export to PDF + KMS-signed artifact.

## Document Structure

### Metadata Section
Tracks document versioning and KMS signing readiness:
- `document_id`: ANNEX-IV-SMAOS-v1.0 (locked identifier for regulatory filing)
- `kms_signature`: null (populated at export time with Ed25519 signature)
- `pdf_export_ready`: false (set to true only after all sections populated)

### 9 Mandatory Sections (EU AI Act Annex IV)

#### Section 1: System Identification
**Update required by:** Week 1 (Phase 1 start)
- System name, version, delivery date (locked: May 31, 2027)
- Complete architecture: 8 layers + line counts
- Provider info (Claude API version, model endpoint)

#### Section 2: Intended Use
**Update required by:** Week 2 (pilot scope definition)
- 3 pilot domain descriptions (hotel, glass, school)
- Decision types and expected volumes
- Data inputs and regulatory categories

#### Section 3: Risk Classification
**Update required by:** Week 3 (risk assessment complete)
- EU AI Act Article mapping (Annex III compliance)
- Risk factors per pilot (biometrics, employment, financial)
- Mitigation strategy per layer (L1→L8 governance)

#### Section 4: Compliance Measures
**Update required by:** Week 4 (compliance plan locked)
- Article 50 (notification) → Sep 16-22, 2026 KARP submission
- Article 13 (transparency) → L1→L7 implementation mapping
- Article 6 (Module H conformity assessment) → Third-party auditor assignment
- Per-layer compliance checklist

#### Section 5: Testing & Validation
**Update required by:** Weeks 5-8 (test execution ongoing) + Week 12 (final report)
**Fields to populate from test runs:**
- `ragas_evaluation.current_baseline` → Actual accuracy % (Sep 2026)
- `ragas_evaluation.final_target` → May 2027 result
- `defect_rate` → cargo clippy + cargo audit results
- Pilot test case results:
  - `hotel_credit.decision_accuracy`
  - `glass_safety.false_positive_rate`
  - `school_access.biometric_match_rate`

#### Section 6: Human Oversight
**Update required by:** Week 4 (escalation policies) + Weeks 9-12 (checkpoint logs)
- Escalation triggers per pilot (auto-approve thresholds)
- Response SLAs and override authority
- LangGraph checkpoint implementation (3-node architecture)
- Override reason capture format (required for Article 22 compliance)

#### Section 7: Data Handling
**Update required by:** Week 2 (architecture) + Weeks 6-8 (GDPR audit)
**Fields to verify:**
- pgvector database: latency benchmarks (<100ms target)
- GDPR Article 15/16/17/20 implementation status
- Consent records per pilot (1000+ entries by May 2027)
- Encryption key rotation schedule + HSM assignment

#### Section 8: Incident Reporting
**Update required by:** Week 3 (policy) + Weeks 9-12 (actual incident logs)
**Fields to populate:**
- Any critical incidents (report within 4 hours to romana.cernikova@karp-kv.cz)
- Root cause analysis (from AP2 ledger)
- Corrective actions taken (commit hash + test evidence)
- Regulatory filing confirmations

#### Section 9: Documentation Trail
**Update required by:** Ongoing (Section 9a: Git commits) + Week 12 (Section 9b: Proof artifacts)
**Critical validation points:**
- All commits to main harness must be signed with Ed25519
- Proof artifacts must exist and be linked:
  - Artifact 1: CanIRun.ai integration (hardware detection)
  - Artifact 2: FreeToken benchmark (cost model)
  - Artifact 3: Is Agentic A+ report (third-party verification)
  - Artifact 4: agentacct (cost accounting)
  - Artifact 5: unlazy (lazy evaluation detector)
  - Artifact 6: RAGAS golden set report
  - Artifact 7: AP2 immutable ledger (1000+ decisions)

## Population Timeline

```
Week 1-2:   Sections 1, 2 (system definition + use cases)
Week 3-4:   Sections 3, 4, 8 (risk + compliance + incident policies)
Week 5-8:   Section 5 (test execution, populate results)
Week 6-8:   Section 7 (GDPR audit, encryption validation)
Week 9-10:  Section 6 (human oversight logs, SLA verification)
Week 11-12: Section 9 (proof artifacts, KMS signing)
```

## Export Workflow

### Step 1: Validation Checklist
Before exporting, verify all sections:
```
[ ] Section 1: System Identification complete
[ ] Section 2: Intended Use (all 3 pilots defined)
[ ] Section 3: Risk Classification (Article mapping done)
[ ] Section 4: Compliance Measures (KARP/Module H paths clear)
[ ] Section 5: Testing (129 tests passing, RAGAS ≥87%)
[ ] Section 6: Human Oversight (3 LangGraph checkpoints live)
[ ] Section 7: Data Handling (pgvector latency <100ms, GDPR verified)
[ ] Section 8: Incident Reporting (contact: romana.cernikova@karp-kv.cz)
[ ] Section 9: Documentation (all 7 proof artifacts linked)
```

### Step 2: JSON Finalization
1. Update `metadata.pdf_export_ready` → true
2. Validate JSON syntax: `jq . annex_iv_structure.json`
3. Commit to git (signed):
   ```
   git add dossier/annex_iv_structure.json
   git commit -S -m "annex-iv: populate all 9 sections, ready for export (Phase 1 week 12)"
   ```

### Step 3: PDF Generation
Use a PDF template with EU AI Act Annex IV formatting:
```
Input:  annex_iv_structure.json
Output: ANNEX-IV-SMAOS-v1.0.pdf
```

Recommended tool: Python + reportlab or LibreOffice Calc (JSON → CSV → Writer).

### Step 4: KMS Signing
1. Calculate SHA-256 digest of JSON:
   ```
   shasum -a 256 annex_iv_structure.json
   ```
2. Sign with Ed25519 (KMS system):
   ```
   # Pseudo-code; actual KMS integration depends on provider
   kms_signature = ed25519_sign(json_digest, kms_private_key_version=current)
   ```
3. Update `metadata.kms_signature` field with signature bytes
4. Store public key fingerprint in AP2 ledger (immutable record)

### Step 5: Regulatory Submission (Sep 16-22, 2026)
1. Recipient: romana.cernikova@karp-kv.cz
2. Attachments:
   - ANNEX-IV-SMAOS-v1.0.pdf (KMS-signed, QR code page)
   - annex_iv_structure.json (source data)
   - proof_artifacts/ folder (7 files + checksums)
3. Subject: "SMAOS v1.0 Annex IV Technical Dossier — KARP Submission"
4. Body: 1-page Czech summary (see KARP_SUBMISSION.md)

## Pilot Data Integration Points

### Hotel Credit Scoring Pilot
**Location:** Section 2 + Section 5 + Section 6
- Population: 100+ guest profiles (synthetic + real test data)
- Data file: `pilots/hotel_credit_scoring.json`
- Escalation log: `pilots/hotel_escal_decisions.csv` (500+ rows by May 2027)
- Human review records: `pilots/hotel_human_approvals.json` (5% escalation rate)

### Glass Manufacturing Safety Pilot
**Location:** Section 2 + Section 5 + Section 8
- Population: 500+ defect images (synthetic + archive)
- Data file: `pilots/glass_defect_dataset.json`
- Incident report (if any): `pilots/glass_incidents.md`
- False positive rate baseline: Target <2%, actual TBD (Week 5)

### School Access Control Pilot
**Location:** Section 2 + Section 6 + Section 7
- Population: 200+ identity verification scenarios
- Data file: `pilots/school_access_log.json`
- Biometric validation records: `pilots/school_biometric_results.csv`
- Human approval rate: 100% (no auto-approve for education/identity)

## Proof Artifacts Checklist

Each artifact must include:
1. File (executable, report, or log)
2. Hash (SHA-256, reproducible)
3. Timestamp (locked to Phase 1 completion)
4. Signature (Ed25519)
5. Verification instructions (how to reproduce)

### Artifact 7: AP2 Immutable Ledger
Most critical proof artifact for regulatory defense.
**Content by May 31, 2027:**
- 1000+ decision records (hotel + glass + school pilots)
- Per decision: timestamp, policy layer evaluation, human approval (if escalated), outcome
- Cryptographic linking: Hash(decision_i) → Hash(decision_i+1) → ... → AP2_root_hash
- Public key: Ed25519 public key for verification

Example AP2 entry:
```json
{
  "sequence": 1,
  "timestamp": "2027-05-15T14:32:18Z",
  "pilot": "hotel_credit_scoring",
  "decision": "ESCALATE",
  "policy_evaluation": "{ L1: PASS, L2: score=0.78, L3: REQUIRE_HUMAN_REVIEW }",
  "human_reviewer": "alice@hotel-credit.com",
  "human_decision": "APPROVED",
  "override_reason": "guest had valid external credit reference",
  "previous_hash": "abc123...",
  "this_hash": "def456...",
  "signature": "ed25519_sig_xyz789..."
}
```

## Compliance Checklist Integration

The `compliance_checklist` section tracks regulatory dependencies:
- **Article 50:** Technical documentation status (Sep 16 submission)
- **Article 13:** Transparency + feedback loop (ongoing through May 2027)
- **Article 6:** Module H conformity assessment (third-party audit in parallel)
- **GDPR:** Data subject rights implementation (verified per pilot)

Update status weekly:
```
Week 1: most = PENDING
Week 4: Article 50 → IN PROGRESS (technical doc drafted)
Week 8: Article 13 → IN PROGRESS (L1-L8 layers functional)
Week 11: Article 6 → PENDING (awaiting third-party auditor assignment)
Week 12: All → COMPLETE or PENDING (with clear remediation path)
```

## Export Verification

After PDF + KMS signing, verify:
1. PDF renders correctly (open in Acrobat, verify all 9 sections present)
2. QR code signature page scans and decodes correctly
3. Ed25519 signature verifies against public key in AP2 ledger:
   ```
   ed25519_verify(
     message=json_digest,
     signature=metadata.kms_signature,
     public_key=ap2_ledger.smaos_public_key
   )
   ```
4. Timestamp in QR code matches KARP submission date (Sep 16-22, 2026)

## Archival Instructions

After successful KARP submission:
1. Store signed PDF in immutable repository (git-lfs or archive storage)
2. Commit proof artifacts with signed tag:
   ```
   git tag -s v1.0-annex-iv -m "SMAOS Annex IV dossier, KARP submission complete"
   ```
3. Notify KARP of archival URL (for public reference)
4. Retain for minimum 10 years (regulatory requirement)
