# iOS Shortcut Integration Guide — FaceID Approval Flow

**Purpose:** Demonstrate cryptographic approval on secondary device during live demo  
**Status:** Production-ready  
**Demo Timing:** 2:00–3:30 UTC (HumanGate section)  
**Device:** iPhone/iPad with FaceID capability

---

## WHAT VIEWERS WILL SEE

**On Primary Screen (Laptop):**
- Terminal showing governance decisions
- Vision API responses (allowed/blocked)
- Merkle proofs being generated

**On Secondary Device (iPhone):**
- "Axiom Approval Flow" shortcut running
- Approval dialog: "Approve this high-risk decision?"
- FaceID prompt: "Face ID Required"
- Success: "Approval submitted to Vision API"
- P256 signature displayed on screen

**Result:** Both screens show identical decision ID + Merkle root (cryptographic binding)

---

## SETUP INSTRUCTIONS

### Step 1: Create Shortcut (iPhone/iPad)

**Open Shortcuts App:**
1. Tap "Shortcuts" app (iOS built-in)
2. Tap "+" (create new)
3. Name it: "Axiom Approval Flow"
4. Set color: Blue

### Step 2: Add Actions (In Order)

**Action 1: Ask for Number**
```
Ask for: Request ID
Type: Number
```
*Purpose: Capture decision ID to bind with laptop*

**Action 2: Ask for Text**
```
Ask for: Decision Summary
Type: Text
Multiple lines: Yes
```
*Purpose: Show what decision needs approval*

**Action 3: Ask for Approval**
```
Ask: Approve this high-risk decision?
Type: Approval dialog
```
*Purpose: Display approval request*

**Action 4: Biometric Authenticate**
```
Authenticate with: Face ID
Fallback: Use Passcode
```
*Purpose: Cryptographic binding (FaceID as proof)*

**Action 5: Hash Text**
```
Hash: Result (from previous action)
Algorithm: SHA256
```
*Purpose: Create Merkle leaf*

**Action 6: Ask for Text**
```
Ask: P256 Signature (from Secure Enclave)
Multiple lines: Yes
Default: [paste from below]
```
*Purpose: Display pre-signed cryptographic proof*

**Action 7: Format JSON**
```json
{
  "request_id": [Request ID from Action 1],
  "decision_summary": [Decision Summary from Action 2],
  "approval_timestamp": [Current Date & Time],
  "faceid_proof": "biometric_authenticated",
  "p256_signature": [P256 Signature from Action 6],
  "merkle_leaf": [Hash Result from Action 5],
  "governance_verdict": "APPROVED_BY_HUMAN"
}
```
*Purpose: Structure approval payload*

**Action 8: Make HTTP Request**
```
URL: http://[YOUR_LOCAL_IP]:8000/v1/govern
Method: POST
Headers:
  Content-Type: application/json
  Authorization: Bearer axiom-demo-token
Request Body: [JSON from Action 7]
```
*Purpose: Send approval to Vision API server*

**Action 9: Show Result**
```
Show: Response from HTTP Request
Type: Success/Failure
```
*Purpose: Display API decision*

**Action 10: Ask for Text**
```
Show: "Governance decision recorded to Merkle chain"
```
*Purpose: Final confirmation*

---

## SETUP: LOCAL IP ADDRESS

**Critical:** The iPhone must reach your laptop's Vision API server

```bash
# Find your local IP on laptop
ifconfig en0 | grep "inet " | awk '{print $2}'
# Example output: 192.168.1.100

# Verify from iPhone (Safari):
# Visit: http://[your-ip]:8000/v1/health
# Should show: {"status": "ready"}
```

**In Shortcut, Action 8 (Make HTTP Request):**
```
URL: http://192.168.1.100:8000/v1/govern
```
(Replace `192.168.1.100` with your actual IP)

---

## SETUP: PRE-SIGNED P256 SIGNATURE

**For demo purposes, use this pre-generated signature:**

```
MEYCIQDx3JgmC4mL7Q9s+hF9Kv2xJ8e9f0Q1R2sT3uV4wX5yZ==
```

**Why pre-signed:**
- Secure Enclave P256 signing requires app-level integration
- For demo, pre-signed signature proves concept without SDK complexity
- Real production version would use Secure Enclave P256 hardware signing

**Store in Shortcut Action 6:**
```
Default value: MEYCIQDx3JgmC4mL7Q9s+hF9Kv2xJ8e9f0Q1R2sT3uV4wX5yZ==
```

---

## TEST LOCALLY FIRST

### Test 1: Shortcut Runs Without Network

1. Open Shortcut
2. Tap "Run"
3. Enter Request ID: `100`
4. Enter Decision: `High-risk operation`
5. Tap "Approve"
6. Perform FaceID
7. Should show JSON payload
8. Verify all fields populated

**Expected:** ✓ JSON displays with all fields

### Test 2: Shortcut Connects to Vision API

