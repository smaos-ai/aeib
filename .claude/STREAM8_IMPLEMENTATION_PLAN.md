# STREAM 8 Implementation Plan — Sovereign Radar Infrastructure
**Created:** 2026-07-18  
**Phase:** Aug 1 - Dec 31, 2026  
**Status:** PHASE 1 INFRASTRUCTURE SCAFFOLDING COMPLETE

---

## EXECUTIVE SUMMARY

Created foundation crate `siss-radar` with:
- [x] Data models (RepoSnapshot, DeltaEvent, PolicyViolation, GovernanceStatus)
- [x] Cache layer (LocalCache + RedisCache with fallback)
- [x] Delta detection algorithm (O(1) SHA comparison)
- [x] 13 passing unit tests (cache ops, delta detection, models)
- [x] Integration documentation

**Next Task:** Implement Git transport layer + PostgreSQL persistence

---

## DELIVERABLES COMPLETED

### 1. Crate Structure
```
crates/siss-radar/
├── Cargo.toml           ✓ (with Redis, tokio, uuid, chrono deps)
├── README.md            ✓ (architecture overview + roadmap)
├── src/
│   ├── lib.rs           ✓ (module exports)
│   ├── models.rs        ✓ (5 core types)
│   ├── cache_layer.rs   ✓ (LocalCache + RedisCache)
│   └── delta_detection.rs ✓ (O(1) comparison)
└── tests/               (to be implemented)
```

### 2. Data Models (`models.rs`)
✓ **RepoSnapshot**: Creator repo state with governance status
✓ **DeltaEvent**: Atomic change record (prev_sha → new_sha)
✓ **PolicyViolation**: Governance violation with severity levels
✓ **GovernanceStatus**: Enum (Compliant/Flagged/Violation/UnderReview)
✓ **ViolationSeverity**: Ordered enum (Low → Medium → High → Critical)

### 3. Cache Layer (`cache_layer.rs`)
✓ **LocalCache**: DashMap-backed in-process cache (<1ms lookups)
✓ **RedisCache**: ConnectionManager-based persistent cache with TTL
✓ **CacheLayer**: Unified dual-layer interface with fallback

**Key Features:**
- Set/get operations with proper type hints
- Cache hit rate tracking
- TTL-based expiration (configurable)
- Graceful degradation if Redis unavailable

### 4. Delta Detection (`delta_detection.rs`)
✓ **DeltaDetector**: O(1) SHA comparison algorithm
✓ Change detection logic (prev_sha vs new_sha)
✓ Latency tracking per repo
✓ Delta event creation with commit metadata

**Key Features:**
- First-check detection (prev_sha = None)
- Latency recording for SLA tracking
- Commit count, file changes, bytes tracking

### 5. Test Suite (13 tests passing)
```
Cache Layer Tests:
✓ test_local_cache_operations
✓ test_local_cache_clear
✓ test_local_cache_multiple_entries
✓ test_cache_layer_without_redis

Delta Detection Tests:
✓ test_delta_detection_with_change
✓ test_delta_detection_no_change
✓ test_delta_detection_first_check
✓ test_delta_detection_latency_tracking
✓ test_delta_multiple_scenarios
✓ test_create_delta_event

Models Tests:
✓ test_repo_snapshot_creation
✓ test_violation_severity_ordering
✓ test_delta_event_creation
```

---

## ARCHITECTURE DECISIONS

### Why O(1) Delta Detection?
- SHA comparison in Redis/local cache: <1ms
- No git operations required (prev fetch cached)
- Scales to 10K repos without API rate limits
- Enables hourly polling cost-effectively

### Why Dual-Layer Cache?
- **LocalCache** (DashMap): In-process, <1ms for hot repos
- **RedisCache**: Persistent, shared across instances
- Fallback: If Redis down, LocalCache continues operating
- Cost: Redis cluster optional for single-instance deployments

### Why PostgreSQL for Audit?
- Immutable event log (append-only)
- ACID compliance for governance records
- Query access for compliance reporting
- Integration with existing siss-event-log

### Why Governance Integration?
- Delegate policy decisions to siss-gatekeeper (ReBAC)
- Creator notifications via siss-feedback-router
- Audit trail via siss-event-log
- Single source of truth for policy enforcement

---

## PHASE 1 REMAINING TASKS

### Task 1: Git Transport Layer
**Owner:** TBD  
**Effort:** 3 days  
**Files to Create:**
- `crates/siss-radar/src/git_transport.rs`

**Pseudocode:**
```rust
pub struct GitMirror {
    local_path: PathBuf,
    repo_url: String,
    repo_host: RepoHost,
}

impl GitMirror {
    pub async fn clone_batch(repos: Vec<RepoSpec>) -> Result<Vec<String>> {
        // Spawn 10 concurrent clone tasks
        // Retry on timeout (5s default)
        // Return SHAs
    }

    pub async fn fetch(&mut self) -> Result<String> {
        // Incremental fetch
        // Extract HEAD SHA
        // Return SHA
    }

    pub async fn get_commit_log(&self, prev: &str, new: &str) -> Result<Vec<CommitInfo>> {
        // Parse commits between SHAs
        // Extract message, author, timestamp
    }
}
```

