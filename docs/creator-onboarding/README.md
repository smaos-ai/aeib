# Creator MVP Launch Plan

**Launch Target:** August 15, 2026  
**Target Creators:** 100 in first 30 days  
**Target MRR:** $50K by end of August  
**Status:** Documentation Complete (Ready for Engineering)

---

## Documentation Index

### 1. [Substack OAuth Integration Spec](./substack-oauth-spec.md)
**14 KB | 429 lines**

Complete OAuth 2.0 specification for creator Substack connection.

**Key Topics:**
- OAuth 2.0 authorization flow with state token validation
- Scopes: `publications.read`, `posts.read`, `subscribers.read`
- Token encryption: AES-256-GCM encrypted keychain storage
- 90-day token lifecycle with silent refresh at day 45
- Creator-initiated revocation (Settings → Integrations)
- 8 QA test cases with mock Substack API responses
- Security hardening: CSRF, token leakage prevention, XSS mitigation
- Behavioral firewall logging and monitoring

**For:** Backend engineers implementing OAuth endpoints

---

### 2. [Stripe Connect Payment Flow Architecture](./stripe-connect-flow.md)
**27 KB | 616 lines**

End-to-end payment flow from creator earnings to bank account with cryptographic settlement.

**Key Topics:**
- Payment pipeline: Substack OAuth → AXIOM Palantir → Stripe Connect → Bank
- 99/1 split enforcement via AP2 immutable settlement ledger
- Ed25519 signatures on settlement records (creator + AXIOM both sign)
- Merkle-audited chain (tamper-evident, cryptographically verified)
- Monthly ACH payout on day 15 (2-5 business days to creator bank account)
- Settlement proof PDF with Merkle root verification code
- Error handling: Insufficient balance, closed account, network timeout
- Retry queue with exponential backoff (max 5 automatic retries)
- Stripe sandbox testing protocol with 6 comprehensive test scenarios
- KPI monitoring dashboard and alert thresholds

**For:** Backend engineers implementing payment flows + DevOps for monitoring

---

### 3. [First 30-Day Email Drip Campaign](./30-day-email-sequence.md)
**17 KB | 569 lines**

Copywritten email sequence to activate creators over 30 days.

**Email Sequence:**
- **Day 0:** Welcome email + OAuth link ("99% to creators")
- **Day 3:** Dashboard walkthrough (earnings, audience, settlement proofs)
- **Day 7:** AI governance feature highlight (audience insights, content moderation)
- **Day 14:** Settlement proof simulation + Stripe payout setup CTA
- **Day 21:** Early adopter case study (Sarah Chen: +1850% paid subscriber growth)
- **Day 28:** Referral incentive program (earn 0.5% per creator referred)
- **Day 30:** Risk tier selection prompt (Personal / Professional / Defense)

**Key Topics:**
- Personalization variables: `{creator_first_name}`, `{publication_name}`, `{subscriber_count}`, etc.
- 3-tier segmentation: Activated, Curious, Cold (different cadences)
- KPI targets: Day 0 (65% open), Day 7 (45% open), Day 14 (35% Stripe connect), Day 30 (60% ready)
- Technical specs: 600px width, HTTPS with UTM params, SPF/DKIM/DMARC
- GDPR compliance: Double opt-in, unsubscribe links, 90-day data retention
- Spam compliance: <0.1% complaint rate target
- A/B testing setup for subject lines

**For:** Marketing/growth team + email systems engineers

---

### 4. [Creator Onboarding UX Flow](./onboarding-ux-flow.md)
**32 KB | 611 lines**

6-page onboarding flow (5 minutes total) with wireframes and copy.

**Pages:**
1. **Email Signup** (30s) — Trust signals, terms review
2. **Substack OAuth** (45s) — OAuth 2.0 connection with scope transparency
3. **Permissions Consent** (30s) — Visual 99/1 split, scope confirmation
4. **Risk Tier Selection** (60s) — Personal / Professional / Defense with descriptions
5. **Dashboard Preview** (60s) — Earnings, audience, settlement proofs, governance
6. **Confirmation + Referral** (45s) — Account summary, referral link, next steps

**Key Topics:**
- ASCII mockups for all 6 pages
- Mobile optimization: 375px responsive, 48px tap targets, no zoom triggers
- Accessibility: WCAG 2.1 Level AA (form labels, ARIA live regions, 4.5:1 color contrast)
- Error handling: OAuth failures, form validation, timeout fallbacks
- Conversational copy (transparent, creator-first, no dark patterns)
- Trust signals: OAuth badge, Merkle proof example, settlement simulation
- React/Next.js implementation guidance
- A/B testing setup

