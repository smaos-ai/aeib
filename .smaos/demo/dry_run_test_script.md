# Prague Demo Validation — Dry-Run Test Script
**Date:** June 23-24, 2026  
**Owner:** Demo Team (Andrei)  
**Objective:** Validate fail-closed properties under 10 test scenarios (normal + adversarial + failure)  
**Success Criteria:** All 10 tests PASS with no crashes; fail-closed gates activate on error  
**Timeline:** June 24, 0800–1000 UTC (2 hours)

---

## Test Environment Setup

### Prerequisites
- Machine: Mac Studio M3 Pro (macOS 14+, 32GB RAM minimum)
- Network: Air-gapped (WiFi OFF, Ethernet disconnected)
- Build: `cargo build --release` completed and binary available at `target/release/demo-app`
- Logging: All test output captured to `logs/dry_run_test_YYYYMMDD_HHMMSS.log`

### Pre-Test Checks
```bash
# Verify network isolation
lsof -i -P -n | grep ESTABLISHED  # Should return 0 connections

# Verify binary ready
file target/release/demo-app  # Should exist and be executable

# Verify no cloud SDK refs
strings target/release/demo-app | grep -i "aws\|azure\|gcp"  # Should return nothing
```

---

## Test Scenarios (10 Total)

### Test 1: Happy Path — Normal Decision Flow
**Objective:** Verify Genesis Capsule executes correctly under normal conditions  
**Input:** Valid decision with:
- Merkle-DAG root hash (SHA256)
- Input payload (simple JSON: `{"action": "governance", "severity": "low"}`)
- Ed25519 public key (valid signer)
- N=3 swarm nodes voting consensus (all 3 vote YES)

**Expected Behavior:**
- ✅ Capsule generates hash proof
- ✅ Merkle chain verifies (no tampering)
- ✅ Consensus gate opens (3/3 nodes approve)
- ✅ Ed25519 signature generated
- ✅ AP2 settlement computed (1% platform, 99% creator)
- ✅ Execution proceeds (no crash)
- ✅ Andon log: `[PASS] Normal execution, signature verified`

**Test Command:**
```bash
./target/release/demo-app --scenario test_happy_path --log-level info
```

**Expected Log Output:**
```
[INFO] Genesis Capsule initialized
[INFO] Merkle-DAG root: 0x<hash>
[INFO] Consensus: 3/3 nodes voting YES
[INFO] Ed25519 signature verified
[INFO] AP2 settlement: 1% platform (creator_fee), 99% creator (creator_revenue)
[INFO] Execution PASSED, capsule deterministic replay successful
```

---

### Test 2: Invalid Input — Merkle-DAG Injection Attack
**Objective:** Verify system rejects tampered data without executing  
**Input:** Valid decision with:
- Merkle-DAG root hash (SHA256) — MODIFIED after creation
- Input payload (injected malicious data: `{"action": "escalate", "override": true}`)
- Ed25519 public key (valid signer)
- N=3 swarm nodes (all vote YES, unaware of tampering)

**Expected Behavior:**
- ✅ Merkle chain verification fails (hash mismatch)
- ✅ Tamper detection gate closes (FAIL-CLOSED)
- ✅ Execution BLOCKED (decision NOT executed)
- ✅ Error logged with original hash vs. computed hash
- ✅ Andon log: `[FAIL] Merkle-DAG integrity check failed; execution blocked`
- ✅ System remains stable (no crash, no silent corruption)

**Test Command:**
```bash
./target/release/demo-app --scenario test_merkle_tamper --log-level info --inject-payload "malicious_data"
```

**Expected Log Output:**
```
[INFO] Genesis Capsule initialized
[WARN] Merkle-DAG verification in progress...
[ERROR] Hash mismatch detected:
  Expected: 0x<original_hash>
  Computed: 0x<tampered_hash>
[CRITICAL] Merkle-DAG integrity check FAILED
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE (no execution attempted)
```

---

### Test 3: Tamper Attempt — Modify Previous Decision Hash
**Objective:** Verify Merkle chain detects and rejects lineage modifications  
**Input:** Decision flow with:
- Lineage of 3 previous decisions (Day 1, 2, 3)
- Attempt to modify Day 2 decision hash in the chain
- Current decision depends on Day 2 (parent hash validation)

**Expected Behavior:**
- ✅ Lineage chain verification fails at Day 2 parent check
- ✅ Tainting propagates backward (Day 3 inherits bad parent)
- ✅ Execution BLOCKED for all downstream decisions
- ✅ Audit log shows exact tampering point
- ✅ Andon log: `[FAIL] Lineage verification failed at decision 2/3; execution blocked`
- ✅ System enters QUARANTINE mode (no new decisions until lineage is fixed)

