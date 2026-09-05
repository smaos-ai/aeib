# QA Testing Checklist: SMAOS UI

**Before showing to UniCredit CTO, verify ALL of these:**

---

## 🎬 CRITICAL PATH TEST (5 minutes)

### ✅ Form Input Works
- [ ] Open http://127.0.0.1:5174
- [ ] Capsule dropdown changes between Hotel and Treasury
- [ ] Type in Counterparty field → text appears
- [ ] Type in Amount field → numbers appear
- [ ] Risk preview card appears (with dashed border, pulsing)

### ✅ High-Risk Classification
- [ ] Fill form:
  - Counterparty: Goldman Sachs
  - Amount: 50000000 (€50M)
  - Instrument: Corporate Bond
  - Capital Impact: CAR-Impacting
- [ ] Risk badge shows: 🔴 HIGH-RISK
- [ ] Badge color is RED (not orange or green)

### ✅ Veto Gate Appears
- [ ] Click "Send to Work Surface"
- [ ] Wait 1 second
- [ ] RED veto card appears in CENTER pane
- [ ] Card says: "🔐 EXECUTION BLOCKED"
- [ ] Card says: "CAR-IMPACTING DECISION"
- [ ] Card shows legal basis (CRR Article 92)

### ✅ Authorization Button Works
- [ ] Two buttons visible:
  - [ ] "✓ Authorize & Sign (Ed25519)" (RED/DANGER)
  - [ ] "🚫 Veto & Abort" (ORANGE/WARNING)
- [ ] Both buttons are CLICKABLE (not greyed out)
- [ ] Click "Authorize & Sign"
- [ ] Button text changes to "Signing..." (loading state)
- [ ] Button text changes back after 0.5 sec

### ✅ Signature Generated
- [ ] Ed25519 signature is created (should see evidence)
- [ ] Proof receipt appears in RIGHT pane
- [ ] Receipt shows: "✅ VETO.AUTHORIZE"
- [ ] Receipt shows timestamp (14:23:45 format)
- [ ] Receipt shows "✓ VERIFIED"

### ✅ Proof Verification
- [ ] Click receipt to expand
- [ ] See full Ed25519 signature
- [ ] Click "Verify" button
- [ ] Status changes to "✓ VERIFIED"
- [ ] Verification happens <100ms

---

## 🎨 UI/UX CHECKS

### ✅ Visual Clarity
- [ ] Veto card is RED (not hard to see)
- [ ] Text is BLACK on WHITE (high contrast, readable)
- [ ] Icons are clear (🔐 lock icon, ⚠️ warning)
- [ ] Buttons are large and obvious (not tiny)
- [ ] Animations are smooth (not janky)

### ✅ User Doesn't Get Lost
- [ ] When veto card appears, it's OBVIOUS where to click
- [ ] Button text is clear ("Authorize & Sign", not "OK")
- [ ] Instruction text appears: "👆 Click one of these buttons"
- [ ] No confusing modal pop-ups
- [ ] All interaction is INLINE (in the center pane, not elsewhere)

### ✅ Responsive Design
- [ ] Resize browser window (make narrow, make wide)
- [ ] Veto card still fits and is readable
- [ ] Buttons don't wrap (stay on same line)
- [ ] Text doesn't overflow
- [ ] All three panes are visible (left/center/right)

---

## 🔒 CRYPTO VERIFICATION

