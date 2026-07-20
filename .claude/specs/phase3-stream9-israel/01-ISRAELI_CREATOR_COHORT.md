# Israeli Creator Cohort Spec — Phase 3 Stream 9

**Date:** June 4, 2026  
**Phase:** 3 Beta Launches  
**Stream:** 9 (Israel Market Entry)  
**Status:** Specification Phase  
**Target Launch:** August 1, 2026  
**Budget:** €30K  
**Timeline:** Aug 1–31, 2026  

---

## Executive Summary

**Mission:** Onboard 25–50 independent Israeli content creators (Hebrew + English) as the first cohort for Axiom Protocol's governance platform, demonstrating 1%/99% settlement mechanics and creator-owned economic participation.

**Success Metric:** 50+ creators active by Aug 31, generating €15K in earnings via governance participation (€0.30–0.50 per action), all settlements transparent via AP2 Ledger + cryptographic proofs.

---

## 1. Target Creator Cohort

### 1.1 Persona & Segments

**Primary Segments:**
- **Independent creators** (YouTube, TikTok, Substack): 30 creators
  - Hebrew-language content (tech, politics, education)
  - 10K–100K followers per creator
  - Revenue-aware; seeking alternative monetization
  
- **Podcasters + Opinion Leaders:** 15 creators
  - Talk radio, political commentary, tech newsletters
  - 5K–50K engaged followers
  - Trust-sensitive (credibility is brand asset)
  
- **Open-source developers + Tech Speakers:** 5 creators
  - Code contributors, conference speakers
  - Community-driven, mission-aligned
  - GitHub rep + Twitter influence

**Geographic:** Israel-based or Israel-diaspora (Hebrew fluency preferred)

**Psychographic:** Values sovereignty, skeptical of extractive platforms, interested in cryptography + governance

---

### 1.2 Onboarding Mechanics

**Phase 1: Recruitment (Aug 1–10)**
- Outreach: DMs via Twitter/LinkedIn, direct emails, Yozma Fund network referrals
- Messaging: "Own 99% of your earnings. Transparent, cryptographic payouts. Join 25 founders testing sovereign creator economy."
- Acceptance criteria: Agreement to Terms of Service + KYC verification (Pearl Cohen legal review)

**Phase 2: Wallet Setup (Aug 11–15)**
- MetaMask or Safe Wallet onboarding (guided video + support chat)
- Create on-chain sovereign identity (SovereignIdentity NFT on Optimism testnet)
- Local custody verification (signature of random challenge)
- Backup seed phrase in Hebrew + English

**Phase 3: Governance Participation (Aug 16–31)**
- Assign creator roles (Observer, Participant, Delegate tiers)
- Introduce first governance actions:
  - Vote on settlement fee mechanics (binary: 1% platform vs. 0.5% platform)
  - Propose content categories eligible for governance premiums
  - Approve settlement window adjustments
- Each action: €0.30–0.50 payment via AP2 Ledger → visible Merkle proof

---

## 2. Settlement Mechanics (1% Platform / 99% Creator)

### 2.1 Revenue Flow

```
Governance Action Initiated
        ↓
Creator or Platform proposes change
        ↓
Creators vote (via AP2 ballot)
        ↓
Decision recorded (Merkle root + timestamp)
        ↓
Settlement calculation:
  - Base payout: €1.00 (per action average)
  - Platform fee: €0.01 (1%)
  - Creator payout: €0.99 (99%)
        ↓
AP2 Ledger settlement (cryptographic proof)
        ↓
Creator wallet receives USDC / stablecoin
        ↓
Settlement logged to audit trail (immutable + queryable)
```

### 2.2 Creator Earnings Projection

**Conservative Scenario (Aug 1–31):**
- 25 creators × 20 governance actions/creator = 500 total actions
- Avg payout: €0.40/action (weighted toward participation votes)
- Total pool: €200 (€100 creators, €2 platform)
- Per creator avg: €4.00
- Total creator earnings: €100

**Realistic Scenario:**
- 40 creators × 30 governance actions/creator = 1,200 total actions
- Avg payout: €0.40/action
- Total pool: €480 (€475 creators, €5 platform)
- Per creator avg: €12
- Total creator earnings: €475

**Optimistic Scenario (Phase 3 goal):**
- 50 creators × 30 governance actions/creator = 1,500 total actions
- Avg payout: €0.50/action (governance becomes valuable signal)
- Total pool: €750 (€743 creators, €7 platform)
- Per creator avg: €15
- Total creator earnings: €743

**Target by Aug 31:** €15K total creator earnings (requires 60+ active creators or higher action frequency) — stretch goal, acceptable to achieve €5–10K.

---

## 3. Onboarding Flow (User Experience)

### 3.1 Signup Flow