**Test Command:**
```bash
./target/release/demo-app --scenario test_lineage_tamper --decision-count 3 --modify-parent 2
```

**Expected Log Output:**
```
[INFO] Genesis Capsule decision flow initialized
[INFO] Decision 1/3: hash=0x<d1>, timestamp=2026-06-20T08:00:00Z
[INFO] Decision 2/3: hash=0x<d2>, parent=0x<d1>, timestamp=2026-06-20T08:05:00Z
[WARN] Decision 2/3 has been tampered with (hash mismatch in lineage)
[CRITICAL] Lineage verification FAILED at decision 2/3
[INFO] Andon breaker triggered: QUARANTINE mode activated
[INFO] System state: SAFE (all downstream decisions blocked)
```

---

### Test 4: Consensus Failure — N-1 Nodes Vote No
**Objective:** Verify system blocks execution when consensus threshold not met  
**Input:** Decision routed to N=3 swarm nodes:
- Node 1: YES (approve execution)
- Node 2: NO (reject execution)
- Node 3: NO (reject execution)
- Consensus threshold: >66% (2/3 needed) — FAILED (only 1/3 approval)

**Expected Behavior:**
- ✅ Consensus gate detects insufficient approval (1/3 < 2/3)
- ✅ Execution BLOCKED without escalation (fail-closed)
- ✅ Decision enters QUARANTINE state (waits for operator override, does NOT auto-escalate)
- ✅ Andon log shows per-node votes
- ✅ Andon log: `[FAIL] Consensus failed: 1/3 approved (<66% threshold); execution quarantined`
- ✅ System remains stable (no rogue escalation, no crash)

**Test Command:**
```bash
./target/release/demo-app --scenario test_consensus_fail --node-votes "YES,NO,NO"
```

**Expected Log Output:**
```
[INFO] Genesis Capsule consensus routing
[INFO] Node 1: decision=YES (approval)
[INFO] Node 2: decision=NO (rejection)
[INFO] Node 3: decision=NO (rejection)
[WARN] Consensus threshold check: 1/3 ≠ >66%
[CRITICAL] Consensus FAILED
[INFO] Andon breaker triggered: decision quarantined (no escalation)
[INFO] System state: SAFE, awaiting operator override
```

---

### Test 5: Validator Timeout — Decision Validator Hangs
**Objective:** Verify system times out gracefully without waiting indefinitely  
**Input:** Decision routed to validator that artificially hangs:
- Validator receives request at T=0
- No response for 5 seconds (exceeds 1000ms timeout)
- Background process must kill the validator before timeout fires

**Expected Behavior:**
- ✅ Timeout gate activates at T=1000ms (configurable)
- ✅ Validator process killed (SIGKILL)
- ✅ Execution BLOCKED (fail-closed, not auto-retry)
- ✅ Decision enters QUARANTINE (operator must investigate)
- ✅ Andon log: `[FAIL] Validator timeout after 1000ms; execution blocked`
- ✅ System recovers gracefully (no hanging processes, no resource leaks)

**Test Command:**
```bash
./target/release/demo-app --scenario test_validator_timeout --timeout-ms 1000 --hang-duration 5000
```

**Expected Log Output:**
```
[INFO] Genesis Capsule routing to validator
[INFO] Validator started at T=0ms
[WARN] Validator response timeout: waiting at T=500ms...
[WARN] Validator response timeout: waiting at T=900ms...
[CRITICAL] Validator timeout at T=1000ms (exceeded limit)
[INFO] Terminating validator process (PID 12345)
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE, validator recovered
```

---

### Test 6: Adversarial Input — Malicious Payload Injection
**Objective:** Verify payload inspection gate rejects hostile data without parsing  
**Input:** Decision with malicious payload:
- XSS vector: `<script>alert('xss')</script>` in decision field
- SQL injection: `'; DROP TABLE decisions; --` in action field
- Buffer overflow candidate: 10KB string in fixed 1KB field
- Executable payload: Binary shellcode in text field

**Expected Behavior:**
- ✅ Payload inspection gate runs BEFORE deserialization
- ✅ Malicious patterns detected (XSS, SQL, oversized, binary)
- ✅ Execution BLOCKED (fail-closed)
- ✅ Payload quarantined (not parsed, not executed)
- ✅ Andon log: `[FAIL] Payload inspection: 4 security violations detected; execution blocked`
- ✅ System remains stable (no injection, no parsing error)

**Test Command:**
```bash
./target/release/demo-app --scenario test_adversarial_payload \
  --inject-xss '<script>alert("xss")</script>' \
  --inject-sql "'; DROP TABLE decisions; --" \
  --inject-oversized $(printf 'A%.0s' {1..10000}) \
  --inject-binary '\x00\x01\x02'
```

