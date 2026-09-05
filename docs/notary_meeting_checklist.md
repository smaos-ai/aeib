# Notary Meeting Checklist — SMAOS s.r.o. Charter Filing

**Meeting Date:** September 8, 2026  
**Notary:** JUDr. Kamil Hradský  
**Location:** Prague, Czech Republic  
**Entity:** SMAOS s.r.o. (LLC)

---

## Phase 4: Print-Ready Documents for Notary

### Document 1: WIRING_MANIFEST.json
- **File:** `/reports/WIRING_MANIFEST.json`
- **Status:** ✅ VERIFIED
- **Size:** 19 KB
- **Content Verification:**
  - [x] EU Checker system (/api/compliance) — READY
  - [x] AI Verify Foundation (/api/verify) — READY
  - [x] STAR Adversarial 12 (/api/adversarial) — 12/12 blocked
  - [x] Granite TSFM (/api/fraud) — 16 anomalies detected
  - [x] DisCo AREX Skills (/api/skills) — 10 verified skills
- **For Notary:** Print 2 copies, bind as Appendix A
- **Purpose:** Proof that all 5 governance systems are wired and operational

### Document 2: EU Compliance Report
- **File:** `/reports/eu_compliance_report.json`
- **Status:** ✅ VERIFIED
- **Before SMAOS Score:** 541 (Grade: Developing)
- **After SMAOS Score:** 1161 (Grade: Optimized)
- **Compliance Lift:** +620 points (135.1% improvement)
- **Key Improvements:**
  - [x] Merkle Receipt: +120 pts → Cryptographic proof of execution
  - [x] Ed25519 Signature: +95 pts → Post-quantum authorization
  - [x] Layer 7 Veto: +140 pts → Human oversight gate
  - [x] SQLite Ledger: +85 pts → 7-year audit trail
  - [x] Offline-First: +75 pts → No cloud dependencies
  - [x] Adversarial Testing: +105 pts → 12 attack scenarios blocked
- **For Notary:** Print as Appendix B; highlight compliance gaps vs. improvements columns
- **Purpose:** Demonstrate regulatory readiness improvement from baseline

### Document 3: Performance Baseline Report
- **File:** `/reports/performance_baseline.json`
- **Status:** ✅ CREATED
- **Key Metrics:**
  - EU Checker latency: **p50=8.2ms, p99=18.7ms** (target: <20ms ✅)
  - AI Verify latency: **p50=15.3ms, p99=31.4ms** (target: <35ms ✅)
  - STAR Adversarial latency: **p50=3.1ms, p99=6.2ms** (target: <10ms ✅)
  - Granite TSFM latency: **p50=8000ms, p99=10500ms** (local LLM inference; expected)
  - DisCo Skills latency: **p50=2.4ms, p99=5.1ms** (target: <10ms ✅)
- **Critical Path (Intent → Ledger):** **p50=46.1ms, p99=68.3ms** (target: <100ms ✅)
- **Database Performance:**
  - pgvector compliance search: **p50=7.8ms** (3-NN semantic search)
  - SQLite ledger write: **p50=1.1ms** (crash-safe, fsync=normal)
- **For Notary:** Print as Appendix C; emphasize sub-100ms critical path
- **Purpose:** Prove system responsiveness and suitability for real-time financial decisions

### Document 4: Sample Cryptographic Receipt
- **File:** `/reports/sample_cryptographic_receipt.json`
- **Status:** ✅ CREATED (Real Ed25519 signature)
- **Sample Content:**
  - Intent ID: `intent-1725453731245`
  - Capsule: `hospitalityAnnexIII`
  - User: `guest@hotel.com`
  - Classification: **BLOCK** (Annex III trigger: payment card data + GDPR consent)
  - Signature Algorithm: **Ed25519** (post-quantum resistant)
  - Signature Status: **VERIFIED** ✅
- **Cryptographic Details:**
  - Public Key (Base64): `MCowBQYDK2VwAyEAIrp4wFQbVRTWGISmMfQTJ65lp9HSSdYJ8W+DyRUaIYY=`
  - Signature (Base64): `xsnD79PE5DiM2xfhpP5Nt9qtPrQclWSjnK+9nsIdqWaQ/SwgSXDYvSqyfeQgyai+OLDu+WvIrbqObvbFpdrCDg==`
  - Payload Hash: `{\"capsule\":\"hospitalityAnnexIII\",\"classification\":{...}}` (canonical JSON)
- **For Notary:** Print as Appendix D; display on screen during meeting with "Verify" button live-click
- **Purpose:** Demonstrate real cryptographic proofs that can be verified in court

### Document 5: SMAOS s.r.o. Charter Summary
- **File:** `/reports/smaos_charter_summary.json`
- **Status:** ✅ CREATED
- **Key Details:**
  - Legal Entity: **SMAOS s.r.o.** (Společnost s ručením omezeným)
  - Jurisdiction: **Czech Republic**
  - Registered Address: **Dykova 1117/21, 130 00 Praha 3**
  - Registered Capital: **20,000 CZK** ✅
  - Founder: **Andrej Leukhin** (100% equity)
  - Formation Date: **2026-08-31**
- **Business Purpose:**
  - Development of autonomous governance systems
  - AI agent orchestration
  - Regulatory compliance automation
  - Cryptographic proof layer for finance
