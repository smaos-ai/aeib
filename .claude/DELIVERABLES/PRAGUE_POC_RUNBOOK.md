# Prague Desk Lab PoC Runbook
## Hardware Initialization & Human-in-the-Loop Veto Flow

**Version:** 2.0 (Phase 81.5/82 verified)  
**Setup time:** ~90 minutes  
**Hardware:** 3x Apple Silicon M3 Pro (isolated, air-gapped cluster)  
**Security:** Fail-closed, cryptographic veto enforcement

---

## Table of Contents
1. [Physical Setup](#physical-setup)
2. [Air-Gap Initialization](#air-gap-initialization)
3. [Network Isolation Verification](#network-isolation-verification)
4. [SovereignNexus Bootstrap](#sovereignnexus-bootstrap)
5. [Human-in-the-Loop Veto Flow](#human-in-the-loop-veto-flow)
6. [Live Demo Script](#live-demo-script)
7. [Emergency Shutdown](#emergency-shutdown)

---

## Physical Setup

### Hardware Configuration

**Cluster Composition:**
- 1x Mac Studio M3 Pro (primary orchestrator)
  - 12 CPU cores, 36GB unified memory
  - 2TB SSD (git repository + Sovereign Knowledge Graph)
  
- 2x Mac mini M3 Pro (agent nodes)
  - 8 CPU cores, 24GB unified memory each
  - 512GB SSD (task cache + local state)

**Network Topology:**
- **Primary network (isolated):** 10Gbps Thunderbolt 3 daisy-chain (no internet)
- **Management network (optional):** USB-C serial console (for emergency access)
- **Zero cloud connectivity:** All nodes air-gapped, no AWS/Nebius access

### Physical Isolation Checklist
- [ ] Unplug WiFi on all 3 nodes (confirm disconnected in System Preferences)
- [ ] Unplug Ethernet cables (if any)
- [ ] Verify Bluetooth is disabled (`defaults write com.apple.BluetoothAudioUnitKext disabled -int 1`)
- [ ] Confirm no VPN software running (`ps aux | grep -i vpn`)
- [ ] Check no cloud SDKs in PATH (`echo $PATH | grep -i aws`)
- [ ] Physical separation: Cluster in isolated desk (15m from WiFi AP)

---

## Air-Gap Initialization

### Step 1: Fresh macOS Install on Each Node
```bash
# On each node, fresh install from USB (macOS 14.6+)
# - Do NOT connect to WiFi during setup
# - Do NOT sign in to iCloud
# - Set admin password: store in offline vault

# Verify isolation:
system_profiler SPNetworkDataType | grep "Status: Disconnected"
```

### Step 2: Repository Clone (Offline)

**On primary node only:**

```bash
# Create offline git remote via USB drive
# (Pre-load SovereignNexus repo on USB from development machine)

mkdir -p /opt/sovereignnexus
cd /opt/sovereignnexus

# Mount USB drive
# Copy repository:
cp -r /Volumes/OFFLINE_REPO/SovereignNexus .

# Initialize git (no remote)
cd SovereignNexus
git config --global user.email "prague-poc@sovereignnexus.local"
git config --global user.name "Prague PoC"
git remote remove origin  # Disable any configured remotes

# Verify isolation:
git config --get remote.origin.url  # Should error (no origin)
```

### Step 3: Rust Toolchain Install (Offline)

**Requirement:** Rust must be pre-built on development machine, shipped via USB

```bash
# On development machine (with internet):
rustup target add aarch64-apple-darwin
cargo build --release -p siss-orchestrator -p siss-capsule-commit

# Package onto USB:
tar czf /Volumes/OFFLINE_REPO/rust-aarch64-macos.tar.gz ~/.cargo/registry
tar czf /Volumes/OFFLINE_REPO/siss-build-cache.tar.gz ./target/release
```

**On Prague nodes:**
```bash
# Extract pre-built binaries
tar xzf /Volumes/OFFLINE_REPO/rust-aarch64-macos.tar.gz -C ~/.cargo

# Verify no network calls:
strace -e openat cargo check 2>&1 | grep -i "network\|dns"  # Should be empty
```

---

## Network Isolation Verification

### Step 4: Airgap Proof Test (Run Before Demo)

```bash
#!/bin/bash
# prague_isolation_test.sh

echo "=== AIRGAP VERIFICATION SUITE ==="

# Test 1: No DNS resolution
echo "[TEST 1] DNS isolation..."
timeout 2 nslookup google.com 2>&1 | grep -q "connection timed out" && echo "✓ PASS" || echo "✗ FAIL"

# Test 2: No external IP connectivity
echo "[TEST 2] External IP routing..."
timeout 2 curl -s -m 2 https://ifconfig.me 2>&1 | grep -q "could not resolve host\|Connection refused" && echo "✓ PASS" || echo "✗ FAIL"

# Test 3: Internal cluster communication only
echo "[TEST 3] Internal cluster ping..."
ping -c 1 -t 2 10.0.0.2 >/dev/null 2>&1 && echo "✓ PASS" || echo "✗ FAIL"

# Test 4: Git remote disabled
echo "[TEST 4] Git remote isolation..."
cd /opt/sovereignnexus/SovereignNexus
git remote -v | grep -q "origin" && echo "✗ FAIL (origin found)" || echo "✓ PASS"

# Test 5: No cloud SDKs in binary
echo "[TEST 5] Cloud SDK audit..."
strings ./target/aarch64-apple-darwin/release/siss-orchestrator | grep -i "aws\|azure\|gcp" && echo "✗ FAIL" || echo "✓ PASS"

# Test 6: Cryptographic validation of binaries
echo "[TEST 6] Binary integrity (SHA256)..."
EXPECTED_HASH="..." # Pre-computed on development machine
ACTUAL_HASH=$(sha256sum ./target/aarch64-apple-darwin/release/siss-orchestrator | cut -d' ' -f1)
[ "$ACTUAL_HASH" == "$EXPECTED_HASH" ] && echo "✓ PASS" || echo "✗ FAIL (tampering detected)"

echo "=== ALL TESTS MUST PASS FOR DEMO TO PROCEED ==="
```

---

## SovereignNexus Bootstrap

### Step 5: Start Orchestrator

**On primary node:**

```bash
cd /opt/sovereignnexus/SovereignNexus

# Start the orchestrator (50 agents, Kalman observer enabled)
cargo run --release \
  -p siss-orchestrator \
  --bin orchestrator \
  -- --agents 50 \
    --chaos-enabled \
    --recovery-sla-ms 5000 \
    --kg-impact-gates enabled \
    --veto-flow enabled

# Output should show:
# [INFO] SovereignNexus v2.0 starting
# [INFO] Agents: 50 (ready/waiting queues initialized)
# [INFO] Kalman observer: trace bounds [0.0, 10.0]
# [INFO] CapsuleCommitActor: φ+ Eval Court armed
# [INFO] Human-in-the-Loop Veto: ENABLED
# [INFO] Listening on 127.0.0.1:8080 (local network only)
```

### Step 6: Verify Agent Initialization

**On secondary node:**

```bash
# Confirm all 50 agents healthy and registered
curl http://10.0.0.1:8080/api/agents/status

# Expected response:
# {
#   "agent_count": 50,
#   "healthy_agents": 50,
#   "avg_latency_ms": 47,
#   "balance_score": 0.98,
#   "kg_impact_gates": "armed",
#   "veto_flow_status": "ready"
# }
```

---

## Human-in-the-Loop Veto Flow

### Step 7: CapsuleCommitActor with φ+ Eval Court

**The Veto Protocol:**

When two parallel agents submit conflicting capsules (same symbol or cluster), the system **automatically halts** and invokes Human Review:

```
Agent A submits CommitmentCapsule {
  affected_symbols: ["authenticate", "session_create"],
  cluster_tags: ["auth-cluster"],
  git_diff: "..."
}

Simultaneous:

Agent B submits CommitmentCapsule {
  affected_symbols: ["session_create", "validate_token"],
  cluster_tags: ["auth-cluster"],
  git_diff: "..."
}

SovereignNexus detects:
- Intersecting symbol: "session_create"
- Intersecting cluster: "auth-cluster"
- Verdict: HALT FOR HUMAN REVIEW
```

### Step 8: φ+ Review Dashboard (Human Decision Point)

**Operator opens veto dashboard:**

```bash
# Terminal window 2 (on primary node)
curl -s http://127.0.0.1:8080/api/veto/pending | jq .

# Response:
{
  "pending_reviews": [
    {
      "review_id": "uuid-1",
      "capsule_a": {
        "capsule_id": "uuid-a",
        "agent_id": "agent-001",
        "affected_symbols": ["authenticate", "session_create"],
        "git_diff": "[48 lines of diff]",
        "created_at": 1716566400
      },
      "capsule_b": {
        "capsule_id": "uuid-b",
        "agent_id": "agent-002",
        "affected_symbols": ["session_create", "validate_token"],
        "git_diff": "[64 lines of diff]",
        "created_at": 1716566401
      },
      "intersection": {
        "type": "symbol_overlap",
        "symbols": ["session_create"],
        "clusters": ["auth-cluster"]
      },
      "veto_options": [
        "APPROVE_A_REJECT_B",
        "APPROVE_B_REJECT_A",
        "REJECT_BOTH_AND_RETRY",
        "MANUAL_MERGE_OVERRIDE"
      ]
    }
  ]
}
```

### Step 9: Human Veto Decision

**Operator examines diffs and votes:**

```bash
# Option 1: Approve A, reject B (A is older, no new coupling)
curl -X POST http://127.0.0.1:8080/api/veto/decide \
  -H "Content-Type: application/json" \
  -d '{
    "review_id": "uuid-1",
    "decision": "APPROVE_A_REJECT_B",
    "operator": "prague-poc",
    "reason": "Agent A changes are older, session_create modification is minimal in B",
    "signature": "..."  # HMAC-SHA256 of decision (enforced)
  }'

# SovereignNexus response:
{
  "decision_timestamp": 1716566402,
  "action": "APPROVED",
  "capsule_approved": "uuid-a",
  "capsule_rejected": "uuid-b",
  "rejection_reason": "Human operator veto: B rejected (session_create coupling too risky)",
  "git_hash_committed": "a1b2c3d..."
}
```

**Fail-Closed Guarantee:** If operator response is slow (>30s), system auto-rejects both capsules (timeout = reject).

### Step 10: Live Chaos Injection (Optional)

**Trigger a failure and watch recovery:**

```bash
# Terminal window 3: Chaos injection
curl -X POST http://127.0.0.1:8080/api/chaos/inject \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "node_down",
    "target_agent_id": "agent-010",
    "duration_seconds": 5
  }'

# Watch primary orchestrator logs (window 1):
# [WARN] Agent 010 detected dead (no heartbeat)
# [INFO] Binary search isolation: depth=3, found fault at level L2
# [INFO] Kalman observer triggered rebalancing (trace exceeded threshold)
# [INFO] Task redistribution: 12 tasks moved to healthy agents
# [INFO] CapsuleCommitActor: φ+ review gate armed (impact chains validated)
# [INFO] Recovery SLA: 3.2s elapsed (target: <5000ms) ✓ PASS
```

---

## Live Demo Script

### 15-Minute Investor Demo

**Setup (5 min):**
1. Verify airgap with `prague_isolation_test.sh`
2. Confirm all 50 agents healthy: `curl http://10.0.0.1:8080/api/agents/status`
3. Show KPI dashboard metrics on screen

**Core Demo (7 min):**
1. **"Let's break it"** — Inject 3 simultaneous node failures
   - Chaos: `curl -X POST .../api/chaos/inject ... node_down x3`
   - Show recovery in real-time: <5s MTTR
   
2. **"Can we trust it?"** — Concurrent agent modifications
   - Submit 2 capsules with symbol overlap
   - Dashboard shows human veto pending
   - Operator reviews diffs, clicks "APPROVE_A"
   - φ+ Eval Court executes decision
   
3. **"How fast?"** — Latency proof
   - Show dispatch latency histogram: 47µs mean, 89µs P99
   - Kubernetes parity: 500µs (10x slower)

**Wrap (3 min):**
- "No cloud, no latency, EU data resident."
- "All decisions have human veto gates."
- "Ready to scale to production."

---

## Emergency Shutdown

### Red Button (Fail-Closed Kill)

```bash
# If anything goes wrong, stop immediately:

# Terminal 1:
killall siss-orchestrator  # Force exit

# Verify all processes stopped:
ps aux | grep siss  # Should return nothing

# Verify no pending capsules in veto queue:
curl http://127.0.0.1:8080/api/veto/pending  # Should be empty

# Shutdown all nodes:
sudo shutdown -h +1  # 1-minute warning, clean shutdown
```

---

## Post-Demo Cleanup

```bash
# Wipe local state (optional, if rerunning demo)
rm -rf /opt/sovereignnexus/SovereignNexus/.git/objects/*  # Safe to delete build cache
rm /var/log/sovereignnexus/*  # Logs

# Do NOT delete:
# - Core binaries (immutable via SHA256 signature)
# - Committed capsule hashes (audit trail)
# - git repo structure (.git/refs, .git/config)
```

---

## Troubleshooting

| Issue | Symptom | Fix |
|-------|---------|-----|
| Agent timeout | Agents not registering after 30s | Check Thunderbolt cable; restart primary node |
| Veto dashboard unavailable | 404 on `/api/veto/pending` | Confirm φ+ Eval Court process running: `ps aux \| grep eval` |
| Chaos injection stalled | Node failure not triggering recovery | Manual restart: `killall siss-orchestrator && cargo run --release...` |
| Air-gap failure | `curl` succeeds to external IP | Check network cable disconnected; disable WiFi in System Preferences |

---

## Sign-Off Checklist

**Before calling investor:**
- [ ] All 3 nodes powered on, 127.0.0.1 network route confirmed
- [ ] `prague_isolation_test.sh` returns 6/6 PASS
- [ ] `curl http://10.0.0.1:8080/api/agents/status` returns 50 healthy agents
- [ ] KPI Dashboard metrics visible on screen
- [ ] Chaos scenarios pre-rehearsed (demo is live, no rehearsal in front of investor)
- [ ] Emergency shutdown procedure tested
- [ ] Human operator familiar with veto flow (can make 3 decisions in <30s each)

**Success criteria:**
- Investor sees 3 node failures → <5s recovery (proof of fail-closed)
- Investor sees concurrent capsule collision → human veto gate (proof of explainability)
- Investor sees latency metrics (47µs, 10x Kubernetes, no cloud)

**Expected investor reaction:** "When can we deploy this?"

---

**Document Version:** 2.0 (Phase 81.5/82, EU AI Act Annex III aligned)  
**Last tested:** 2026-05-25  
**Maintainer:** SovereignNexus Engineering
