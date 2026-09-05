# KARP Submission: Pilot Specifications Overview
**Phase 1 Stream F: Pilot Specifications (Sep 8-15)**  
**Prepared:** Aug 31, 2026  
**Submission Deadline:** Sep 16-22, 2026  

---

## Executive Summary

Three fully-specified, Annex III/I-compliant pilot use cases demonstrate SMAOS (Sovereign Machine-Agent Operating System) across 8 layers. All pilots integrate natural-language governance, immutable proof trails (AP2 ledger), and regulatory compliance evidence.

---

## Pilot 1: Hotel Credit Scoring
| Attribute | Value |
|-----------|-------|
| **Regulatory Class** | Article 6(2) High-Risk (Essential Service: Credit Access) |
| **Annex** | Annex III (Section 5: Finance & Credit) |
| **Deadline** | Dec 2, 2027 |
| **SMAOS Layers** | L1 (Policy) → L2 (Retrieval) → L3 (Gates) → L4 (Orchestration) → L6 (FreeToken) → L8 (Proof) → L7 (RAGAS) |
| **Use Case** | Real-time pre-authorization for hotel guest credit applications (100+ properties, 500 applications/day) |
| **Success Metrics** | <15s latency, 87%+ RAGAS accuracy, 99.9% uptime, <1.25x disparate impact |
| **Failure Escalation** | All uncertain decisions → human credit analyst |
| **Proof Artifact** | AP2 ledger (50,000+ decisions by Dec 2), RAGAS baseline (50-question set), fairness audit |
| **Integration** | Hotel front-desk workflow; decision impacts room access + payment terms |

---

## Pilot 2: Glass Factory CAD Safety Review
| Attribute | Value |
|-----------|-------|
| **Regulatory Class** | Article 6(1) Regulated Product (Safety-Critical Component) |
| **Annex** | Annex I (Safety Component: Tempered Glass) |
| **Deadline** | Aug 2, 2028 |
| **SMAOS Layers** | L1→L2→L3→L4→L5 (Communication) →L6→L8→L7 (Full stack, 8 layers) |
| **Use Case** | AI pre-screen of CAD designs for automotive/architectural glass (100K units/month, 200 designs/month) |
| **Success Metrics** | <1 false negative per 10K designs (0.01%), <10% false positive, 95%+ precision, 99%+ recall, 90%+ RAGAS |
| **Failure Escalation** | Risk score <70% confidence → human safety engineer (2-hour review) |
| **Proof Artifact** | AP2 ledger (2,400+ reviews by Aug 2028), RAGAS baseline (100-design golden set), zero false-negative production failures |
| **Integration** | Pre-production design workflow; final approval gate before manufacturing |

---

## Pilot 3: School Access Control (Biometric + Attendance)
| Attribute | Value |
|-----------|-------|
| **Regulatory Class** | Article 6(2) High-Risk (Essential Service: Education + Biometric) |
| **Annex** | Annex III (Section 2: Education & Access Control) |
| **Deadline** | Dec 2, 2027 |
| **SMAOS Layers** | L1→L2→L3→L4→L5→L6→L8→L7 + **Temporal Durability** (network-resilient 48-hour workflow) |
| **Use Case** | Verify student enrollment + 48-hour attendance before granting building access (500 students, 2000 attempts/day) |
| **Success Metrics** | 98%+ biometric accuracy, <2% false reject, <0.5% false accept, <5s latency, 99.9% uptime, survive 24-hour network outage |
| **Failure Escalation** | Biometric confidence 70-90% → on-site admin; attendance <80% → allow access + notify admin; network down → Temporal checkpoint |
| **Proof Artifact** | AP2 ledger (250,000+ accesses by Dec 2), RAGAS baseline (100 students + 20 impersonation tests), fairness audit, GDPR DPIA |
| **Integration** | School entrance biometric scanner; Temporal cache survives network failure (local SQLite + sync on recovery) |

---

## Cross-Pilot Patterns

### Regulatory Alignment
- **Hotel (Annex III-5):** Dec 2, 2027 deadline (7 months post-Phase-1-close)
- **Glass (Annex I):** Aug 2, 2028 deadline (14 months post-Phase-1-close)
- **School (Annex III-2):** Dec 2, 2027 deadline (7 months post-Phase-1-close)

All three pilots integrate with Phase 1 KARP submission (Sep 16-22, 2026):
- Specifications complete (3 × 9-section dossier template)
- Proof artifacts accumulating (AP2 ledger as daily journal through May 31, 2027)
- RAGAS baseline targets documented (hotel 87%+, glass 90%+, school 98%+ biometric)
- Regulatory dossiers auto-generated from AP2 ledger by Dec 2, 2027 and Aug 2, 2028

