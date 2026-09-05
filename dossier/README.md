# SMAOS Annex IV Regulatory Dossier

## Overview

This directory contains the complete EU AI Act Annex IV technical dossier for SMAOS v1.0 (Sovereign Multi-Agent Operations System). The dossier documents the compliance measures, testing results, human oversight mechanisms, and proof artifacts required for high-risk AI system approval.

## Deliverable Status

| Item | Status | Target Date |
|------|--------|-------------|
| Dossier Structure (9 sections) | COMPLETE | May 31, 2027 |
| Pilot Execution Data | PENDING | May 31, 2027 |
| RAGAS 87%+ Accuracy | PENDING | May 31, 2027 |
| 7 Proof Artifacts | PENDING | May 31, 2027 |
| PDF + KMS Signature | PENDING | May 31, 2027 |
| KARP Submission | PENDING | Sep 16-22, 2026 initial, May 31, 2027 final |

## Files in This Directory

### Core Documents

1. **annex_iv_structure.json** (9.5 KB)
   - Complete JSON template for all 9 regulatory sections
   - Ready to populate with Phase 1 execution data
   - Includes metadata for KMS signing and PDF export
   - Regulatory fields:
     - Section 1: System Identification (8-layer harness)
     - Section 2: Intended Use (3 pilots: hotel, glass, school)
     - Section 3: Risk Classification (Annex III mapping)
     - Section 4: Compliance Measures (Article 50/13/6)
     - Section 5: Testing & Validation (129 tests, 87%+ RAGAS)
     - Section 6: Human Oversight (LangGraph checkpoints)
     - Section 7: Data Handling (pgvector, GDPR)
     - Section 8: Incident Reporting (KARP contact)
     - Section 9: Documentation Trail (7 proof artifacts)

2. **ANNEX_IV_POPULATION_GUIDE.md** (5.2 KB)
   - Step-by-step instructions for populating the dossier
   - Timeline for each section (Weeks 1-12)
   - Export workflow (JSON → PDF → KMS signature)
   - Pilot data integration points
   - Proof artifacts checklist
   - Compliance verification steps

3. **pilot_data_templates.json** (6.8 KB)
   - Template JSON files for real pilot execution data
   - 6 mandatory data files:
     - `ragas_baseline.json` (RAGAS evaluation results)
     - `test_results.json` (cargo test suite results)
     - `hotel_credit_test_results.json` (pilot 1 metrics)
     - `glass_safety_test_results.json` (pilot 2 metrics)
     - `school_access_test_results.json` (pilot 3 metrics)
     - `pgvector_benchmark.json` (database performance)
   - 2 optional files:
     - `compliance_status.json` (Article tracking)
     - `incident_log.json` (if any incidents occurred)
   - File locations and integration instructions

4. **populate_annex_iv.sh** (executable script, 2.1 KB)
   - Bash script to merge pilot data into dossier
   - Automatically updates Section 5, 7, 9 with real results
   - Usage: `./populate_annex_iv.sh pilots/ annex_iv_structure.json`
   - Sets `pdf_export_ready=true` when complete

## Regulatory Context

### EU AI Act Compliance

**System Classification:** Annex III High-Risk (Article 6)
- Biometric identification (school access)
- Employment/educational decisions (hotel + school)
- Safety-critical process control (glass manufacturing)

**Conformity Assessment Module:** H (full quality assurance + third-party audit)

**Regulatory Requirements:**
- Article 50: Technical documentation + notification
- Article 13: Transparency & feedback loops
- Article 6: Conformity assessment procedure
- Article 22: Human involvement in decisions
- GDPR Articles 15-20: Data subject rights

### Submission Timeline

| Date | Milestone | Responsible |
|------|-----------|-------------|
| Aug 25, 2026 | Dossier structure created | Engineers |
| Sep 1, 2026 | Phase 1 execution starts | Team |
| Sep 16-22, 2026 | Initial KARP submission (preliminary) | Romana Cernikova |
| May 31, 2027 | Phase 1 completion + final dossier | Team |
| May 31, 2027 | Final KARP submission with proofs | Romana Cernikova |
| Jun 2027 (est.) | Third-party auditor certification | EU notified body |
| Aug 2, 2028 | Annex I compliance deadline (glass/auto) | Governance |

## How to Use This Directory

### Phase 1 Execution (Weeks 1-12)

**Week 1-2: Section 1 & 2**
- Confirm system architecture (8 layers, 1500+ lines)
- Define 3 pilot use cases and success metrics

**Week 3-4: Section 3, 4, 8**
- Complete risk classification per pilot
- Map Article 50/13/6 compliance requirements
- Define incident reporting policy (KARP contact)

**Week 5-8: Section 5**
- Execute 129 tests (cargo test)
- Collect RAGAS baseline (50-question golden set)
- Populate hotel/glass/school pilot test results

**Week 6-8: Section 7**
- Verify pgvector <100ms latency
- Audit GDPR Article 15-20 implementation
- Collect encryption key management records

**Week 9-10: Section 6**
- Capture LangGraph checkpoint logs (3 nodes)
- Verify escalation SLAs per pilot
- Log human override reasons

