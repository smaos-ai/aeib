# Phase 3 Stream 12: APAC Global Expansion — Planning & Execution

**Session Start:** June 4, 2026  
**Timeline:** Aug 1 - Dec 31 (6-month execution)  
**Budget:** €40K  
**Success Metric:** 300+ creators across 5 regions + 3 partnerships + localization MVP live

---

## Execution Tasks (Sequential Delivery)

### Task 1: APAC Market Research Report (Due: Week 1)
**Deliverable:** 5 KB report covering 5 regions

- Regional creator cohort breakdown:
  - Singapore: 80 creators
  - Hong Kong: 70 creators
  - Japan: 60 creators
  - Korea: 50 creators
  - Australia: 40 creators

- Creator economy TAM by region:
  - Singapore: €500M (high concentration in Southeast Asia tech hub)
  - Hong Kong: €450M (Asia-Pacific finance + content capital)
  - Japan: €700M (largest creator economy in APAC)
  - Korea: €600M (webtoon + streaming dominance)
  - Australia: €250M (English-speaking, Patreon penetration)
  - **Total TAM: €2.5B**

- Competitive analysis:
  - Singapore: Patreon (dominant), local platforms (rare)
  - Hong Kong: SCMP creator platform, local WeChat
  - Japan: LINE Creators (LINE ecosystem), pixiv (illustration)
  - Korea: Naver Webtoon, Naver V Live, Kakao creator tools
  - Australia: Patreon, YouTube, Twitch (Western platforms)

- Regulatory landscape:
  - Singapore: Personal Data Protection Act (PDPA) — local data residency recommended
  - Hong Kong: POPC (Personal Data Protection Ordinance) — compliant via Stripe
  - Japan: APPI (Act on Protection of Personal Information) — strict consent model
  - Korea: PIPA (Personal Information Protection Act) — DPA required
  - Australia: Privacy Act + Notifiable Data Breaches Scheme — low friction

- Opportunity assessment:
  - Singapore: Uncontested (no dominant creator platform)
  - Hong Kong: Medium competition (SCMP positioned for enterprise)
  - Japan: High competition but massive TAM (LINE Creators not creator-focused)
  - Korea: High competition but webtoon segment under-served
  - Australia: Low friction, English language advantage

### Task 2: Regional Payment Infrastructure (Due: Sept 1)
**Deliverable:** 5 KB config document + processor setup for 3 regions

- Singapore: Stripe + Wise (lowest fees for international transfers)
  - Setup: Stripe Connect (local merchant account)
  - Local bank: OCBC/DBS via FPS-style integration
  - Fee model: 2.2% + $0.30 (Stripe) + 1% (Wise for international)
  - Expected payout velocity: T+2 days

- Hong Kong: Stripe + FPS (local banking integration)
  - Setup: Stripe Connect + direct FPS payment method
  - Local bank integration for HKD settlement
  - Fee model: 2.2% + $0.30 (Stripe) + local rail fees
  - Expected payout velocity: Same-day (FPS)

- Japan: GMO Payment Gateway (preferred for JPY)
  - Setup: GMO-PG (local payment processor, not Stripe)
  - Reason: Stripe + 3% credit card fee = 5%+ for JPY
  - GMO fee model: 2.5% for settled accounts
  - Expected payout velocity: T+1 day (Japan standard)

- Korea: Toss Payments (local expertise + low fees)
  - Setup: Toss Payments API (Korean-native processor)
  - Reason: Lower fees than Stripe (2.0%) + local support
  - Bank account settlement via Korean standard
  - Expected payout velocity: T+1 day

- Australia: Stripe (same as US model)
  - Setup: Stripe Connect (local merchant account)
  - Fee model: 2.2% + $0.30 (AUD equivalent)
  - Local bank settlement (Commonwealth Bank integration)
  - Expected payout velocity: T+1 day

**Critical Path for Sept 1 Launch:**
1. Set up Stripe merchant accounts: SG, HK, AU (Week 1 of Aug)
2. Integrate GMO API: Japan (Week 2 of Aug)
3. Integrate Toss API: Korea (Week 2 of Aug)
4. Test transactions in each region (Week 3 of Aug)
5. Go-live: Sept 1 for SG, JP, AU (core payment system ready)

### Task 3: Partnership Strategy & Outreach (Due: Sept 30)
**Deliverable:** 4 KB strategy document + 3 signed LOIs

- **Singapore: TechCrunch APAC + 500Global**
  - TechCrunch APAC: Media + startup visibility (launch coverage)
  - 500Global: Investor network (lead generation for creators)
  - Outreach: Co-branded "Creator Summit Singapore" (Aug 15)
  - LOI target: Revenue share (5% of regional ARR)

