# STAR SPEC: STORY-001 — Treasury Officer Authorizes High-Risk Transfer

## S — Story

**Story ID:** STORY-001  
**Persona:** Treasury Officer at UniCredit Bank  
**Risk Level:** HIGH  
**Regulatory Context:** Basel III CAR (Capital Adequacy Ratio) breach  

**Situation:**  
Treasury officer receives a €2.4M transfer request to a new counterparty. The system flags it as high-risk because:
- Amount > €1M threshold
- Counterparty credit rating: unrated
- System estimates CAR impact: -0.82% (below 10.50% minimum)

**Task:**  
Officer must review the risk assessment, authorize the transfer with an Ed25519 cryptographic signature, and receive an immutable receipt proving authorization.

**Expected Outcome:**  
- Transfer authorized
- Ed25519 signature generated and verified
- Receipt persisted to EXEC_LOG
- Merkle root computed and stored
- Trace spans in correct order: intent → classification → veto gate → authorization → receipt

---

## T — Trace (Complete Execution Path)

| Step | Actor | Action | System State | Verify | Timeout |
|------|-------|--------|--------------|--------|---------|
| 1 | User | Navigate to http://127.0.0.1:5173 | React app loads, 3-pane layout visible | `[data-testid='governance-pane']` visible | 10s |
| 2 | User | Switch capsule to "Treasury (Basel III)" | Left pane shows Treasury form fields | Form fields visible (amount, counterparty, etc.) | 5s |
| 3 | User | Fill intent form: €2.4M, EUR, new counterparty | Form validated, submit button enabled | All fields have values, no error messages | 5s |
| 4 | User | Click "Send to Work Surface" | API call POST /api/execute initiated | HTTP 201 response, trace_id returned | 10s |
| 5 | System | Classification engine runs | Intent classified as "treasury_transfer", severity = "block" | Trace span type="classification" exists, confidence > 0.90 | 5s |
| 6 | System | Blast radius computed | CAR impact calculated: -0.82%, below 10.50% | Trace span type="veto_gate" exists, payload.blast_radius = 0.82 | 5s |
| 7 | System | Veto gate triggers HUMAN_GATE | Yellow veto card appears in center pane | `[data-testid='veto-card']` visible, border-color = amber | 5s |
| 8 | System | Veto card displays risk details | Card shows Basel III classification, CAR breach reason | Text contains "CET1 ratio breach", "10.18% < 10.50%" | 3s |
| 9 | User | Click "✓ Authorize & Sign (Ed25519)" | Authorization prompt appears (browser crypto API) | Button clickable, click triggers signing | 3s |
| 10 | System | Ed25519 signature generated on client | Signature bytes created via crypto.subtle.sign() | Signature hex string length = 128 (64 bytes), valid format | 5s |
| 11 | System | Signature self-verified immediately | Crypto.subtle.verify() returns TRUE | Receipt object has verified=true | 2s |
| 12 | System | Receipt object created | Receipt contains: id, timestamp, alg, payload, signature, publicKey | Receipt visible in right pane | 3s |
| 13 | System | Veto card disappears | state.resolvedIntentId === state.currentIntentId | `[data-testid='veto-card']` not visible | 2s |
| 14 | System | Receipt persisted to EXEC_LOG | POST /api/rce/decision succeeds, returns receipt_id | HTTP 200 response, receipt_id = rcpt-XXXXXXXX | 5s |
| 15 | System | Merkle root computed | SHA-256 hash of all trace spans | Receipt contains merkle_root, length = 64 hex chars | 2s |
| 16 | User | Expand receipt in right pane | Full receipt details visible | Canonical payload shown, signature shown, merkle root shown | 2s |
| 17 | User | Click "Verify" button on receipt | Crypto.subtle.verify() runs in browser | Button shows "✓ Verified" (green) | 5s |
| 18 | System | Database written | EXEC_LOG table updated with new row | SELECT * FROM exec_log ORDER BY timestamp DESC LIMIT 1 returns new row | 3s |

---

## A — Assertions (Every Step Verified)

### UI Assertions
```python
# Step 1: React app loads
assert page.locator("[data-testid='governance-pane']").is_visible()
assert page.locator("[data-testid='left-pane']").is_visible()
assert page.locator("[data-testid='center-pane']").is_visible()
assert page.locator("[data-testid='right-pane']").is_visible()

# Step 2: Treasury capsule selected
assert page.locator("[data-testid='amount-input']").is_visible()
assert page.locator("[data-testid='counterparty-input']").is_visible()

# Step 7: Veto card appears
veto_card = page.locator("[data-testid='veto-card']")
assert veto_card.is_visible()
assert veto_card.get_attribute("style") and "amber" in veto_card.get_attribute("style").lower()

# Step 13: Veto card disappears after authorization
assert not page.locator("[data-testid='veto-card']").is_visible()

# Step 12: Receipt appears
receipt = page.locator("[data-testid='receipt-card']")
assert receipt.is_visible()
assert receipt.locator("text=✓ Verified").is_visible() or receipt.locator("text=⏳ Unverified").is_visible()
```

