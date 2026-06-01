# Israel Trip Execution Checklist — June 2–5, 2026
**Mission:** Lock patent priority dates (June 2) → Demo + secure Tnufa + Series A prep (June 3–5)  
**Status:** Ready for deployment  
**Owner:** SMAOS Founding Team

---

## PRE-TRIP (May 29 — June 1)

### Legal & IP ✅
- [ ] Encrypt patent claims (GPG symmetric AES256)
- [ ] Send to Zysman Law via ProtonMail + Signal
- [ ] Receive confirmation (target: <4 hrs)
- [ ] Prepare USPTO filing (June 2, 10:00 UTC)
- [ ] Prepare ILPO filing (June 2, 14:00 UTC)
- [ ] Print provisional certificates (proof of filing)

### Materials ✅
- [ ] Print Tnufa Prospectus (10 copies)
- [ ] Print Israel Demo Brief (5 copies)
- [ ] Print Series A Dual-Deck summary (investor list)
- [ ] Download Prague PoC backup video (Tnufa demo fallback)
- [ ] Prepare architecture spec + covenant legal framework

### Hardware ✅
- [ ] Mac Studio 128GB ready (packed, charged)
- [ ] Rapid-MLX binaries pre-loaded
- [ ] Demo dataset (drone video, tactical scenario) cached locally
- [ ] Power adapter + international outlets
- [ ] USB-C cable (backup, just in case)

### Logistics ✅
- [ ] Flight booked (June 2 departure)
- [ ] Hotel (Tel Aviv June 2–3, Jerusalem June 4–5)
- [ ] Transportation (Tel Aviv ↔ Jerusalem)
- [ ] Calendar blocks: IDM meeting (June 3), Tnufa (June 4–5)
- [ ] Contact list (IDM program manager, Tnufa point of contact)

### Communication ✅
- [ ] Phone: Test international roaming (or local SIM)
- [ ] Email: Filter setup (mark Tnufa + IDM as VIP)
- [ ] Signal: Confirm counsel number (Zysman Law)
- [ ] ProtonMail: Backup encrypted email if needed

---

## JUNE 2 (PATENT FILING DAY)

### Morning (8:00–10:00 UTC)

- [ ] **8:00 UTC:** Confirm GPG encryption complete
- [ ] **8:30 UTC:** Final review of PROVISIONAL_CLAIMS_FINAL_v1.0.md
- [ ] **9:00 UTC:** Send to Zysman Law via ProtonMail
- [ ] **9:30 UTC:** Send passphrase via Signal (separate channel)
- [ ] **9:45 UTC:** Confirm receipt from counsel

### Late Morning (10:00–12:00 UTC)

- [ ] **10:00 UTC:** USPTO provisional filing (RCE + Capsule + IVB claims)
  - File online via USPTO PAIR portal
  - Include drawings (Merkle-DAG structure)
  - Mark as "Patent Application Filing"
  - Receive confirmation number + filing date
- [ ] **10:30 UTC:** Screenshot USPTO confirmation (for records)

### Afternoon (14:00–16:00 UTC)

- [ ] **14:00 UTC:** ILPO (Israeli Patent Office) provisional filing
  - File via ILPO online portal (Hebrew + English)
  - Include same claims as USPTO
  - Receive ILPO receipt
- [ ] **14:30 UTC:** Screenshot ILPO confirmation

### End of Day

- [ ] **16:00 UTC:** Log both filings to EXEC_LOG.json (Merkle-rooted)
- [ ] **16:30 UTC:** Email counsel + self: "IP fortress locked. Global PCT priority date secured. Safe to demo."
- [ ] **17:00 UTC:** Depart for Israel (flight departs June 2 evening)

**Outcome:** Both provisionals filed, priority dates locked globally, IP fortress established.

---

## JUNE 3 (IDM BRIEFING, TEL AVIV)

### Morning Prep (9:00–12:00)

