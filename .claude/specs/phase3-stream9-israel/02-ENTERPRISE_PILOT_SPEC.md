# Enterprise Pilot Spec — Israeli Civil Defense Integration

**Date:** June 4, 2026  
**Phase:** 3 Beta Launches  
**Stream:** 9 (Israel Market Entry)  
**Status:** Specification Phase  
**POC Start:** August 11, 2026  
**POC Duration:** 15 days (Aug 11–25)  
**Budget:** €20K (allocation from Stream 9 €30K)  

---

## Executive Summary

**Mission:** Pilot Axiom Protocol's governance framework with Israeli civil defense agency to demonstrate:
1. **Authorization layer** (ReBAC with time windows, blackout dates, geographic constraints)
2. **Audit compliance** (cryptographic proofs, Merkle chain, tamper-proof logs)
3. **Operational readiness** (real-world policy enforcement, <100ms latency p99, 99.9% uptime)

**Success Metric:** POC completion by Aug 25 with zero unauthorized access incidents, all settlements audited, decision gate approval for enterprise rollout.

---

## 1. Use Case: Civil Defense Policy Governance

### 1.1 Scenario

Israeli civil defense agency (Pikud HaOref equivalent) manages distributed authorization for:
- **Alert dissemination** (public warnings, siren activation)
- **Resource allocation** (emergency responders, shelter coordination)
- **Policy decisions** (evacuation zones, shelter capacity)
- **Cross-agency approvals** (Mossad ↔ Shin Bet ↔ IDF coordination)

**Current Pain Point:** Centralized authority (one minister signs off), no audit trail, slow approval (<2 hours).

**Axiom Solution:** Distributed multi-stakeholder governance with ReBAC + cryptographic proof → Policy changes within minutes, full audit trail.

---

### 1.2 Authorization Matrix

**Roles (Relationships via ReBAC):**

| Role | Entities | Permissions | Time Window | Approval Count |
|---|---|---|---|---|
| **Initiator** | Regional commanders (8) | Propose alert, suggest evacuation | No limit | — |
| **Approver** | Deputy directors (3) | Approve/deny alert (1 needed) | UTC 06:00–22:00 | 1 of 1 |
| **Override** | Director (1) | Veto any decision | Unrestricted | 1 of 1 |
| **Auditor** | Audit committee (2) | View all decisions, verify proofs | UTC 08:00–18:00 | Read-only |
| **Observer** | Policy analysts (5) | Monitor in real-time | UTC 08:00–18:00 | Read-only |

**Enforcement:**
- **Time Window:** Each role restricted to UTC hours (no off-hours approvals without director override)
- **Blackout Dates:** Fridays 16:00 UTC–Sunday 08:00 UTC (Shabbat + religious observance)
- **Geographic Constraint:** Only approvers in Tel Aviv headquarters can sign off on national alerts
- **Rate Limit:** Max 10 approval decisions/hour per approver (sliding window)

---

## 2. ReBAC + AP2 Integration

### 2.1 Policy Engine Composition

```
Request: Regional Commander submits "Activate Siren Zone 1"
    ↓
Phase 1: ReBAC Check
  - Is requester Initiator role? → YES
  - Is requester delegated by someone? → NO
  - Relationship valid? → YES
  - Expires_at checked? → NOT YET
    ↓ PASS
Phase 2: AP2 Attributes Check
  - Is approver on-duty (trust_level > 70)? → YES
  - Is approver not blacklisted? → YES
  - Geographic match (Tel Aviv)? → YES
    ↓ PASS
Phase 3: Temporal Guard Check
  - Is current time in allowed window (06:00–22:00 UTC)? → YES (14:33 UTC)
  - Is today a blackout date (Fri–Sun)? → NO (Tuesday)
  - Rate limit exceeded? → NO (2 of 10 approvals/hour)
    ↓ PASS
    ↓
DECISION: Allow
    ↓
Audit log: requester_id | action=ApproveAlert | resource=SirenZone1 | decision=Allow | reasons=[...] | timestamp=2026-08-15T14:33:42Z
    ↓
Merkle proof: sha256(previous_audit + this_entry) = 0x7f3a...
    ↓
Approval logged to PostgreSQL + immutable archive
```

---

### 2.2 Merkle Chain Validation

**Every settlement/decision:**
1. Log entry created with (requester, action, decision, reasons, timestamp)
2. Hash computed: `merkle_root = sha256(prev_root || entry_json)`
3. Root stored in AP2 Ledger (immutable)
4. Audit committee verifies chain integrity daily:
   - Recompute all hashes from genesis
   - Check against stored roots
   - Flag any discrepancies immediately

**Example:**
```
Audit 1: Alice approves alert → Merkle root = 0xabc123...
Audit 2: Bob denies evacuation → Merkle root = sha256(0xabc123... || audit2_json) = 0xdef456...
Audit 3: Carol reviews logs → Root matches 0xdef456... ✓ (chain unbroken)
```

---

## 3. Cryptographic Proof & Audit Trail

### 3.1 Audit Entry Schema

```rust
pub struct CivilDefenseAuditEntry {
    pub audit_id: Uuid,                    // Unique ID
    pub requester_id: Uuid,                // Commander/Approver
    pub action: CivilDefenseAction,        // ApproveAlert, ProposeEvacuation, etc.
    pub resource: AlertZone,               // Zone 1, Zone 5, etc.
    pub decision: AllowDeny,               // Allow or Deny
    pub reasons: Vec<String>,              // ["ReBAC passed", "Temporal window valid", "Trust level sufficient"]
    pub timestamp: SystemTime,             // UTC only
    pub merkle_root: [u8; 32],             // sha256(prev_root || this_entry)
    pub signature: Ed25519Signature,       // Signed by approver's key
}
```

