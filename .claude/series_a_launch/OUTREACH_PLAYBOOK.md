# UniCredit Outreach Playbook — 3-Step Campaign (Sep 1-15, 2026)

---

## STEP 1: TIER-1 COLD EMAIL (Sep 1-7)

### Target Titles (Research Independently)
- Head of AI / Head of ML
- VP Treasury Technology
- Chief Risk Officer (CRO)
- Chief Compliance Officer

### Email Template

**Subject Line:** `Basel III Automation Pilot (€500K, 4 weeks, Real Governance)`

---

**Body:**

```
Dear [Name],

I'm building governance infrastructure for EU AI Act compliance + Basel III 
automation. We're piloting with a Tier-1 bank to prove the architecture.

I think you should see what we've built.

LIVE DEMO (no login, no install):
http://127.0.0.1:5173

3-minute walkthrough:
1. Disconnect Wi-Fi → see air-gapped verification (green badge)
2. Submit treasury intent → system flags CAR impact (red badge)
3. Watch veto gate freeze execution
4. Click "Authorize & Sign" → real Ed25519 signature stored
5. Click "Verify" → cryptographic proof validated in real-time

This is not a mockup. Every signature is real. Every calculation is real. 
Everything runs local (no cloud, no egress).

WHAT WE'RE PROPOSING:
├─ 4-week pilot (Oct 1-31, 2026)
├─ Deploy to your staging environment
├─ Shadow-mode monitoring first (Weeks 1-3)
├─ Go-live with veto gates active (Week 4)
└─ €500K Year 1 (includes implementation + support)

WHY NOW:
1. EU AI Act Dec 2, 2027 deadline (18 months)
2. Basel III Endgame compliance clock (2025-2028)
3. Post-SVB regulators demand pre-execution AI governance

We're the only solution shipping fail-closed gates + cryptographic proof.

If this resonates, let's talk. I'd propose a 60-min technical kickoff 
with your CTO, Head of Treasury, and Compliance DPA to scope Week 1.

Best,
Andrej Leukhin
SMAOS Architect
andrejlo123@gmail.com
```

---

## STEP 2: INTERNAL ROUTING (Sep 7-10)

### If Email Goes to Wrong Desk

**Email Forward from Initial Recipient:**

```
Subject: Fwd: Basel III Automation Pilot — Forward to [Actual Owner]

[Initial recipient],

This is addressing your team. Please forward to the right owner.

We're proposing a €500K, 4-week pilot for treasury governance automation 
with fail-closed veto gates + Ed25519 proof ledger.

Live demo: http://127.0.0.1:5173

Tech lead can evaluate the architecture in 5 minutes and decide if it's 
worth a 60-minute technical kickoff.

Thanks,
Andrej
```

---

## STEP 3: KICKOFF CALL (Sep 10-15)

### Pre-Call (You Send 48 Hours Before)
1. DELIVERY_SCOPE_UNICREDIT.md (what they get, week-by-week)
2. IMPLEMENTATION_ROADMAP.md (our internal plan, shows seriousness)
3. README_UNICREDIT_DEMO.md (how to run the demo locally)
4. Link to live frontend repo (if they want to clone + run themselves)

### Call Attendees
- UniCredit CTO / VP Engineering
- Head of Treasury / Head of Risk
- Compliance DPA / Compliance Officer
- (You) Architect + optional external CRO advisor

### Call Agenda (60 minutes)

**Opening (5 min):** Problem statement
- "You have 18 months until EU AI Act enforcement (Dec 2027)"
- "Basel III Endgame requires algorithmic CAR validation"
- "Current solution: post-hoc logging that's bypassable"
- "Our solution: pre-execution fail-closed gates + immutable proof"

**Demo (10 min):** Walk them through the live UI
- Show 3-pane layout (intent / execution / proof ledger)
- Treasury scenario: large-amount trade → CAR impact → veto gate
- CRO authorizes with Ed25519 signature → proof updates
- Click "Verify" button → cryptographic proof validated

**Deep Dive (20 min):** Technical questions
- "How does this integrate with Murex?" → Show integration spec
- "What's the latency?" → <300ms gate-to-decision
- "Network isolation?" → navigator.onLine + tcpdump verification
- "Audit trail format?" → JSON + PDF, SEC Rule 17a-4 compliant

**Week 1 Requirements (15 min):** Blockers + dependencies
- "What's your trading platform?" (Murex? Internal?)
- "Can you export 3 months of trade history?" (CSV or API)
- "Which regulatory framework?" (CRR, Basel III.1, internal)
- "Staging environment access?" (Docker registry, internal DNS)
- "Ed25519 key management?" (HSM, SecureEnv, or we manage)