- **Hong Kong: SCMP (South China Morning Post)**
  - SCMP: Editorial + creator community platform
  - Partnership: Featured creator interviews + promotion
  - Outreach: SCMP CEO (direct media partnership)
  - LOI target: 20% of SCMP creator traffic to our platform

- **Japan: LINE Creators (Line partnership)**
  - LINE: Dominant messaging platform (250M+ users in Japan)
  - Partnership: Integration with LINE creator ecosystem
  - Outreach: LINE Japan business development
  - LOI target: Cross-promotion + revenue share (10% of LINE creator referrals)

- **Korea: Naver Webtoon (webtoon creator network)**
  - Naver Webtoon: 500K+ webtoon creators, massive reach
  - Partnership: Webtoon creator monetization (tier 2 creators)
  - Outreach: Naver Webtoon's creator relations team
  - LOI target: Revenue share (8% of Webtoon referrals)

- **Australia: Patreon AU user group**
  - Patreon AU: Existing 50K+ Australian creators (migration target)
  - Partnership: "Creator upgrade" program (Patreon → our platform)
  - Outreach: Patreon community leaders + Patreon Inc. (strategic)
  - LOI target: 10% of Patreon AU creators migrate + revenue share

**Outreach Timeline:**
- Aug 1: Initial contact to all 5 partners (email + LinkedIn)
- Aug 10: Follow-up calls + relationship building
- Aug 25: Draft LOI for first 3 partners (SG, HK, JP)
- Sept 1: First LOI signed (TechCrunch or LINE)
- Sept 30: All 3 LOIs signed (success metric)

### Task 4: Localization Roadmap (Due: Sept 1)
**Deliverable:** 3 KB roadmap document + i18n infrastructure

- **Language support (5 languages priority):**
  - Chinese (Simplified + Traditional) — Hong Kong, Singapore
  - Japanese — Japan
  - Korean — Korea
  - Vietnamese — regional (optional Phase 2)
  - Thai — regional (optional Phase 2)
  - English — Australia + all regions (fallback)

- **Legal compliance by region:**
  - Singapore: PDPA compliance (data residency not required but recommended)
  - Hong Kong: POPC (no special data residency)
  - Japan: APPI (consent model + opt-in required)
  - Korea: PIPA (DPA required for payment processing)
  - Australia: Privacy Act (standard Australian hosting)

- **Tax reporting by country:**
  - Singapore: GST on creator services (7%)
  - Hong Kong: No VAT (0%)
  - Japan: Consumption tax on services (10%)
  - Korea: VAT on digital services (10%)
  - Australia: GST on digital services (10%)

- **Cultural adaptation:**
  - Payment UX: Local payment methods (Alipay/WeChat Pay for CN, bank transfers for JP)
  - Creator expectations: Payout frequency, minimum thresholds, tax docs
  - Content moderation: Regional guidelines (Singapore stricter than AU)
  - Support: Local language support + timezone coverage

**Localization Timeline:**
- Aug 1-15: Extract strings + create i18n framework
- Aug 16-31: Chinese translation (SG/HK) + QA
- Sept 1: Launch Chinese + English (SG/HK)
- Sept 1-15: Japanese translation + QA
- Sept 16-30: Korean translation + QA
- Oct 1: Launch Japanese + Korean + English for all regions

### Task 5: Revenue Projections (Due: Dec 31)
**Deliverable:** 2 KB financial model

- **Creator payout model:**
  - Average creator payout: €0.30-0.50 per transaction/month
  - 300 creators × €0.40 avg = €120K/month by Dec 31
  - Ramp: Sept 15 (50 creators) → Oct 31 (150 creators) → Dec 31 (300 creators)

- **Platform take rate:**
  - Initial: 20% (€0.08 per €0.40 creator payout) = €24K/month
  - Target after partnerships: 15% (€0.06 per €0.40) = €18K/month

- **Partnership revenue:**
  - TechCrunch APAC: 5% of regional ARR (~€2K/month)
  - LINE Creators: 10% of referral revenue (~€4K/month)
  - Naver Webtoon: 8% of webtoon creator revenue (~€3K/month)
  - Patreon AU: Revenue share on migrations (~€1K/month)
  - **Total partnership revenue: €10K/month by Dec 31**

- **Total APAC revenue projection:**
  - Platform take: €18K/month × 4 months (Sept-Dec) = €72K
  - Partnership revenue: €10K/month × 4 months = €40K
  - **Total FY revenue: €112K (€1.34M ARR)**
  - Exit valuation (at 5x ARR): €6.7M APAC-only

**Sensitivity analysis:**
- Scenario A (Upside): 400 creators + higher take rate = €200K/month = €2.4M ARR
- Scenario B (Base case): 300 creators + 15% take = €120K/month = €1.44M ARR
- Scenario C (Downside): 200 creators + 12% take = €72K/month = €860K ARR

