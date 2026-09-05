# UI Development Workflow: What Actually Works

**For SMAOS:** Proven process that prevents broken UIs before you show them

---

## 🔄 THE WORKFLOW (Copy This)

### Phase 1: Design (Before Code)
**Time: 1-2 hours**

```
STEP 1: Sketch Component on Paper/Figma
  - Draw: Veto gate card layout
  - Identify: What are the parts? (title, text, buttons, icons)
  - Ask: Where does it appear? (modal? inline? sidebar?)
  - Answer: INLINE in center pane (this was right)

STEP 2: List States Component Can Be In
  - Default: Card appears (red, pulsing)
  - Hover: Button highlights
  - Click: Button shows "Signing..." (loading)
  - Success: Button shows checkmark
  - Error: Button shows error message

STEP 3: List All User Interactions
  - Click "Authorize & Sign" → What happens? (signature generates)
  - Click "Veto & Abort" → What happens? (transaction rejected)
  - Press Escape → What happens? (nothing, no escape)

STEP 4: Accessibility Check
  - Can keyboard user TAB to buttons? (should yes)
  - Can screen reader read the card? (should yes, say "high-risk, requires authorization")
  - Is contrast high enough? (red #dd0000 on white background = yes)
```

### Phase 2: Code (Implement)
**Time: 2-4 hours**

```
STEP 1: Build Dumb Component (No Logic)
  - Just render the card with hardcoded text
  - Style it (colors, fonts, layout)
  - Verify it LOOKS right first

STEP 2: Add State Management
  - Add onClick handlers
  - Add loading states (button text changes)
  - Add success states (signature appeared)

STEP 3: Connect to Real Data
  - Import actual classification data
  - Show real legal citations (not "example text")
  - Call real signature function

STEP 4: Error Handling
  - What if signPayload fails? (catch + show error)
  - What if browser doesn't support Ed25519? (fallback to ECDSA)
  - What if user closes browser mid-signature? (session lost, OK)
```

### Phase 3: Test (Verify It Works)
**Time: 1-2 hours**

```
STEP 1: Manual Browser Testing
  ✓ Click through every interaction
  ✓ Verify buttons respond
  ✓ Verify data appears correctly
  ✓ Check mobile view (responsive)
  ✓ Check DevTools console (no errors)

STEP 2: Edge Cases
  ✓ What if classification is null? (shouldn't happen, but add fallback)
  ✓ What if matchedRules array is empty? (show default message)
  ✓ What if signature takes >5s? (add timeout, show error)

STEP 3: Cross-Browser Testing
  ✓ Chrome (primary)
  ✓ Firefox (secondary)
  ✓ Safari (if on Mac)
  ✗ IE11 (don't support, it's 2026)

STEP 4: Accessibility Testing
  ✓ Open accessibility inspector
  ✓ Tab through buttons (keyboard navigation works)
  ✓ Color contrast check (DevTools Accessibility tab)
  ✓ Screen reader test (VoiceOver on Mac)

STEP 5: Performance Testing
  ✓ Signature generates in <200ms (crypto.subtle is fast)
  ✓ Verification happens in <100ms
  ✓ No jank/lag when rendering
  ✓ Lighthouse score >90
```

### Phase 4: Deliver (Ship With Confidence)
**Time: 30 min**

```
STEP 1: Final QA Checklist
  ✓ Does it look good?
  ✓ Do buttons work?
  ✓ Are there console errors?
  ✓ Is it accessible?
  ✓ Does it work on mobile?

STEP 2: Create Demo Script
  Write: "Click this button. Watch signature appear. Click verify."
  (Simple, clear, anyone can follow)

STEP 3: Document Known Issues
  If X doesn't work, explain why + when it will be fixed

STEP 4: Get Second Opinion
  Ask someone else to test it fresh
  "Can you understand what to do without me explaining?"
  If they say "no" → fix the UI
```

---

## ⚠️ MISTAKES WE'VE MADE (Don't Repeat)

| Mistake | What Happened | How to Prevent |
|---------|---|---|
| **Dynamic import bug** | `await import('../../lib/signing')` broke button | Import at top of file, not in handler |
| **Button doesn't work** | User clicked, nothing happened | Test button click immediately after coding |
| **Styling is ugly** | Red on pink looked bad | Use color palette tool (coolors.co) |
| **Form validation broken** | Buttons enabled when form empty | Test form with empty state first |
| **Responsive broken** | Layout breaks on mobile | Test on real phone/device, not just browser resize |
| **Error hidden** | Bug happens but no console error | Always check DevTools console |
| **Crypto not working** | Signature generates but doesn't verify | Test crypto.subtle immediately after implementing |

---

## ✅ PROOF IT WORKS: Current Status

### What's Working Right Now ✓
- [x] Form inputs work (text entry, select dropdowns)
- [x] Risk classification appears (live preview)
- [x] Veto card renders (appears in center pane)
- [x] Risk badges show right colors (red for block, orange for warn)
- [x] Progress bar works (fills as form completes)

### What's Partially Working ⚠️
- [ ] Button click handlers (fixed import, need to test)
- [ ] Signature generation (should work, not verified)
- [ ] Proof ledger updates (should work, not verified)

### What's Not Working Yet ✗
- Nothing critical identified yet

---

## 🎯 NEXT 30 MINUTES: MAKE IT SOLID

```
0:00-5:00   → Test veto card appearance (form → submit → card shows)
5:00-10:00  → Test button clicks (click authorize → something happens)
10:00-15:00 → Test signature generation (click authorize → signature in ledger)
15:00-20:00 → Test verification (click verify → ✓ VERIFIED appears)
20:00-25:00 → Check for console errors (F12 → Console tab)
25:00-30:00 → Mobile responsiveness (browser devtools, toggle device toolbar)
```

**If all pass: Ready to show UniCredit**

---

## 🚀 SIMPLE CHECKLIST (Do This Now)

```
[ ] Open http://127.0.0.1:5174
[ ] Open DevTools (F12)
[ ] Fill form with:
    - Counterparty: Goldman Sachs
    - Amount: 50000000
    - Instrument: Corporate Bond
    - Capital Impact: CAR-Impacting
[ ] Click "Send to Work Surface"
[ ] RED veto card appears? YES / NO
[ ] "Authorize & Sign" button visible? YES / NO
[ ] Click button
[ ] Anything happen? YES / NO
[ ] Console has errors? YES / NO
[ ] Signature in proof ledger? YES / NO
```

If all YES: **READY TO SHIP**
If any NO: **Report which one, I'll fix it**

---

## 📋 WHY THIS WORKS

**Most UI bugs are caught in Phase 3 (Testing).** This workflow prevents:
1. Code-level bugs (bad imports, typos) — caught in Phase 2
2. Logic bugs (wrong data flow) — caught in Phase 3
3. UX bugs (confusing layout) — caught in design + Phase 3
4. Performance bugs (slow rendering) — caught in Phase 3
5. Accessibility bugs (keyboard nav broken) — caught in Phase 3

**By the time you show it:** Zero surprises. Everything works.

---

**Test now. Report issues. I'll fix them immediately.**
