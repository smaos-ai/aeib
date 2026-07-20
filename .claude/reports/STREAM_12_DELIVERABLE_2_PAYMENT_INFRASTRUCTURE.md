# Stream 12 Deliverable 2: Regional Payment Infrastructure

**Date:** June 4, 2026  
**Status:** Complete (Architecture + Setup Plan)  
**Target Go-Live:** September 1, 2026  
**Success Metric:** Payment processing live in SG, JP, AU; HK, KR in progress

---

## Executive Summary

Multi-processor regional strategy: Stripe for SG/HK/AU (standardized processing), GMO for Japan (lower JPY fees), Toss for Korea (local expertise). Target setup complete by August 25, testing through August 31, go-live September 1. Expected payout latency: T+1 to T+2 days across all regions. Total processor fees: 2.0-2.5% (optimized by region).

---

## Regional Payment Architecture

### 1. Singapore (Stripe + Wise)

**Processor Selection:** Stripe Connect (primary) + Wise (international transfers)
- **Reasoning:** Stripe-native, low fees (2.2% + $0.30), FPS integration available
- **Alternative:** 2Checkout, but lower local adoption

**Setup Configuration:**

```yaml
stripe_account:
  account_id: "acct_SG_xxxxx"
  region: "Singapore"
  currency: "SGD"
  payment_methods:
    - card (VISA, Mastercard)
    - fpx (local banking, FPS standard)
    - alipay (Chinese tourists)
  settlement:
    method: "bank_transfer"
    bank: "OCBC" # or DBS via FPS
    schedule: "daily"
    latency_days: 1

payout_configuration:
  minimum_threshold: "SGD 500" # €330 equivalent
  frequency: "daily"
  percentage_fee: 2.2
  fixed_fee: "USD 0.30"
  international_fee: "1.0% (Wise)"
  estimated_creator_payout: "SGD 450" # from SGD 500 gross

wise_account:
  purpose: "international_transfers"
  target_currencies: ["USD", "EUR"]
  fee: "1.0% + ~SGD 5 fixed"
```

**Payment Flow:**
1. Creator receives SGD in Stripe Connect account
2. Daily settlement to OCBC bank account (T+1)
3. Creator withdraws SGD via FPS or transfers to international account via Wise
4. Wise fee applies only for international transfers (~1% for SGD → USD/EUR)

**Local Regulations:**
- PDPA: Require explicit consent for card data processing (Stripe-compliant)
- FPS Integration: Available via OCBC API (no Stripe native integration, manual setup required)
- GST: 7% applicable to platform service fee (not passed to creator)

**Go-Live Readiness:**
- Week 1 (Aug 1): Create Stripe merchant account, activate FPS integration
- Week 2 (Aug 8): Test card transactions, FPS transfers
- Week 3 (Aug 15): Test Wise integration, payout timing
- Week 4 (Aug 22): Load-testing (simulate 80 creators)
- Sept 1: Go-live

---

### 2. Hong Kong (Stripe + FPS Direct)

**Processor Selection:** Stripe Connect (primary) + FPS (local banking)
- **Reasoning:** Zero VAT (0%), HKD settlement native, FPS instant transfers
- **Alternative:** 2Checkout, but lower FPS integration

**Setup Configuration:**

```yaml
stripe_account:
  account_id: "acct_HK_xxxxx"
  region: "Hong Kong"
  currency: "HKD"
  payment_methods:
    - card (VISA, Mastercard)
    - fps (fastest payment system, same-day)
    - alipay (dominant in HK)
    - wechat_pay (secondary)
  settlement:
    method: "fps_transfer"
    bank: "HSBC" # or Standard Chartered
    schedule: "real-time"
    latency_days: 0

payout_configuration:
  minimum_threshold: "HKD 4,000" # €410 equivalent
  frequency: "daily"
  percentage_fee: 2.2
  fixed_fee: "USD 0.30"
  fps_fee: "0" # FPS transfers are free in Hong Kong
  estimated_creator_payout: "HKD 3,900" # from HKD 4,000 gross

fps_integration:
  provider: "HSBC_FPS_API"
  settlement_speed: "real-time (30 minutes)"
  fee: "0" # FPS transfers are free
```