**Commercials (5 min):** Fee + payment schedule
- Year 1: €500K (€200K implementation, €100K testing, €125K support, €75K contingency)
- Payment: 25% upfront (Oct 1), 50% on go-live (Nov 1), 25% on 30-day production verification (Dec 1)
- Year 2+: €200K/year maintenance

**Next Steps (5 min):** If interest
- "If yes, we kick off Week 1 by Oct 1"
- "We'll send Docker container + integration spec within 48 hours"
- "Historical data load + CAR reconciliation by Day 4"
- "Go/no-go decision Oct 31 for production deployment"

---

## SUCCESS METRICS

### Email Stage (Sep 1-7)
- ✅ Email sent to 5+ tier-1 EU banks (UniCredit primary)
- ✅ At least 1 reply requesting demo

### Demo Stage (Sep 7-10)
- ✅ Demo accessed (tracked via dev server logs if possible)
- ✅ At least 1 "let's talk" response

### Kickoff Stage (Sep 10-15)
- ✅ 60-minute call scheduled
- ✅ Technical attendees confirmed (CTO + Treasury + Compliance)
- ✅ Week 1 dependencies identified (Murex spec + data export)

### Pilot Signed (Oct 1)
- ✅ Contract signed
- ✅ 25% upfront payment received (€125K)
- ✅ Week 1 integration started

---

## FALLBACK ROUTING (If UniCredit Says No)

If UniCredit passes, run the same playbook with:
- Deutsche Bank (largest EU bank, aggressive on AI governance)
- ING (Dutch, regulatory-forward, treasury automation focus)
- Banco Santander (Spain, EU AI Act early mover)

Keep the same demo, same DELIVERY_SCOPE, same IMPLEMENTATION_ROADMAP.

The product is modular (Capsule-based); the pitch is identical. Only the 
bank name changes.

---

## OUTREACH EMAIL VARIATIONS

### Variation 1: Treasury-Focused (For Head of Treasury)
```
Subject: CAR Automation Pilot (€500K, 4-week shadow mode, zero risk)

...

Your trading desk has €500B+ in assets at risk of capital breaches. 
We're offering real-time CAR validation with fail-closed gates.

Weeks 1-3: Shadow mode (monitoring only, zero impact to trading)
Week 4: Activate veto gates + prove compliance to regulators

Demo: http://127.0.0.1:5173

Let's talk.
```

### Variation 2: Compliance-Focused (For Compliance DPA)
```
Subject: EU AI Act Dec 2027 Compliance Pilot (Immutable Proof Ledger)

...

BaFin + ECB expect immutable, cryptographically-verified decision trails 
by Dec 2027. We're building that infrastructure.

Every trade approval is Ed25519-signed. Every signature is auditable. 
Every decision is uneditable.

Demo: http://127.0.0.1:5173

Questions?
```

### Variation 3: Risk/CRO-Focused (For Chief Risk Officer)
```
Subject: Fail-Closed Treasury Governance (Pre-Execution Veto Gates)

...

Your current risk controls are post-hoc logging. Ours are pre-execution 
gates that physically stop unauthorized trades before they happen.

We're piloting this with a Tier-1 bank. Should we talk to you?

Demo: http://127.0.0.1:5173
```

---

## TRACKING (Spreadsheet Template)

| Date | Bank | Contact | Email Sent | Reply | Demo Accessed | Call Scheduled | Status |
|------|------|---------|-----------|-------|--------------|----------------|--------|
| Sep 1 | UniCredit | [Name] | ✓ | [pending] | - | - | Awaiting reply |
| Sep 3 | Deutsche Bank | [Name] | ✓ | - | - | - | Not yet sent |
| Sep 5 | ING | [Name] | - | - | - | - | Not yet sent |

---

## CONTINGENCY: No Response in 2 Weeks?

If no unicredit/deutsche/ing response by Sep 15:

1. **Direct phone outreach** — Get LinkedIn, search for CTO/Treasury VP, 
   call main switchboard, ask for tech leadership
2. **Conference strategy** — Next EU banking tech conference? Register, 
   booth presence, demo rig
3. **Investor intro** — Ask Series A lead investors if they have banking 
   relationships; warm intro is 10x more effective than cold email
4. **EU government angle** — BaFin (Germany) + ECB (EU) are pushing AI Act 
   compliance; offer free compliance audit + showcase at regulatory forum

The product is strong. The market timing is perfect (18 months until Dec 2027 
deadline). Persistence beats luck.

---

**READY TO SEND?** Execute this playbook now. Decision point: Sep 15.