### 3.2 Audit Log Storage

**Hot Storage (PostgreSQL, 90 days):**
- All audit entries queryable in real-time
- indexed by requester_id, resource, timestamp
- TTL: auto-delete after 90 days
- Backup: replicated to 2 regional read-replicas

**Cold Storage (S3, immutable):**
- Daily export of yesterday's logs (gzipped JSONL)
- Immutable append-only bucket
- Retention: 7 years (regulatory requirement)
- Verification: Each file signed with agency's PGP key

### 3.3 Tamper Detection

**If audit entry modified:**
```
Original: Merkle root = 0xabc123...
Modified: Changed decision from Allow to Deny
New root = sha256(0xabc123... || modified_entry) = 0xXYZ999...
Chain break detected: Expected 0xdef456..., got 0xXYZ999...
Alert: Unauthorized audit modification detected
Response: Immediate notification to Director + FBI (if applicable)
```

---

## 4. POC Success Metrics

### 4.1 Performance SLAs

| Metric | Target | Measurement |
|---|---|---|
| **Authorization Latency** | <100ms p99 | From request to decision |
| **Audit Latency** | <10ms p99 | From decision to audit log write |
| **Merkle Proof Gen** | <50ms p99 | Hash computation + signature |
| **Uptime** | 99.9% | Over 15-day POC window |
| **False Positives** | <0.1% | Legitimate requests denied |
| **Audit Integrity** | 100% | Zero undetected modifications |

### 4.2 Functional Validation

- ✅ All 8 authorization roles working (initiator, approver, override, auditor, observer)
- ✅ Time windows enforced (06:00–22:00 UTC, blackout dates, rate limits)
- ✅ ReBAC cycle detection operational (max depth 3, no infinite delegation)
- ✅ AP2 attributes verified correctly (trust level, geographic match, blacklist check)
- ✅ Merkle chain unbroken across 100+ audit entries
- ✅ Cold storage export functional (daily JSONL export to S3)
- ✅ Tamper detection working (modified entry caught immediately)

### 4.3 Security Validation

- ✅ Zero unauthorized access incidents
- ✅ All high-privilege actions audited (override decisions logged)
- ✅ Signature verification passing (Ed25519)
- ✅ Credential verification (MetaMask/Safe wallet setup)
- ✅ Rate limiting enforced (no actor exceeded quota)

---

## 5. Pilot Timeline (Aug 11–25)

### Phase 1: Preparation (Aug 11–13)
- Deploy PostgreSQL + audit schema to staging
- Integrate ReBAC + AP2 (from Phase 25 completion)
- Set up S3 bucket + PGP key distribution
- Train civil defense stakeholders (3-hour workshop)

### Phase 2: Soft Launch (Aug 14–18)
- Run 50 test transactions (50% approval, 50% denial)
- Verify all metrics pass SLA targets
- Stakeholders execute 10 real policy decisions (advisory, non-critical)
- Daily Merkle chain validation

### Phase 3: Full Operation (Aug 19–24)
- Live civil defense decisions on real alerts (all roles active)
- Continuous monitoring (latency, uptime, audit integrity)
- Daily incident reports (if any anomalies)
- Stakeholder feedback collection

### Phase 4: Sign-Off (Aug 25)
- Final audit trail verification
- Merkle chain integrity certified by audit committee
- Go/no-go decision for enterprise rollout

---

## 6. Risk & Contingency

| Risk | Probability | Mitigation |
|---|---|---|
| **ReBAC not ready by Aug 11** | Medium | Phase 25 WAR: parallel mock API, integration via stub |
| **Latency >100ms p99** | Low | Cache authorization decisions (5-min TTL) |
| **Merkle chain breaks** | Very Low | Dual chain (hot + cold backup), daily verification |
| **Stakeholder rejection** | Very Low | Legal/compliance pre-approval, training reinforcement |
| **S3 export fails** | Low | Fallback to local archive + manual weekly export |
| **PostgreSQL replication lag** | Medium | Synchronous replication (increased latency, acceptable for audit) |

---

## 7. Success Criteria (August 25)

- ✅ 0 unauthorized access incidents
- ✅ All 4 phases completed on schedule
- ✅ Latency SLA: <100ms p99 consistently
- ✅ Uptime SLA: 99.9% achieved
- ✅ Merkle chain integrity certified (0 anomalies)
- ✅ 100+ audit entries logged successfully
- ✅ S3 cold storage operational + tested
- ✅ Director sign-off for enterprise rollout (go/no-go gate)

---

## 8. Post-POC Deliverables

1. **POC Report** (5 pages: timeline, metrics, incidents, recommendation)
2. **Audit Trail Export** (All Aug 11–25 transactions + Merkle proofs)
3. **Operational Runbook** (Deployment, monitoring, incident response)
4. **Stakeholder Feedback** (Qualitative + quantitative from workshop retrospective)
5. **Go/No-Go Decision** (Director approval for Phase 3 rollout)

---

## 9. Phase 3 Rollout (If Go Decision)

- **Timeline:** Sep 1+
- **Scope:** Production deployment, 24/7 monitoring, SRE handoff
- **Budget:** €80K+ (separate allocation)
- **Governance:** Quarterly reviews, annual security audit