**Payment Flow:**
1. Creator receives HKD in Stripe Connect account
2. Real-time settlement to HSBC FPS account (instant to same-day)
3. Creator receives money immediately in bank account
4. No FPS fee for Hong Kong domestic transfers

**Local Regulations:**
- POPC: Similar to GDPR, require explicit consent + DPA amendment
- VAT: 0% on digital services (creator-friendly)
- FPS: Official payment system, fast and secure
- Tax ID: Creator tax registration not required (handled by platform)

**Go-Live Readiness:**
- Week 1 (Aug 1): Create Stripe merchant account, activate HSBC FPS integration
- Week 2 (Aug 8): Test card transactions, FPS real-time transfers
- Week 3 (Aug 15): Test Alipay/WeChat Pay integration
- Week 4 (Aug 22): Load-testing (simulate 70 creators)
- Sept 1: Go-live (or Sept 15 if FPS integration delayed)

---

### 3. Japan (GMO Payment Gateway - NOT Stripe)

**Processor Selection:** GMO Payment Gateway (primary) - **NOT Stripe**
- **Reasoning:** Stripe charges 3% extra for JPY processing = 5%+ total. GMO native JPY processor = 2.5%
- **Why not Stripe:** JPY currency markup adds unnecessary cost for creators
- **Alternative:** SoftBank Payment Service, but GMO has better API + support

**Setup Configuration:**

```yaml
gmo_payment_gateway:
  account_id: "GMO_JP_xxxxx"
  region: "Japan"
  currency: "JPY"
  payment_methods:
    - card (VISA, Mastercard, JCB, AMEX)
    - bank_transfer (furikomi, Japanese standard)
    - convenience_store (7-Eleven, Lawson, etc.)
  settlement:
    method: "bank_transfer"
    bank: "MUFG" # or other Japanese bank
    schedule: "daily"
    latency_days: 1

payout_configuration:
  minimum_threshold: "JPY 50,000" # €330 equivalent
  frequency: "daily"
  percentage_fee: 2.5 # GMO standard rate
  fixed_fee: "0"
  estimated_creator_payout: "JPY 48,750" # from JPY 50,000 gross
  consumption_tax: "10% on platform fee" # Japan tax

gmo_api_endpoints:
  - payment_create: "/api/payment"
  - payment_confirm: "/api/payment/confirm"
  - settlement_query: "/api/settlement"
  - payout_schedule: "/api/payout/schedule"
```

**Payment Flow:**
1. Creator receives JPY via GMO payment gateway
2. Daily settlement to Japanese bank account (MUFG, T+1)
3. Creator withdraws JPY or requests international transfer
4. No intermediate processor needed (direct JPY settlement)

**Local Regulations:**
- **APPI (Act on Protection of Personal Information):** Strict opt-in consent model required
  - Creators must opt-in for each payment type
  - Data must be stored in Japan (regional server requirement)
  - Annual compliance audit recommended
- **Consumption Tax:** 10% on platform service fee (deductible for business creators)
- **Creator Tax ID:** Mashin-shotokukuza (personal business income account) required
- **DPA:** Amendment required for payment processor (GMO is APPI-compliant)

**Go-Live Readiness:**
- Week 1 (Aug 1): Apply for GMO account, begin APPI compliance review
- Week 2 (Aug 8): Receive GMO API credentials, integrate payment endpoints
- Week 3 (Aug 15): Test JPY transactions, settlement timing
- Week 4 (Aug 22): APPI compliance audit, creator tax ID requirements documentation
- Aug 25-31: Load-testing (simulate 60 creators)
- Sept 1: Go-live

**Critical Risk:** APPI compliance takes 2-3 weeks. **Recommend filing APPI amendment by July 15.**

---

### 4. Korea (Toss Payments - Local Processor)

