# Standard Test Procedure (Follow Exactly)

**URL:** http://127.0.0.1:5173

---

## STEP 1: OPEN PAGE
- [ ] Click link: http://127.0.0.1:5173
- [ ] Wait 2 seconds
- [ ] Page loads? **YES / NO**

If NO: Stop. Report "Page didn't load"

---

## STEP 2: SEE 3-PANE DASHBOARD
- [ ] Left pane: Form visible? **YES / NO**
- [ ] Center pane: Empty area visible? **YES / NO**
- [ ] Right pane: "Proof Ledger" text visible? **YES / NO**

If NO: Stop. Report which pane is missing

---

## STEP 3: FILL FORM (Exact Values)
```
Counterparty: Goldman Sachs
Amount: 50000000
Instrument: Corporate Bond
Capital Impact: CAR-Impacting
```

- [ ] Counterparty filled? **YES / NO**
- [ ] Amount filled? **YES / NO**
- [ ] Instrument filled? **YES / NO**
- [ ] Capital Impact selected? **YES / NO**
- [ ] Red badge appears (HIGH-RISK)? **YES / NO**

If any NO: Stop. Report which field

---

## STEP 4: CLICK "SEND TO WORK SURFACE"
- [ ] Button visible? **YES / NO**
- [ ] Button clickable? **YES / NO**
- [ ] Click button
- [ ] Wait 1 second

---

## STEP 5: RED VETO CARD APPEARS
- [ ] Red card visible in CENTER pane? **YES / NO**
- [ ] Card says "EXECUTION BLOCKED"? **YES / NO**
- [ ] Card has TWO buttons? **YES / NO**

If NO: Stop. Report what you see instead

---

## STEP 6: FIND AUTHORIZE BUTTON
- [ ] First button says "Authorize & Sign"? **YES / NO**
- [ ] Button is RED? **YES / NO**
- [ ] Button is clickable? **YES / NO**

If NO: Stop. Report what you see

---

## STEP 7: CLICK "AUTHORIZE & SIGN"
- [ ] Click button
- [ ] Wait 1 second
- [ ] Button shows "Signing..."? **YES / NO**
- [ ] After 1 sec, button returns to normal? **YES / NO**

If NO: Stop. Report what happened

---

## STEP 8: RECEIPT APPEARS IN RIGHT PANE
- [ ] Right pane shows receipt (row with timestamp)? **YES / NO**
- [ ] Receipt says "VETO.AUTHORIZE"? **YES / NO**
- [ ] Receipt shows "✓ VERIFIED"? **YES / NO**

If NO: Stop. Report what you see

---

## STEP 9: EXPAND RECEIPT
- [ ] Click on receipt row
- [ ] Receipt expands? **YES / NO**
- [ ] Shows signature (long text)? **YES / NO**

If NO: Stop. Report what happens

---

## STEP 10: VERIFY SIGNATURE
- [ ] "Verify" button visible? **YES / NO**
- [ ] Click "Verify" button
- [ ] Status shows "✓ VERIFIED"? **YES / NO**

If NO: Stop. Report what you see

---

## FINAL RESULT

**All 10 steps passed?**

- **YES:** ✅ SYSTEM WORKING
- **NO:** ❌ Report which step failed and what you saw

---

## IF ANYTHING FAILS

**Report EXACTLY:**
1. Which step number?
2. What you clicked?
3. What you expected?
4. What you actually saw?

**Example:** 
"Step 5 failed. I clicked 'Send to Work Surface'. Expected red card to appear. Instead nothing happened."

Then I fix it and you test again.

---

**Follow this EXACTLY. Same steps every time. Clear result.**