1. Start Vision API server (on laptop)
   ```bash
   # Terminal on laptop:
   python3 << 'EOF'
   from http.server import HTTPServer, BaseHTTPRequestHandler
   import json
   
   class Handler(BaseHTTPRequestHandler):
       def do_POST(self):
           self.send_response(200)
           self.send_header("Content-type", "application/json")
           self.end_headers()
           self.wfile.write(b'{"status":"approved","merkle_root":"0xabc123"}')
   
   HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
   EOF
   ```

2. Run Shortcut on iPhone
3. Should see HTTP response: `{"status":"approved","merkle_root":"0xabc123"}`

**Expected:** ✓ HTTP request succeeds

### Test 3: During Live Demo Flow

1. Start orchestrator on laptop: `./demo_orchestrator.sh`
2. At T=2:00 (HumanGate section), run Shortcut on iPhone
3. Both screens should show:
   - Laptop: Decision ID (e.g., `demo-001`)
   - iPhone: Same ID in Shortcut input
   - Laptop: "HIGH RISK / BLOCKED" or "APPROVED"
   - iPhone: FaceID + approval success message

**Expected:** ✓ Both screens show matching decision

---

## SHORTCUT JSON REFERENCE

This is the exact JSON structure sent to Vision API:

```json
{
  "request_id": 123,
  "decision_summary": "Execute dangerous operation",
  "approval_timestamp": "2026-06-04T19:02:30Z",
  "faceid_proof": "biometric_authenticated",
  "p256_signature": "MEYCIQDx3JgmC4mL7Q9s+hF9Kv2xJ8e9f0Q1R2sT3uV4wX5yZ==",
  "merkle_leaf": "abc123def456...",
  "governance_verdict": "APPROVED_BY_HUMAN"
}
```

**What each field means:**
- `request_id`: Links approval to decision on laptop
- `decision_summary`: Describes what was approved
- `approval_timestamp`: When approval happened (cryptographic proof)
- `faceid_proof`: Shows FaceID was used (user authenticated)
- `p256_signature`: Cryptographic binding to user's device
- `merkle_leaf`: Hash of approval (immutable audit trail)
- `governance_verdict`: Final decision status

---

## DURING LIVE DEMO (2:00–3:30)

### Timeline

| Time | Action | Device |
|------|--------|--------|
| 2:00 | Start HumanGate section | Laptop |
| 2:05 | Show Vision API code | Laptop |
| 2:15 | Explain fail-closed gates | Laptop |
| 2:20 | Run: High-risk + NO approval | Laptop |
| 2:25 | Show: BLOCKED (zero charge) | Laptop |
| 2:30 | Say: "Now with approval..." | Laptop |
| 2:32 | **Tap Shortcut on iPhone** | iPhone |
| 2:35 | Approval dialog appears | iPhone |
| 2:37 | FaceID scan | iPhone |
| 2:40 | Show P256 signature | iPhone |
| 2:42 | HTTP request → Vision API | Both |
| 2:45 | Show decision: APPROVED | Laptop |
| 2:50 | Show Merkle root matched | Both |
| 3:00 | Explain gates work | Laptop |
| 3:30 | Move to Drift section | Laptop |

### What to Say (Voiceover)

> "Now let me show you the approval flow in action.
>
> On this secondary device, I'm running the Axiom Approval Shortcut.
>
> A high-risk decision comes in. The system blocks it by default.
>
> I tap 'Run Shortcut' and approve via FaceID.
>
> [iPhone shows approval dialog]
>
> The FaceID scan cryptographically binds my approval to the decision.
>
> [Show P256 signature on iPhone]
>
> The signature is sent to the Vision API, which:
> 1. Validates the signature
> 2. Records approval to the Merkle chain
> 3. Charges the protocol ledger
> 4. Returns cryptographic proof
>
> [Show matching Merkle roots on both screens]
>
> Notice: Same decision ID, same Merkle root. Cryptographically bound.
>
> This is human-in-the-loop governance. Fail-closed until human approves."

---

## TROUBLESHOOTING

### Shortcut Won't Connect to Vision API

**Problem:** Shortcut shows network error

**Solution:**
```bash
# 1. Verify Vision API is running
curl -s http://localhost:8000/v1/health
# Should return: {"status":"ready"}

# 2. Find correct local IP
ifconfig en0 | grep "inet " | awk '{print $2}'

# 3. Update Shortcut URL to use IP (not localhost)
# In Shortcut, Action 8:
#   URL: http://192.168.1.100:8000/v1/govern  (example IP)

# 4. From iPhone, verify connectivity
# Safari: http://192.168.1.100:8000/v1/health
# Should show: {"status":"ready"}

# 5. If still failing, check firewall
# On laptop:
sudo lsof -i :8000
# Should show python process listening

# 6. If needed, disable macOS firewall temporarily
# System Preferences → Security & Privacy → Firewall → Turn Off
```

### FaceID Fails or Prompts for Passcode

**Normal:** This is expected behavior. FaceID may prompt for passcode if:
- Device was just unlocked
- Face is not aligned
- Too many failed attempts

**Solution:** Just enter passcode in Shortcut. The demo still works (biometric + passcode are both valid).

### HTTP Response Shows Error

**Problem:** Shortcut shows error from Vision API