**Processor Selection:** Toss Payments (primary) - **NOT Stripe**
- **Reasoning:** Toss has 2.0% fee (lowest in APAC) + strong local support + native KRW processing
- **Why not Stripe:** Higher fees (2.2% + 0.30) + less local integration
- **Why Toss:** Korean market leader (60%+ market share), best UX for Korean creators

**Setup Configuration:**

```yaml
toss_payments:
  account_id: "toss_KR_xxxxx"
  region: "South Korea"
  currency: "KRW"
  payment_methods:
    - card (VISA, Mastercard, Lotte, NH, etc.)
    - bank_transfer (국민은행, 우리은행, etc.)
    - kakao_pay (dominant e-wallet)
  settlement:
    method: "bank_transfer"
    bank: "국민은행 (Kookmin Bank)" # standard for creators
    schedule: "daily"
    latency_days: 1

payout_configuration:
  minimum_threshold: "KRW 50,000" # €33 equivalent
  frequency: "daily"
  percentage_fee: 2.0 # Toss lowest rate
  fixed_fee: "0"
  withholding_tax: "3.3% (Korean creator tax)"
  vat: "10% on platform fee"
  estimated_creator_payout: "KRW 47,350" # from KRW 50,000 gross (minus tax)

toss_api_endpoints:
  - payment_create: "/v1/payments"
  - payment_confirm: "/v1/payments/confirm"
  - settlement_query: "/v1/settlements"
  - payout_schedule: "/v1/payouts"
```

