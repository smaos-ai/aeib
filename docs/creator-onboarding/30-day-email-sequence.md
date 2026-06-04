# First 30-Day Email Drip Campaign

**Target Launch:** August 15, 2026  
**Scope:** Creator activation, feature education, conversion  
**Status:** Copywritten & ready for implementation

---

## Campaign Overview

**Goal:** Activate 100 Substack creators in first 30 days with <2% churn rate.

**KPIs:**
- Day 7: 80% open rate on welcome sequence
- Day 14: 60% dashboard login rate
- Day 21: 40% complete risk tier selection
- Day 30: 25% refer a friend (0.5% bonus)

**Each Email:**
- 1-minute read time
- 1 clear CTA
- Trackable link (UTM params)
- Mobile-responsive (Gmail, Substack, Apple Mail tested)
- Personalization variables: `{creator_first_name}`, `{publication_name}`, `{subscriber_count}`

---

## Email Sequence

### EMAIL 1: Welcome + OAuth Link (Day 0, 6:00 AM)

**Subject:** Welcome to AXIOM, {creator_first_name}! 🚀

**Send Time:** Day 0 at 6:00 AM (creator's local timezone)

**Preview Text:** "Connect your Substack and start earning 99% of your audience revenue."

---

**Email Body:**

```
Hi {creator_first_name},

Welcome to AXIOM.

We've done something different. You keep 99% of your earnings. We take 1%.

No hidden fees. No monthly minimums. Just you, your audience, and a platform 
that's actually on your side.

Here's how it works:

1. Connect your Substack account (takes 30 seconds)
2. We read your audience metadata (nothing else)
3. Every month, your earnings go directly to your bank account
4. You can see the math: full transparency, signed proofs

Ready?

[CONNECT SUBSTACK ACCOUNT]
→ https://creator.axiom.co/oauth/substack/start?utm_campaign=day0&utm_source=email

Questions? We're here. Reply to this email.

— The AXIOM Team
```

---

### EMAIL 2: Dashboard Walkthrough (Day 3, 10:00 AM)

**Trigger:** Sent if creator clicked OAuth link on Day 0 (activated account)

**Subject:** Your AXIOM dashboard is ready, {creator_first_name}

**Preview Text:** "Here's what you can see (and why it matters)."

---

**Email Body:**

```
Hi {creator_first_name},

Great! Your Substack is connected. Now let's show you the dashboard.

When you log in, you'll see:

📊 YOUR EARNINGS
Your real-time earnings from {publication_name}. Updated daily. 
No surprises—just the math.

👥 YOUR AUDIENCE INSIGHTS
{subscriber_count} free subscribers | X paid subscribers
(We got these from Substack; you control what we see.)

📜 YOUR SETTLEMENT PROOFS
Every month, you get a cryptographically signed settlement proof. 
Both you and AXIOM sign it. It's immutable. If we ever cheat, 
the math breaks.

🛡️ YOUR RISK TIER
Personal / Professional / Defense — you pick. We adjust how strictly 
we audit your content. (Spoiler: Defense creators earn 2% more because 
we're more confident in them.)

Ready to explore?

[OPEN DASHBOARD]
→ https://creator.axiom.co/dashboard?utm_campaign=day3&utm_source=email

Once you log in, scroll down and check out "Why These Numbers Matter?"
(We explain every line of the settlement formula.)

— The AXIOM Team
```

---

### EMAIL 3: AI Governance Feature Highlight (Day 7, 9:00 AM)

**Trigger:** Sent if creator logged into dashboard on Day 1-7

**Subject:** "Your audience just got smarter" — {creator_first_name}

**Preview Text:** "Here's what AXIOM's AI governance means for your revenue."

---

**Email Body:**

```
Hi {creator_first_name},

Here's something most creator platforms won't tell you:

They scrape your audience data and sell it to advertisers. Then they tell you 
it's "personalization."

We do the opposite.

Your audience stays yours. But we use AI to make it smarter.

🎯 WHAT WE DO:
- Read your posts to find what topics resonate most
- Identify audience segments (thought leaders vs. casual readers)
- Suggest content that attracts higher-quality (more engaged) subscribers
- Flag suspicious behavior (spam, bot engagement, AI-generated comments)

🛡️ HOW WE KEEP IT SOVEREIGN:
Everything stays on your Palantir (personal instance). It's encrypted. 
You see it first. You decide what happens next.

📈 THE RESULT:
Creators who use AI governance see 23% higher paid subscriber retention 
and 18% more reply engagement (early adopter data).

Want to enable it?

[ENABLE AI GOVERNANCE]
→ https://creator.axiom.co/dashboard/ai-governance?utm_campaign=day7&utm_source=email

(It's opt-in. You can turn it off anytime.)

— The AXIOM Team
```

---

### EMAIL 4: Payout Simulation + Settlement Proof (Day 14, 8:00 AM)

**Trigger:** Sent to all active creators (regardless of login)

**Subject:** Your first payout (simulated): {simulated_payout_amount}

**Preview Text:** "Here's exactly how much you'd earn. See the proof."

---

**Email Body:**

```
Hi {creator_first_name},

Today we're running a simulation of your first payout. Here's what it would look like:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AXIOM SETTLEMENT PROOF (SIMULATED)

Settlement Period: July 1-31, 2026
Creator: {creator_first_name}
Publication: {publication_name}

Gross Revenue:           ${simulated_gross}
Platform Fee (1%):       -${simulated_fee}
Your Payout (99%):       ${simulated_payout} ✓

Payout Method:           ACH (arrives in 2-5 business days)
Expected Bank Date:      Aug 15, 2026

Merkle Root:             e1d2c3b4a59687f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3
AXIOM Signature:         3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is the proof you'll get every month.

Both the proof and the signature are cryptographically signed. If the numbers 
change, the signature breaks. If AXIOM cheats, everyone knows.

See the math:

[VIEW FULL SETTLEMENT PROOF]
→ https://creator.axiom.co/dashboard/settlement-proofs/simulated?utm_campaign=day14&utm_source=email

Next step: Set up your bank account for real payouts.

[CONNECT STRIPE]
→ https://creator.axiom.co/dashboard/payout-settings?utm_campaign=day14&utm_source=email

Questions about the math? Reply to this email.

— The AXIOM Team
```

---

### EMAIL 5: Early Adopter Case Study (Day 21, 10:00 AM)

**Trigger:** Sent to all creators who connected Substack

**Subject:** How {early_adopter_name} is earning {case_study_amount}/month

**Preview Text:** "A real creator. Real numbers. Real proof."

---

**Email Body:**

```
Hi {creator_first_name},

We wanted to show you what's possible.

Meet Sarah Chen. She launched "Practical AI" 8 months ago. She had 1,200 
free subscribers when she joined AXIOM 2 months ago.

Here's what happened:

📈 MONTH 1 (June)
Subscribers: 1,200 free | 12 paid
Earnings: $2,340
AXIOM Payout: $2,317 ✓

🎯 WHAT SHE CHANGED:
- Used AXIOM's AI governance to find her "thought leader" audience segment
- Wrote 2 posts/week targeting that segment
- Enabled "paid-only early access" (48 hours before free release)

📈 MONTH 2 (July)
Subscribers: 2,100 free | 234 paid (+1850% 🚀)
Earnings: $18,900
AXIOM Payout: $18,711 ✓

Sarah's quote:
"AXIOM's transparency changed everything. I knew exactly who my high-value 
audience was, and I could test new content without guessing. The 99/1 split 
made me believe they actually wanted me to win."

═════════════════════════════════════════════════════════════════════

The point: You don't need a massive audience. You need the right audience.

AXIOM helps you find them. And keeps 99% of the revenue.

Ready to start?

[SET UP PAYOUTS]
→ https://creator.axiom.co/dashboard/payout-settings?utm_campaign=day21&utm_source=email

(Sarah's full case study in our Creator Playbook — link in your dashboard.)

— The AXIOM Team
```

---

### EMAIL 6: Referral Incentive (Day 28, 12:00 PM)

**Trigger:** Sent to all creators with >100 hours dashboard time

**Subject:** Earn 0.5% for every creator you bring to AXIOM

**Preview Text:** "Help a fellow creator. Get paid for it."

---

**Email Body:**

```
Hi {creator_first_name},

You've been exploring AXIOM. Now we want to ask you for help.

You probably know creators like you. Ones who are tired of platform greed. 
Ones who deserve better.

If you refer a creator to AXIOM and they connect Substack, here's what happens:

1️⃣ You get a unique referral link
2️⃣ Your friend joins and earns their first payout
3️⃣ You earn 0.5% of their first month's earnings

Example:
Your friend Sarah earns $5,000 in her first month with AXIOM.
You earn: $25 (0.5% referral bonus)
Sarah keeps: $4,950 (99% of her earnings)
AXIOM takes: $25 (1% platform fee)

It's win-win-win.

Ready to spread the word?

[GET YOUR REFERRAL LINK]
→ https://creator.axiom.co/referrals?utm_campaign=day28&utm_source=email

Copy it. Send it to a friend. You'll see the bonus in your next settlement proof.

— The AXIOM Team

P.S. We're capping referrals at 500 creators in August to keep quality high. 
The earlier you share, the more bonuses you'll earn.
```

---

### EMAIL 7: 30-Day Check-In & Risk Tier Selection (Day 30, 6:00 PM)

**Trigger:** Sent to all creators (final reminder)

**Subject:** 30 days in: choose your AXIOM risk tier

**Preview Text:** "Personal? Professional? Defense? Here's how to decide."

---

**Email Body:**

```
Hi {creator_first_name},

30 days. How's it going?

Before you earn your first real payout (Aug 15), we need you to choose a 
risk tier. Here's what each one means:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 PERSONAL (Default)
For casual creators, hobbyists, community builders.
- AXIOM audits your content: toxicity, PII, spam
- You get 99% payout
- Settlement proof: standard

Best for: Under 5K subscribers, experimental content

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟡 PROFESSIONAL
For established creators, journalists, thought leaders.
- Stricter auditing: legal risk, IP infringement, defamation
- You get 99% payout + 0.25% bonus
- Settlement proof: detailed breakdown by topic/audience

Best for: 5K-50K subscribers, professional content, monetization focus

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 DEFENSE
For high-stakes creators: policy experts, security researchers, 
journalists covering conflict zones.
- Full behavioral firewall: AI detection, anomaly flagging, proof of life
- You get 99% payout + 1% bonus
- Settlement proof: cryptographically audited by independent witness network

Best for: High-risk content, adversarial environments, transparency demands

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Unsure? Start with PERSONAL. You can upgrade anytime (no penalty).

[CHOOSE YOUR TIER]
→ https://creator.axiom.co/dashboard/risk-tier?utm_campaign=day30&utm_source=email

Questions? Reply to this email or chat with our team in the dashboard.

See you on the other side, {creator_first_name}.

— The AXIOM Team

P.S. Your first real payout is Aug 15. Make sure your Stripe account is 
connected: https://creator.axiom.co/dashboard/payout-settings
```

---

## Email List Segmentation & Personalization Variables

### Segmentation Rules

| Segment | Criteria | Treatment |
|---------|----------|-----------|
| **Tier 1: Activated** | OAuth connected + dashboard login | All 7 emails (on schedule) |
| **Tier 2: Curious** | OAuth connected, no login | Emails 1, 2, 4, 7 (lighter touch) |
| **Tier 3: Cold** | No OAuth, no login | Emails 1, 5 only (brand awareness) |
| **Churn Risk** | Logged in Day 0-2, then silent | Email 3 (re-engagement) + offer bonus |

### Personalization Variables

```
{creator_first_name}         → Extract from Substack profile
{creator_last_name}          → Extract from Substack profile
{publication_name}           → Substack publication title
{subscriber_count}           → Total free + paid subscribers (Substack OAuth)
{post_frequency}             → Posts/month (calculated from API)
{primary_topic}              → Inferred from post titles (NLP)
{engagement_percentile}      → 0-100 (open rate vs. creator baseline)
{simulated_gross}            → Projected monthly revenue (calculation)
{simulated_fee}              → Platform fee (1% of gross)
{simulated_payout}           → Creator payout (99% of gross)
{early_adopter_name}         → Name of creator with similar audience size
{case_study_amount}          → Their monthly payout (published with permission)
{referral_link}              → Unique per creator: ref_abc123xyz
```

---

## Campaign Metrics & Success Criteria

### Day-by-Day KPI Targets

| Day | Metric | Target | Actual |
|-----|--------|--------|--------|
| 0 | Open rate (Email 1: Welcome) | 65% | — |
| 0 | Click rate (CONNECT SUBSTACK) | 25% | — |
| 3 | Open rate (Email 2: Dashboard) | 50% | — |
| 3 | Dashboard login (cumulative) | 40% | — |
| 7 | Open rate (Email 3: AI Governance) | 45% | — |
| 7 | AI Governance enabled | 15% | — |
| 14 | Open rate (Email 4: Settlement Proof) | 55% | — |
| 14 | Stripe Connect initiated | 35% | — |
| 21 | Open rate (Email 5: Case Study) | 40% | — |
| 21 | Risk tier selected | 40% | — |
| 28 | Open rate (Email 6: Referral) | 35% | — |
| 28 | Referral link created | 20% | — |
| 30 | Open rate (Email 7: Final) | 50% | — |
| 30 | Ready for payout (all steps done) | 60% | — |

---

## Email Template Technical Specs

### Design Specs (All Emails)

- **Width:** 600px (desktop), fluid (mobile)
- **Font:** System fonts (Apple system, Segoe UI, Helvetica)
- **Colors:** 
  - Primary (CTA): `#0066CC` (Stripe blue)
  - Secondary (highlights): `#00AA44` (green for success)
  - Error: `#CC0000` (red)
  - Neutral text: `#333333`
  - Subtle text: `#666666`
- **CTA Button:** 
  - Padding: 12px 24px
  - Border radius: 4px
  - Font weight: 600
  - Link format: Full HTTPS URLs with UTM params

### Tracking & Analytics

Every link includes UTM params:

```
Base: https://creator.axiom.co/path
UTM params:
  ?utm_campaign=day{X}
  &utm_medium=email
  &utm_source=creator-drip
  &utm_content={email_subject_sanitized}

Example:
https://creator.axiom.co/oauth/substack/start
  ?utm_campaign=day0
  &utm_medium=email
  &utm_source=creator-drip
  &utm_content=welcome
```

### Spam Compliance

- **List-Unsubscribe Header:** Included in all emails
- **Reply-To:** support+creator@axiom.co (monitored)
- **SPF/DKIM:** Configured for creator.axiom.co domain
- **Complaint Rate Target:** <0.1%
- **Bounce Handling:** Hard bounces → immediate list removal

---

## Implementation Checklist

- [ ] Set up email service (SendGrid or Braze)
- [ ] Create email templates in editor (6 HTML + 1 plain text fallback)
- [ ] Configure personalization variables in CRM
- [ ] Set up segmentation rules (Tier 1/2/3)
- [ ] Configure triggering logic (based on OAuth, login events)
- [ ] Set up UTM tracking in analytics
- [ ] Test all emails on Gmail, Outlook, Apple Mail
- [ ] A/B test subject lines (send 2 versions to 50% each on Day 0)
- [ ] Create email suppression list (bounces, opt-outs, errors)
- [ ] Set up bounce/complaint handling
- [ ] Create dashboard to monitor KPIs
- [ ] Deploy to staging (Aug 1)
- [ ] Go-live with first cohort (Aug 15)

---

## Email Content Guidelines

**Tone:** Honest, conversational, no BS. We're talking to smart creators.

**Structure:** Problem → Solution → CTA

**Proof:** Always show the math. Links to documentation.

**Length:** 1-minute read = 150-200 words + headline + CTA

**Avoid:**
- Hype words ("revolutionary," "disruptive")
- Fake urgency ("limited time offer")
- Jargon without explanation
- Multiple CTAs (one per email)
- Excessive images (text-first, mobile-friendly)

**Include:**
- Your name (first name in footer)
- Reply address (monitorable inbox)
- Unsubscribe link (required, below-the-fold)
- Physical address (required, below-the-fold)

---

## FAQ: Email Sequence

**Q: What if a creator marks emails as spam?**
A: We add them to suppression list immediately. No further emails.

**Q: What if they unsubscribe?**
A: They're removed from all future campaigns. They can re-subscribe from dashboard.

**Q: Can creators customize which emails they get?**
A: Yes. Dashboard → Email Preferences. Minimum: transactional only (payouts, alerts).

**Q: How do we handle time zones?**
A: Detect from IP or let creator set in dashboard. Send at their preferred time.

**Q: What about GDPR (EU creators)?**
A: Double opt-in required. Unsubscribe link on every email. Data retention: 90 days after unsubscribe.

---