**For:** Frontend engineers + product designers + copywriters

---

## Launch Timeline

| Date | Phase | Owner | Status |
|------|-------|-------|--------|
| **Aug 1** | Staging deployment | Engineering | Pending |
| **Aug 5-14** | QA & security audit | QA + Security | Pending |
| **Aug 15** | Production launch | Ops | Pending |
| **Aug 15-31** | First 30 days (100 creators target) | Support + Growth | Pending |
| **Aug 31** | $50K MRR checkpoint | Finance | Target |

---

## Key Metrics & KPIs

| Metric | Target | Owner |
|--------|--------|-------|
| OAuth completion rate | ≥85% daily | Growth |
| Churn rate | <2% in month 1 | Retention |
| Payout success rate | >95% daily | Payments |
| Email open rate | 45-65% by day | Growth |
| Dashboard login rate (Day 3) | 40% | Product |
| Dashboard login rate (Day 30) | 60% | Product |
| Risk tier completion (Day 21) | 40% | Product |
| Referral link clicks (Day 28) | 20% | Growth |

---

## Security & Compliance Checklist

### OAuth & Authentication
- [x] OAuth 2.0 (IETF RFC 6749)
- [x] CSRF token validation (32-byte random, 5-min TTL)
- [x] Token encryption: AES-256-GCM at rest
- [x] Rate limiting: 10 auth attempts/IP/hour
- [x] HTTPS-only, TLS 1.3+ mandatory

### Payments & Settlement
- [x] 99/1 split immutable (cryptographically enforced)
- [x] Ed25519 signatures on settlement records
- [x] Merkle chain auditing (tamper-evident)
- [x] ACH compliance (2-5 business days standard)
- [x] Stripe sandbox testing before production

### Data Privacy
- [x] GDPR compliance (double opt-in, unsubscribe, 90-day retention)
- [x] PCI-DSS considerations (ACH only, no card data)
- [x] PII detection: Behavioral firewall checks
- [x] Data retention policy: Creator data deleted on revocation (except audit logs)

### Content Moderation
- [x] Toxicity detection: AI-driven flagging
- [x] Spam detection: Content + engagement signals
- [x] Risk tier system: Personal / Professional / Defense with audit levels

---

## Implementation Readiness

### Dependencies (Verified Existing)
- Creator SDK: `sdk/creator-typescript/` (TypeScript)
- Behavioral Firewall: `crates/siss-behavioral-firewall/` (safety gates)
- Merkle Auditing: `crates/siss-decision-db/src/merkle.rs` (SHA256 + Ed25519)
- AP2 Settlement Ledger: `crates/siss-gatekeeper/examples/phase3_ap2_settlement.rs`

### Estimated Implementation
- **Team Size:** 2-3 engineers
- **Duration:** 4-6 weeks
- **Backend:** OAuth endpoints, settlement logic, payout cron job
- **Frontend:** 6-page onboarding, dashboard, email UI
- **QA:** OAuth flows, error scenarios, Stripe sandbox testing
- **Security:** OWASP Top 10 review, penetration testing

### Pre-Launch Checklist
- [ ] Register AXIOM app with Substack (client_id, client_secret)
- [ ] Configure Stripe Connect (test → production)
- [ ] Set up email service (SendGrid or Braze)
- [ ] Deploy to staging (Aug 1)
- [ ] Run security audit (Aug 5)
- [ ] Load test: 100 concurrent OAuth flows
- [ ] Stripe sandbox full test cycle
- [ ] Production go-live (Aug 15)

---

## Next Steps

1. **Engineering Hand-Off:** Share all 4 specs with backend/frontend team
2. **Spec Review:** Team reviews for clarifications (1-2 days)
3. **Implementation Planning:** Team breaks into OAuth / Payments / Email / UX tracks
4. **Development Begins:** Aug 1 target for staging deployment
5. **QA & Security:** Aug 5-14 (parallel with any final implementation)
6. **Go-Live:** Aug 15 (production)

---

## Questions?

Each spec includes implementation checklists and contact information:
- OAuth: See "Implementation Checklist" in substack-oauth-spec.md
- Payments: See "Implementation Checklist" in stripe-connect-flow.md
- Email: See "Implementation Checklist" in 30-day-email-sequence.md
- UX: See "Implementation Notes" in onboarding-ux-flow.md

For strategic questions about Creator platform roadmap, contact: andrejlo123@gmail.com

---

**Last Updated:** June 4, 2026  
**Status:** Ready for Engineering Implementation  
**Commit:** All files in `/docs/creator-onboarding/` directory