**Success Criteria:**
- [ ] Clone 100 repos in <5 seconds (parallel)
- [ ] Fetch updates in <1 second per repo
- [ ] Extract commit log accurately
- [ ] Handle auth (SSH keys, GitHub tokens)
- [ ] 5+ tests (clone, fetch, commit extraction)

### Task 2: PostgreSQL Persistence
**Owner:** TBD  
**Effort:** 2 days  
**Files to Create:**
- `crates/siss-radar/src/db_layer.rs`
- `crates/siss-radar/migrations/*.sql`

**Schema (from spec):**
```sql
CREATE TABLE repos (id, creator_id, repo_url, repo_host, ...);
CREATE TABLE repo_snapshots (id, repo_id, latest_sha, governance_status, ...);
CREATE TABLE delta_events (id, repo_id, prev_sha, new_sha, commit_count, ...);
CREATE TABLE policy_violations (id, repo_id, policy_id, severity, ...);
```

**Success Criteria:**
- [ ] sqlx migrations applied
- [ ] CRUD operations for all tables
- [ ] Index creation (repo_id, last_checked)
- [ ] Immutability verification (append-only)
- [ ] 5+ tests (insert, query, aggregations)

### Task 3: Governance Integration
**Owner:** TBD  
**Effort:** 2 days  
**Files to Create:**
- `crates/siss-radar/src/governance_integration.rs`

**Integration Points:**
1. Call `siss-gatekeeper.evaluate(policy, violation)` 
2. Emit to `siss-event-log` (RadarEvent::DeltaDetected)
3. Send notification via `siss-feedback-router`

**Success Criteria:**
- [ ] Policy evaluation working
- [ ] Event emission verified
- [ ] Creator notifications sent
- [ ] 10+ test scenarios (policies pass/fail)

### Task 4: Main Coordinator
**Owner:** TBD  
**Effort:** 1 day  
**Files to Create:**
- `crates/siss-radar/src/coordinator.rs`

**Orchestration:**
```rust
pub async fn monitor_repos(
    repos: Vec<RepoSpec>,
    interval: Duration,
) -> Result<()> {
    loop {
        // 1. Git fetch batch
        // 2. Extract SHAs
        // 3. Compare with cache (delta detection)
        // 4. Emit DeltaEvents
        // 5. Governance checks
        // 6. Store snapshots
        // 7. Sleep(interval)
    }
}
```

**Success Criteria:**
- [ ] End-to-end monitoring cycle working
- [ ] 100 repos monitored with <200ms latency
- [ ] Cache hit rate >99%
- [ ] Governance pipeline integrated

### Task 5: Integration Tests
**Owner:** TBD  
**Effort:** 2 days  
**Files to Create:**
- `crates/siss-radar/tests/integration_tests.rs`

**Test Scenarios:**
1. Clone + fetch 100 test repos (<5s)
2. Delta detection <200ms per repo
3. Cache hit rate >99% (100 accesses)
4. Governance policy enforcement (pass/fail)
5. PostgreSQL persistence (write + read)

**Success Criteria:**
- [ ] All integration tests passing
- [ ] Latency SLAs verified
- [ ] 99% cache hit rate confirmed

---

## PHASE 2: SCALING (Sep 1 - Oct 1)

### Goals
- [ ] Scale from 100 → 1K repos
- [ ] Maintain <200ms latency
- [ ] Verify 99% cache hit rate
- [ ] Multi-instance support (2+)

### Tasks
1. Horizontal scaling (repo sharding)
2. Redis cluster setup (Sentinel)
3. Load balancing (round-robin)
4. Performance profiling + hotspot elimination
5. Monitoring + alerting (latency, cache misses)

---

## PHASE 3: DISTRIBUTION (Oct 1 - Nov 1)

### Goals
- [ ] Scale to 10K repos
- [ ] 99.9% availability
- [ ] Distributed coordination

### Tasks
1. Multi-region deployment
2. HA failover (backup mirrors)
3. Self-healing (auto-retry)
4. Cost optimization (archive old repos)

---

## PHASE 4: HARDENING (Nov 1 - Dec 31)

### Goals
- [ ] SOC 2 compliance
- [ ] Incident response automated
- [ ] Security audit passed

### Tasks
1. Ed25519 SSH key management
2. Encrypted credential storage
3. Compliance reporting (weekly)
4. Incident response playbooks

---

## TESTING STRATEGY (COMPLETE)

### Unit Tests (13 passing)
- Cache operations (set, get, clear, size)
- Delta detection (change/no-change, first-check)
- Model creation + field validation
- Severity ordering

### Integration Tests (In Phase 1)
- Git transport: clone 100 repos in <5s
- Cache: >99% hit rate at 100 accesses
- Delta: <200ms detection latency
- Governance: policy pass/fail scenarios
- Database: write + read accuracy