### API Assertions
```python
# Step 4: Execute returns mandate and trace_id
response = client.post("/api/execute", json={
    "capsule": "treasuryBaselIII",
    "intent": {"amount": "2400000", "counterparty": "DE89..."},
    "classification": {"highestSeverity": "block"}
})
assert response.status_code == 201
data = response.json()
assert "mandate_id" in data
assert "trace_id" in data
assert data["status"] == "ready"

# Step 14: Decision authorization succeeds
response = client.post("/api/rce/decision", json={
    "mandate_id": data["mandate_id"],
    "decision": "authorize",
    "signature": "sig:ed25519:..."
})
assert response.status_code == 200
receipt_data = response.json()
assert receipt_data["status"] == "APPROVED_WITH_OVERRIDE"
assert "receipt_id" in receipt_data
```

### Trace Assertions
```python
# Fetch trace for verification
response = client.get(f"/api/traces/{trace_id}")
trace = response.json()

# Step 5: Classification span exists
spans = trace["spans"]
span_types = [s["span_type"] for s in spans]
assert "classification" in span_types

# Step 6: Veto gate span exists
assert "veto_gate" in span_types
veto_span = next(s for s in spans if s["span_type"] == "veto_gate")
assert veto_span["payload"]["blast_radius"] == 0.82

# Step 15: Merkle root correct
assert trace["merkle_root"] is not None
assert len(trace["merkle_root"]) == 64  # SHA-256 hex

# Span order verification
types_in_order = [s["span_type"] for s in spans]
assert types_in_order.index("intent") < types_in_order.index("classification")
assert types_in_order.index("classification") < types_in_order.index("veto_gate")
assert types_in_order.index("veto_gate") < types_in_order.index("authorization")
assert types_in_order.index("authorization") < types_in_order.index("receipt")
```

### Cryptography Assertions
```python
# Step 10-11: Signature valid
receipt = get_latest_receipt()
assert receipt["alg"] == "Ed25519"
assert receipt["verified"] == True
assert len(receipt["signatureBase64"]) > 0
assert receipt["publicKeyBase64"] is not None

# Step 17: Live verification in browser
# (Playwright will click "Verify" and assert UI shows "✓ Verified")
verify_button = page.locator("[data-testid='verify-button']")
verify_button.click()
assert page.locator("text=✓ Verified").is_visible()
```

### Database Assertions
```python
# Step 18: EXEC_LOG written
import sqlite3
conn = sqlite3.connect("/tmp/agentacct.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM agentacct_ledger ORDER BY timestamp DESC LIMIT 1")
row = cursor.fetchone()
assert row is not None
assert row[3] == "veto.authorize"  # action column
assert row[4] == "APPROVED_WITH_OVERRIDE"  # status column
assert row[11] is not None  # merkle_root column
conn.close()
```

---

## R — Receipt (Cryptographic Proof)

**Final State:**
- Receipt ID: `rcpt-XXXXXXXX` (8-char unique ID)
- Timestamp: ISO 8601 (2026-09-02T19:05:30Z)
- Algorithm: Ed25519 (Post-Quantum Resistant)
- Action: `veto.authorize`
- Amount: €2.4M (captured in signed payload)
- Signature: 128-char hex string (64 bytes)
- Public Key: 88-char base64 (Ed25519 public key)
- Merkle Root: 64-char hex (SHA-256 of all trace spans)
- Verified: TRUE (crypto.subtle.verify() passed)

**Canonical Payload (Signed):**
```json
{
  "action": "veto.authorize",
  "amount": "€2400000",
  "classification": "Basel III / CAR-Impacting",
  "rules": ["Large Amount Transfer", "Unrated Counterparty", "CAR Breach"],
  "timestamp": "2026-09-02T19:05:30.123Z"
}
```

**EXEC_LOG Entry:**
```
id: rcpt-af2146ad
timestamp: 2026-09-02 19:05:30
mandate_id: mandate-b0b18d89
action: veto.authorize
status: APPROVED_WITH_OVERRIDE
cet1_ratio_current: 11.2
cet1_ratio_projected: 10.18
signature_ed25519: sig:ed25519:9a8b7c6d...
merkle_root: a1b2c3d4e5f6g7h8...
git_commit: 5430f8d2
```

---

## Edge Cases (Must Also Test)

### Edge Case 1: CAR Breach → RED Card (Hard Reject)
**Scenario:** User tries to submit €15M transfer (exceeds hard limit)
**Expected:** RED veto card, no authorize button, no receipt generated

### Edge Case 2: User Rejects Authorization
**Scenario:** User clicks "🚫 Veto & Abort"
**Expected:** Receipt shows `veto.revise` action, status = `REJECTED_BY_CRO`, no execution

### Edge Case 3: Network Timeout During Signing
**Scenario:** Browser loses connection while Ed25519 signature is being computed
**Expected:** Timeout error shown, user can retry

### Edge Case 4: Invalid Ed25519 Signature
**Scenario:** Attacker tampers with signature bytes
**Expected:** Verification button shows "✗ Invalid", ledger entry never written

### Edge Case 5: EXEC_LOG Write Fails
**Scenario:** Database locked or disk full during EXEC_LOG insert
**Expected:** Error message, receipt NOT marked as valid, user prompted to retry

---

## Success Criteria

✅ **All 18 trace steps complete in order**  
✅ **Ed25519 signature generated and verified**  
✅ **Receipt persisted to EXEC_LOG**  
✅ **Merkle root computed from all spans**  
✅ **No console errors**  
✅ **Zero network calls to external services**  
✅ **All 5 edge cases tested and passing**  

---

**Story Status:** READY FOR IMPLEMENTATION  
**Test Framework:** Playwright + pytest + sqlite3  
**Expected Duration:** 18 steps, ~3 minutes wall-clock time  
**Acceptable Failure Rate:** 0% (all steps must pass)