### SMAOS Layer Coverage
| Layer | Hotel | Glass | School |
|-------|-------|-------|--------|
| **L1: Policy** | ✓ (OFAC, sanctions) | ✓ (material grade, baseline specs) | ✓ (enrollment, attendance) |
| **L2: Knowledge** | ✓ (credit history) | ✓ (CAD similarity, failures) | ✓ (biometric, enrollment, attendance) |
| **L3: Gates** | ✓ (fairness enforcement) | ✓ (safety rules) | ✓ (biometric threshold, attendance) |
| **L4: Orchestration** | ✓ | ✓ | ✓ |
| **L5: Communication** | - | ✓ (CAD output) | ✓ (access decision) |
| **L6: FreeToken** | ✓ | ✓ | ✓ |
| **L7: RAGAS** | ✓ | ✓ | ✓ |
| **L8: Proof (AP2)** | ✓ | ✓ | ✓ |
| **Temporal Durability** | - | - | ✓ (48-hour network outage) |

### Proof Metrics (All Pilots)
Each pilot generates immutable proof via AP2 ledger:
- **Completeness:** 100% decision logging (hotel: 50K, glass: 2.4K, school: 250K decisions)
- **RAGAS Baseline:** Minimum 87%+ accuracy on golden set
- **Fairness Audit:** Monthly disparate impact analysis (<1.25x delta for protected classes)
- **Temporal Durability (School only):** 24-hour network outage survival + checkpoint recovery

---

## KARP Submission Artifacts (by Sep 16-22)

1. **Pilot Specifications** (3 documents, 2-3 pages each)
   - PILOT_1_HOTEL.md (9 sections: risk, narrative, metrics, layers, deadline, failures, proof, integration, long-tail)
   - PILOT_2_GLASS.md (10 sections: + post-deployment false negative scenario)
   - PILOT_3_SCHOOL.md (11 sections: + Temporal durability, GDPR, deepfake defense)

2. **Pilot Specs Summary** (this document, 1 page overview)

3. **Integration Checklist** (Sep 8-15 execution)
   - [ ] All 3 specs written & reviewed
   - [ ] Regulatory deadlines mapped to Phase 1 timeline
   - [ ] SMAOS layer coverage verified (L1-L8 across all pilots)
   - [ ] Success metrics measurable & baselined
   - [ ] AP2 ledger schema designed (ready for May 31 integration)
   - [ ] Git commit with evidence links

---

## Success Criteria (May 31, 2027 Phase 1 Close)

- ✅ 3 fully-specified pilots, each with 2-3 pages + 9+ sections
- ✅ 50K+ hotel decisions logged in AP2 (87%+ RAGAS baseline)
- ✅ 2.4K+ glass CAD reviews logged in AP2 (90%+ RAGAS, 0 false negatives)
- ✅ 250K+ school access attempts logged in AP2 (98%+ biometric, survived 24h network test)
- ✅ Fairness audits show <1.25x disparate impact for all protected classes
- ✅ Temporal durability verified on school pilot (network outage recovery)
- ✅ 3 auto-generated Annex III/I compliance dossiers ready (Dec 2, 2027 / Aug 2, 2028)
- ✅ Pilot specs submitted to KARP (Sep 16-22, 2026) as evidence of Phase 1 progress

---

## Next Steps (Immediate)

1. **Stream F Execution (Aug 31 - Sep 8):**
   - All 3 specifications written (this artifact completed)
   - Git commit with evidence links

2. **KARP Submission (Sep 16-22):**
   - Package: Pilot specs + summary + 1-page Czech project description
   - Recipient: Romana Cernikova (romana.cernikova@karp-kv.cz)
   - Budget: 120K CZK (60k engineer + 8k hardware + 12k testing + 40k contingency)
   - Timeline: May 31, 2027 delivery (9 months from submission)

3. **Phase 1 Integration (Sep 1 - May 31):**
   - Parallel tracks A-D execute simultaneously
   - Pilot execution logs accumulate in AP2 ledger (weekly dumps)
   - RAGAS baselines tracked monthly (hotel 87%+, glass 90%+, school 98%+)
   - Fairness audits run monthly (disparate impact analysis)

4. **Annex III/I Compliance (Dec 2, 2027 / Aug 2, 2028):**
   - Compliance dossiers auto-generated from AP2 ledger
   - Submit to ECB (hotel) and NANDO (glass)
   - School GDPR DPIA submitted to DPA (Dec 1, 2027)

---

## Document References

- `/PILOT_1_HOTEL.md` — Hotel credit scoring (9 sections)
- `/PILOT_2_GLASS.md` — Glass factory CAD safety (10 sections)
- `/PILOT_3_SCHOOL.md` — School access control (11 sections)
- `/KARP_SUBMISSION.md` — 1-page Czech project description (for Romana Cernikova)
- `/PHASE1_STATUS.md` — Weekly progress tracker (A-D tracks, completion %)