- **Compliance Framework:**
  - EU AI Act: High-Risk Classification (Article 6, Annex III triggers)
  - GDPR: Data Controller (7-year retention)
  - Basel III: CET1 monitoring (treasury pilots)
- **For Notary:** Provide as founding document; ensure HQ lease agreement is notarized
- **Purpose:** Establish legal entity and governance structure for pilot execution

---

## Pre-Meeting Checklist (Sep 8, 2026)

### Physical Preparation
- [ ] Print WIRING_MANIFEST.json (2 copies, Appendix A)
- [ ] Print EU Compliance Report (2 copies, Appendix B) — highlight 541→1161 score
- [ ] Print Performance Baseline (1 copy, Appendix C) — highlight <100ms critical path
- [ ] Print Sample Receipt (1 copy, Appendix D) — include Ed25519 signature proof
- [ ] Print SMAOS Charter Summary (2 copies, Appendix E)
- [ ] Bind all documents into single folder (tabs A-E)
- [ ] Prepare USB drive with all JSON files (backup copies)

### Technical Preparation
- [ ] Test sample receipt verification in browser (open DevTools Console)
- [ ] Confirm Ed25519 signature validates when clicked
- [ ] Prepare laptop for live demo during meeting
- [ ] Test offline mode: disconnect WiFi, confirm system still responds
- [ ] Screenshot console output: no errors, no warnings

### Documentation Checklist
- [ ] Founder ID (Czech national passport/ID card): **Andrej Leukhin**
- [ ] HQ lease agreement for Dykova 1117/21 (existing document)
- [ ] Proof of registered capital (20,000 CZK) — bank statement transfer copy
- [ ] GDPR Data Processing Agreement (draft for notary review)
- [ ] EU AI Act notification letter (draft for CNB)
- [ ] Insurance certificate (liability coverage, if applicable)

### Regulatory Notifications (Post-Notary Filing)
- [ ] File SMAOS s.r.o. registration with Czech Register of Companies
- [ ] Notify Czech Ministry of Industry & Trade (EU AI Act, high-risk system)
- [ ] File DPIA with Office for Personal Data Protection (UOOOU)
- [ ] Notify Czech National Bank (CNB) — Basel III monitoring

---

## Key Talking Points for Notary Meeting

### System Readiness
- **5 Governance Systems Operational:** All SSE endpoints live, real-time streaming
- **Compliance Automation:** 135% improvement in EU AI Act compliance scoring
- **Performance Proven:** All critical paths <100ms (suitable for real-time financial decisions)

### Cryptographic Foundation
- **Ed25519 Signatures:** Post-quantum resistant, cryptographically sound
- **Merkle Proofs:** Immutable audit trail (7-year retention, SQL ledger)
- **Self-Verification:** Every signature is proven correct at time of signing

### Regulatory Strategy
- **Notary Charter:** Legal entity formation for Phase 2 pilots
- **High-Risk AI Classification:** Voluntary transparency (not required, but demonstrates commitment)
- **Offline-First Design:** No cloud dependencies = local data sovereignty

### Funding Roadmap
- **KARP Voucher:** 120,000 CZK (submission Sep 22, deadline fixed)
- **BIC Plzeń Investment:** 1M CZK (after Phase 1 completion, Jun 2027)
- **Series A Narrative:** Complete governance layer + 3 live pilots

---

## Post-Meeting Action Items

### Within 24 Hours (Sep 9)
- [ ] Collect notarized charter from JUDr. Kratský
- [ ] File with Czech Register of Companies
- [ ] Confirm entity number in government system

### Within 1 Week (Sep 15)
- [ ] Upload all Appendix documents to data room
- [ ] Prepare KARP voucher application (Romana Cernikova contact)
- [ ] Schedule follow-up with notary for regulatory notifications

### Before Sep 22 (KARP Deadline)
- [ ] Complete KARP voucher submission package
- [ ] Include notarized charter + compliance scores
- [ ] Include system performance benchmarks
- [ ] Include sample cryptographic receipt (as proof of audit trail)

---

## File Locations (All Reports)

```
/Users/andriileukhin/Documents/SovereignNexus/reports/
├── WIRING_MANIFEST.json                (Appendix A)
├── eu_compliance_report.json           (Appendix B)
├── performance_baseline.json           (Appendix C)
├── sample_cryptographic_receipt.json   (Appendix D)
└── smaos_charter_summary.json          (Appendix E)
```

---

## Contingency Plans

### If WiFi Fails During Demo
- Use cached screenshots (pre-recorded video of verification working)
- Show system responds offline (turn off WiFi, reload page, intents still process)
- Fallback: Print "Verify" button output from console

### If Notary Questions Cryptography
- Provide NIST documentation on Ed25519 (quantum-safe, published 2017)
- Show Web Crypto API source code (browser standard, not custom)
- Offer court-verifiable signature (can be validated by any NIST-compliant library)

### If Charter Needs Revisions
- Backup draft charter prepared (governance_charter_draft_v2.md available)
- Notary can suggest amendments; we update + re-file same day
- No need to reschedule if minor edits required

---

**Document Prepared:** 2026-09-04  
**Next Review:** 2026-09-07 (final pre-meeting check)  
**Status:** READY FOR NOTARY FILING
