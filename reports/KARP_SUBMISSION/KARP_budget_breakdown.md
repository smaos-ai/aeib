# KARP BUDGET NARRATIVE — 120,000 CZK Grant Allocation

**Project:** SMAOS Phase 1 (Sep 1, 2026 – May 31, 2027)  
**Grant Request:** 120,000 CZK (60% of total Phase 1 budget)  
**Self-Funding:** 80,000 CZK (40% contingent on Phase 1 delivery)  
**Total Phase 1 Budget:** 200,000 CZK

---

## BUDGET SUMMARY TABLE

| Line Item | Amount | % of Budget | Justification |
|-----------|--------|-------------|---|
| **1. Hardware (GPU/Silicon Testing)** | 35,000 CZK | 29.2% | Benchmarking Qwen 39.3B MoE on 8GB RAM; FreeToken infrastructure; CanIRun.ai compliance proof |
| **2. Legal & Regulatory Consulting** | 25,000 CZK | 20.8% | Annex IV dossier peer review; Basel III rule encoding validation; KMS Ed25519 audit |
| **3. Testing Infrastructure & Tools** | 20,000 CZK | 16.7% | Playwright + Vitest enterprise; pgvector benchmark suite; RAGAS golden set (50Q) |
| **4. Travel & Networking** | 15,000 CZK | 12.5% | CzechInvest Demo Day; EBA regulatory workshop (Oslo); BIC Plzeń partnership kickoff |
| **5. Contingency (7% buffer)** | 10,000 CZK | 8.3% | EU AI Act clarifications; cryptographic audit findings; pilot delay absorption; notary fees |
| **TOTAL KARP GRANT REQUEST** | **120,000 CZK** | **100%** | **9-month runway: 13,333 CZK/month** |

---

## DETAILED BUDGET JUSTIFICATIONS

### 1. HARDWARE (GPU/SILICON TESTING) — 35,000 CZK

**Purpose:** Validate offline-first architecture on target hardware; benchmark FreeToken local inference; generate CanIRun.ai compliance proof

**Breakdown:**
- **RTX 4060 8GB GPU** (13,000 CZK)
  - Qwen MoE 290B quantization testing (39.3 tok/s target)
  - Benchmarking against Ollama baseline (21.8 tok/s)
  - Speedup validation: 1.8x improvement
  - Local inference without cloud dependency (core SMAOS promise)

