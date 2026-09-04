# SMAOS Phase 1: Demo Day Operational Runbook

**Event Date:** Sep 15, 2026  
**Demo Duration:** 12 minutes (compressed, investor-focused)  
**Pre-Flight Window:** 30 minutes before go-live  
**Location:** Prague / Remote (TBD)

---

## Phase 10: Operational Checklist (Sep 15, 14:30-15:00)

### CRITICAL: Do NOT skip any step. This runbook is your safety net.

---

## SECTION 1: Hardware & Connectivity (5 min)

### Prerequisites Verification

- [ ] **Machine isolation verified**
  - Turn OFF WiFi / Ethernet
  - Verify: `airport -I` (macOS) should show "agrctlrssi: 0" or similar (no signal)
  - Reason: Demonstrate "offline-first" capability without external network calls

- [ ] **Port availability check**
  ```bash
  lsof -i :8000    # Should return NO results (port available)
  lsof -i :5173    # Should return NO results (port available)
  ```
  - If ports in use, identify process and terminate gracefully: `kill -TERM <PID>`

- [ ] **Database location verified**
  ```bash
  ls -lh /tmp/agentacct.db
  # If not exists: will be created during demo (acceptable)
  ```

- [ ] **Project root accessible**
  ```bash
  cd /Users/andriileukhin/Documents/SovereignNexus
  pwd  # Verify correct location
  ls -d reports/ star_protocol/ frontend/ scripts/ docs/
  ```

---

## SECTION 2: Backend Startup (5 min)

### Step 1: Terminal Window A (Backend)

```bash
# Open new terminal window for backend
cd /Users/andriileukhin/Documents/SovereignNexus/frontend

# Activate Python environment (if using venv)
# source venv/bin/activate

# Start backend server
python3 sovereign-backend.py
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Verification checklist:**
- [ ] Backend shows "Uvicorn running on http://127.0.0.1:8000"
- [ ] No errors in startup logs
- [ ] Database path logged correctly
- [ ] CORS headers configured (logs should show no CORS errors on frontend requests)

### Step 2: Verify Backend Health

```bash
# In separate terminal
curl -s http://127.0.0.1:8000/health | jq .
```

**Expected response:**
```json
{
  "status": "ok",
  "timestamp": "2026-09-15T14:45:00Z",
  "db_path": "/tmp/agentacct.db",
  "db_exists": false
}
```

**Verification checklist:**
- [ ] HTTP 200 status code
- [ ] Status: "ok"
- [ ] Timestamp is current (within 5 seconds)

---

## SECTION 3: Frontend Startup (5 min)

### Step 1: Terminal Window B (Frontend)

```bash
# Open new terminal window for frontend
cd /Users/andriileukhin/Documents/SovereignNexus/frontend

# Install dependencies (if needed)
npm install

# Start dev server
npm run dev
```

**Expected output:**
```
  VITE v4.x.x  ready in X ms

  ➜  Local:   http://127.0.0.1:5173/
  ➜  press h to show help
```

**Verification checklist:**
- [ ] Frontend shows "Local: http://127.0.0.1:5173/"
- [ ] No build errors during startup
- [ ] Webpack/Vite watching for changes

### Step 2: Verify Frontend Loads

- [ ] Open browser: `http://127.0.0.1:5173`
- [ ] Page loads (should see React app, not blank page)
- [ ] Open DevTools (F12) → Console tab
- [ ] Verify console is CLEAN: no errors, no warnings
  - [ ] Check Network tab: all static assets loaded (green status codes)
  - [ ] Check for failed API calls to external services (should see none)

---

## SECTION 4: Pre-Flight Component Checks (10 min)

### Check 1: STAR Protocol & Report Data

```bash
# Verify all required report files exist
cd /Users/andriileukhin/Documents/SovereignNexus
ls -lh reports/

# Should see these files:
# - eu_compliance_report.json        ✓
# - granite_fraud_report.json        ✓
# - story-banking-governance-report.json (will be created during demo)
```

**Verification checklist:**
- [ ] eu_compliance_report.json exists and is readable
- [ ] granite_fraud_report.json exists and is readable
- [ ] star_protocol/core.py is executable

```bash
# Test STAR protocol in isolation
python3 star_protocol/core.py

# This should complete in <2 sec and print final receipt
# SUCCESS: "✅ STAR TEST PASSED" or "⚠️ STAR TEST PARTIAL SUCCESS"
# FAILURE: Script exits with error (check stderr for cause)
```

**Verification checklist:**
- [ ] STAR protocol runs without errors
- [ ] story-banking-governance-report.json is created
- [ ] Receipt contains merkle_root and signature fields
- [ ] No "backend not responding" warnings (acceptable but note it)

### Check 2: SQLite Ledger

```bash
# Verify database table structure
sqlite3 /tmp/agentacct.db ".schema agentacct_ledger"

# Expected output:
# CREATE TABLE agentacct_ledger (...)
```

**Verification checklist:**
- [ ] Table exists OR will be created on first STAR run
- [ ] If entries exist: `sqlite3 /tmp/agentacct.db "SELECT COUNT(*) FROM agentacct_ledger;"`