**Expected Log Output:**
```
[INFO] Genesis Capsule payload inspection initiated
[WARN] Payload inspection: XSS pattern detected in field 'decision'
[WARN] Payload inspection: SQL pattern detected in field 'action'
[WARN] Payload inspection: Oversized field detected (10000 bytes > 1000 limit)
[WARN] Payload inspection: Binary pattern detected in field 'data'
[CRITICAL] Payload inspection FAILED (4 violations)
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE, payload quarantined
```

---

### Test 7: Network Failure — No Swarm Response
**Objective:** Verify system gracefully handles swarm node unavailability  
**Input:** Decision requires N=3 consensus, but:
- Node 1: REACHABLE (responds YES)
- Node 2: UNREACHABLE (timeout after 1000ms)
- Node 3: UNREACHABLE (timeout after 1000ms)
- Quorum rule: >50% must respond for consensus → FAILED (only 1/3 reachable)

**Expected Behavior:**
- ✅ Consensus gateway detects quorum failure (1/3 < 50%)
- ✅ Execution QUARANTINED (does NOT auto-retry or escalate)
- ✅ Fallback: Safe default policy applied (no decision until quorum restored)
- ✅ Andon log: `[FAIL] Swarm quorum lost (1/3 nodes reachable); execution quarantined`
- ✅ System remains stable (no partial execution, no timeout pile-up)

**Test Command:**
```bash
./target/release/demo-app --scenario test_network_failure --node-reachable "UP,DOWN,DOWN"
```

**Expected Log Output:**
```
[INFO] Genesis Capsule swarm consensus routing
[INFO] Node 1: REACHABLE (decision=YES)
[WARN] Node 2: UNREACHABLE (timeout after 1000ms)
[WARN] Node 3: UNREACHABLE (timeout after 1000ms)
[CRITICAL] Swarm quorum check: 1/3 ≠ >50%
[CRITICAL] Swarm quorum LOST
[INFO] Andon breaker triggered: decision quarantined (safe default applied)
[INFO] System state: SAFE, awaiting network recovery
```

---

### Test 8: Cryptographic Failure — Ed25519 Key Unavailable
**Objective:** Verify system fails closed when signing key is missing  
**Input:** Valid decision, but:
- Ed25519 private key file deleted or inaccessible
- Public key still available (for verification)
- System attempts to sign decision (required for execution approval)

**Expected Behavior:**
- ✅ Signing gate attempts key load (fails)
- ✅ Execution BLOCKED immediately (fail-closed)
- ✅ No fallback signing (no unsigned decisions allowed)
- ✅ No attempt to proceed without cryptographic proof
- ✅ Andon log: `[FAIL] Ed25519 signing key unavailable; execution blocked`
- ✅ System recovers when key is restored (re-run decision flow)

**Test Command:**
```bash
./target/release/demo-app --scenario test_key_unavailable --key-file "/nonexistent/ed25519.key"
```

**Expected Log Output:**
```
[INFO] Genesis Capsule initialization
[WARN] Loading Ed25519 signing key from /nonexistent/ed25519.key...
[CRITICAL] Key file not found (ENOENT)
[ERROR] Signing gate activation FAILED
[CRITICAL] Cannot sign decision without Ed25519 key
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE, awaiting key restoration
```

---

### Test 9: Configuration Error — Invalid SLO Threshold
**Objective:** Verify system pre-flight checks catch configuration errors  
**Input:** Decision with invalid SLO parameters:
- Risk SLO threshold: 150% (invalid, must be 0–100%)
- Approval timeout: -5000ms (invalid, must be positive)
- Consensus requirement: 0% (invalid, must be >50%)

**Expected Behavior:**
- ✅ Pre-flight gate validates config BEFORE decision processing
- ✅ Config errors detected (3 violations found)
- ✅ Execution BLOCKED (fail-closed)
- ✅ No partial execution with bad config
- ✅ Andon log: `[FAIL] Pre-flight config validation failed (3 violations); execution blocked`
- ✅ Operator must fix config before re-run

**Test Command:**
```bash
./target/release/demo-app --scenario test_config_error \
  --risk-threshold 150 \
  --approval-timeout -5000 \
  --consensus-requirement 0
```

**Expected Log Output:**
```
[INFO] Genesis Capsule pre-flight configuration check
[ERROR] Config validation: risk_threshold=150% (must be 0-100%)
[ERROR] Config validation: approval_timeout=-5000ms (must be positive)
[ERROR] Config validation: consensus_requirement=0% (must be >50%)
[CRITICAL] Pre-flight config validation FAILED (3 violations)
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE, fix config and retry
```

