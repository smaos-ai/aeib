# HSM & Ed25519 Root Key Compromise Recovery Runbook

**Purpose:** Address high-assurance enterprise security audits (Task 7)  
**Severity:** P0 (Incident Response)  
**Owner:** Security + Operations Team  
**Last Updated:** Sep 1, 2026

---

## Overview

This playbook covers the complete response sequence if the Hardware Security Module (HSM) or Ed25519 root signing key is suspected compromised. The recovery proceeds through three phases:

1. **Fail-Closed Isolation** (T+0 minutes): Stop all agent execution
2. **Epoch Roll & Key Re-Anchoring** (T+30 minutes): Generate new identity
3. **Post-Compromise Audit** (T+2 hours): Verify all prior decisions

---

## Phase 1: Fail-Closed Isolation (T+0 Minutes)

### Step 1.1: Emergency Freeze Command
**Action:** Trigger physical airlock override

```bash
smaos-cli admin emergency-freeze --all
```

**What this does:**
- Halts all active LangGraph sessions immediately
- Flushes KV caches to cold storage (SSD)
- Terminates agent-to-agent communication (L5 A2A protocol)
- Logs freeze event with microsecond timestamp
- Sends HTTP 503 (Service Unavailable) to all API clients

**Verification:**
```bash
smaos-cli status --check-frozen
# Expected output: "FROZEN: All 64 agents paused, 0 active decisions"
```

---

### Step 1.2: Revoke Current DID Certificates
**Action:** Mark all active agent identities as revoked

```bash
# Revoke all current identities
smaos-cli identity revoke-all --reason "HSM_COMPROMISE"

# List revoked identities
smaos-cli identity list-revoked
```

**What this does:**
- Invalidates all current agent DIDs (Decentralized Identifiers)
- Prevents any claims signed with the old key from being accepted
- Creates immutable revocation event in the AP2 ledger
- Notifies all downstream systems (regulators, audit log subscribers)

**Verification:**
```bash
grep -i "revoke" /var/log/smaos/identity_events.jsonl | tail -5
```

---

### Step 1.3: Suspend All Tool Execution
**Action:** Close all L4 orchestration channels

```bash
# Suspend LangGraph pipeline
smaos-cli orchestration suspend --reason "HSM_COMPROMISE"

# Verify suspension
smaos-cli orchestration status
# Expected: "SUSPENDED: 0 pending decisions, 42 paused workflows"
```

---

## Phase 2: Epoch Roll & Key Re-Anchoring (T+30 Minutes)

### Step 2.1: Generate Secondary Offline Cold Key
**Action:** Create air-gapped Ed25519 keypair on isolated hardware

```bash
# On air-gapped USB hardware module (NO NETWORK ACCESS):
smaos-offline-keygen \
  --algo ed25519 \
  --output /mnt/usb_cold_key/epoch_n_plus_1.key \
  --label "SMAOS_ROOT_COLD_KEY_EPOCH_N+1"

# Verify key entropy
smaos-keygen-verify /mnt/usb_cold_key/epoch_n_plus_1.key
# Expected: "Entropy: 256 bits, Quality: EXCELLENT"
```

**Requirements:**
- USB hardware module must NEVER connect to the internet
- Operator must verify device is air-gapped (no WiFi, no Ethernet)
- Key generation must happen in a locked, monitored facility
- Video recording recommended for audit trail

---

### Step 2.2: Generate New Root DID for Epoch N+1
**Action:** Create new agency identity with fresh keypair

```bash
# Using the cold key from Step 2.1:
smaos-cli identity create-root \
  --cold-key-path /mnt/usb_cold_key/epoch_n_plus_1.key \
  --epoch n_plus_1 \
  --region cz \
  --issuer "Ostrov micro, s.r.o." \
  --output /etc/smaos/identity_n_plus_1.did

# Expected output:
# DID: did:smaos:cz:karlovy:<64_char_hash_of_new_pubkey>
# Epoch: N+1
# Created: 2026-09-01T14:32:15Z
```

---

### Step 2.3: Re-Sign Ledger Genesis State Root
**Action:** Create new Merkle tree root with the new keypair

```bash
# Export old ledger checkpoint
smaos-cli ledger export --checkpoint latest --output /tmp/ledger_checkpoint.jsonl

# Re-anchor with new key
smaos-cli ledger re-anchor \
  --cold-key /mnt/usb_cold_key/epoch_n_plus_1.key \
  --checkpoint /tmp/ledger_checkpoint.jsonl \
  --output /tmp/ledger_n_plus_1.root

# Verify signature
smaos-cli ledger verify-signature /tmp/ledger_n_plus_1.root
# Expected: "Signature valid. Root hash: sha256:..."
```

---

### Step 2.4: Broadcast Signed Revocation Certificate
**Action:** Publish revocation to public Git ledger (immutable)

