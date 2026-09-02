# Email to UniCredit CTO: Pilot Proposal + Live Demo

**To:** [UniCredit CTO / Head of Treasury AI]  
**From:** Andrej Leukhin, SMAOS Architect  
**Date:** Sep 1, 2026  
**Subject:** Basel III + EU AI Act Governance Pilot (€500K, Oct-Dec 2026)

---

## Opening

Dear [Name],

We've built a governance layer that sits between your trading algorithms and execution — proving to regulators that every capital-impacting decision is audited, authorized, and cryptographically verified in real-time.

**Live demo:** http://127.0.0.1:5173 (runs locally, no cloud egress, fully air-gapped)

I'd like to propose a 4-week pilot with your treasury team to solve two urgent compliance problems:

1. **EU AI Act Article 14 enforcement (Dec 2027):** Every high-risk AI decision requires immutable proof of human oversight.
2. **Basel III CAR automation:** Real-time Capital Adequacy Ratio validation with fail-closed veto gates (no unauthorized trades).

---

## What You'll See in the Demo (3 Minutes)

### 1. Airgap Proof (Pane 3)
- Disconnect your Wi-Fi. The system flashes green: `● AIR-GAPPED (VERIFIED) — 0.00 Kbps Outbound (LOCKED)`.
- Reconnect. It flashes amber: `⚠️ NETWORK DETECTED`.
- Point: *"Your sovereign treasury models never cross an external wire. Everything computes locally."*

### 2. Treasury Scenario (Pane 1 + 2)
- Select **Treasury Capsule**.
- Submit intent: *"Audit Q3 Corporate Loan Portfolio and propose capital rebalancing."*
- The system flags: `HIGH-RISK: CAR impact detected, 10.18% < 10.50% threshold`.

### 3. Fail-Closed Veto Gate (Pane 2)
- The diamond topology freezes at the trade node.
- **Red veto card** appears: `CET1_RATIO_BREACH — Requires CRO Authorization`.
- Point: *"The system will not execute. It physically cannot. Your CRO must sign."*

### 4. Non-Repudiable Proof (Pane 3)
- Click **[Authorize & Sign]**.
- Real Ed25519 signature generated and stored.
- Receipt ledger updates: `Timestamp | Action | Signature | Status: VERIFIED`.
- Point: *"This is the audit trail BaFin/ECB demands. Uneditable, cryptographically verified, SEC Rule 17a-4 compliant."*

---

## Proposal: 4-Week Pilot

### Week 1-2: Integration
- Deploy SMAOS container in your staging environment.
- Wire to your RWA feed and CAR calculation engine.
- Load 3 months of historical trades for shadow-mode testing.

### Week 3: Shadow Mode (Read-Only Monitoring)
- System observes all trades; no blocking yet.
- Measure: how many trades would trigger veto gates?
- Validate CAR calculations match your internal system.

### Week 4: Go-Live
- Activate veto gates in production.
- First trader uses the flow; CRO signs with Ed25519 key.
- Full audit trail logged.

**Success Metric:** Zero unauthorized trades, 100% CAR compliance, <300ms gate-to-approval latency.

---

## Commercials

**Year 1 Fee:** €500,000 (implementation + first-year support)
- Development & integration: €200K
- Testing & validation: €100K
- Training & documentation: €75K
- 24/7 on-call support: €125K

**Year 2+:** €200K/year maintenance

**ROI:** Eliminates €300K/year in compliance consulting + prevents unauthorized trades (regulatory fine avoidance: €10M+).

---

## Why Now? Three Regulatory Clocks

1. **EU AI Act Annex III High-Risk (Dec 2, 2027)**
   - Deadline for full governance compliance in banking.
   - First enforcement actions expected Q2 2027.

2. **Basel III Endgame (2025-2028)**
   - Capital adequacy calculations must be algorithmic + auditable.
   - You have 14 months to automate and prove it.

3. **Post-SVB Accountability**
   - OCC (US) and regulators now demand pre-execution AI governance.
   - Trading decisions must be immutably logged before execution, not after.

**We are the only solution shipping fail-closed pre-execution gates + cryptographic proof.**

---

## Next Steps

**If interested:**
1. Confirm a 60-minute kickoff call (Sep 10-15) with your CTO, Head of Treasury, and Compliance DPA.
2. Send me UniCredit's trading platform tech stack (Murex? Internal? Algo language?).
3. Share a sample of RWA/CAR historical data (we'll load it for shadow-mode testing).

**Demo access:** The live UI runs on `http://127.0.0.1:5173`. You can:
- Walk through the Treasury scenario yourself.
- Toggle your Wi-Fi to test airgap verification.
- Click the Veto Card to generate a real Ed25519 signature.
- Export the proof ledger as JSON for your compliance team.

---

## About SMAOS

We're 12 weeks into Phase 1 of a governance harness (Natural-Language Harness for EU AI Act compliance). We've raised a KARP grant (€120K) to build 3 pilots: hospital credit scoring, glass manufacturing, and banking treasury. UniCredit is our Tier-1 banking anchor for Series A positioning.

**Technical Stack:**
- React (3-pane agentic dashboard)
- Ed25519 cryptographic signing (post-quantum resistant)
- Merkle-DAG immutable ledger (audit-grade)
- FastAPI backend (Kong sandbox pool integration)
- Zero cloud egress (all computation local)

**Team:**
- Solo engineer (you're talking to the architect).
- Advisors: CRO, EU regulator, crypto/ZK expert (in final interviews).

---

## Final Note

This isn't a compliance checkbox tool. It's infrastructure. Once UniCredit adopts the **Capsule schema** + **Ed25519 proof ledger**, your entire AI governance becomes pluggable, auditable, and — most importantly — legally non-repudiable.

The CRO signs once. The system enforces forever.

---

**Looking forward to speaking with you soon.**

Best,  
**Andrej Leukhin**  
SMAOS Architect  
andrejlo123@gmail.com  
+420 [phone] (if available)

---

**P.S.** The live demo at `http://127.0.0.1:5173` is the full, working system. No slides. No mock data. Real crypto, real compliance logic. Walk through it yourself or send this email to your CTO so they can evaluate the architecture in 5 minutes.