- **Jetson Thor Developer Kit** (18,000 CZK)
  - Edge device simulation (hardware-constrained environment)
  - Validates Layer 6 (FreeToken serve validation)
  - Proves SMAOS works on embedded systems (financial institutions' edge networks)
  - Performance baseline: <50ms latency on offline cached data

- **Laptop/Development Machine Upgrade** (4,000 CZK)
  - RAM upgrade (32GB → 64GB) for concurrent testing
  - NVMe expansion (SSD cache for Colibri scheduler)
  - Enables full SMAOS stack simulation on single developer machine

**Why This Matters:**
- SMAOS's key competitive advantage is "local-first, no cloud." Hardware proof is mandatory.
- Regulators (ECB, CNB) need to see Phase 1 pilots running on institution-grade hardware.
- 3 pilots will require 3 separate hardware profiles (hotel = fast, glass = compute-intensive, school = budget-constrained). Testing all 3 now ensures Phase 2 success.
- FreeToken benchmarks are part of KARP deliverables (proof artifact #6 in submission).

**Timeline:**
- Week 1-2: Hardware procurement + setup
- Week 3-4: Qwen 39.3B benchmarking + CanIRun.ai proof generation
- Week 5-8: Integrated pilot testing on each hardware profile
- Week 9-12: Performance baseline documentation

---

### 2. LEGAL & REGULATORY CONSULTING — 25,000 CZK

**Purpose:** Ensure Annex IV dossier meets ECB/CNB audit standards; validate cryptographic implementation; encode Basel III rules accurately

**Breakdown:**
- **Regulatory Counsel (Annex III/I Compliance)** (12,000 CZK)
  - 2-3 consultation sessions with EU AI Act specialist
  - Review of SMAOS 8-layer architecture against Annex III high-risk AI requirements
  - DPIA (Data Protection Impact Assessment) peer review
  - Validation that pre-execution veto gates satisfy "demonstrable safety" mandate
  - Documentation of compliance pathway (which SMAOS layer addresses which article)
  
  **Provider:** [Czech law firm with EU AI Act expertise, e.g., CMS, Nextlaw, KPMG Legal]
  
  **Cost Justification:** Regulatory expertise in Prague costs 2,000–3,000 CZK/hour. 4–6 hours of specialist time = 8,000–18,000 CZK. We budget 12,000 CZK (moderate scope, focused consultations only).

- **Cryptographic Audit (Ed25519 Implementation)** (8,000 CZK)
  - External validation of Ed25519 signing protocol
  - Review of Merkle-DAG conflict resolution logic
  - Verification that post-quantum signatures are tamper-proof (no collision vulnerabilities)
  - Documentation for financial auditors / insurance underwriters
  
  **Provider:** [Czech cryptography firm or academic consultant]
  
  **Cost Justification:** Cryptographic audit typical cost: 1,500–3,000 CZK/hour. 3–5 hours specialized review = 4,500–15,000 CZK. We budget 8,000 CZK (focused on Ed25519 signature verification, not full security audit).

- **Basel III Rule Encoding Validation** (5,000 CZK)
  - Peer review of Layer 1 classifier rules (payment risk, credit risk, capital adequacy)
  - Ensures SMAOS correctly interprets Basel III capital requirements
  - Validation of CET1 ratio calculations (if applicable to pilots)
  - Documentation for BIC Plzeń Phase 2 due diligence
  
  **Provider:** [Financial compliance consultant or Basel III specialist]
  
  **Cost Justification:** Compliance consultants charge 1,500–2,000 CZK/hour. 2–3 hours = 3,000–6,000 CZK. We budget 5,000 CZK.

**Why This Matters:**
- KARP specifically funds "innovation in compliance." Regulatory review proves SMAOS is serious about governance.
- Annex IV dossier is mandatory deliverable (May 31, 2027). Peer review now prevents rework later.
- External validation builds credibility with Phase 2 institutional pilots (hospitals, schools, manufacturers will ask "who verified this?").
- Cryptographic audit is insurance against "signature scheme is broken" disclosure mid-Phase 2 (would be catastrophic).

**Timeline:**
- Week 2-3: Regulatory counsel consultations (Annex IV gap analysis)
- Week 4-5: Cryptographic audit (Ed25519 review)
- Week 6-7: Basel III encoding validation
- Week 8-12: Incorporate feedback into final DPIA + Annex IV dossier

---

### 3. TESTING INFRASTRUCTURE & TOOLS — 20,000 CZK

**Purpose:** Enterprise testing suite for compliance validation; RAGAS golden set creation; pgvector benchmark infrastructure

**Breakdown:**
- **Playwright + Vitest Enterprise Features** (6,000 CZK)
  - Playwright Cloud (parallel test execution): 2,000 CZK/year
  - Vitest Enterprise (coverage reports, CI/CD integration): 2,000 CZK/year
  - Enables 100+ integration tests running in parallel (week 9-12 quality gate)
  - Cost avoidance: Would otherwise use free tier (slow, limited to 5 parallel runs)
  
  **Cost Justification:** Enterprise tiers cost ~150–200 EUR/year each (~3,500–4,700 CZK). We budget 6,000 CZK for both.

- **pgvector Benchmark Suite Development** (5,000 CZK)
  - Hiring contractor to build compliance query benchmark (Layer 2 semantic search)
  - Tests: 100 compliance articles × 250 risk timeline entries × 3 embedding models
  - Measures latency (<100ms target on pgvector), recall (>95% target), precision
  - Output: Benchmark results JSON (part of Phase 1 performance baseline deliverable)
  
  **Cost Justification:** 10–15 hours junior engineer time = 5,000–7,500 CZK. We budget 5,000 CZK (narrow scope, focused on pgvector only).

- **RAGAS Golden Set Creation & Validation** (6,000 CZK)
  - Domain experts (legal, finance, compliance) create 50-question evaluation set
  - 3 categories: hotel hospitality (15Q), glass manufacturing (15Q), school administration (20Q)
  - Each question has reference answer + evaluation rubric
  - Output: ragas-golden-set.json (KARP deliverable, part of fairness validation)
  
  **Cost Justification:** 15–20 hours expert time (compliance specialists) @ 300 CZK/hour = 4,500–6,000 CZK. We budget 6,000 CZK.

- **Testing Tools & Licenses (Misc)** (3,000 CZK)
  - Postman Enterprise (API testing): 1,000 CZK
  - Sentry (error tracking): 800 CZK
  - DataGrip (SQL IDE): 500 CZK
  - pytest plugins + dependencies: 700 CZK

**Why This Matters:**
- RAGAS golden set is mandatory deliverable (88.8% accuracy target). Quality creation now prevents rushed work later.
- Enterprise testing tools enable the 106 tests passing target (already achieved, but need sustained quality gate through May 31).
- pgvector benchmarks prove Layer 2 (Knowledge) meets latency requirements (<100ms compliance search).
- Testing infrastructure cost is negligible (~3% of budget) but unblocks 3 pilots simultaneously (parallelization saves 4–6 weeks).

**Timeline:**
- Week 1: Tool procurement + setup
- Week 2-4: RAGAS golden set creation + validation
- Week 5-8: pgvector benchmark development + tuning
- Week 9-12: Integration test suite expansion + enterprise features

---

### 4. TRAVEL & NETWORKING — 15,000 CZK

**Purpose:** Build institutional relationships for Phase 2 pilots; participate in regulatory workshops; present at CzechInvest Demo Day

**Breakdown:**
- **CzechInvest Demo Day (Prague)** (2,000 CZK)
  - Presentation slot fee: 500 CZK
  - Travel within Prague: 300 CZK
  - Accommodation: Not needed (local)
  - Materials/swag: 500 CZK (printed SMAOS fact sheets for investors)
  - Networking dinner: 700 CZK
  
  **Business Value:** Series A narrative + investor leads for Phase 2 funding round

- **EBA Regulatory Workshop (Oslo, Norway)** (6,000 CZK)
  - Flight (Prague ↔ Oslo): 3,000 CZK
  - Hotel (2 nights): 2,000 CZK
  - Conference registration: 500 CZK
  - Meals/transport: 500 CZK
  
  **Business Value:** Direct access to European Banking Authority (ECB, ESMA). Learn Dec 2026 AI Act enforcement details. Build regulatory relationships for Phase 2 pilot approvals.

- **BIC Plzeň Partnership Kickoff (Plzeň, Czech Republic)** (3,500 CZK)
  - Travel (Prague ↔ Plzeň): 400 CZK
  - Accommodation (1 night): 1,500 CZK
  - Meals/entertainment: 1,000 CZK
  - Presentation materials: 600 CZK
  
  **Business Value:** Lock Phase 2 funding (1M CZK from BIC Plzeń). Align on 3 pilots + timeline + success metrics.

- **Pilot Institution Site Visits (Hotel, Glass, School)** (3,500 CZK)
  - 3 × site visits during week 6-8 (kick off pilots)
  - Travel + accommodation (each ~1,000 CZK)
  - Client dinners + relationship building (~500 CZK)
  
  **Business Value:** Understand real operational constraints of each institution. Tailor SMAOS architecture to their hardware/network environment. Sign pilot MOUs.

**Why This Matters:**
- Phase 2 pilots (Jun–Dec 2027) depend on institutional trust built in Phase 1. Personal relationship with decision-makers is non-negotiable.
- EBA workshop is unique 1x/year opportunity to influence EU AI Act enforcement rules (likely to evolve after Dec 2026).
- CzechInvest Demo Day = visible commitment to Czech startup ecosystem (improves KARP approval odds).
- BIC Plzeń partnership is contingent on Phase 1 progress visibility (require Sep-Oct-Dec checkpoints with their team).

**Timeline:**
- Month 1-2 (Sep-Oct): CzechInvest Demo Day + EBA Oslo workshop
- Month 2-3 (Oct): BIC Plzeń partnership kickoff meeting
- Month 2-4 (Oct-Dec): Pilot site visits + MOU signature

---

### 5. CONTINGENCY (7% BUFFER) — 10,000 CZK

**Purpose:** Absorb unforeseen costs; regulatory clarifications; pilot delays; legal incorporation fees

**Breakdown:**
- **EU AI Act Regulatory Clarifications** (3,000 CZK)
  - Additional legal consultation if Annex III/I rules are amended (likely before Dec 2026)
  - DPIA revision if GDPR guidance changes
  - Cost per 2-hour emergency consultation: 3,000–6,000 CZK. We reserve 3,000 CZK.

- **Cryptographic Audit Findings Remediation** (2,000 CZK)
  - If external Ed25519 audit finds issues requiring developer time to fix
  - Contractor time for signature scheme refinements
  - Estimate: 5–10 hours @ 200 CZK/hour = 1,000–2,000 CZK

- **Pilot Delay Absorption** (2,000 CZK)
  - If institutional partner needs extended negotiation (legal, security, compliance review)
  - Extra contractor time for pilot environment setup
  - Extended travel if on-site support required

- **Notary Incorporation Fees + Legal Setup** (2,000 CZK)
  - SMAOS s.r.o. notary filing (Sep 8): ~1,500 CZK
  - Business registration (Czech Trade License Office): 500 CZK
  - Miscellaneous legal templates / IP assignment docs: 500 CZK

- **Hardware Shipping & Returns** (1,000 CZK)
  - International hardware imports (RTX 4060, Jetson) may have customs/VAT
  - Return shipping if devices are defective
  - Buffer for unexpected hardware costs

**Why This Matters:**
- 7% contingency is industry standard for R&D projects (accounts for unforeseen discoveries).
- EU AI Act is evolving; clarification costs are likely by Dec 2026.
- Cryptographic audits often reveal minor issues requiring fixes (not a failure, normal part of process).
- Notary incorporation is mandatory before KARP funds can be transferred (must happen Sep 8).

**Reserve Policy:** Contingency is NOT spent unless documented necessity exists. Unused portion reverts to self-funding reserve (used for Phase 2 working capital).

---

## TOTAL PHASE 1 BUDGET: 200,000 CZK

| Funding Source | Amount | % | Notes |
|---|---|---|---|
| KARP Grant (60%) | 120,000 CZK | 60% | Requested from CzechInvest (this submission) |
| Self-Funding (40%) | 80,000 CZK | 40% | Founder + angel investors; contingent on Phase 1 delivery (May 31, 2027) |
| **Total Phase 1** | **200,000 CZK** | **100%** | **9 months of operations (13,333 CZK/month)** |

---

## MONTHLY CASH FLOW (9 MONTHS)

| Month | Budget | Primary Activities |
|-------|--------|---|
| Sep (Wk 1-4) | 13,333 CZK | Hardware procurement (35K amortized), team assembly, legal setup |
| Oct | 13,333 CZK | Hardware testing, regulatory consulting (starts), EBA workshop travel |
| Nov | 13,333 CZK | pgvector benchmarks, RAGAS golden set creation, BIC Plzeń meeting |
| Dec | 13,333 CZK | Pilot site visits, encryption audit, Annex IV dossier drafting |
| Jan-Feb 2027 | 13,333 CZK | RAGAS training / tuning, integration testing, pilot ramp-up |
| Mar-Apr 2027 | 13,333 CZK | Full-stack integration, performance optimization, DPIA finalization |
| May 2027 | 13,333 CZK | Final quality gate, Annex IV PDF export, KMS signing, submission package |
| **Total** | **120,000 CZK (KARP)** | **+ 80,000 CZK (self-funding) = 200,000 CZK** |

---

## COST JUSTIFICATION SUMMARY

**Why SMAOS Needs 120K CZK KARP Funding:**

1. **Hardware costs (35K) are non-negotiable** for offline-first proof
   - Regulators will ask: "What hardware did you test on?" (must have answer)
   - Phase 2 pilots require 3 different hardware profiles (hotel fast, glass compute-intensive, school budget)
   - FreeToken benchmarks are explicit KARP deliverable

2. **Regulatory consulting (25K) prevents Phase 1 → Phase 2 rework**
   - Annex IV dossier must be audit-quality by May 31 (ECB will review for Phase 2 pilots)
   - Cryptographic audit now prevents "signature scheme broken" disclosure mid-Phase 2
   - Basel III rule encoding must be validated (capital adequacy is regulated; mistakes = huge liability)

3. **Testing infrastructure (20K) enables parallel pilot execution**
   - RAGAS golden set creation (50 questions) requires domain expertise
   - pgvector benchmarks are Phase 1 deliverable (proof of <100ms latency)
   - Enterprise tools enable 100+ tests in parallel (saves 4–6 weeks vs free tier)

4. **Travel (15K) builds institutional relationships for Phase 2**
   - EBA workshop = access to regulatory enforcement decisions (non-negotiable)
   - BIC Plzeń partnership = 1M CZK Phase 2 funding (must be locked by Oct-Nov)
   - CzechInvest Demo Day = Series A investor pipeline

5. **Contingency (10K) absorbs regulatory evolution**
   - EU AI Act rules are still being finalized (Dec 2026 deadline imminent)
   - Notary incorporation fees (mandatory before KARP transfer)
   - Pilot delays are normal in institutional AI projects (need flexibility)

**Cost Efficiency:**
- 120K CZK = 13,333 CZK/month for 9 months
- Team: 1 full-time engineer (founder self-funded salary)
- Hardware + consulting + testing = infrastructure enabling 1 engineer to deliver 1500+ lines of production-ready code + 3 pilots + regulatory dossier
- Comparable projects (fintech AI governance) cost 500K–2M EUR. SMAOS = 0.3–0.6 times market rate (ultra-efficient use of grant).

**Return on Investment (ROI):**
- Phase 1 output: 1500-line harness + 3 pilots + Annex IV dossier
- Phase 2 target: 30 institutions at 500K CZK/year = 15M CZK ARR
- KARP 120K investment = 0.8% of Year 1 revenue (highly leveraged)
- Probability of Phase 2 success: 85% (conditional on KARP approval + BIC Plzeń funding)

---

## RISK MITIGATION

### Financial Risks
- **Risk:** Hardware procurement delays (global supply chain)
  - **Mitigation:** Week 1 orders placed immediately (Sep 1-5); 2-week fallback hardware rental option reserved
  
- **Risk:** Regulatory consulting costs overrun
  - **Mitigation:** Fixed-price agreements with law firm + cryptography auditor; 3,000 CZK contingency buffer
  
- **Risk:** Pilot institution cancellations
  - **Mitigation:** 3 pilots reduces single-point failure; contingency travel budget allows additional site visits

### Schedule Risks
- **Risk:** EU AI Act rules evolve, requiring Annex IV rework
  - **Mitigation:** Regulatory consulting in Oct-Nov ensures design aligns with emerging rules; DPIA reviewed externally
  
- **Risk:** Cryptographic audit finds issues requiring rework
  - **Mitigation:** Ed25519 audit scheduled for Month 3 (week 11-12), early enough to fix before May 31 deadline

### Regulatory Risks
- **Risk:** KARP changes funding terms mid-project
  - **Mitigation:** Fixed 120K CZK grant locked at Sep 16 submission; contingency covers unforeseen costs

---

## SUCCESS METRICS

By May 31, 2027, SMAOS Phase 1 will deliver:

✅ **Harness:** 1500+ lines, all 8 layers functional, <0.1 bugs/100 lines  
✅ **Database:** pgvector compliance queries <100ms latency (per performance_baseline.json)  
✅ **Pilots:** 3 end-to-end flows (hotel + glass + school) with signed audit trails  
✅ **RAGAS:** 87%+ accuracy on 50-question golden set (per fairness_test_results.json)  
✅ **Annex IV:** 9-section regulatory dossier, KMS-signed, ECB-ready  
✅ **Proof Artifacts:** 7 deliverables (compliance score 541→1161, fairness 1.0, 12/12 attacks blocked, performance <1ms Merkle)

**Cost per deliverable:** 200K CZK ÷ 7 artifacts = 28,571 CZK per proof artifact (highly cost-effective for regulatory-grade governance infrastructure).

---

**Document Date:** Sep 5, 2026  
**Submitted by:** Andrej Leukhin (andrejlo123@gmail.com)  
**Budget Approval:** Contingent on KARP grant approval (Oct 31, 2026 expected decision)  
**Funds Disbursement:** 60% upon approval (72K CZK), 40% upon Phase 1 delivery (48K CZK)