### Check 3: Demo Script

```bash
# Verify demo script is executable
bash scripts/unicredit_demo_12min.sh --help 2>&1 || echo "Script found (no --help)"

# Run preflight checks built into script
bash scripts/unicredit_demo_12min.sh 2>&1 | head -50
# Should show checkmarks: ✓ Pre-flight checks passed
```

**Verification checklist:**
- [ ] Demo script is executable
- [ ] All preflight checks pass
- [ ] No red X marks (errors)

---

## SECTION 5: Functional Smoke Tests (10 min)

### Test 1: Veto Gate Trigger

**What you're testing:** Layer 7 human authorization gate works in UI

```bash
# In browser, navigate to: http://127.0.0.1:5173
# 
# Sequence:
# 1. Click "Submit Intent" button (or similar)
# 2. Enter:
#    - Amount: €2,400,000
#    - Description: Basel III capital optimization
# 3. Click "Submit"
# 4. Expected: Page should show HALT / VETO notification
#    (red banner: "EXECUTION HALTED - CRO Authorization Required")
```

**Verification checklist:**
- [ ] Intent submission form accessible
- [ ] Submission triggers classification (should be fast, <1 sec)
- [ ] Veto gate notification appears (red banner or modal)
- [ ] DevTools Console: no JavaScript errors
- [ ] DevTools Network: requests to /api/execute and /api/classify show 200/201

### Test 2: Signature Verification

**What you're testing:** Cryptographic verification button works

```bash
# In browser UI:
# 1. Look for "Verify Signature" button (or similar)
# 2. Click it
# 3. Expected: Button changes color/text to show verification passed
#    (green checkmark or "Verified" label)
```

**Verification checklist:**
- [ ] Verify button exists and is clickable
- [ ] Clicking Verify shows success state
- [ ] DevTools Console: no JavaScript errors
- [ ] DevTools Console: Ed25519 signature validation logged (optional but nice)

### Test 3: Ledger Display

**What you're testing:** SQLite ledger entries appear in UI

```bash
# In browser UI:
# 1. Look for "Audit Trail" or "Ledger" section
# 2. Expected: Should show list of recent transactions
#    (at least 1 entry from STAR test)
```

**Verification checklist:**
- [ ] Ledger section visible
- [ ] At least 1 entry displayed
- [ ] Entry shows: ID, Status, Timestamp, Merkle root (truncated)

---

## SECTION 6: Demo Choreography & Timing (12 min)

### Pre-Demo Briefing (for investor/audience)

**Talking points (read slowly, let audience absorb):**

> "Today we're showing three things:
>
> 1. **Compliance transformation**: How AI governance moved from 541 to 1161 points on EU AI Act compliance.
> 2. **Human oversight**: How a Layer 7 veto gate stops risky capital moves until a human approves them.
> 3. **Cryptographic certainty**: How every decision is recorded in a tamper-proof ledger with Ed25519 signatures.
>
> Zero cloud. Cryptographically certain. Human-governed."

### Running the Demo

```bash
# Terminal Window C: Run demo script
cd /Users/andriileukhin/Documents/SovereignNexus
bash scripts/unicredit_demo_12min.sh

# Expected timeline:
# 0:00-2:00  → SECTION 1: EU Compliance Lift
# 2:00-5:00  → SECTION 2: STAR Receipt Generation
# 5:00-9:00  → SECTION 3: Basel III Veto Gate
# 9:00-10:00 → SECTION 4: Fraud Detection
# 10:00-12:00 → SECTION 5: Ledger Verification
# 12:00      → Conclusion & applause
```

