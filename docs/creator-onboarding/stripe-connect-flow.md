# Payment Flow Architecture: Stripe Connect Integration

**Target Launch:** August 15, 2026  
**Scope:** Creator payout, settlement & auditing  
**Status:** Design (pre-implementation)

---

## 1. Overview

Creators receive monthly payouts via Stripe Connect (ACH in US, SEPA in EU). AXIOM takes a 1% platform fee; creators keep 99% of earnings. Every payout is cryptographically signed (Merkle chain + Ed25519) and auditable by both parties.

**Key Promise:** "99% of your earnings go straight to you. No hidden fees. Full transparency."

---

## 2. End-to-End Payment Flow Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      CREATOR EARNING CYCLE (Monthly)                      │
└──────────────────────────────────────────────────────────────────────────┘

Day 1-30: Creators publish content → Audience engagement tracked

                            ↓

Day 30 (23:00 UTC): Earning Calculation
┌────────────────────────────────────────────────────────────────┐
│ 1. Query all creator earnings from AP2 ledger                  │
│    (published posts, subscriber interactions, monetization)     │
│ 2. Calculate gross revenue: $X                                  │
│ 3. Validate with behavioral firewall (toxicity, PII, etc)      │
│ 4. Compute splits:                                              │
│    - Platform fee (1%): $X * 0.01                              │
│    - Creator payout (99%): $X * 0.99                           │
│ 5. Log to AP2 settlement ledger (immutable)                    │
└────────────────────────────────────────────────────────────────┘

                            ↓