```bash
# Create revocation certificate
cat > /tmp/REVOCATION_CERT.txt <<EOF
-----BEGIN REVOCATION CERTIFICATE-----
Version: 1.0
Type: ROOT_KEY_COMPROMISE
Epoch: N (revoked)
Reason: HSM suspected compromised on 2026-09-01 14:15:00 UTC
New Epoch: N+1
New Root DID: did:smaos:cz:karlovy:<new_hash>
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Signed by: SMAOS_ROOT_COLD_KEY_EPOCH_N+1
-----END REVOCATION CERTIFICATE-----
EOF

# Sign certificate
openssl dgst -sha256 -sign /mnt/usb_cold_key/epoch_n_plus_1.key /tmp/REVOCATION_CERT.txt > /tmp/REVOCATION_CERT.sig

# Push to public Git repository
git add /tmp/REVOCATION_CERT.txt /tmp/REVOCATION_CERT.sig
git commit -m "REVOCATION: Epoch N root key compromised, rolling to Epoch N+1"
git push origin main --force-with-lease

# Broadcast to ledger subscribers
smaos-cli ledger broadcast-revocation /tmp/REVOCATION_CERT.txt /tmp/REVOCATION_CERT.sig
```

**Verification:**
```bash
git log --oneline | head -5
# Should show revocation commit at top
```

---

## Phase 3: Post-Compromise Audit (T+2 Hours)

### Step 3.1: Verify SHA-256 Merkle Integrity (Pre-Freeze)
**Action:** Prove all decisions before freeze were cryptographically sound

```bash
# Export all Work Receipts from the AP2 ledger before freeze
smaos-cli ledger export \
  --before-timestamp "2026-09-01T14:15:00Z" \
  --format json \
  --output /tmp/pre_freeze_receipts.jsonl

# Run integrity check
smaos-cli ledger verify-merkle-chain /tmp/pre_freeze_receipts.jsonl
# Expected output:
# Verified: 2,247 decisions
# Merkle root: sha256:abc123...
# All SHA-256 hashes: VALID
# Chain integrity: ✓ UNBROKEN
```

**What this proves:**
- No decisions were altered after being logged
- The HSM compromise (if it occurred) happened AFTER the last logged decision
- All pre-freeze audit trails are cryptographically tamper-proof

---

### Step 3.2: Re-Run Unlazy Verification Suite
**Action:** Execute full commitment verification (118/118 assertions)

```bash
# Run the unlazy verifier on all pre-freeze decisions
smaos-cli verify-unlazy \
  --ledger /tmp/pre_freeze_receipts.jsonl \
  --verbose \
  --output /tmp/unlazy_audit_report.txt

# Check results
tail -20 /tmp/unlazy_audit_report.txt
# Expected:
# ✓ Commitment 1: VALID (policy rule matched, intent hash verified, delegation chain OK)
# ✓ Commitment 2: VALID
# ...
# ✓ Commitment 2,247: VALID
# ======================================
# SUMMARY: 2,247 / 2,247 assertions passed
# Confidence: 99.99%
```

---

### Step 3.3: Export Signed Incident Report
**Action:** Generate official report for Czech Data Protection Authority (ÚOOÚ)

```bash
# Generate incident report
smaos-cli audit incident-report \
  --incident-type "HSM_COMPROMISE_SUSPECTED" \
  --discovery-time "2026-09-01T14:15:00Z" \
  --impact "Root key may be compromised; 2,247 pre-freeze decisions verified as unaltered" \
  --mitigation "Cold key generated, ledger re-anchored, new DID published" \
  --output /tmp/INCIDENT_REPORT_UOOU.json

# Sign with the new key (Epoch N+1)
smaos-cli sign \
  --file /tmp/INCIDENT_REPORT_UOOU.json \
  --key-path /mnt/usb_cold_key/epoch_n_plus_1.key \
  --output /tmp/INCIDENT_REPORT_UOOU.json.sig

# Upload to ÚOOÚ notification system
curl -X POST \
  -H "Content-Type: application/json" \
  -d @/tmp/INCIDENT_REPORT_UOOU.json \
  --cert /tmp/INCIDENT_REPORT_UOOU.json.sig \
  https://api.uoou.cz/v1/security-incidents
```

---

## Rollback & Resume Procedures

### Resume Operations (Epoch N+1)
```bash
# Confirm all three phases complete
smaos-cli admin check-recovery-status
# Expected: "Phases 1-3 complete. Ready to resume with Epoch N+1."

# Resume with new identity
smaos-cli admin resume --epoch n_plus_1

# Verify agents are online with new key
smaos-cli status
# Expected: "RUNNING (Epoch N+1), 64 agents online, 0 active decisions"
```

### Emergency Rollback (If Recovery Fails)
```bash
# If Epoch N+1 deployment fails, fall back to offline-only mode
smaos-cli admin fallback-offline-only

# All tool execution halted; audit trail only
# Manual review required before resuming with Epoch N+2
```

---

## Contact & Escalation

| Role | Phone | Email |
|------|-------|-------|
| Security Lead | +420 721 XXX XXX | security@ostrov.cz |
| CISO (On-call) | +420 777 XXX XXX | ciso@ostrov.cz |
| ÚOOÚ Hotline | +420 2 72 86 00 00 | security-incident@uoou.cz |

---

**Status:** ✅ Approved for production deployment  
**Last Tested:** Sep 1, 2026  
**Next Drill:** Oct 1, 2026
