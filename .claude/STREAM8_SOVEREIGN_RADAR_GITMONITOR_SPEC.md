# STREAM 8: Sovereign Radar Infrastructure (Git Monitoring)
## O(1) Delta Change Tracking for 10K+ Creator Repos
**Date:** 2026-07-18  
**Phase:** Aug 1 - Dec 31, 2026  
**Status:** Specification COMPLETE  
**Target:** <200ms delta detection per repo, 99% cache hit rate, 100K repos scalable

---

## EXECUTIVE SUMMARY

**Goal:** Deploy local Git mirrors using raw Git transport with cached SHAs to run O(1) delta change tracking (<200ms per repo).

This system enables SMAOS agents to monitor creator repos for compliance violations without API rate limits or latency penalties. Uses Redis SHA caching + PostgreSQL audit trails + S3 cold storage.

**Success Metrics (by Dec 31):**
- [ ] 10K repos monitored in production
- [ ] Delta detection <200ms per repo (O(1) SHA comparison)
- [ ] SHA cache hit rate >99%
- [ ] Zero missed changes (100% accuracy)
- [ ] Governance policy integration verified
- [ ] SOC 2 compliance reporting ready

---

## ARCHITECTURE OVERVIEW

### System Flow

```
┌─ Source Repos ──────────────────┐
│ (GitHub, GitLab, Gitea, etc.)   │
└──────────────┬──────────────────┘
               ↓
┌─ Git Clone Pipeline ────────────┐
│ - Batch clone (100+ repos/cycle)│
│ - Daily incremental fetch       │
│ - Store locally (cold storage)  │
└──────────────┬──────────────────┘
               ↓
┌─ SHA Cache Layer ───────────────┐
│ - Redis: Latest SHA per repo    │
│ - DashMap: Comparison cache     │
│ - Query: <1ms per repo          │
└──────────────┬──────────────────┘
               ↓
┌─ Delta Detection (O(1)) ────────┐
│ - Compare cached SHAs           │
│ - Flag changed repos            │
│ - Trigger governance checks     │
└──────────────┬──────────────────┘
               ↓
┌─ Governance Pipeline ───────────┐
│ - ReBAC policy check            │
│ - Changes allowed? (audit log)  │
│ - Notify creator if violation   │
└──────────────┬──────────────────┘
               ↓
┌─ Compliance Dashboard ──────────┐
│ - Real-time repo health         │
│ - Anomaly detection (commits)   │
│ - Creator notifications         │
└─────────────────────────────────┘
```

### Data Flow (Per Cycle)

1. **Git Mirror Update** (Hourly)
   - Batch fetch 100 repos in parallel
   - Extract HEAD SHA for each repo
   - Store in Redis (key: `repo:{repo_id}:sha`)
   - Timestamp: `repo:{repo_id}:last_checked`

2. **Delta Detection** (<1ms)
   - Query Redis for current SHA
   - Compare to cached previous SHA
   - If changed → log DeltaEvent
   - Emit to governance pipeline

3. **Governance Check** (Async)
   - Fetch DeltaEvent from queue
   - Run policy rules (e.g., "no adult content commits")
   - Update `governance_status` field
   - If violation → notify creator

4. **Audit & Reporting**
   - Record all deltas in PostgreSQL
   - Archive snapshots to S3 (daily)
   - Generate SOC 2 reports (weekly)

---

## TECHNICAL STACK

### Storage Layers

| Layer | Technology | Use Case | SLA |
|-------|-----------|----------|-----|
| **Hot** | Redis | SHA cache, active lookups | <1ms, 99.9% uptime |
| **Warm** | PostgreSQL | Audit trail, delta events | <10ms, 99% uptime |
| **Cold** | S3 | Historical snapshots | <1s, 99.9% durability |
| **Local** | Filesystem | Git mirrors | <200ms, local FS perf |

### Processing Stack

| Component | Technology | Capacity |
|-----------|-----------|----------|
| **Async Runtime** | Tokio | 10K concurrent repo monitoring |
| **Batch Processing** | Cargo (Rust) | 100 repos per polling cycle |
| **Polling Interval** | Tunable | Default: 1 hour |
| **Concurrency** | tokio::task::spawn | Non-blocking I/O |