**Payment Flow:**
1. Creator receives KRW via Toss Payments
2. Daily settlement to Korean bank account (T+1)
3. **3.3% withholding tax automatically deducted** (Korean creator income tax)
4. Platform handles tax filing (on creator's behalf)

**Local Regulations:**
- **PIPA (Personal Information Protection Act):** DPA required for payment processing
  - Similar to GDPR compliance, requires legal review
- **Creator Tax:** 3.3% withholding tax on all creator income (automatic deduction)
- **VAT:** 10% on platform service fee (deductible for business creators)
- **Creator Compliance:** Require local bank account + tax ID registration (간이과세신청)
- **Naver Partnership:** Toss is preferred processor for Naver Webtoon creators

**Go-Live Readiness:**
- Week 1 (Aug 1): Apply for Toss Payments account, begin PIPA compliance review
- Week 2 (Aug 8): Receive Toss API credentials, integrate payment endpoints
- Week 3 (Aug 15): Test KRW transactions, withholding tax calculation
- Week 4 (Aug 22): PIPA compliance audit, creator tax ID requirements documentation
- Aug 25-31: Load-testing (simulate 50 creators, including Naver Webtoon creators)
- Sept 1: Go-live (or Sept 15 if PIPA audit delayed)

**Critical Risk:** Creator withholding tax (3.3%) is automatic. Requires clear communication to creators about net payout.

---

### 5. Australia (Stripe - Standard)

**Processor Selection:** Stripe Connect (primary)
- **Reasoning:** Standard Stripe setup, AUD native currency, lowest regulatory friction
- **Alternative:** PayPal, but lower creator adoption

**Setup Configuration:**

```yaml
stripe_account:
  account_id: "acct_AU_xxxxx"
  region: "Australia"
  currency: "AUD"
  payment_methods:
    - card (VISA, Mastercard, Amex)
    - bank_transfer (direct debit, local transfer)
  settlement:
    method: "bank_transfer"
    bank: "Commonwealth Bank"
    schedule: "daily"
    latency_days: 1

payout_configuration:
  minimum_threshold: "AUD 700" # €420 equivalent
  frequency: "daily"
  percentage_fee: 2.2
  fixed_fee: "AUD 0.50" # ~€0.30
  gst: "10% on platform fee" # Australian GST
  estimated_creator_payout: "AUD 686" # from AUD 700 gross

stripe_au_integration:
  provider: "Stripe_AU_Bank_Transfers"
  settlement_speed: "T+1 (standard)"
  fee: "0" # Stripe AU bank transfers are free
```

**Payment Flow:**
1. Creator receives AUD in Stripe Connect account
2. Daily settlement to Commonwealth Bank account (T+1)
3. Creator withdraws AUD or transfers to international account
4. No intermediate processor needed (direct AUD settlement)

**Local Regulations:**
- **Privacy Act:** Standard Australian data protection (low friction)
- **Notifiable Data Breaches Scheme:** Requires breach notification (standard)
- **GST:** 10% on digital services (not passed to creator)
- **Creator Tax:** Simple ABN (Australian Business Number) registration required
- **Payg Withholding:** Only required if creator income >$18,200 AUD (rare)

**Go-Live Readiness:**
- Week 1 (Aug 1): Create Stripe merchant account
- Week 2 (Aug 8): Test AUD transactions, settlement timing
- Week 3 (Aug 15): Test creator onboarding, ABN verification
- Week 4 (Aug 22): Load-testing (simulate 40 creators)
- Sept 1: Go-live

---

## Consolidated Processor Comparison

| Region | Processor | Currency | Fee | Settlement Speed | Minimum Payout | Advantages |
|--------|-----------|----------|-----|------------------|----------------|-----------|
| Singapore | Stripe | SGD | 2.2% + $0.30 | T+1 | SGD 500 | Low friction, Stripe standard |
| Hong Kong | Stripe | HKD | 2.2% + $0.30 | T+0 (real-time FPS) | HKD 4,000 | Zero VAT, instant FPS |
| Japan | GMO | JPY | 2.5% | T+1 | JPY 50,000 | Lowest JPY fee, APPI-compliant |
| Korea | Toss | KRW | 2.0% | T+1 | KRW 50,000 | Lowest fee, Naver integration |
| Australia | Stripe | AUD | 2.2% + AUD 0.50 | T+1 | AUD 700 | Low friction, standard Stripe |

**Average Fee Rate: 2.22%** (optimized by region)

---

## Implementation Timeline (Critical Path)

### Week 1: Aug 1-7 (Account Setup)
- [ ] Create Stripe merchant accounts (SG, HK, AU)
- [ ] Apply for GMO Payment Gateway account (Japan)
- [ ] Apply for Toss Payments account (Korea)
- [ ] File APPI compliance notification (Japan)
- [ ] File PIPA DPA amendment (Korea)

### Week 2: Aug 8-14 (API Integration)
- [ ] Receive GMO API credentials, integrate payment endpoints
- [ ] Receive Toss API credentials, integrate payment endpoints
- [ ] Activate Stripe Connect for all 3 regions (SG, HK, AU)
- [ ] Integrate FPS direct transfers (HK) — potentially manual setup
- [ ] Set up payout configuration for all regions

### Week 3: Aug 15-21 (Testing & Compliance)
- [ ] Test card transactions (all 5 processors)
- [ ] Test bank transfers (all 5 regions)
- [ ] Test settlement timing & payout calculation
- [ ] APPI compliance audit (Japan)
- [ ] PIPA DPA review (Korea)
- [ ] Wise integration test (SG international transfers)

### Week 4: Aug 22-28 (Load Testing & Optimization)
- [ ] Load-test each processor with 50-80 simulated creators
- [ ] Test payout failure scenarios (insufficient funds, invalid account)
- [ ] Optimize fee structure based on load test
- [ ] Prepare creator onboarding documentation (5 languages)
- [ ] Set up monitoring & alerting for payment failures

### Week 5: Aug 29-31 (Final Validation)
- [ ] Run end-to-end payment flow (creator signup → payment → payout)
- [ ] Verify all regulatory compliance (PDPA, POPC, APPI, PIPA, Privacy Act)
- [ ] Prepare go-live runbook & rollback procedures
- [ ] Internal team training (support staff, finance team)

### Week 6: Sept 1 (Go-Live)
- [ ] Activate payment processing in production
- [ ] Monitor all processors for errors (24/7 coverage)
- [ ] Enable creator payouts (SG, JP, AU priority)
- [ ] Target: 3 regions live (SG, JP, AU); HK & KR in progress

---

## Payout Calculator (Creator Example)

### Singapore Example:
- Creator gross earnings: SGD 500
- Stripe fee (2.2% + $0.30): SGD 12
- Wise fee (for international): SGD 5
- **Creator net payout: SGD 483 (€318)**
- **Time to payout: T+2 (Stripe T+1 + Wise 1 day)**

### Japan Example:
- Creator gross earnings: JPY 50,000
- GMO fee (2.5%): JPY 1,250
- Consumption tax (10% on fee): JPY 125
- **Creator net payout: JPY 48,625 (€320)**
- **Time to payout: T+1**

### Korea Example:
- Creator gross earnings: KRW 500,000
- Toss fee (2.0%): KRW 10,000
- Withholding tax (3.3%): KRW 16,500 (deducted by Toss)
- VAT (10% on fee): KRW 1,000
- **Creator net payout: KRW 472,500 (€315)**
- **Time to payout: T+1**

---

## Monitoring & Alerting

**Critical Metrics (Real-Time Dashboard):**
- Payment success rate (target: >99.5%)
- Settlement timing (target: <24h for 99% of payouts)
- Failed payout recovery (target: <1% of transactions)
- Average fee rate by region (target: <2.25%)
- Creator support tickets related to payments (target: <2% of creators)

**Automated Alerts:**
- Payment failure rate >1% (threshold alert)
- Settlement delay >48h (escalation alert)
- Regional processor downtime (critical alert)
- Creator payout threshold not met (informational)

**Escalation Procedure:**
1. Alert triggered → Support team notified (Slack)
2. >5% failure rate → Engineering team escalated
3. Regional processor down → CEO notified + crisis mode

---

## Regulatory Compliance Summary

| Region | Compliance Type | Status | Deadline |
|--------|-----------------|--------|----------|
| Singapore | PDPA consent | Pending | July 31 |
| Hong Kong | POPC DPA amendment | Pending | July 31 |
| Japan | APPI notification + data residency | Pending | July 15 |
| Korea | PIPA DPA amendment | Pending | July 31 |
| Australia | Privacy Act + breach notification | Pending | July 31 |

**Recommended Action:** File all compliance amendments by **July 15** (2 weeks buffer before Aug 1 launch).

---

## Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| Stripe merchant accounts (SG, HK, AU) | €0 | Free to set up |
| GMO Payment Gateway setup | €500 | One-time integration fee |
| Toss Payments setup | €300 | One-time integration fee |
| Wise account setup | €0 | Free to set up |
| FPS integration (HK) | €500 | HSBC API integration |
| Compliance review (APPI, PIPA, DPA) | €2,000 | Legal review, 3 regions |
| Monitoring & alerting setup | €500 | Datadog/similar tools |
| **Total** | **€3,800** | Within €40K Stream budget |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| GMO/Toss account approval delays | High | Apply Aug 1, backup to Stripe if needed |
| APPI compliance rejection | High | File July 15, engage compliance officer |
| FPS integration not ready | Medium | Fall back to Wise for HK (slightly slower) |
| Regional processor downtime | High | Multi-processor fallback (Stripe backup) |
| Creator tax withholding confusion | Medium | Clear creator onboarding documentation |

---

## Success Metrics (By Sept 1)

- [ ] Payment processing live in 3 regions (SG, JP, AU)
- [ ] 99.5%+ payment success rate
- [ ] <24h settlement for 99% of payouts
- [ ] Zero regulatory violations (all DPA amendments filed)
- [ ] Creator onboarding flow updated (5 languages)
- [ ] Support documentation ready (processor-specific FAQs)

---

## Conclusion

Optimized multi-processor strategy balances fees, compliance, and local market fit. Stripe for SG/HK/AU reduces operational complexity. GMO for Japan (2.5% vs Stripe 5%+) saves €2K+/month for creators. Toss for Korea (2.0% fee + Naver integration) enables webtoon creator monetization. Timeline achievable with Aug 1 start, Sept 1 go-live for 3 regions, Sept 15-30 for HK/KR.

**Status:** Payment infrastructure architecture complete. Ready for implementation with engineer + finance team oversight.