**During demo:**
- [ ] Keep hands off keyboard (script is autonomous)
- [ ] If output pauses >5 sec: check backend/frontend terminals for errors
- [ ] Narrate key sections (talk about what's happening on screen)
- [ ] Point to browser UI when ledger appears (cross-reference backend output)

---

## SECTION 7: Troubleshooting & Recovery

### Issue: Backend Crashes During Demo

```bash
# Recovery:
1. Note the error message from backend terminal
2. Restart backend: 
   cd frontend && python3 sovereign-backend.py
3. Wait for "Uvicorn running..." message
4. Verify health: curl http://127.0.0.1:8000/health
5. Restart demo script
```

**Expected cause:** Port conflict or missing dependency  
**Prevention:** Pre-check ports (see Section 1)

### Issue: Frontend Shows Blank Page

```bash
# Recovery:
1. Check DevTools Console (F12) for errors
2. Look for CORS errors or failed API calls
3. Restart frontend:
   cd frontend && npm run dev
4. Hard refresh browser: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
```

**Expected cause:** Webpack hot-reload failed  
**Prevention:** Pre-test before demo (see Section 5)

### Issue: STAR Protocol Fails

```bash
# Recovery:
1. Check backend is running: curl http://127.0.0.1:8000/health
2. Run STAR manually: python3 star_protocol/core.py
3. Check stderr for specific error (backend timeout, database locked, etc.)
4. If backend timeout: restart backend and retry STAR
5. If database locked: close any other connections
   sqlite3 /tmp/agentacct.db ".quit"
```

**Expected cause:** Backend not responding or database contention  
**Prevention:** Run smoke test (see Section 5)

### Issue: Demo Script Hangs (>10 sec on any section)

```bash
# Recovery:
1. Press Ctrl+C to stop demo script
2. Check which section failed (from last printed line)
3. Run that section manually (see demo_section_X functions in script)
4. Debug the root cause (see above)
5. Restart demo from beginning or run final sections only
```

**Expected cause:** Backend latency, database slow, or network issue  
**Prevention:** Monitor backend logs during preflight checks

---

## SECTION 8: Post-Demo (After Demo Completes)

### Step 1: Save Evidence

```bash
# Screenshot final demo output (terminal and browser side-by-side)
# Save as: demo-evidence-2026-09-15.png

# Export ledger for record-keeping
sqlite3 /tmp/agentacct.db ".mode csv" ".output ledger_export_2026-09-15.csv" "SELECT * FROM agentacct_ledger;"

# Save final report
cp reports/story-banking-governance-report.json reports/demo-final-receipt-2026-09-15.json
```

### Step 2: Archive Demo Artifacts

```bash
# Create demo archive
mkdir -p /tmp/demo_2026_09_15
cp reports/story-banking-governance-report.json /tmp/demo_2026_09_15/
cp reports/eu_compliance_report.json /tmp/demo_2026_09_15/
sqlite3 /tmp/agentacct.db ".dump" > /tmp/demo_2026_09_15/ledger_dump.sql
tar -czf demo-2026-09-15.tar.gz /tmp/demo_2026_09_15/

# Upload/archive for stakeholder review
# Location: [data room or archive path]
```

### Step 3: Feedback Collection

- [ ] Investor/audience Q&A (document questions + answers)
- [ ] Technical feasibility assessment (any concerns raised?)
- [ ] Next steps confirmation (Series A timeline, pilot expansion, etc.)

---

## SECTION 9: Emergency Rollback (If Demo Fails Completely)

**Only use if script aborts with critical errors**

```bash
# Stop all processes
pkill -f "python3 sovereign-backend.py"
pkill -f "npm run dev"

# Reset database to clean state
rm -f /tmp/agentacct.db

# Clear recent reports
rm -f reports/story-banking-governance-report.json

# Optional: Reset frontend node_modules (if suspected corruption)
cd frontend && rm -rf node_modules && npm install

# Restart from Section 2 (Backend Startup)
```

---

## SECTION 10: Success Criteria

### Demo is SUCCESSFUL if ALL of these are true:

- [ ] Script completes without Ctrl+C interruption
- [ ] All 5 sections execute (compliance, STAR, veto, fraud, ledger)
- [ ] Terminal output shows at least 3 GREEN checkmarks (✓) per section
- [ ] Browser UI responds to interactions (no hanging)
- [ ] DevTools Console has ZERO errors or warnings (or documented acceptable warnings only)
- [ ] Final output shows: "🌟 SMAOS Phase 1 Demonstration: SUCCESS"

### Demo is PARTIAL SUCCESS if:

- [ ] 4 of 5 sections complete successfully
- [ ] Ledger shows at least 1 entry with valid signature
- [ ] Veto gate triggered (even if approval button didn't work)
- [ ] Investor understands core value proposition ("human oversight + cryptographic proof")

### Demo is FAILURE if:

- [ ] <3 sections complete
- [ ] Backend crashes and cannot restart
- [ ] Frontend shows unrecoverable errors
- [ ] Investor walkaway saying "not ready" (last resort only)

---

## FINAL CHECKLIST (5 min before go-live)

```bash
# Quick sanity check (copy-paste this entire block)
echo "=== FINAL SANITY CHECK ===" && \
echo "" && \
echo "Backend health:" && \
curl -s http://127.0.0.1:8000/health | jq .status && \
echo "" && \
echo "Frontend reachable:" && \
curl -s http://127.0.0.1:5173 | head -5 | grep -q "<!DOCTYPE\|<html" && echo "✓ Frontend loads" || echo "✗ Frontend issue" && \
echo "" && \
echo "Reports exist:" && \
ls -1 reports/eu_compliance_report.json reports/granite_fraud_report.json && \
echo "" && \
echo "Demo script runnable:" && \
bash scripts/unicredit_demo_12min.sh 2>&1 | head -20 && \
echo "" && \
echo "=== READY FOR DEMO ==="
```

---

## Contact & Support

- **Technical Issues:** Andrej Leukhin (andrejlo123@gmail.com)
- **Backup Terminal A (Backend):** Have second terminal ready in case first crashes
- **Backup Internet:** None (offline-first by design)
- **Live Demo Restart:** Max 2 restarts before fallback to pre-recorded video (not ideal but acceptable)

---

**Document Version:** 1.0  
**Created:** 2026-09-04  
**Last Updated:** 2026-09-04  
**Next Review:** 2026-09-15 (morning of demo)

---

**Doctrine Alignment:** This runbook adheres to RULE 0 (Hands-On-Silicon Invariant) from CLAUDE.md v2.1. Every step is empirically verifiable on actual hardware before claiming demo readiness.