### Crate Architecture

**New Crate:** `siss-radar` (Git transport + delta detection)

```
crates/siss-radar/
├── src/
│   ├── lib.rs                    (exports)
│   ├── git_transport.rs          (clone, fetch, SHA extraction)
│   ├── cache_layer.rs            (Redis interface)
│   ├── delta_detection.rs        (O(1) SHA comparison)
│   ├── models.rs                 (RepoSnapshot, DeltaEvent)
│   ├── governance_integration.rs (policy hooks)
│   └── tests/
│       ├── integration_tests.rs  (end-to-end latency)
│       ├── cache_tests.rs        (hit rate verification)
│       ├── git_tests.rs          (clone/fetch accuracy)
│       └── governance_tests.rs   (policy enforcement)
└── Cargo.toml
```

---

## DATA MODELS

### Core Types

```rust
// RepoSnapshot: Current state of a creator's repo
pub struct RepoSnapshot {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub repo_url: String,
    pub repo_host: RepoHost,  // GitHub, GitLab, Gitea
    
    // Git state
    pub latest_sha: String,
    pub previous_sha: String,
    pub last_checked: DateTime<Utc>,
    pub fetch_latency_ms: u32,
    
    // Governance
    pub governance_status: GovernanceStatus,
    pub policy_violations: Vec<PolicyViolation>,
    pub creator_flagged: bool,
    
    // Metadata
    pub default_branch: String,
    pub is_private: bool,
    pub last_commit_message: String,
    pub last_commit_author: String,
    pub commit_count_since_last_check: u32,
}

pub enum RepoHost {
    GitHub,
    GitLab,
    Gitea,
    Gitpod,
}

pub enum GovernanceStatus {
    Compliant,
    Flagged,
    Violation,
    UnderReview,
}

pub struct PolicyViolation {
    pub policy_id: Uuid,
    pub rule_name: String,
    pub violation_type: String,  // e.g., "large_binary_add", "credential_commit"
    pub severity: ViolationSeverity,
    pub detected_at: DateTime<Utc>,
    pub resolved_at: Option<DateTime<Utc>>,
}

pub enum ViolationSeverity {
    Low,
    Medium,
    High,
    Critical,
}

// DeltaEvent: Atomic change record
pub struct DeltaEvent {
    pub id: Uuid,
    pub repo_id: Uuid,
    pub prev_sha: String,
    pub new_sha: String,
    pub timestamp: DateTime<Utc>,
    pub commit_count: u32,
    pub commit_log: Vec<CommitInfo>,
    pub files_changed: u32,
    pub bytes_added: u32,
    pub bytes_deleted: u32,
}

pub struct CommitInfo {
    pub sha: String,
    pub message: String,
    pub author: String,
    pub timestamp: DateTime<Utc>,
}

// Cache Key Patterns
pub const CACHE_KEY_SHA: &str = "radar:repo:{repo_id}:sha";
pub const CACHE_KEY_CHECKED: &str = "radar:repo:{repo_id}:last_checked";
pub const CACHE_KEY_STATUS: &str = "radar:repo:{repo_id}:gov_status";
```

### Database Schema (PostgreSQL)

```sql
-- Repos table
CREATE TABLE repos (
    id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    repo_url VARCHAR(1024) NOT NULL UNIQUE,
    repo_host VARCHAR(50) NOT NULL,
    default_branch VARCHAR(255),
    is_private BOOLEAN,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (creator_id) REFERENCES creators(id)
);

-- Snapshots table (current + historical)
CREATE TABLE repo_snapshots (
    id UUID PRIMARY KEY,
    repo_id UUID NOT NULL,
    latest_sha VARCHAR(40) NOT NULL,
    previous_sha VARCHAR(40),
    governance_status VARCHAR(50) NOT NULL,
    last_checked TIMESTAMP NOT NULL,
    fetch_latency_ms BIGINT,
    commit_count_since_check BIGINT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    INDEX idx_repo_id (repo_id),
    INDEX idx_last_checked (last_checked)
);

-- Delta events table (immutable audit log)
CREATE TABLE delta_events (
    id UUID PRIMARY KEY,
    repo_id UUID NOT NULL,
    prev_sha VARCHAR(40) NOT NULL,
    new_sha VARCHAR(40) NOT NULL,
    commit_count BIGINT,
    files_changed BIGINT,
    bytes_added BIGINT,
    bytes_deleted BIGINT,
    detected_at TIMESTAMP NOT NULL,
    processed_at TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    INDEX idx_repo_id (repo_id),
    INDEX idx_detected_at (detected_at)
);

-- Policy violations
CREATE TABLE policy_violations (
    id UUID PRIMARY KEY,
    repo_id UUID NOT NULL,
    policy_id UUID NOT NULL,
    violation_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    INDEX idx_repo_id_severity (repo_id, severity)
);
```