### Task 6: Go-Live Checklist (Due: Dec 31)
**Deliverable:** 2 KB checklist + deployment readiness

- **Legal:**
  - [ ] DPA amendments for SG, HK, JP, Korea (data residency clauses)
  - [ ] Tax IDs registered in each region (for VAT/GST collection)
  - [ ] Privacy policy localized for each country
  - [ ] Terms of service compliant with regional law
  - [ ] Payment processor agreements signed (Stripe, GMO, Toss)

- **Payment:**
  - [ ] Stripe merchant accounts created (SG, HK, AU)
  - [ ] GMO test transactions pass (Japan)
  - [ ] Toss test transactions pass (Korea)
  - [ ] Payout processing verified (creator payouts working)
  - [ ] Currency conversion rates set (EUR → SGD, HKD, JPY, KRW, AUD)

- **Onboarding:**
  - [ ] Creator onboarding flow localized (5 languages)
  - [ ] KYC/AML checks configured per region
  - [ ] Creator documentation templates translated
  - [ ] Payout threshold set per region (€50 minimum)

- **Support:**
  - [ ] Support team trained on regional differences
  - [ ] Support email addresses set up (hello@[region].platform.com)
  - [ ] Response SLA: <24h in local timezone
  - [ ] FAQ translated (5 languages)

- **Monitoring:**
  - [ ] Observability dashboards set up (creator signup by region)
  - [ ] Payment failure alerts configured
  - [ ] Revenue tracking by region (daily reconciliation)
  - [ ] Creator churn monitoring (by region + cohort)

---

## Critical Path Summary

| Week | Task | Deliverable | Owner |
|------|------|------------|-------|
| Aug 1-7 | Market research + payment setup | Report + processor setup plan | Research + Engineering |
| Aug 8-14 | Partnership outreach kickoff | Initial contact + relationship building | BD/Partnerships |
| Aug 15-21 | i18n framework + payment testing | Localization framework + processor test results | Engineering |
| Aug 22-31 | Translation + creator onboarding | Translated strings + onboarding flow | Localization |
| Sept 1 | Payment go-live (SG, JP, AU) | Live payment processing | Engineering |
| Sept 15 | Creator onboarding begins | First 50 creators signed up | Growth/Partnerships |
| Sept 30 | 3 partnership LOIs signed | Signed agreements | BD/Partnerships |
| Oct 1 | Localization go-live (JP, KR) | Launch in Japanese + Korean | Engineering |
| Dec 31 | Final metrics report | 300 creators + revenue validated | Growth/Analytics |

---

## Success Metrics & Validation

**By Dec 31, 2026:**
- [ ] 300+ creators across APAC signed up
- [ ] 3 partnership LOIs signed (TechCrunch, LINE or Naver, Patreon)
- [ ] Payment processing live in 5 regions (SG, HK, JP, KR, AU)
- [ ] Localization MVP live (Chinese, Japanese, Korean)
- [ ] €120K/month creator payouts by Dec 31
- [ ] Zero payment processing failures (99.9% uptime)
- [ ] <24h support response in all regions

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Payment processor delays (GMO, Toss) | Parallel setup with backup (Wise + direct bank transfer) |
| Partnership LOI negotiation | Engage law firm early (Aug 1), use template LOI |
| Localization quality | Hire native speakers, 2-round QA per language |
| Creator onboarding churn | Regional creator communities (Discord) + buddy system |
| Regulatory delays (Japan APPI) | File DPA amendments in July (before Aug 1 start) |

---

## Estimated Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| Localization (5 languages, 3 rounds) | €8K | 50 hours × €160/hour |
| Payment processor setup (5 regions) | €5K | Integration fees + testing |
| Partnership outreach (events, travel) | €12K | Singapore summit + manager time |
| Regional support hiring (0.5 FTE) | €10K | Part-time support coverage |
| Legal (DPA, tax, compliance) | €5K | Law firm amendments |
| **Total** | **€40K** | |

---

## Next Steps (Upon Approval)

1. **Week 1 (June 4-10):** Create APAC Market Research Report (task 1)
2. **Week 1-2 (June 4-18):** Set up payment infrastructure (task 2, critical path)
3. **Week 1 (June 4-10):** Draft partnership strategy + initial outreach (task 3)
4. **Week 2-3 (June 11-25):** Build localization framework + i18n setup (task 4)
5. **Week 4 (June 25-July 1):** Revenue projections model + validation (task 5)
6. **Week 4 (June 25-July 1):** Draft go-live checklist + rollout plan (task 6)

**Status:** Ready for execution once approved.
