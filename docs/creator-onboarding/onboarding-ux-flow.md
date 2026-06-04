# Creator Onboarding UX Flow

**Target Launch:** August 15, 2026  
**Scope:** 6-page signup & profile setup  
**Status:** Wireframe descriptions + copy

---

## Overview

The onboarding flow transforms a cold visitor into an active creator in ~5 minutes. Each page has one decision, clear copy, and a visible trust signal (OAuth badge, Merkle proof, settlement example).

**Key Principle:** No dark patterns. Every field is optional or explained. Creator controls what they share.

---

## PAGE 1: Email Signup

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║                                                   ║  │
│  ║              AXIOM CREATOR PLATFORM              ║  │
│  ║                                                   ║  │
│  ║  99% to creators. 1% platform fee. That's it.    ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Email                                           │   │
│  │ [                                              ]│   │
│  │                                                 │   │
│  │ [CREATE ACCOUNT]  ──→ Continue                 │   │
│  │                                                 │   │
│  │ By signing up, you agree to:                   │   │
│  │ • Terms of Service                              │   │
│  │ • Privacy Policy                                │   │
│  │ • Creator Code of Conduct                       │   │
│  │ (You can see all three before confirming.)      │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  Already have an account? [LOG IN]                      │
│                                                           │
│  Questions? Email hello@axiom.co                        │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "99% to creators. 1% platform fee. That's it."

**Subheading:** "Create your AXIOM account in 30 seconds."

**CTA Button:** "CREATE ACCOUNT"

**Trust Signals:**
- "Used by 147 Substack creators"
- "Trust Score: 4.8/5 (Creator reviews)"
- "Settlement proofs signed by both parties"

### Form Validation

- Email must be valid format
- Error message (inline, red text): "Please enter a valid email"
- Success state: Checkmark icon, proceed to Page 2

---