---

## IMPLEMENTATION PHASES

### Phase 1: Infrastructure (Aug 1 - Sep 1)

**Deliverable:** Git mirror system + SHA cache layer + delta detection

**Tasks:**

1. **Git Transport Layer** (3 days)
   - Implement `GitMirror` struct with clone/fetch methods
   - Support GitHub, GitLab, Gitea (raw SSH + HTTPS)
   - Batch cloning (100 repos in parallel)
   - Error handling + retry logic
   - [ ] Test: Clone 100 repos in <5s

2. **Cache Layer** (2 days)
   - Redis connection pool
   - SHA cache with TTL (1 hour default)
   - DashMap for in-process comparison cache
   - Cache invalidation strategy
   - [ ] Test: <1ms SHA lookups, >99% hit rate

3. **Delta Detection** (2 days)
   - O(1) SHA comparison algorithm
   - Event emission (prev_sha → new_sha)
   - Commit log extraction
   - [ ] Test: <200ms per repo delta detection

4. **Database & Audit** (3 days)
   - PostgreSQL schema (repos, snapshots, deltas, violations)
   - Immutable event log
   - S3 archival (daily snapshots)
   - [ ] Test: 10K delta events logged accurately

5. **Governance Integration** (2 days)
   - Hook into siss-gatekeeper ReBAC policies
   - Policy violation detection
   - Creator notification (async)
   - [ ] Test: 10+ governance scenarios

**Success Criteria:**
- [ ] 100 repos monitored in pilot
- [ ] Delta detection <200ms per repo
- [ ] Cache hit rate >99%
- [ ] 10+ tests (latency verification)
- [ ] Zero false positives (accuracy 100%)
- [ ] `cargo test -q` passing

---

### Phase 2: Scaling to 1K Repos (Sep 1 - Oct 1)

**Goal:** Add 900 repos from USA creator cohort

**Tasks:**

1. **Horizontal Scaling**
   - Multi-instance Radar deployment
   - Load balancing (repo assignment)
   - Redis cluster (Sentinel for HA)
   - [ ] Test: 1K repos with <200ms latency per repo

2. **Performance Optimization**
   - Batch fetch optimization (reduce SSH overhead)
   - Cache hit rate tuning (target >99%)
   - Latency profiling + hotspot elimination
   - [ ] Test: Verify <200ms maintained at 1K scale

3. **Monitoring & Alerting**
   - Cache miss rates
   - Fetch latency anomalies
   - Governance violation spikes
   - [ ] Test: 5+ alerts configured

**Success Criteria:**
- [ ] 1K repos monitored with <200ms latency
- [ ] SHA cache hit rate >99%
- [ ] Governance pipeline integrated

---

### Phase 3: Scaling to 10K Repos (Oct 1 - Nov 1)

**Goal:** Onboard 10K creators' repos

**Tasks:**

1. **Distributed Architecture**
   - Multiple Radar instances (10+)
   - Repo sharding by hash(repo_url)
   - Redis cluster (3-node minimum)
   - PostgreSQL read replicas

2. **Reliability**
   - HA failover (backup mirror servers)
   - Graceful degradation (read-only mode if mirror fails)
   - Self-healing (auto-retry failed fetches)

3. **Cost Optimization**
   - Archive cold repos (>30d no changes)
   - Compress historical snapshots
   - S3 Glacier tier for >1 year

**Success Criteria:**
- [ ] 10K repos monitored
- [ ] <200ms latency maintained
- [ ] 99.9% availability

---

### Phase 4: Production Hardening (Nov 1 - Dec 31)

**Goal:** Enterprise-grade compliance + incident response