- [ ] Hotel check-in (Tel Aviv)
- [ ] Set up demo: Mac Studio + WiFi
- [ ] Test Rapid-MLX performance (should show 57 tokens/sec)
- [ ] Review IDM_DEMO_BRIEF (5 min narrative, 3 innovations, 10 min demo, 5 min ask)

### Afternoon (14:00–17:00)

**Meeting with IDM (Israeli Defense Ministry)**

1. **Opening (5 min):**
   - Introduce SMAOS as sovereign AI OS
   - "We've just filed US + IL provisional patents June 2 (IP protected; safe to demo)"
   - Show three core innovations: RCE, Capsule, IVB

2. **Innovation Deep-Dive (3×5 min = 15 min):**
   - **RCE:** "Every decision is cryptographically signed by a human + fail-closed"
   - **Capsule:** "Complete, immutable Merkle-DAG audit trail"
   - **IVB:** "Self-improving AI, local only, no data exfiltration"

3. **Live Demo (10 min):**
   - Show Prague PoC validation (6/6 air-gap checks ✅)
   - Run RCE example: "Drone analysis → Human approval required"
   - Show Merkle-DAG: "Every decision is cryptographically hashed"
   - Demonstrate replay: "Same execution, 1000x identical output"

4. **Ask (5 min):**
   - Tnufa funding opportunity (€200K–€500K Phase 1)
   - Pilot deployment (1–2 initial projects)
   - Timeline: Phase 1 August 31, pilots September 15

5. **Q&A (remaining time)**

### Evening (17:00+)

- [ ] Debrief: What feedback did IDM give?
- [ ] Note any pilot opportunities (sensor fusion, tactical analysis, logistics)
- [ ] Update Israel brief with intelligence for Tnufa pitch

---

## JUNE 4 (TNUFA DEEP DIVE, JERUSALEM)

### Morning (9:00–12:00)

- [ ] Travel Tel Aviv → Jerusalem
- [ ] Set up demo (new venue, test tech again)
- [ ] Review TNUFA_FUNDING_PROSPECTUS (4 pages, key ask: €200K–€500K)

### Afternoon (14:00–17:00)

**Meeting with Tnufa (Israeli Innovation Authority)**

1. **Opening (5 min):**
   - "SMAOS is sovereign infrastructure for Israeli tech leadership"
   - Show patent certificates (US + IL, filed June 2)
   - Position as dual-HQ strategy: Czech operations, Israeli IP fortress

2. **Strategic Alignment (10 min):**
   - Show how SMAOS aligns with Tnufa's mission (sovereign tech strength)
   - Explain 1%/99% covenant (why it matters for Israeli values)
   - Position Phase 1 as "Israeli innovation proving ground"

3. **Phase 1 Breakdown (15 min):**
   - Wave 1: ReBAC Foundation (weeks 1–2, 12+ tests)
   - Wave 2: AP2 + TemporalGuard + PolicyEngine (weeks 3–4, 45+ tests, parallel 3-agent)
   - Wave 3: Audit + Archive (weeks 5, 10+ tests)
   - Total: 55+ tests, zero warnings, enterprise-ready

4. **Demo (10 min):**
   - Same as IDM (RCE, Capsule, IVB, Prague PoC)
   - Focus on cryptographic auditability (Tnufa cares about compliance)

5. **Ask (5 min):**
   - €200K–€500K for Phase 1 (show budget breakdown)
   - Phase 1 deliverables: 55+ tests, PostgreSQL schema, first pilots
   - Success metrics: KPI dashboard (test pass rate, air-gap isolation, enterprise pilots)

6. **Covenant Alignment (5 min):**
   - Show AP2 ledger: 1% → builders, 99% → beneficiaries
   - "We embed fairness in the code; it's cryptographically enforced"
   - Position as proof SMAOS is ethical from Day 1

7. **Q&A (remaining time)**

### Evening (17:00+)

- [ ] Debrief: Is Tnufa interested? What questions remain?
- [ ] Note timeline for application submission (June 6)
- [ ] Confirm any follow-up materials needed

---

## JUNE 5 (SERIES A PREP, JERUSALEM)

### Morning (9:00–12:00)