---

### Test 10: Replay Attack — Re-Execute Old Decision
**Objective:** Verify system rejects timestamp-based replay attacks  
**Input:** Two decision flows:
- Decision 1: Created at 2026-06-20T08:00:00Z, executed successfully
- Decision 2: Exact copy of Decision 1 (same payload, same hash), timestamp unchanged
- Attempt to execute Decision 2 (replay attack) at 2026-06-20T08:05:00Z

**Expected Behavior:**
- ✅ Timestamp guard detects duplicate timestamp in swarm history
- ✅ Merkle chain shows Decision 1 already executed at T=08:00
- ✅ Execution BLOCKED (fail-closed, no re-execution)
- ✅ Andon log: `[FAIL] Duplicate timestamp detected (decision already executed); execution blocked`
- ✅ Audit trail immutable: both attempts logged, only Decision 1 executed

**Test Command:**
```bash
./target/release/demo-app --scenario test_replay_attack --decision-timestamp "2026-06-20T08:00:00Z" --replay-attempt true
```

**Expected Log Output:**
```
[INFO] Genesis Capsule history check
[INFO] Decision A: hash=0x<d1>, timestamp=2026-06-20T08:00:00Z (EXECUTED)
[INFO] Decision B: hash=0x<d1>, timestamp=2026-06-20T08:00:00Z (DUPLICATE)
[WARN] Timestamp guard: duplicate timestamp detected in decision B
[CRITICAL] Replay attack detected: decision already executed
[INFO] Andon breaker triggered: execution blocked (fail-closed)
[INFO] System state: SAFE, replay rejected
[INFO] Audit trail: both decisions logged, only Decision A executed
```

---

## Validation Matrix

| # | Test Scenario | PASS | FAIL | Notes |
|---|---------------|------|------|-------|
| 1 | Happy path | ☐ | ☐ | Normal execution, no crashes |
| 2 | Merkle injection | ☐ | ☐ | Tamper detection gate works |
| 3 | Lineage tamper | ☐ | ☐ | Chain verification catches modification |
| 4 | Consensus fail | ☐ | ☐ | Blocks on insufficient approval |
| 5 | Validator timeout | ☐ | ☐ | Graceful timeout, no hangs |
| 6 | Adversarial input | ☐ | ☐ | Payload inspection rejects hostile data |
| 7 | Network failure | ☐ | ☐ | Quorum loss → quarantine |
| 8 | Key unavailable | ☐ | ☐ | Signing gate blocks unsigned decisions |
| 9 | Config error | ☐ | ☐ | Pre-flight catch misconfiguration |
| 10 | Replay attack | ☐ | ☐ | Timestamp guard prevents re-execution |

---

## Success Criteria (ALL MUST PASS)

- ✅ No crashes under any scenario (return code 0 or graceful error)
- ✅ Fail-closed gates activate on error (execution blocked, never escalates)
- ✅ Merkle chain integrity maintained (no silent corruption detected)
- ✅ Swarm consensus enforced (N-1 failure → quarantine, not escalation)
- ✅ Cryptographic proof generated on success (Ed25519 signature present in logs)
- ✅ Andon breaker triggers all 9 failure scenarios (payload quarantine, safe defaults applied)
- ✅ System recovers gracefully (can re-run failed tests after fix)

---

## Execution Timeline

| Time | Task | Owner | Duration |
|------|------|-------|----------|
| 0800 | Pre-flight setup (network check, binary verify) | Demo Team | 10 min |
| 0810 | Test 1 (Happy path) | Demo Team | 5 min |
| 0815 | Tests 2-4 (Merkle, lineage, consensus) | Demo Team | 15 min |
| 0830 | Tests 5-7 (Timeout, payload, network) | Demo Team | 15 min |
| 0845 | Tests 8-10 (Crypto, config, replay) | Demo Team | 15 min |
| 0900 | Validate results & signature (all tests passed) | Demo Team | 10 min |
| 0910 | Generate demo video script (30 sec highlight reel) | Demo Team | 30 min |
| 0940 | Capture video of fail-closed proof (3 scenes) | Demo Team | 15 min |
| 0955 | QR code generation (video link embedding) | Demo Team | 5 min |
| 1000 | Final verification & artifact hand-off | Demo Team | 5 min |

---

## Artifact Outputs

All logs and results saved to:
- **Test logs:** `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/logs/dry_run_test_YYYYMMDD_HHMMSS.log`
- **Video:** `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/videos/genesis_capsule_dry_run_2026_06_24.mp4`
- **QR code:** `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/demo_qr.png`
- **Results:** `/Users/andriileukhin/Documents/SovereignNexus/.smaos/demo/demo_validation_results.md`