**Tasks:**

1. **Security Hardening**
   - Ed25519 SSH key management
   - Encrypted credential storage
   - Audit trail encryption (AES-256-GCM)
   - [ ] Security audit passed

2. **Compliance Reporting**
   - SOC 2 Appendix A (audit trail evidence)
   - GDPR data request fulfillment (show all changes)
   - NIS2 incident response (timeline of changes)
   - [ ] Reports generated weekly

3. **Incident Response**
   - Auto-revert unauthorized commits (if policy allows)
   - Creator escalation playbooks
   - Anomaly detection (unusual commit patterns)

**Success Criteria:**
- [ ] SOC 2 compliance reporting ready
- [ ] Incident response automation verified
- [ ] Zero missed changes (100% accuracy confirmed)

---

## PERFORMANCE TARGETS

### Latency SLA

| Operation | Target | Method |
|-----------|--------|--------|
| SHA cache lookup | <1ms | Redis query |
| Delta detection | <200ms | SHA comparison |
| Batch fetch (100 repos) | <10s | Parallel Tokio tasks |
| Governance check | <500ms | ReBAC policy eval |
| End-to-end (detect + notify) | <2s | All above |

### Throughput

| Metric | Target |
|--------|--------|
| Concurrent repos monitored | 10K |
| Polling interval | 1 hour (tunable) |
| Deltas/hour at 10K scale | ~100-500 (varies by cohort) |
| SHA cache entries | 10K (1 per repo) |
| Cache hit rate | >99% |

### Storage

| Layer | Capacity | Growth |
|-------|----------|--------|
| Git mirrors (local) | 2TB (100 repos avg 20GB each) | +100 repos/month = +2TB/month |
| Redis cache | 50MB (10K SHA entries) | Fixed |
| PostgreSQL audit | 100GB (first year) | +10GB/month |
| S3 cold storage | 500GB | +500MB/month |

---

## USE CASES

### 1. Creator Compliance Monitoring

**Scenario:** Flag repos with suspicious commits (e.g., large binary additions)

**Process:**
1. Radar detects new SHA for creator's repo
2. Delta extraction shows 50MB binary file added
3. Governance rule: "no binary files >10MB"
4. Creator flagged + notification sent
5. Creator can override or revert commit

**Latency:** <2 seconds from commit to notification

### 2. Governance Enforcement

**Scenario:** Enforce creator policies (e.g., "no adult content repos")

**Process:**
1. Creator commits code with adult content message
2. Radar extracts commit message
3. Policy rule: "block commits with keywords [adult, NSFW, ...]"
4. Violation recorded, escalated to trust team
5. Creator blocked from platform (if critical)

**Audit Trail:** Immutable PostgreSQL log of all violations

### 3. Anomaly Detection

**Scenario:** Detect unusual commit patterns (suspicious timing, size, frequency)

**Process:**
1. Creator's repo normally has 5 commits/week
2. Radar detects 200 commits in 1 hour (anomaly)
3. Governance alert: "unusual commit frequency"
4. Human review + creator override option
5. If confirmed malicious → quarantine repo

**ML Future:** Train anomaly model on historical patterns

### 4. Compliance Reporting

**Scenario:** Generate SOC 2 reports for auditors

**Process:**
1. Extract all delta events for date range
2. Filter by governance status (compliant/violated)
3. Generate PDF report with:
   - Total repos monitored
   - Violation count + breakdown
   - Response times
   - Creator notifications sent
4. Sign with Ed25519 key for audit trail integrity

---

## INTEGRATION POINTS

### With siss-gatekeeper (ReBAC)

```rust
// Radar calls gatekeeper to evaluate policies
pub async fn check_governance(
    violation: &DeltaEvent,
    policies: &[Policy],
) -> Result<GovernanceStatus> {
    for policy in policies {
        // Call gatekeeper.evaluate(policy, violation)
        let result = gatekeeper.evaluate(policy, violation).await?;
        if !result.is_allowed {
            return Ok(GovernanceStatus::Violation);
        }
    }
    Ok(GovernanceStatus::Compliant)
}
```

### With siss-event-log (Audit Trail)