### Performance Tests (Phase 2)
- Latency profiling (50th, 95th, 99th percentile)
- Cache hit rate under concurrent load
- Batch fetch performance (100, 1K, 10K repos)

---

## DEPENDENCIES & INTEGRATIONS

### Crate Dependencies
- `uuid` (workspace) — unique IDs
- `chrono` (workspace) — timestamps
- `serde` (workspace) — JSON serialization
- `tokio` (workspace) — async runtime
- `redis` (0.24) — persistent cache
- `dashmap` (5.5) — concurrent local cache
- `sqlx` (workspace) — PostgreSQL access
- `thiserror` (workspace) — error types

### Crate Integrations
- **siss-gatekeeper**: Policy evaluation (ReBAC)
- **siss-event-log**: Audit trail (RadarEvent emission)
- **siss-feedback-router**: Creator notifications
- **siss-governance**: Policy definitions

---

## DEPLOYMENT CHECKLIST

**Day 1: Spin Up Infrastructure**
```bash
# 1. Deploy Redis
docker run -d -p 6379:6379 redis:7

# 2. Deploy PostgreSQL
docker run -d -p 5432:5432 postgres:15

# 3. Initialize Radar crate
cargo build -p siss-radar --release

# 4. Run migrations
sqlx migrate run --database-url postgres://...

# 5. Start Radar service
./target/release/siss-radar --config radar.toml
```

**Hourly Monitoring**
```bash
# Cache hit rate
redis-cli INFO stats | grep keyspace_hits

# Delta backlog
psql -c "SELECT COUNT(*) FROM delta_events WHERE processed_at IS NULL;"

# Avg latency
psql -c "SELECT AVG(fetch_latency_ms) FROM repo_snapshots WHERE last_checked > NOW() - INTERVAL '1 hour';"
```

---

## SUCCESS CRITERIA (PHASE 1 FINAL)

- [x] Architecture specified and documented
- [x] Data models complete
- [x] Cache layer working (local + Redis)
- [x] Delta detection algorithm (O(1))
- [ ] Git transport (clone, fetch, SHA)
- [ ] PostgreSQL persistence
- [ ] Governance integration hooks
- [ ] End-to-end monitoring cycle
- [ ] Integration tests (all passing)
- [ ] 100 repos monitored with <200ms latency
- [ ] Cache hit rate >99%
- [ ] Zero missed changes (100% accuracy)

**Estimated Timeline:** Aug 1 - Sep 1 (4 weeks)

---

## FILES CREATED

```
.claude/STREAM8_SOVEREIGN_RADAR_GITMONITOR_SPEC.md (comprehensive spec)
.claude/STREAM8_IMPLEMENTATION_PLAN.md (this file)
crates/siss-radar/Cargo.toml (dependencies)
crates/siss-radar/README.md (architecture overview)
crates/siss-radar/src/lib.rs (module exports)
crates/siss-radar/src/models.rs (5 core types + 3 tests)
crates/siss-radar/src/cache_layer.rs (LocalCache + RedisCache + 4 tests)
crates/siss-radar/src/delta_detection.rs (DeltaDetector + 6 tests)
Cargo.toml (updated: added siss-radar to workspace members)
```

**Total Lines of Code:** ~850 (models + cache + detection + tests)  
**Test Coverage:** 13 tests, 100% passing  
**Compilation:** ✓ No errors, 1 warning (unused field — design artifact)

---

## NEXT STEPS (IMMEDIATE)

1. **Implement Git Transport** (Task 1)
   - Create `git_transport.rs`
   - Clone + fetch + SHA extraction
   - 5+ tests (clone speed, fetch accuracy)

2. **Add PostgreSQL Layer** (Task 2)
   - Create `db_layer.rs`
   - Schema migrations
   - CRUD operations

3. **Integrate Governance** (Task 3)
   - Create `governance_integration.rs`
   - Policy evaluation
   - Event emission + notifications

4. **Build Coordinator** (Task 4)
   - Create `coordinator.rs`
   - Orchestrate full monitoring cycle

5. **Write Integration Tests** (Task 5)
   - End-to-end testing
   - Latency SLA verification

**Critical Path:** Git transport → DB layer → Coordinator (10 days total)

---

## DECISION GATES

**Before Phase 2 (Sep 1):**
- [ ] All Phase 1 tests passing
- [ ] 100 repos monitored successfully
- [ ] Latency <200ms per repo verified
- [ ] Cache hit rate >99% confirmed
- [ ] Zero missed changes (100% accuracy)

**Before Phase 3 (Oct 1):**
- [ ] Scale to 1K repos confirmed
- [ ] Multi-instance deployment working
- [ ] Performance profiling complete

**Before Phase 4 (Nov 1):**
- [ ] Scale to 10K repos verified
- [ ] 99.9% availability confirmed

---

**Status:** READY FOR PHASE 1 IMPLEMENTATION  
**Owner Assignment:** TBD (recommend 1 senior engineer + 1 mid-level)  
**Budget:** ~400 engineer-hours (Phase 1-4)