## PAGE 2: "Connect Your Substack"

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ STEP 2 OF 6: CONNECT YOUR AUDIENCE              ║  │
│  ║                                                   ║  │
│  ║ [✓ Email] → [⭘ Connect Substack] → [ ] Payouts  ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ YOUR PUBLICATIONS                               │   │
│  │                                                 │   │
│  │ Connect your Substack account to let us read:   │   │
│  │ • Publication name & description                │   │
│  │ • Subscriber counts (free & paid)               │   │
│  │ • Post frequency & topics                       │   │
│  │                                                 │   │
│  │ We NEVER:                                       │   │
│  │ ✓ Post on your behalf                           │   │
│  │ ✓ Access your subscriber email list             │   │
│  │ ✓ Sell your audience data                       │   │
│  │ ✓ Modify your posts or settings                 │   │
│  │                                                 │   │
│  │  [CONNECT WITH SUBSTACK OAUTH]  ──→ Substack   │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  Questions about privacy?                               │
│  [See our OAuth & Data Handling Policy]                 │
│                                                           │
│  [SKIP FOR NOW]  (But you'll need this for payouts)     │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "Connect your Substack"

**Subheading:** "We read your audience metadata. We never touch your posts or subscribers."

**OAuth Button:** "CONNECT WITH SUBSTACK OAUTH"

**Trust Signals:**
- "OAuth 2.0 secure connection"
- "Your tokens are encrypted at rest"
- "You can disconnect anytime (Settings → Integrations)"
- Checkmark list: "We NEVER..."

**Fallback (if OAuth fails):**
```
⚠️ Something went wrong connecting to Substack.
Error: [connection_timeout | invalid_scope | etc.]

What to try:
1. Refresh this page
2. Make sure you're logged into Substack in another tab
3. Check that your Substack account hasn't been deleted

[TRY AGAIN]

Still stuck? Email us: support@axiom.co
```

---

## PAGE 3: Permissions Consent + Split Visualization

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ STEP 3 OF 6: CONFIRM PERMISSIONS                ║  │
│  ║                                                   ║  │
│  ║ [✓ Email] → [✓ Substack] → [⭘ Confirm] →      ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ AXIOM WILL READ (SUBSTACK OAUTH SCOPE):         │   │
│  │                                                 │   │
│  │ ✓ publications.read   (Your publication info)   │   │
│  │ ✓ posts.read          (Your post titles/dates)  │   │
│  │ ✓ subscribers.read    (Free & paid counts)      │   │
│  │                                                 │   │
│  │ AXIOM WILL NOT REQUEST:                         │   │
│  │ ✗ posts.write         (Never post for you)      │   │
│  │ ✗ subscribers.modify  (Never change your list) │   │
│  │ ✗ billing.read        (Your Substack revenue)  │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ THE 99/1 SPLIT (EVERY PAYOUT)                  │   │
│  │                                                 │   │
│  │  Example: You earn $1,000 in a month            │   │
│  │                                                 │   │
│  │  ██████████████████████ 99%                    │   │
│  │  You get: $990 (to your bank account)          │   │
│  │                                                 │   │
│  │  █ 1%                                           │   │
│  │  AXIOM takes: $10 (platform fee)               │   │
│  │                                                 │   │
│  │  This split is guaranteed. Signed in every     │   │
│  │  settlement proof.                              │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  [I UNDERSTAND & CONSENT]  ──→ Continue               │   │
│                                                           │
│  Questions about the split? [See settlement examples]   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "Confirm permissions & see the 99/1 split"

**Subheading:** "Everything is transparent. Here's exactly what we read and why."

**CTA Button:** "I UNDERSTAND & CONSENT"

**Trust Signals:**
- Checkmark list of what we read
- X list of what we don't request
- Visual 99/1 bar chart
- Link to settlement examples
- Explicit guarantee: "This split is signed in every settlement proof"

---

## PAGE 4: Risk Tier Selection

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ STEP 4 OF 6: CHOOSE YOUR RISK TIER              ║  │
│  ║                                                   ║  │
│  ║ [✓] [✓] [✓] → [⭘ Risk Tier] → [ ] Payouts     ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ AXIOM audits your content using AI governance.  │   │
│  │ Pick a tier that matches your content.          │   │
│  │ (You can change this later.)                     │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🟢 PERSONAL (Default)                           │   │
│  │                                                 │   │
│  │ For hobbyists, community builders, lifestyle    │   │
│  │ creators with mainstream content.               │   │
│  │                                                 │   │
│  │ Auditing: Standard (toxicity, spam, PII check) │   │
│  │ Your Payout: 99%                                │   │
│  │ Ideal for: <5K subscribers, experimental       │   │
│  │                                                 │   │
│  │ ☐ SELECT PERSONAL                               │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🟡 PROFESSIONAL                                 │   │
│  │                                                 │   │
│  │ For journalists, thought leaders, analysts      │   │
│  │ covering business, politics, tech, policy.      │   │
│  │                                                 │   │
│  │ Auditing: Strict (legal risk, IP, defamation)  │   │
│  │ Your Payout: 99% + 0.25% bonus                 │   │
│  │ Ideal for: 5K-50K subscribers, professional    │   │
│  │                                                 │   │
│  │ ☐ SELECT PROFESSIONAL                           │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🔴 DEFENSE                                      │   │
│  │                                                 │   │
│  │ For security researchers, policy experts,       │   │
│  │ journalists in conflict zones, high-stakes      │   │
│  │ investigative work.                             │   │
│  │                                                 │   │
│  │ Auditing: Maximum (full behavioral firewall,    │   │
│  │ anomaly detection, witness attestation)         │   │
│  │ Your Payout: 99% + 1% bonus                     │   │
│  │ Ideal for: High-risk content, adversarial env   │   │
│  │                                                 │   │
│  │ ☐ SELECT DEFENSE                                │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  [CONTINUE WITH SELECTION]  ──→ Next              │   │
│                                                           │
│  Still unsure? [See tier comparison]                    │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "Choose your risk tier"

**Subheading:** "AXIOM audits your content. Pick the tier that matches your work."

**Tier Colors:**
- Personal: Green (safe, mainstream)
- Professional: Yellow (careful, high-value)
- Defense: Red (critical, high-stakes)

**Tier Details Include:**
- Who it's for (audience persona)
- What we audit (specific risks)
- Your payout % (includes bonus)
- Ideal subscriber range

**CTA Button:** "CONTINUE WITH SELECTION"

**Fallback Option:** "Still unsure? We'll start you with Personal. You can upgrade anytime."

---

## PAGE 5: Dashboard Preview

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ STEP 5 OF 6: YOUR DASHBOARD                      ║  │
│  ║                                                   ║  │
│  ║ [✓] [✓] [✓] [✓] → [⭘ Dashboard] → [ ] Invite   ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  Here's what you'll see when you log in.                │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📊 EARNINGS (This Month)                        │   │
│  │                                                 │   │
│  │ Your Gross Revenue:     $0 (posts start earning │   │
│  │ AXIOM Fee (1%):         $0   after 48 hours)    │   │
│  │ Your Payout (99%):      $0                      │   │
│  │                                                 │   │
│  │ Next Payout Date: Aug 15 (manual, then monthly) │   │
│  │ Payout Method: ACH Transfer (2-5 business days) │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 👥 YOUR AUDIENCE (from Substack)                │   │
│  │                                                 │   │
│  │ Free Subscribers: 1,234                         │   │
│  │ Paid Subscribers: 45                            │   │
│  │                                                 │   │
│  │ 📈 Growth: +212 free (+20%), +8 paid (+21%)    │   │
│  │    (Last 30 days)                               │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🔐 YOUR SETTLEMENT PROOFS                       │   │
│  │                                                 │   │
│  │ [Jun 2026 Settlement] [View PDF] [Verify]       │   │
│  │ Gross: $1,234 | Fee: $12.34 | Payout: $1,221.66│   │
│  │ Status: ✓ Signed by AXIOM & You                 │   │
│  │                                                 │   │
│  │ [Show older payouts...]                         │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🛡️ YOUR GOVERNANCE (AI Auditing)               │   │
│  │                                                 │   │
│  │ Risk Tier: PROFESSIONAL                         │   │
│  │                                                 │   │
│  │ Content Audits:                                 │   │
│  │ ✓ Toxicity Detection: PASS (0.2%)              │   │
│  │ ✓ PII Detection: PASS (no personal data)        │   │
│  │ ✓ Legal Risk Scan: PASS (0 issues)              │   │
│  │                                                 │   │
│  │ [See detailed audit logs]                       │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  More features:                                         │
│  • AI Governance Recommendations                       │
│  • Audience Insight Engine                             │
│  • Merkle Proof Verification                           │
│  • Referral Dashboard                                  │
│                                                           │
│  [CONTINUE]  ──→ Next Step                              │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "Here's your dashboard"

**Subheading:** "Everything you need to see: earnings, audience, proofs, and AI governance."

**Section Headings:**
- "Earnings (This Month)"
- "Your Audience (from Substack)"
- "Your Settlement Proofs"
- "Your Governance (AI Auditing)"

**Trust Signals:**
- Real-time earnings display
- Subscriber counts (verified via OAuth)
- Settlement proof examples
- Audit logs (toxicity score, PII detection)

**CTA Button:** "CONTINUE"

---

## PAGE 6: Confirmation + Invite Friends Link

### Visual Layout

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ STEP 6 OF 6: WELCOME TO AXIOM                   ║  │
│  ║                                                   ║  │
│  ║ [✓] [✓] [✓] [✓] [✓] → [⭘ Complete]            ║  │
│  ║                                                   ║  │
│  ╚═══════════════════════════════════════════════════╝  │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │         ✓ YOUR ACCOUNT IS READY!               │   │
│  │                                                 │   │
│  │  Account Name: alice@substack.com              │   │
│  │  Publication: "The Sovereign Stack"             │   │
│  │  Risk Tier: PROFESSIONAL                        │   │
│  │  Substack Connected: ✓                          │   │
│  │  Payout Ready: (After bank setup on Day 1)      │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  What's next?                                           │
│                                                           │
│  1. Check your email (Day 0)                           │
│     We sent a welcome email with useful links.         │
│                                                           │
│  2. Set up your bank account (by Day 7)                │
│     Settings → Payout → Connect Stripe                 │
│                                                           │
│  3. Start exploring your dashboard                     │
│     [GO TO DASHBOARD]  ──→ creator.axiom.co/app      │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🤝 INVITE FRIENDS & EARN                        │   │
│  │                                                 │   │
│  │ Know creators like you? Earn 0.5% per referral. │   │
│  │                                                 │   │
│  │ Your Referral Link:                             │   │
│  │ https://axiom.co/ref/abc123xyz                  │   │
│  │                                                 │   │
│  │ [COPY LINK]  [SHARE ON TWITTER]  [EMAIL FRIEND]│   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  Questions?                                             │
│  • Dashboard Help: [See docs]                          │
│  • OAuth Issues: [Reconnect Substack]                  │
│  • Technical Support: support@axiom.co                 │
│  • Chat with us: [Open live chat]                      │
│                                                           │
│  [GO TO DASHBOARD]                                      │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Copy

**Headline:** "Welcome to AXIOM!"

**Subheading:** "Your account is ready. Here's what's next."

**Confirmation Details:**
- Account name (email)
- Publication name
- Risk tier selected
- Connection status (Substack ✓, Payouts pending)

**Next Steps:**
1. Check email for welcome message
2. Set up bank account (by Day 7)
3. Explore your dashboard

**Referral Section:**
- Headline: "Invite friends & earn 0.5% per referral"
- Your unique referral link (copyable)
- Share buttons: Twitter, Email, Copy
- Explanation: "They sign up with your link. You earn when they do their first payout."

**CTA Buttons:**
- Primary: "GO TO DASHBOARD"
- Secondary: "COPY REFERRAL LINK"
- Tertiary: "SHARE ON TWITTER"

**Trust Signals:**
- Checkmark for completed setup
- Timeline: "Day 0 (today), Day 7 (bank setup), Day 15 (first payout)"
- Support links: "Questions? We're here."

---

## Flow Summary

| Page | Title | Decision | Flow Time |
|------|-------|----------|-----------|
| **1** | Email Signup | Sign up with email | 30s |
| **2** | Connect Substack | Authorize OAuth | 45s |
| **3** | Confirm Permissions | Accept 99/1 split | 30s |
| **4** | Risk Tier | Choose Personal/Prof/Defense | 60s |
| **5** | Dashboard Preview | See what's inside | 60s |
| **6** | Complete + Invite | Go live + share referral | 45s |
| **TOTAL** | — | — | **≈5 minutes** |

---

## Cross-Page Elements

### Header (All Pages)

```
┌─────────────────────────────────────────────────────────┐
│ AXIOM LOGO    STEP X OF 6: [Title]      [? Help] [⚙️ Settings] │
└─────────────────────────────────────────────────────────┘
```

### Progress Bar (All Pages)

Visual bar showing 6 steps:
```
[✓] [✓] [✓] [⭘] [ ] [ ]
│    │    │    │   │  │
E    S    P    RT  DP Inv
```

### Footer (All Pages)

```
Privacy Policy | Terms of Service | Creator Code | Contact Us | @axiom_creators
```

---

## Mobile Optimization

- **Breakpoint:** 375px (iPhone SE)
- **Layout:** Single column, full width
- **Buttons:** 48px tap target (accessibility)
- **Progress bar:** Vertical timeline on mobile
- **Input fields:** Font-size 16px+ (no zoom trigger)
- **Images:** Responsive (max-width: 100%)

---

## Accessibility Compliance

- **WCAG 2.1 Level AA**
- Form labels: Associated with `<label for="id">` tags
- Error messages: ARIA live region (`aria-live="polite"`)
- Color contrast: 4.5:1 minimum
- Skip links: "Skip to main content"
- Keyboard navigation: Tab order logical, all buttons focusable

---

## Error Handling

### Page 2: OAuth Failure

```
⚠️ Couldn't connect to Substack

Error: [connection_timeout | invalid_grant | scope_mismatch]

Troubleshooting:
1. Make sure you're logged into Substack in another tab
2. Refresh this page
3. Try a different browser

[TRY AGAIN]  [EMAIL SUPPORT]
```

### Page 4: Risk Tier Not Selected

```
⚠️ Please select a risk tier

(Don't worry, you can change it later.)

[SELECT A TIER ABOVE]
```

### Page 5: Dashboard Not Loading

```
⚠️ Dashboard preview is temporarily unavailable

You can still continue. Your dashboard will be ready 
when you log in tomorrow.

[CONTINUE ANYWAY]  [RETRY]
```

---

## Implementation Notes

- **Framework:** React/Next.js (page-based routing, server-side form handling)
- **Form Validation:** Client-side (instant feedback) + server-side (on submit)
- **State Management:** URL params + localStorage (survives refresh)
- **Analytics:** Track page completion, dropoff, time spent
- **A/B Testing:** Page 1 subject line variations (99/1 split vs. "Creator-First Platform")

---