```rust
// Radar emits events to central event log
pub async fn log_delta_event(
    delta: &DeltaEvent,
    event_log: &EventLog,
) -> Result<()> {
    event_log.emit(RadarEvent::DeltaDetected {
        repo_id: delta.repo_id,
        prev_sha: delta.prev_sha.clone(),
        new_sha: delta.new_sha.clone(),
        timestamp: Utc::now(),
    }).await
}
```

### With siss-feedback-router (Creator Notifications)

```rust
// Radar notifies creator of violations
pub async fn notify_creator(
    creator_id: Uuid,
    violation: &PolicyViolation,
    feedback: &FeedbackRouter,
) -> Result<()> {
    feedback.send_notification(
        creator_id,
        NotificationPayload {
            title: format!("Policy Violation: {}", violation.rule_name),
            body: format!("Detected: {}", violation.violation_type),
            severity: violation.severity.clone(),
        },
    ).await
}
```

---

## OPERATIONAL RUNBOOK

### Day 1: Deploy Radar Instance

```bash
# 1. Create siss-radar crate
cargo new --lib crates/siss-radar

# 2. Add to workspace
# Edit Cargo.toml: add "crates/siss-radar" to [workspace] members

# 3. Deploy Redis
# Docker: docker run -d -p 6379:6379 redis:7

# 4. Deploy PostgreSQL
# Docker: docker run -d -p 5432:5432 postgres:15

# 5. Initialize schema
# Run migrations: sqlx migrate run

# 6. Spin up Radar
# Binary: cargo build -p siss-radar --release
# Start: ./target/release/siss-radar --config radar.toml

# 7. Monitor logs
# tail -f logs/radar.log
```

### Hourly Monitoring

```bash
# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits

# Check delta backlog
psql -c "SELECT COUNT(*) FROM delta_events WHERE processed_at IS NULL;"

# Check avg latency
psql -c "SELECT AVG(fetch_latency_ms) FROM repo_snapshots WHERE last_checked > NOW() - INTERVAL '1 hour';"
```

### Weekly Reporting

```bash
# Generate compliance report
./scripts/generate_compliance_report.sh --week --output report.pdf

# Archive snapshots to S3
./scripts/archive_snapshots_to_s3.sh --week
```

---

## SUCCESS CRITERIA (FINAL)

- [x] Architecture specified and documented
- [ ] Phase 1 complete: 100 repos monitored, <200ms latency, >99% cache hit rate
- [ ] Phase 2 complete: 1K repos, latency maintained
- [ ] Phase 3 complete: 10K repos, 99.9% availability
- [ ] Phase 4 complete: SOC 2 compliance reporting, incident response automated
- [ ] 10+ tests verifying latency SLAs
- [ ] Zero missed changes (100% accuracy verified)
- [ ] Governance policy integration verified
- [ ] Creator notification system tested
- [ ] All `cargo test -q` passing

---

## NEXT STEPS

1. **Create siss-radar crate structure**
   - `git_transport.rs` (clone, fetch, SHA extraction)
   - `cache_layer.rs` (Redis interface)
   - `delta_detection.rs` (O(1) comparison)
   - `models.rs` (RepoSnapshot, DeltaEvent, GovernanceStatus)

2. **Write test suite first (TDD)**
   - `tests/integration_tests.rs` — 100 repos in <5s
   - `tests/cache_tests.rs` — >99% hit rate verification
   - `tests/git_tests.rs` — clone/fetch accuracy
   - `tests/governance_tests.rs` — 10+ policy scenarios

3. **Implement core logic**
   - Git transport (clone/fetch in Tokio batch)
   - Redis caching (with TTL + invalidation)
   - Delta detection (prev_sha vs new_sha)
   - Governance hooks (call gatekeeper + notify creator)

4. **Deploy & monitor**
   - Pilot with 100 repos (USA creators)
   - Monitor latency + cache hit rate
   - Scale to 1K, then 10K repos

---

## REFERENCES

- **Governance Model:** siss-gatekeeper ReBAC policies
- **Event Log:** siss-event-log (audit trail integration)
- **Creator Notifications:** siss-feedback-router
- **Compliance:** SOC 2 reporting framework (.claude/SOC2_COMPLIANCE.md)
- **Performance:** Cargo benchmarking suite (.claude/BENCHMARKING_GUIDE.md)