```
Landing Page (Hebrew + English)
    ↓
Email signup + KYC form
    ↓
Verify email + ID (Pearl Cohen legal review)
    ↓
Confirm ToS + data privacy
    ↓
Account created (Axiom creator profile)
    ↓
"Next: Connect Wallet"
```

### 3.2 Wallet Connection

```
"Connect MetaMask" button
    ↓
User authorizes MetaMask connection
    ↓
System detects creator's address
    ↓
Signature challenge (prove address ownership)
    ↓
Local custody verification (signature stored)
    ↓
SovereignIdentity NFT minted (on-chain proof of identity)
    ↓
Creator dashboard loads
```

### 3.3 First Governance Action

```
Creator Dashboard opens
    ↓
"Your First Action" tutorial card
    ↓
Vote on: "Should platform fee be 1% or 0.5%?"
    ↓
Creator votes (option A or B)
    ↓
Transaction submitted → AP2 Ledger records vote
    ↓
"You earned €0.40!" — show Merkle root proof
    ↓
"View on Ledger" link (cryptographic transparency)
    ↓
Creator invited to next action
```

---

## 4. Governance Actions Taxonomy

**Month 1 (Aug 1–10):** Soft-Launch Actions
1. Settlement frequency (weekly vs. bi-weekly)
2. Stablecoin choice (USDC vs. EURS vs. both)
3. Creator tier eligibility (who can participate)

**Month 2 (Aug 11–25):** Feature Voting
4. Content category premiums (news vs. entertainment)
5. Governance power allocation (1 creator = 1 vote vs. reputation-weighted)
6. Blackout dates for settlements (exclude holiday weeks)

**Month 3 (Aug 26–31):** Enterprise Integration
7. Israeli civil defense integration approval (if Pax Silica pilot moves forward)
8. Revenue-sharing model for enterprise data (if applicable)

---

## 5. Success Criteria (August 31)

- ✅ 50+ creators onboarded + verified (min 25, target 50)
- ✅ 99% settlement accuracy (verified via Merkle audit)
- ✅ Total creator earnings: €5K–15K (conservative to optimistic)
- ✅ <24hr settlement latency (AP2 Ledger proven)
- ✅ Zero unauthorized access incidents (ReBAC + temporal guard working)
- ✅ Creator satisfaction NPS >70 (survey post-Aug 31)
- ✅ All settlements logged to immutable audit trail
- ✅ Go/no-go gate: Legal clearances + KYC compliance 100%

---

## 6. Dependencies & Integration Points

**Internal:**
- `siss-behavioral-firewall` — ReBAC for creator roles (Observer, Participant, Delegate)
- `siss-payment` — AP2 Ledger for settlement mechanics
- Creator Dashboard (Jun 30 completion)
- KYC module (external service, TBD)

**External:**
- Pearl Cohen Law Firm (legal review, KYC compliance)
- MetaMask / Safe Wallet (custody providers)
- Optimism testnet (SovereignIdentity NFT issuance)
- USDC stablecoin provider (Coinbase, Circle)

**Pax Silica Integration (if applicable):**
- Data schema alignment for enterprise pilot
- Revenue-share tracking in AP2 Ledger

---

## 7. Risk Mitigation

| Risk | Mitigation |
|---|---|
| Low adoption (<20 creators) | Extend timeline, increase outreach to 100 candidates, launch referral bounty |
| Regulatory blockers (KYC fails) | Pre-approve with Pearl Cohen by Jul 15; have fallback non-regulated cohort |
| Settlement delays (AP2 Ledger unready) | Mock API for Aug 1–15, live integration by Aug 25 |
| Creator churn (low earnings) | Retroactive bonus pool (€500 reserve) for top 10 creators by engagement |
| On-chain costs (transaction fees) | Use testnet initially, batch settlements to reduce gas |

---

## 8. Deliverables by Aug 31

1. **Creator Cohort List** (50+ names, emails, regions, verification status)
2. **Settlement Audit Trail** (all Aug transactions, Merkle proofs, immutable)
3. **Creator Earnings Report** (breakdown by creator, by action type, cumulative)
4. **Investor Demo** (live dashboard, sample creator earnings, Merkle proofs)
5. **Legal Compliance** (Pearl Cohen sign-off, all KYC docs archived)
6. **Creator Feedback** (NPS survey, qualitative interviews, feature requests)

---

## Next Steps

1. **Jun 5–14:** Finalize KYC requirements with Pearl Cohen
2. **Jun 15–30:** Creator Dashboard implementation (Stream 2 SDK + AP2 integration)
3. **Jul 1–31:** Series A close + final governance certification
4. **Aug 1:** Outreach begins, MetaMask setup guidance published
5. **Aug 31:** First cohort complete, go/no-go decision on Pax Silica expansion