### ✅ Ed25519 Signature Works
- [ ] Signature is NOT empty (has real base64 data)
- [ ] Signature length is ~88 characters (Ed25519)
- [ ] Signature starts with real base64 chars (A-Za-z0-9+/)
- [ ] NOT hardcoded (same signature won't appear twice)
- [ ] "Verify" button makes a live call to crypto.subtle.verify

### ✅ Verification is Live
- [ ] Click "Verify" on receipt
- [ ] Status shows "⏳ PENDING" first
- [ ] After <100ms, status shows "✓ VERIFIED"
- [ ] If you modify the signature (manually in UI), verify shows "✗ INVALID"

### ✅ Multiple Authorizations
- [ ] Do the flow twice (submit two different trades)
- [ ] Create two proof receipts
- [ ] Both signatures are DIFFERENT (not the same)
- [ ] Both verify successfully

---

## 📊 REGULATORY COMPLIANCE CHECKS

### ✅ Citations are Real
- [ ] Veto card shows legal basis
- [ ] Legal basis includes: "CRR Article 92", "Basel III", or "EU AI Act"
- [ ] NOT generic text ("Compliance Required")
- [ ] Citations are visible (not hidden in expandable section)

### ✅ Immutability
- [ ] Try to edit a receipt (copy text, paste in input)
- [ ] Receipt hash/signature should NOT update
- [ ] Timestamp doesn't change after authorization

### ✅ Audit Trail
- [ ] Right pane shows "📜 agentacct Proof Ledger"
- [ ] Ledger shows multiple entries (if you do multiple trades)
- [ ] Newest entry is at top
- [ ] All entries show timestamp + action + signature status

---

## ⚡ PERFORMANCE CHECKS

### ✅ Speed
- [ ] Form loads in <1 second
- [ ] Risk preview updates in <200ms (as you type)
- [ ] Veto card appears in <1 second (after submit)
- [ ] Signature generates in <200ms
- [ ] Verification happens in <100ms
- [ ] Browser doesn't freeze (no spinning wheel)

### ✅ No Console Errors
- [ ] Open browser DevTools (F12)
- [ ] Go to Console tab
- [ ] Do the full flow (submit trade, authorize, verify)
- [ ] Check: NO RED ERRORS
- [ ] Only warnings/info messages are OK
- [ ] No "undefined is not a function" errors

### ✅ Network is Local
- [ ] Open DevTools Network tab
- [ ] Do the full flow
- [ ] All requests should be to `127.0.0.1` or `localhost`
- [ ] No requests to `api.openai.com`, `github.com`, `google.com`, etc
- [ ] Proof ledger is stored in browser (sessionStorage), not sent to cloud

---

## 🧪 EDGE CASES

### ✅ Low-Risk Trade (Should NOT Block)
- [ ] Fill form with LOW-RISK trade:
  - Counterparty: Any name
  - Amount: €100,000 (low amount)
  - Instrument: Equity
  - Capital Impact: Non-Impacting
- [ ] Risk classification shows: 🟢 APPROVED
- [ ] Badge color is GREEN
- [ ] Button says "Send to Work Surface" (NOT disabled)
- [ ] Click submit → NO veto card appears

### ✅ Form Validation
- [ ] Try clicking "Send" with empty form
- [ ] Button should be DISABLED (greyed out)
- [ ] Fill one field → button enables
- [ ] Fill all fields → button is bright blue

### ✅ Multiple Submits
- [ ] Submit a trade (get veto card)
- [ ] Authorize it
- [ ] Submit a DIFFERENT trade
- [ ] Should get a NEW veto card (not reuse old one)
- [ ] Both signatures in ledger are DIFFERENT

### ✅ Refresh Page
- [ ] Fill form + authorize
- [ ] See proof receipt
- [ ] Refresh browser (F5)
- [ ] Proof receipts should be GONE (they're session-only)
- [ ] Form should be EMPTY
- [ ] (This is correct behavior: each session is fresh)

---

## ✅ BEFORE YOU CALL IT READY

**DO NOT show to UniCredit until:**

- [ ] All "Critical Path" tests pass
- [ ] UI is visually clear and professional
- [ ] Buttons are obviously clickable
- [ ] Signature generation works
- [ ] Verification works
- [ ] No console errors
- [ ] Network is local only
- [ ] Low-risk trades don't block
- [ ] Form validation works

---

## 📋 SIGN-OFF

When all checks pass, you can confidently say:

> "Our system blocks high-risk trades with real Ed25519 signatures. Every authorization is cryptographically verified and immutably logged. This is production-grade governance infrastructure."

---

## 🚀 WHAT HAPPENS IF A TEST FAILS

| Test | Failure | Fix |
|------|---------|-----|
| Veto card doesn't show | Execution is proceeding without gate | Check: Is `blockedNode` being found? Is `classification.highestSeverity === 'block'`? |
| Button doesn't click | Event handler broken | Check browser console for JS errors. Check: Is `handleVetoAuthorize` being called? |
| Signature doesn't generate | crypto.subtle not working | Check: Is crypto.subtle available in browser? Try incognito mode (test with fresh session). |
| Verification fails | Signature is invalid | Check: Is signature being corrupted? Is payload being canonicalized? |
| Form doesn't validate | Validation logic broken | Check: Is `classifyIntent` being called? Is it returning `highestSeverity === 'block'`? |

---

**Test everything. Deliver with confidence.**