**Week 11-12: Section 9**
- Gather 7 proof artifacts (CanIRun, FreeToken, Is Agentic, agentacct, unlazy, RAGAS, AP2 ledger)
- Sign all commits to main harness with Ed25519
- Run population script: `./populate_annex_iv.sh pilots/`

### PDF Export & KMS Signing (Week 12)

1. **Validate JSON:**
   ```bash
   jq . annex_iv_structure.json > /dev/null
   ```

2. **Generate PDF:**
   ```bash
   python3 json_to_pdf.py annex_iv_structure.json > ANNEX-IV-SMAOS-v1.0.pdf
   ```

3. **Sign with KMS:**
   ```bash
   kms_sign_annex_iv.sh annex_iv_structure.json
   # Outputs: updated JSON + QR code signature page
   ```

4. **Submit to KARP:**
   - Recipient: romana.cernikova@karp-kv.cz
   - Attachments: PDF + JSON + proof_artifacts/ folder
   - Subject: "SMAOS v1.0 Annex IV Technical Dossier — KARP Final Submission"

## Quality Gates (Before Export)

- [ ] All 129 tests passing (`cargo test`)
- [ ] RAGAS accuracy ≥87% on 50-question golden set
- [ ] pgvector query latency <100ms
- [ ] 0 critical static analysis warnings (cargo clippy)
- [ ] Defect rate <0.1% per 100 lines
- [ ] All 7 proof artifacts present and verified
- [ ] Git commits signed with Ed25519
- [ ] No "TBD" fields in dossier (except optional sections)
- [ ] AP2 ledger contains ≥1000 decision records
- [ ] Incident log filed (if any incidents >MEDIUM severity)

## Critical References

### SMAOS Architecture (8 Layers)

1. **L1 Reasoning** — Policy routing (Claude SDK)
2. **L2 Knowledge** — Semantic search (pgvector + BM25)
3. **L3 Permit Gates** — Tool registry + enforcement
4. **L4 Orchestration** — LangGraph checkpoints (3 nodes)
5. **L5 Communication** — MCP servers (4 implementations)
6. **L6 Infrastructure** — FreeToken serve validation
7. **L8 Proof** — agentacct + unlazy + AP2 ledger + KMS
8. **L7 RAGAS** — Golden set evaluation (87%+ target)

### Three Pilots

| Pilot | Use Case | Risk Category | Decision Type | SLA |
|-------|----------|---------------|---------------|-----|
| Hotel Credit | Guest creditworthiness | Annex III (financial) | Auto-approve + escalation | 2 hours |
| Glass Safety | Defect detection | Annex III (safety) | Anomaly escalation | 5 minutes |
| School Access | Identity + enrollment | Annex III (biometric+edu) | 100% human review | 15 minutes |

### 7 Proof Artifacts (Regulatory Defense)

1. **CanIRun.ai Integration** — Hardware capability proof
2. **FreeToken Benchmark** — Cost model validation
3. **Is Agentic A+ Report** — Agent criteria verification (third-party)
4. **agentacct** — Decision cost accounting ledger
5. **unlazy** — Lazy evaluation detector (all rules eager)
6. **RAGAS Baseline Report** — 87%+ accuracy golden set
7. **AP2 Immutable Ledger** — 1000+ signed decisions (Ed25519)

## Tools & Dependencies

### For Population
- `jq` (JSON validation)
- `bash` (population script)
- Pilot test execution results (JSON format)

### For Export
- `python3` (PDF generation, reportlab or similar)
- KMS system (Ed25519 signing, Anthropic KMS or HSM)
- `git` (commit signing verification)

### For Submission
- Email client (to romana.cernikova@karp-kv.cz)
- PDF reader (verify QR code signature page)
- File archival system (10-year retention)

## Frequently Asked Questions

**Q: When does pilot data get added?**
A: Progressively during Phase 1 execution (Weeks 5-12). Use `pilot_data_templates.json` as guide.

**Q: What if a test fails or RAGAS accuracy is <87%?**
A: Log issue in `section_5_testing_validation.validation_methodology`. Remediate before KMS signing. Update AP2 ledger with root cause analysis.

**Q: Can the dossier be revised after KARP submission?**
A: Yes. Create versioned updates (v1.1, v1.2, etc.). Submit revised JSON + incident report to romana.cernikova@karp-kv.cz.

**Q: How is data security handled during export?**
A: JSON encrypted during transmission. KMS signature anchors to immutable AP2 ledger. Public key in git for verification.

**Q: What happens if Ed25519 key rotation occurs?**
A: Old signature remains valid. New signature on updated dossier uses new key version. Both versions retained in AP2 ledger.

## Contact

- **KARP Submission:** romana.cernikova@karp-kv.cz
- **Phase 1 Owner:** SMAOS Engineering Team
- **Regulatory Reviewer:** Governance / Compliance Officer

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-25 | Initial dossier structure + templates + population script |
| TBD | 2027-05-15 | Final populated dossier (post-Phase 1 execution) |

---

**Last Updated:** 2026-08-25
**Delivery Target:** 2027-05-31
**Regulatory Jurisdiction:** EU AI Act (Annex III, Article 6)