- [ ] Final Tnufa meeting or pitch refinement
- [ ] Prepare Series A materials (investor list, contact strategy)
- [ ] Review SERIES_A_DUAL_DECK_STRATEGY (Fortress vs. Platform narrative)

### Afternoon (14:00–17:00)

**Optional:** Meet with potential strategic investors (if connections arranged)

**If no meetings:**
- [ ] Finalize Series A investor list (30 strategic + 50 growth VCs)
- [ ] Prepare investor outreach sequence (starts June 6)

### Evening (17:00+)

- [ ] Pack for return journey (June 5 evening or June 6)
- [ ] Final debrief: What did we learn? What's next?

---

## RETURN TO CZECH REPUBLIC (June 6+)

### Immediate Actions (June 6)

- [ ] **Submit Tnufa application** (formal submission, funding decision expected Aug 1)
- [ ] **Begin Phase 1 Wave 1** (ReBAC Foundation engineering starts)
- [ ] **Begin Series A outreach** (investor pitches, dual-deck deployment)
- [ ] **Log Israel trip results to EXEC_LOG.json** (Merkle-rooted audit trail)

### Week of June 6–13

| Date | Action | Owner | Output |
|------|--------|-------|--------|
| **June 6** | Tnufa application submitted | You | Confirmation email |
| **June 7** | Phase 1 Wave 1 starts (ReBAC) | Engineering team | Test framework setup |
| **June 8–10** | 20 investor pitch outreach | You + investor relations | 5–10 warm intro conversations |
| **June 12** | First tech interview (investor diligence) | CTO | Q&A on architecture |
| **June 13** | Weekly sync: Phase 1 progress + Series A pipeline | Full team | Status dashboard |

### By August 1

- [ ] Phase 1 complete (55+ tests, ready for enterprise)
- [ ] Tnufa decision received (€200K–€500K approved expected)
- [ ] Series A term sheet(s) in hand (€3.5M–€15M range)
- [ ] Enterprise pilots signed (1–2 customers ready to go)

---

## CONTINGENCY PLANS

### If Tnufa Delays
→ **Fallback:** Series A VC sprint accelerates (€3.5M covers Phase 1 + cash runway)

### If IDM Wants Immediate Pilot
→ **Scope:** 4-week minimal pilot (sentiment analysis, offline document classification)  
→ **Revenue:** €50K–€100K (funds partial Phase 1)

### If Demo Tech Fails
→ **Backup:** Prague PoC pre-recorded video (backup-ready on USB)

### If Investor Diligence Stalls
→ **Plan B:** Bridge round (€2M, 12-month runway) while Series A matures

---

## Success Metrics (Post-Israel)

**By August 15, 2026:**
- ✅ Phase 1 complete (55+ tests passing)
- ✅ Tnufa decision received (€200K–€500K approved)
- ✅ Series A term sheet signed (€3.5M–€15M)
- ✅ 1–2 enterprise pilots live
- ✅ Non-provisional patents filed (US + EU + UK)
- ✅ Team hiring plan (CTO, 2–3 engineers)

---

## Document Manifest (Bring & Digital)

### Physical Copies (10 each)
- [ ] TNUFA_FUNDING_PROSPECTUS.md (4 pages)
- [ ] ISRAEL_DEMO_BRIEF.md (3 pages)
- [ ] Patents (US + IL certificates, once filed)

### Digital Copies (on laptop + cloud backup)
- [ ] SERIES_A_DUAL_DECK_STRATEGY.md
- [ ] Prague PoC validation video (backup demo)
- [ ] Architecture spec + covenant legal framework
- [ ] Investor list (Fortress + Platform fund names)

### Post-Trip
- [ ] Scanned IDM meeting notes
- [ ] Scanned Tnufa meeting notes
- [ ] Investor contact database (names, emails, intros)
- [ ] Trip debrief (findings, next steps)

---

**Prepared by:** SMAOS Founding Team  
**Status:** Ready for June 2–5 execution  
**Confidence Level:** 85% (Tnufa + Series A paths validated)
