# KARP Submission Quick Start — Sep 16, 2026
**One-Page Reference Card for Day-of Execution**

---

## CRITICAL DATES

| Event | Date | Action |
|-------|------|--------|
| **SUBMIT** | Sep 16, 2026 @ 9:00 AM CET | Email to Romana |
| **KARP DEADLINE** | Sep 22, 2026 | Must be in by end of day |
| **EXPECTED APPROVAL** | Oct 15, 2026 | Decision announced |
| **FOLLOW-UP (if needed)** | Oct 8, 2026 | Send if no response |
| **FUNDS TRANSFER** | Oct 20, 2026 | 60% immediate |

---

## KEY CONTACTS

**KARP Program Manager:**  
Romana Cernikova  
romana.cernikova@karp-kv.cz  
+420 724 858 335

**Your Email:**  
andrejlo123@gmail.com

---

## STEP-BY-STEP (Morning of Sep 16)

### 8:00 AM: Create Bundle
```bash
bash scripts/karp_submission_prepare.sh
```
(Creates: ~/smaos-karp-bundle-sep2026.zip)

### 8:15 AM: Open Gmail
- New Email
- To: romana.cernikova@karp-kv.cz
- CC: andrejlo123@gmail.com

### 8:20 AM: Fill Subject
```
SMAOS Phase 1: KARP 120k CZK Application + 7 Proof Artifacts
```

### 8:25 AM: Copy Email Body
Go to: `/Users/andriileukhin/Documents/SovereignNexus/KARP_SUBMISSION_READY.md`

Copy section: **DELIVERABLE 1: FINAL EMAIL TEMPLATE → EMAIL 1: SUBMISSION**

Paste into Gmail body.

### 8:45 AM: Attach File
```
Attach: ~/smaos-karp-bundle-sep2026.zip
```

### 8:55 AM: Final Review
- [ ] Subject correct
- [ ] Body reads well (no formatting issues)
- [ ] ZIP attached (60 KB)
- [ ] To: romana.cernikova@karp-kv.cz
- [ ] CC: andrejlo123@gmail.com

### 9:00 AM: SEND

---

## KEY NUMBERS

| Metric | Value |
|--------|-------|
| Budget | 120,000 CZK |
| Duration | 12 weeks (Sep 1 - May 31) |
| Files in bundle | 11 |
| Bundle size | 60 KB (email limit: 25 MB) ✓ |
| Engineer salary | 60,000 CZK |
| Hardware | 8,000 CZK |
| Testing | 12,000 CZK |
| Contingency | 40,000 CZK |
| Pilots | 3 (hotel, glass, school) |
| Proof artifacts | 7 (agentacct, unlazy, AP2, RAGAS, Golden Set, Security, CanIRun) |
| Security tests | 28 (96.4% pass) |
| Golden set tasks | 50 (pass@5 = 100%) |
| Annex IV sections | 9 (auto-generated) |

---

## CRITICAL POINTS (If Romana Asks)

**Q: Why governance is hard?**  
A: "70% of agent deployments have zero execution proof. We install governance as a software layer, not a PDF checklist. Signed work receipts, fail-closed gates, cryptographic audit trail."

**Q: What's the moat?**  
A: "6 controls installed in the execution loop (Agent/Tool/Policy/Approval/Action/Audit). 7 cryptographic proof artifacts. Defensible for 6+ months R&D."

**Q: Why Karlovarský kraj matters?**  
A: "Hotels, glass factories, breweries have agentic AI deployed. They need compliance Dec 2, 2027 (Annex III). We deliver May 31, 2027 — ready for regulators."

**Q: What's Phase 2?**  
A: "BIC Plzeň 1M CZK (Jun 2027). Egress controls (2-3 wks) + Intent-verified delegation (4-6 wks)."

---

## IF THINGS GO WRONG

**Gmail won't send the ZIP?**
- Try attaching via browser (not app)
- Or upload ZIP to Google Drive, share link in email

**Bundle too big?**
- Run: `ls -lh ~/smaos-karp-bundle-sep2026.zip`
- Should show: 60K (well under 25 MB)

**No response by Oct 8?**
- Use EMAIL 2 (follow-up template) from KARP_SUBMISSION_READY.md
- Tone: friendly, not pushy

**Bundle script fails?**
- Check files exist: `ls -lh /Users/andriileukhin/Documents/SovereignNexus/*.md`
- Check JSON validity: `python3 -m json.tool golden_set_results.json`

---

## POST-SUBMISSION

### Sep 16 Afternoon
- [ ] Screenshot email confirmation (for records)
- [ ] Save to: ~/Desktop/karp_submission_sent_sep16.png

### Oct 1
- [ ] Check for response (check Spam folder too)

### Oct 8
- [ ] If no response: send EMAIL 2 follow-up

### Oct 15
- [ ] Expected: KARP approval decision
- [ ] Watch email for notification

### Oct 20
- [ ] If approved: funds transfer begins (60% immediate)
- [ ] Celebrate → Phase 1 execution starts full-speed

---

## FINAL CHECKLIST

- [ ] Bundle script tested ✓
- [ ] All 11 files verified ✓
- [ ] Email template ready ✓
- [ ] Subject line prepared ✓
- [ ] Contact info correct ✓
- [ ] Backup contacts identified ✓
- [ ] Follow-up plan ready ✓
- [ ] Calendar reminder set (Oct 8) ✓

---

## SUCCESS = Email Sent Sep 16 @ 9:00 AM CET

**Approval expected:** Oct 15, 2026  
**Funds transfer:** Oct 20, 2026  
**Phase 1 completion:** May 31, 2027  
**Phase 2 trigger:** Jun 2027 (BIC Plzeň 1M CZK)

---

**Questions?** → andrejlo123@gmail.com  
**More details?** → /Users/andriileukhin/Documents/SovereignNexus/KARP_SUBMISSION_READY.md