Day 31 (09:00 UTC): Stripe Connect Payout Initiation
┌────────────────────────────────────────────────────────────────┐
│ 1. Fetch Stripe Connect account ID from creator record         │
│ 2. Create Stripe Payout object:                                │
│    {                                                             │
│      "amount": 99_00 (cents, creator's 99%),                   │
│      "currency": "usd",                                         │
│      "destination": "acct_xxxxx" (creator's Stripe account),   │
│      "method": "instant" | "standard" (depends on tier),       │
│      "description": "AXIOM Payout - Jun 2026",                │
│      "metadata": {                                              │
│        "creator_id": "uuid-...",                               │
│        "period": "2026-06-01T00:00Z/2026-06-30T23:59Z",       │
│        "settlement_id": "settlement-uuid-...",                 │
│        "merkle_root": "sha256-hex-..."                         │
│      }                                                           │
│    }                                                             │
│ 3. Stripe processes (2-5 business days for standard ACH)       │
│ 4. On success: Mark payout as "initiated"                      │
│    On failure: Queue for manual review (see 5.2)               │
└────────────────────────────────────────────────────────────────┘

                            ↓

Day 33-37: Payout Settlement
┌────────────────────────────────────────────────────────────────┐
│ 1. Poll Stripe Payout status (daily)                           │
│ 2. On completion: Generate settlement proof                    │
│    (Merkle chain + Ed25519 signature from both parties)        │
│ 3. Creator receives email: "Your payout is complete"           │
│ 4. Store proof in immutable ledger (IPFS + database)           │
│ 5. Creator can verify: Dashboard → "See Proof"                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Creator → Substack OAuth → AXIOM Palantir → Stripe Connect

### 3.1 Trust Chain

```
Creator Substack Account
        │
        ├─ OAuth2 grant
        │  "Read my publications & subscribers"
        │
        └─→ AXIOM Creator Profile
            ├─ Publication metadata (name, topics, audience)
            ├─ Subscriber counts (free + paid)
            ├─ Engagement metrics (posts/month, open rates)
            │
            └─→ AXIOM Palantir (Personal)
                ├─ Creator identity (verified via OAuth)
                ├─ Risk tier (Personal / Professional / Defense)
                ├─ Creator's Stripe Connect account ID
                ├─ Payout preferences (instant vs standard ACH)
                │
                └─→ Stripe Connect
                    ├─ Creator's bank account (ACH)
                    ├─ Historical payouts
                    ├─ Account balance
                    └─→ Creator's Bank Account
                        "99% of earnings arrive here"
```

### 3.2 Stripe Connect Account Lifecycle

**Onboarding (Day 0):**
1. Creator clicks "Set up payouts" in dashboard
2. AXIOM creates Stripe Connect account on creator's behalf:
   ```
   POST https://api.stripe.com/v1/accounts
   {
     "type": "express",
     "country": "US" | "GB" | "DE" | ... (detected from IP),
     "email": creator@substack.com,
     "capabilities": {
       "transfers": { "requested": true },
       "card_payments": { "requested": false }
     }
   }
   ```
3. Stripe returns account ID (`acct_xxxxx`)
4. AXIOM stores in creator record (encrypted)
5. Creator completes onboarding at Stripe (bank info, identity)

**Account Verification (Day 1-5):**
- Stripe performs KYC/AML checks
- Creator may need to provide additional docs
- On verification complete: Capability enabled, ready for payouts

---

## 4. 99/1 Split: Architecture & Enforcement

### 4.1 Split Calculation & Validation

**Data Sources:**
1. **Audience Growth:** Posts/month from Substack, subscribers from OAuth
2. **Engagement Metrics:** Open rates, reply rates (estimated from Substack API)
3. **Monetization:** Platform fees, publisher revenue (from AP2 ledger)

**Formula:**
```
Gross Revenue = Sum of all creator earnings in period
Platform Fee (1%) = Gross Revenue * 0.01
Creator Payout (99%) = Gross Revenue * 0.99

Example:
Gross Revenue = $1,000
Platform Fee = $10
Creator Payout = $990
```

### 4.2 Enforcement Mechanisms

**Immutable AP2 Settlement Ledger:**

Each month's settlement is recorded in a cryptographically signed ledger:

```
Settlement Record:
{
  "settlement_id": "settlement-2026-06-uuid",
  "creator_id": "creator-uuid-...",
  "period_start": "2026-06-01T00:00:00Z",
  "period_end": "2026-06-30T23:59:59Z",
  "gross_revenue": 1000.00,
  "platform_fee_pct": 1,
  "platform_fee_amount": 10.00,
  "creator_payout_pct": 99,
  "creator_payout_amount": 990.00,
  "breakdown": {
    "posts_published": 12,
    "free_subscribers_added": 450,
    "paid_subscribers_added": 18,
    "engagement_score": 8.2
  },
  "ledger_hash": "sha256(previous_hash || this_record)",
  "timestamp": "2026-07-01T09:00:00Z"
}
```

**Ed25519 Signature (Both Parties):**

```
Signature {
  "signer": "axiom_platform" | "creator",
  "signed_content": sha256(settlement_record),
  "public_key": "ed25519_pubkey_hex",
  "signature_hex": "ed25519_signature_hex",
  "timestamp": "2026-07-01T09:15:00Z"
}
```

**Verification:**
- Creator can verify signature using AXIOM's public key
- AXIOM can verify creator's signature on acceptance
- Both signatures stored in immutable ledger

---

## 5. Payout Timing: Monthly ACH on Day 15

### 5.1 Scheduled Payout Trigger

**Cron Job:** Daily at 09:00 UTC

```rust
fn nightly_payout_trigger() {
  // Check if today is payout day (15th of month)
  if chrono::Local::now().day() == 15 {
    // Step 1: Fetch all creators with pending payouts
    let creators = db.query_creators_with_pending_payouts()
      .filter(|c| c.stripe_account_id.is_some())
      .filter(|c| c.status == "active")
      .collect();
    
    for creator in creators {
      // Step 2: Calculate payout amount
      let settlement = calculate_settlement(&creator, &last_month);
      
      // Step 3: Sign settlement record
      let signed = sign_settlement(&settlement, &axiom_signing_key);
      
      // Step 4: Initiate Stripe payout
      let payout = stripe_api.create_payout(
        creator.stripe_account_id,
        (settlement.creator_payout_amount * 100) as i64, // in cents
        PayoutMethod::Standard, // 2-5 business days
      );
      
      // Step 5: Log to behavioral firewall
      audit_log.record(CreatorPayoutInitiated {
        creator_id: creator.id,
        settlement_id: settlement.id,
        payout_id: payout.id,
        amount: settlement.creator_payout_amount,
        timestamp: now(),
      });
      
      // Step 6: Email creator
      email_service.send(
        creator.email,
        "payout_initiated",
        PayoutInitiatedEmail {
          name: creator.name,
          amount: settlement.creator_payout_amount,
          date_expected: estimate_ach_arrival(payout.created_at),
        }
      );
    }
  }
}
```

### 5.2 ACH Processing Timeline

| Date | Event | Action |
|------|-------|--------|
| **Day 15, 09:00 UTC** | Payout initiated to Stripe | Email: "Payout processing" |
| **Day 15-17** | ACH batch processing | Stripe batches and sends to creator's bank |
| **Day 17-19** | Bank clears ACH transfer | Creator's bank posts credit |
| **Day 19, 23:59 UTC** | Payout cleared (Stripe confirms) | Email: "Payout complete" + settlement proof |

**Test Timeline (Stripe Sandbox):**
- Use Stripe test keys: `sk_test_...` + `pk_test_...`
- Payout status updates instantly in sandbox (no 2-5 day delay)
- Test cases: successful ACH, insufficient balance, account locked

---

## 6. Stripe Sandbox Testing Protocol

### 6.1 Test Account Setup

```bash
# 1. Create test Stripe account (https://dashboard.stripe.com/test/accounts)
#    - Tier: Express (Creator payout)
#    - Country: United States
#    - Email: test-creator@example.com

# 2. Simulate completed identity verification (sandbox)
#    Stripe automatically verifies in test mode if phone matches pattern

# 3. Fund test account with test ACH balance
#    In Stripe dashboard: Balances → Add test funds → ACH transfer

# 4. Create test payout
curl -X POST https://api.stripe.com/v1/payouts \
  -H "Authorization: Bearer sk_test_..." \
  -d amount=99000 \
  -d currency=usd \
  -d method=instant
```

### 6.2 Test Scenarios

| Test Case | Input | Expected Behavior | Pass Criteria |
|-----------|-------|-------------------|---------------|
| **T1: Successful payout** | Valid Stripe account, sufficient balance | Payout created with `status: "succeeded"` | Settlement proof generated, email sent |
| **T2: Insufficient balance** | Stripe account with $0 balance | Payout fails with `status: "failed"` | Ops team alerted, retry scheduled for Day 16 |
| **T3: Account closed** | Creator's bank account closed | Stripe returns error code `account_closed` | Creator email: "Verify your bank account" |
| **T4: Rate limit** | 1000 payouts in 1 second | Stripe returns 429 Too Many Requests | Exponential backoff, retry with jitter |
| **T5: Network timeout** | Stripe API unreachable | Retry with exponential backoff (max 5 retries) | Payout marked as `pending`, retry queue checked hourly |
| **T6: Concurrent payouts** | 100 creators with payouts same day | All 100 processed in parallel | Stripe batch confirmed, settlement records for all 100 |

---

## 7. Settlement Records: Merkle-Audited & Signed

### 7.1 Merkle Chain Structure

Every settlement is appended to an immutable Merkle chain:

```
Genesis Block:
hash = sha256("0" || "genesis")
     = "8b8f8c8c2e8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c"

Settlement #1 (June 2026):
hash = sha256(genesis_hash || json(settlement_record))
     = "7f9e8d7c6b5a4938271615041302010f0e0d0c0b0a09080706050403020100"

Settlement #2 (July 2026):
hash = sha256(settlement_#1_hash || json(settlement_record))
     = "e1d2c3b4a59687f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a59687f8e9d0c1b"

...and so on (immutable chain)
```

### 7.2 Settlement Proof Document

Creator downloads as PDF after payout completes:

```
┌─────────────────────────────────────────────────────────┐
│         AXIOM PLATFORM SETTLEMENT PROOF                 │
│                                                          │
│ Settlement ID: settlement-2026-06-abc123xyz            │
│ Creator: Alice Sovereign (alice@substack.com)          │
│ Period: June 1 - June 30, 2026                         │
│ Payout Date: July 15, 2026                             │
│                                                          │
│ ╔═══════════════════════════════════════════════════╗  │
│ ║ FINANCIAL SUMMARY                                 ║  │
│ ║ Gross Revenue:         $1,000.00                 ║  │
│ ║ Platform Fee (1%):     -$10.00                   ║  │
│ ║ Creator Payout (99%):  $990.00 ✓                ║  │
│ ║ Stripe Transfer Fee:   $0.00 (waived first mo)  ║  │
│ ║ Net to Your Account:   $990.00                   ║  │
│ ╚═══════════════════════════════════════════════════╝  │
│                                                          │
│ ═══════════════════════════════════════════════════════  │
│ MERKLE CHAIN VERIFICATION                              │
│ ═══════════════════════════════════════════════════════  │
│                                                          │
│ Previous Settlement Hash:                              │
│ 7f9e8d7c6b5a4938271615041302010f0e0d0c0b0a09...  │
│                                                          │
│ This Settlement Hash:                                  │
│ e1d2c3b4a59687f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3... │
│                                                          │
│ Next Settlement Hash: (pending)                        │
│                                                          │
│ ═══════════════════════════════════════════════════════  │
│ CRYPTOGRAPHIC SIGNATURES                               │
│ ═══════════════════════════════════════════════════════  │
│                                                          │
│ Signed by AXIOM Platform (Ed25519)                    │
│ Date: 2026-07-01 09:15:00 UTC                        │
│ Signature:                                             │
│ 3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e... │
│                                                          │
│ Verified by Alice Sovereign on July 15, 2026          │
│ (Signature pending creator acceptance)                 │
│                                                          │
│ ═══════════════════════════════════════════════════════  │
│ PAYOUT DETAILS                                         │
│ ═══════════════════════════════════════════════════════  │
│                                                          │
│ Stripe Payout ID: po_1ABC123XYZ                       │
│ Payment Method: ACH Transfer                           │
│ Bank: ****4321 (First National)                       │
│ Initiated: July 1, 2026, 09:00 UTC                   │
│ Expected Arrival: July 3-5, 2026                      │
│ Actual Arrival: July 4, 2026 ✓                       │
│                                                          │
│ ═══════════════════════════════════════════════════════  │
│ DISPUTE RESOLUTION                                     │
│ ═══════════════════════════════════════════════════════  │
│                                                          │
│ Questions about this payout?                           │
│ Email: settlements@axiom.co                            │
│ Reference: settlement-2026-06-abc123xyz               │
│                                                          │
│ This document is immutable and tamper-evident.        │
│ Verification code: MERKLE:e1d2c3b4a59687f8e9d0c1b2a │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Error Handling & Retry Logic

### 8.1 Payout Failure Scenarios

**Scenario 1: Insufficient Balance in Stripe Account**

```
Stripe Response: {
  "error": {
    "code": "insufficient_funds",
    "message": "The account does not have sufficient balance for the requested transfer"
  }
}

AXIOM Action:
├─ Mark payout as "failed"
├─ Log to behavioral firewall: creator_payout_failed_insufficient_funds
├─ Alert ops team (Slack #payments-issues)
├─ Queue manual review task:
│  └─ Check creator's account for unusual activity
│  └─ Verify Stripe account is in good standing
├─ Send email to creator:
│  "Your payout for June couldn't complete. Our team is investigating.
│   We'll retry on July 16. No action needed."
└─ Retry at Day 16 (automatic)
```

**Scenario 2: Creator's Bank Account Closed**

```
Stripe Response: {
  "error": {
    "code": "account_closed",
    "message": "The specified account has been closed"
  }
}

AXIOM Action:
├─ Mark payout as "failed"
├─ Log to behavioral firewall: creator_payout_failed_account_closed
├─ Pause future payouts (flag: requires_reconnection)
├─ Send email to creator:
│  Subject: "Your bank account is no longer active"
│  Body: "We tried to send your June payout ($990) but your bank account 
│         is closed. Please verify your bank details:"
│  CTA: "Update Bank Account"
├─ Creator clicks link → Update bank via Stripe
└─ Resume payouts on Day 1 of next month
```

**Scenario 3: Stripe API Timeout**

```
AXIOM Action:
├─ Retry immediately (exponential backoff: 1s, 2s, 4s, 8s, 16s)
├─ If still failing after 5 retries:
│  └─ Mark payout as "pending" (not failed)
│  └─ Queue for manual review (Ops team)
│  └─ Send email to Ops: "Payout stuck in retry queue"
├─ Automatic retry every hour for 24 hours
├─ If not resolved after 24 hours:
│  └─ Escalate to Ops (PagerDuty)
│  └─ Creator can click "Manual Payout Request" in dashboard
└─ Resolution: Ops manually initiates via Stripe dashboard
```

### 8.2 Retry Queue Mechanism

```
Payout Retry Queue (PostgreSQL):
┌─────────────────────────────────────────┐
│ payout_retries table                    │
├─────────────────────────────────────────┤
│ id                   (UUID)              │
│ creator_id           (UUID)              │
│ settlement_id        (UUID)              │
│ stripe_account_id    (STRING)            │
│ payout_amount_cents  (INT)               │
│ status               ("pending"|"done")  │
│ retry_count          (INT, max 5)        │
│ last_error           (STRING)            │
│ next_retry_at        (TIMESTAMP)         │
│ created_at           (TIMESTAMP)         │
│ updated_at           (TIMESTAMP)         │
└─────────────────────────────────────────┘

Backoff Strategy:
Retry 1: Immediate
Retry 2: +1 second (jitter ±10%)
Retry 3: +2 seconds (jitter ±10%)
Retry 4: +4 seconds (jitter ±10%)
Retry 5: +8 seconds (jitter ±10%)
Retry 6: +1 hour (manual review required)
```

---

## 9. Monitoring & Alerts

### 9.1 Key Metrics

| Metric | Alert Threshold | Owner | Action |
|--------|-----------------|-------|--------|
| `payout_success_rate` | <95% daily | Payments | Investigate failures, check Stripe status |
| `payout_mean_delay` | >2 hours | Payments | Investigate queue, check Stripe API latency |
| `failed_payout_count` | >10 | Ops | Page on-call, manual review |
| `retry_queue_size` | >50 | Ops | Escalate to Stripe support |
| `settlement_record_lag` | >5 min | Backend | Check database, audit logging |
| `merkle_chain_integrity` | Any break | Security | CRITICAL: Chain compromise detected |

### 9.2 Dashboard View (Payments Team)

```
╔════════════════════════════════════════════════════════════════╗
║                  AXIOM PAYOUT DASHBOARD (Jun 15, 2026)        ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║ TODAY'S PAYOUTS (Day 15)                                      ║
║ ═══════════════════════════════════════════════════════════   ║
║ Total Creators:        147                                    ║
║ Payouts Initiated:     147 ✓                                  ║
║ Payouts Succeeded:     145 ✓                                  ║
║ Payouts Failed:        2 ⚠️                                   ║
║ Payouts Pending:       0                                      ║
║                                                                 ║
║ Total Payout Value:    $146,430.00 (99% of $147,909.09)    ║
║ Platform Fees:        $1,479.09 (1%)                         ║
║                                                                 ║
║ FAILED PAYOUTS (2)                                            ║
║ ─────────────────────────────────────────────────────────────  ║
║ Creator: Bob Pioneer                                           ║
║ Amount: $890.10                                               ║
║ Error: account_closed (bank account closed)                   ║
║ Status: Requires action                                       ║
║ Action: [View Details] [Send Email] [Manual Override]         ║
║                                                                 ║
║ Creator: Carol Visionary                                       ║
║ Amount: $1,340.50                                             ║
║ Error: insufficient_funds (Stripe account balance $0)        ║
║ Status: Queued for retry (next: Jul 1)                        ║
║ Action: [View Details] [Force Retry Now] [Contact Creator]    ║
║                                                                 ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 10. Security & Compliance

### 10.1 PCI-DSS Considerations

- **No card data:** We only handle ACH, not credit cards
- **Bank account masking:** Stored as `****4321`, never full number
- **Encryption at rest:** AES-256-GCM for Stripe account IDs
- **HTTPS only:** All Stripe API calls over TLS 1.3+

### 10.2 Audit Trail (Behavioral Firewall)

Every payout event logged:

```rust
AuditEvent {
  event_type: "creator_payout_initiated" | "creator_payout_succeeded" 
              | "creator_payout_failed" | "creator_payout_retried",
  creator_id: uuid::Uuid,
  settlement_id: uuid::Uuid,
  stripe_payout_id: String,
  amount_cents: i64,
  status: "pending" | "succeeded" | "failed" | "cancelled",
  error_code: Option<String>,
  retry_count: u8,
  timestamp: chrono::DateTime<Utc>,
}
```

### 10.3 Regulatory Compliance

- **SOX 404:** Payout processes are auditable (Merkle chain)
- **GDPR:** Creator can request deletion (payout data retained for 7 years, per law)
- **FinCEN:** AML/KYC performed by Stripe (we don't duplicate)
- **Stripe Connect:** Complies with all US payment regulations

---

## 11. Implementation Checklist

- [ ] Integrate Stripe Python/Node SDK
- [ ] Implement settlement calculation & signing
- [ ] Implement Merkle chain appending logic
- [ ] Implement `/api/v1/creator/stripe-connect/onboard` endpoint
- [ ] Implement `/api/v1/creator/stripe-connect/status` endpoint
- [ ] Implement nightly payout trigger (cron job)
- [ ] Implement retry queue with exponential backoff
- [ ] Implement settlement proof PDF generation
- [ ] Implement Stripe webhook handlers (payout.created, payout.updated)
- [ ] Add behavioral firewall logging for all payout events
- [ ] Create test harness (Stripe sandbox)
- [ ] Load test: 150 payouts simultaneously
- [ ] Security audit: PCI-DSS compliance checklist
- [ ] Deploy to staging (Aug 1, 2026)
- [ ] Go-live: Aug 15, 2026

---

## 12. References

- Stripe Connect Documentation: https://stripe.com/docs/connect
- Stripe Payouts API: https://stripe.com/docs/api/payouts
- ACH Transfer Timeline: https://www.federalreserve.gov/paymentsystems/pch/
- Merkle Tree Auditing: RFC 9162 (CT v2.0)