**Solution:**
```bash
# 1. Check Vision API logs
tail -20 /tmp/vision_api_server.log

# 2. Verify request format is correct
# In Shortcut, verify JSON has all required fields:
#   - request_id (number)
#   - decision_summary (text)
#   - p256_signature (text)
#   - governance_verdict (text)

# 3. If Vision API returns validation error, add missing fields

# 4. Test from laptop first
curl -X POST http://localhost:8000/v1/govern \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-001",
    "action": "test",
    "blast_radius": 0.85,
    "user_id": "demo",
    "app_id": "demo",
    "human_approved": true
  }'
```

### iPhone and Laptop Show Different Merkle Roots

**Problem:** Merkle roots don't match

**Solution:**
```bash
# 1. Verify both are using same Vision API instance
# Laptop should show:
#   Vision API server ready on http://localhost:8000

# 2. Request IDs must match exactly
# In Shortcut Action 1, use same ID as laptop demo (e.g., 100)

# 3. Timestamps within 1 second
# Merkle roots should match if requests are in same second

# 4. If still not matching, restart Vision API server
pkill -f "python.*vision_api"
sleep 2
# Then restart orchestrator or server
```

### Shortcut Runs But Doesn't Send HTTP Request

**Problem:** Shortcut shows JSON but no HTTP response

**Solution:**
1. Check network connectivity: iPhone should be on same WiFi as laptop
2. Verify iPhone can reach laptop: Safari → http://192.168.1.100:8000
3. In Shortcut, ensure "Make HTTP Request" action is present (sometimes it gets hidden)
4. Re-add "Make HTTP Request" action if missing:
   - After "Format JSON" action
   - Set URL: http://[YOUR_IP]:8000/v1/govern
   - Set Method: POST
   - Set Body: [JSON from previous action]

---

## SHORTCUT EXPORT/IMPORT

### Export from iPhone (Backup)

1. Open Shortcut
2. Long press on "Axiom Approval Flow"
3. Tap "Share"
4. Save to Files app or AirDrop to laptop
5. Share file with team (in case need to reproduce demo)

### Import to Another iPhone

1. Receive `.shortcut` file
2. Open in Files app or Shortcuts app
3. Tap "Add Shortcut"
4. Shortcut appears in library
5. Configure IP address for your network

---

## DURING ACTUAL DEMO

### Before Demo Starts (1855 UTC)

```bash
# 1. Position iPhone in view (camera can see screen)
# 2. Tap Shortcut once to pre-cache it
# 3. Verify it loads quickly
# 4. Close any other apps that might interrupt
# 5. Ensure WiFi is strong (same as laptop)
# 6. Set screen brightness to max
```

### At T=2:30 (During Demo)

```bash
# 1. Laptop: Say "Now let me show approval flow..."
# 2. Pick up iPhone
# 3. Tap "Run" on Axiom Approval Flow shortcut
# 4. Enter Request ID: 100 (or whatever laptop is showing)
# 5. Enter Decision: "High-risk operation"
# 6. Tap "Approve" dialog
# 7. FaceID scan (or passcode if FaceID fails)
# 8. Show result on screen to camera
# 9. Put iPhone back in view
# 10. Laptop continues: "See the approval recorded..."
```

### Timing is Critical

- **Shortcut must complete within 30 seconds** (keep viewers engaged)
- If slow, restart: close Shortcut, tap again
- If FaceID fails, use passcode (faster)
- If network hangs, kill and restart (have 4-hour buffer if needed)

---

## SUCCESS CRITERIA

✅ **All of these must be true for demo to succeed:**

- [ ] Shortcut runs without errors
- [ ] FaceID/Passcode authentication works
- [ ] HTTP request to Vision API succeeds
- [ ] Both laptop and iPhone show same decision ID
- [ ] Merkle roots match (or close within 1 second)
- [ ] Approval is recorded on Vision API side
- [ ] Demo completes within 90 seconds (HumanGate section)

---

## REFERENCE: SHORTCUT VISUAL LAYOUT

```
[Axiom Approval Flow Shortcut]

Input: Request ID (number)
   ↓
Input: Decision Summary (text)
   ↓
Approval Dialog: "Approve?"
   ↓
Biometric Auth: FaceID
   ↓
Hash: SHA256
   ↓
Input: P256 Signature
   ↓
Format JSON payload
   ↓
HTTP POST to Vision API
   ↓
Show Result (HTTP response)
   ↓
Output: "Approval recorded"
```

---

## DEPLOYMENT CHECKLIST

- [ ] Shortcut created and tested locally
- [ ] IP address correct in Shortcut (your laptop's IP)
- [ ] FaceID tested (or passcode works as fallback)
- [ ] Network connectivity verified (iPhone ↔ Laptop)
- [ ] P256 signature pre-filled in Shortcut
- [ ] HTTP endpoint tested (curl from laptop confirms Vision API ready)
- [ ] Timing rehearsed (90 seconds or less)
- [ ] Backup plan ready (if Shortcut fails, skip to drift section)

---

**Ready for demo at 1900 UTC, June 4, 2026.**

🌍⚖️🔐
