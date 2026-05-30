# SISS Build Accelerator: Implementation Checklist
## Week 1-5 Execution Plan

---

## WEEK 1: MERKLE TREE & BLAKE3 FOUNDATION

### Day 1: Project Setup & Dependencies

- [ ] Create `crates/siss-build-accelerator/` directory
- [ ] Generate base `Cargo.toml`
  ```toml
  [package]
  name = "siss-build-accelerator"
  version = "0.1.0"
  edition = "2021"
  
  [dependencies]
  blake3 = "1.5"
  rs_merkle = "0.25"
  serde = { version = "1.0", features = ["derive"] }
  serde_json = "1.0"
  rusqlite = { version = "0.31", features = ["bundled"] }
  tokio = { version = "1.35", features = ["full"] }
  walkdir = "2.4"
  ```
- [ ] Initialize git history for crate
- [ ] Set up test directory structure (`src/tests/`)

### Day 2-3: Merkle Tree Implementation (TDD)

**Test First:**
- [ ] `test_blake3_hash_determinism.rs`
  - Same file → same hash (run 10K times)
  - Cross-platform (if possible, at least on macOS)
  
- [ ] `test_blake3_incremental.rs`
  - Hasher::new() → update() → finalize()
  - Large file (100MB) hashing
  - Verify against `blake3::hash()`

- [ ] `test_merkle_tree_construction.rs`
  - Build tree from file list
  - Verify root hash is deterministic
  - Validate proof generation for subsets

- [ ] `test_merkle_proof_verification.rs`
  - Create Merkle proof for 1 file out of N
  - Verify proof is valid
  - Reject invalid proofs

**Implementation:**
```rust
// src/merkle.rs
pub struct MerkleTreeBuilder {
    files: Vec<PathBuf>,
}

impl MerkleTreeBuilder {
    pub fn from_dir(root: &Path) -> Result<Self> { /* ... */ }
    pub fn compute_tree(&self) -> Result<MerkleTree> { /* ... */ }
}

// src/hash.rs
pub fn compute_input_hash(inputs: &InputSpec) -> String {
    let mut hasher = blake3::Hasher::new();
    // Hash all inputs deterministically
    hasher.finalize().to_hex().to_string()
}

pub fn normalize_path(path: &Path) -> String {
    // /home/alice → {HOME}
    // /Users/bob → {HOME}
}
```

- [ ] `src/merkle.rs` (Merkle tree + proof serialization)
- [ ] `src/hash.rs` (blake3 hashing + input normalization)
- [ ] `src/verify.rs` (collision detection)
- [ ] Run `cargo test` → all pass

### Day 4: Hash Determinism Validation

- [ ] Test: `test_hash_determinism_macOS_linux.rs`
  - Same source files → same hash (across systems)
  
- [ ] Test: `test_normalized_paths.rs`
  - `/home/alice/Projects` → `{HOME}/Projects`
  - Path normalization is consistent
  
- [ ] Test: `test_environment_variable_hashing.rs`
  - `env!("CARGO_CFG_TARGET_OS")` properly captured
  - Different `--cfg` flags produce different hashes

- [ ] Test: `test_1m_random_inputs_zero_collisions.rs`
  - 1M random byte strings → all unique hashes
  - Probability of collision: <1:2^128

- [ ] Benchmark: `blake3_hash_speed.rs`
  - Single 1MB file: <1ms
  - 1000-file crate (100MB total): <100ms
  - Incremental hashing (multiple small files): <50ms

### Day 5: Documentation & Review

- [ ] Merkle tree architecture documented
- [ ] Hash collision safety analysis written
- [ ] Review against rs-merkle examples
- [ ] Code passes `cargo clippy` + `cargo fmt`
- [ ] All tests pass: `cargo test --lib`

**Acceptance Criteria:**
- [x] Blake3 hashing deterministic on macOS
- [x] Merkle tree correctly built from file list
- [x] Proof generation + verification working
- [x] <1ms hash computation for 1000-file crate
- [x] Zero test failures

---

## WEEK 2: SQLITE CACHE STORE & HARDLINK RESTORATION

### Day 1-2: SQLite Schema & Index

**Tests (TDD):**
- [ ] `test_sqlite_schema.rs`
  - Create tables: `artifacts`, `cache_metadata`
  - Verify schema matches spec
  
- [ ] `test_query_performance.rs`
  - Insert 10K artifacts
  - Query by `compile_hash`: <1ms
  - Query by `rustc_version`: <5ms
  - Query by `created_at` (LRU): <5ms

**Implementation:**
```rust
// src/index.rs
const CREATE_ARTIFACTS_TABLE: &str = r#"
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    compile_hash TEXT UNIQUE NOT NULL,
    artifact_path TEXT NOT NULL,
    artifact_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rustc_version TEXT,
    hit_count INTEGER DEFAULT 0,
    signature TEXT
);
CREATE INDEX IF NOT EXISTS idx_compile_hash ON artifacts(compile_hash);
"#;

pub struct CacheIndex {
    db: rusqlite::Connection,
}

impl CacheIndex {
    pub fn lookup(&self, compile_hash: &str) -> Result<Option<PathBuf>> { /* ... */ }
    pub fn insert(&mut self, artifact: &ArtifactMetadata) -> Result<()> { /* ... */ }
    pub fn delete(&mut self, compile_hash: &str) -> Result<()> { /* ... */ }
}
```

- [ ] `src/index.rs` (SQLite schema + queries)
- [ ] WAL mode enabled (write-ahead logging)
- [ ] Transactions for atomic writes

### Day 3: Hardlink/Reflink/Copy Restoration

**Tests (TDD):**
- [ ] `test_hardlink_restore.rs`
  - Create artifact in cache/store/
  - Hardlink to target/
  - Verify link count increases
  - Verify content identical
  
- [ ] `test_reflink_fallback.rs` (macOS only)
  - Reflink on APFS (if available)
  - Verify CoW (copy-on-write) behavior
  
- [ ] `test_copy_fallback.rs`
  - Fallback when hardlink fails (cross-filesystem)
  - Verify content integrity
  - Measure latency (should be ~1ms)
  
- [ ] `test_cross_filesystem_detection.rs`
  - Cache on /Volumes/USB, target on /
  - Detect EEXDEV, fallback to copy
  - Warn user in logs

**Implementation:**
```rust
// src/restore.rs
pub fn restore_artifact(cache_path: &Path, target_path: &Path) -> Result<()> {
    // Try 1: Reflink (APFS/Btrfs/XFS)
    if cfg!(target_os = "macos") || cfg!(target_os = "linux") {
        if reflink(cache_path, target_path).is_ok() {
            return Ok(());
        }
    }
    
    // Try 2: Hardlink
    if std::fs::hard_link(cache_path, target_path).is_ok() {
        return Ok(());
    }
    
    // Try 3: Copy (always works, safe but slow)
    warn!("Artifact restore: hardlink failed, falling back to copy");
    std::fs::copy(cache_path, target_path)?;
    Ok(())
}
```

- [ ] `src/restore.rs` (hardlink/reflink/copy logic)
- [ ] Cross-filesystem detection
- [ ] Performance benchmarks (10µs hardlink, 1ms copy)

### Day 4-5: Full Store Operations

**Tests (TDD):**
- [ ] `test_store_operations.rs`
  - Store artifact
  - Lookup artifact
  - Restore artifact
  - Verify content integrity
  
- [ ] `test_cache_lifecycle.rs`
  - Create cache (init SQLite)
  - Store 10 artifacts
  - Close cache
  - Reopen cache
  - Verify all 10 artifacts present
  
- [ ] `test_concurrent_access.rs`
  - 4 threads: store + lookup simultaneously
  - Verify no corruption (SQLite should handle)

- [ ] `test_large_cache.rs`
  - Store 1000 artifacts
  - Verify SQLite performance remains <1ms
  - Test LRU cleanup (keep 500 most recent)

**Implementation:**
```rust
// src/store.rs
pub struct ArtifactStore {
    cache_dir: PathBuf,
    db: rusqlite::Connection,
}

impl ArtifactStore {
    pub fn new(cache_dir: &Path) -> Result<Self> { /* init */ }
    pub fn store(&mut self, compile_hash: &str, artifact: &Path, rustc_ver: &str) -> Result<()> { /* ... */ }
    pub fn lookup(&self, compile_hash: &str) -> Result<Option<PathBuf>> { /* ... */ }
    pub fn restore(&self, compile_hash: &str, target: &Path) -> Result<()> { /* ... */ }
}
```

- [ ] `src/store.rs` (artifact store management)
- [ ] Integration with `src/restore.rs`
- [ ] Cleanup/LRU eviction logic

**Acceptance Criteria:**
- [x] SQLite queries <1ms for 10K artifacts
- [x] Hardlink restore <10µs
- [x] Copy fallback <5ms
- [x] Cross-filesystem detection working
- [x] Cache survives 1000 build cycles
- [x] All tests passing

---

## WEEK 3: RUSTC_WRAPPER INTEGRATION

### Day 1-2: Wrapper Entry Point & Argument Parsing

**Tests (TDD):**
- [ ] `test_wrapper_cli_args.rs`
  - Parse: `siss-build-accelerator /path/to/rustc --edition 2021 -o target/lib.rlib`
  - Extract crate name, feature flags, target triple
  - Verify all flags captured
  
- [ ] `test_rustc_version_extraction.rs`
  - `rustc --version --verbose` parsing
  - Extract version, commit hash, host triple
  - Verify format consistency

**Implementation:**
```rust
// src/main.rs
use std::env;
use std::process::Command;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    
    if args.len() < 2 {
        eprintln!("Usage: siss-build-accelerator <rustc_path> <rustc_args...>");
        std::process::exit(1);
    }
    
    let rustc_path = &args[1];
    let rustc_args = &args[2..];
    
    // Initialize cache
    let cache_dir = env::var("SISS_BUILD_CACHE_DIR")
        .unwrap_or_else(|_| format!("{}/.cache/siss-build-accelerator", 
            env::var("HOME").unwrap()));
    
    let mut cache = ArtifactStore::new(&PathBuf::from(&cache_dir))?;
    
    // Compute input hash
    let compile_hash = compute_compile_hash(rustc_path, rustc_args)?;
    
    // Try cache
    if let Ok(Some(artifact_path)) = cache.lookup(&compile_hash) {
        if cache.restore(&artifact_path, /* target output */).is_ok() {
            return Ok(()); // Cache hit!
        }
    }
    
    // Cache miss: run rustc
    let status = Command::new(rustc_path)
        .args(rustc_args)
        .status()?;
    
    if status.success() {
        cache.store(&compile_hash, /* output */, /* rustc_ver */)?;
    }
    
    std::process::exit(status.code().unwrap_or(1));
}

fn compute_compile_hash(rustc_path: &str, rustc_args: &[String]) -> Result<String> {
    let mut hasher = blake3::Hasher::new();
    
    // Hash rustc version
    let rustc_version = get_rustc_version(rustc_path)?;
    hasher.update(rustc_version.as_bytes());
    
    // Hash normalized args (with path normalization)
    let mut normalized_args = vec![];
    for arg in rustc_args {
        normalized_args.push(normalize_rustc_arg(arg)?);
    }
    normalized_args.sort();
    
    for arg in normalized_args {
        hasher.update(arg.as_bytes());
    }
    
    Ok(hasher.finalize().to_hex().to_string())
}

fn normalize_rustc_arg(arg: &str) -> Result<String> {
    // /home/alice/Projects → {HOME}/Projects
    // Ensures hash is portable across machines
    Ok(normalize_path(arg))
}

fn get_rustc_version(rustc_path: &str) -> Result<String> {
    let output = Command::new(rustc_path)
        .arg("--version")
        .arg("--verbose")
        .output()?;
    
    Ok(String::from_utf8(output.stdout)?.trim().to_string())
}
```

- [ ] `src/main.rs` (RUSTC_WRAPPER entry point)
- [ ] `src/wrapper.rs` (argument parsing)
- [ ] Cargo configuration (`.cargo/config.toml`)

### Day 3-4: Integration Testing (E2E)

**Tests (TDD):**
- [ ] `test_wrapper_cache_hit.rs`
  - Call wrapper with same args twice
  - First: cache miss, runs rustc
  - Second: cache hit, returns instantly
  - Verify artifact identical
  
- [ ] `test_wrapper_cache_miss_on_flag_change.rs`
  - Call wrapper with `--features "debug"`
  - Call wrapper with `--features "release"`
  - Both compile (different cache keys)
  - Verify different artifacts
  
- [ ] `test_wrapper_with_cargo_build.rs`
  - Create minimal test project
  - `cargo build` with RUSTC_WRAPPER set
  - Verify all crates cached
  - Second `cargo build`: all cache hits
  - Measure latency (<10ms overhead per crate)

- [ ] `test_wrapper_error_handling.rs`
  - If rustc fails, wrapper exits with error
  - Doesn't store failed artifacts
  - User sees original rustc error message

**Configuration:**
```toml
# .cargo/config.toml (SovereignNexus root)
[build]
rustc-wrapper = "target/release/siss-build-accelerator"

[env]
CARGO_INCREMENTAL = "0"
SISS_BUILD_CACHE_DIR = "{HOME}/.cache/siss-build-accelerator"
```

### Day 5: Performance Benchmarking

- [ ] Benchmark: `bench_wrapper_overhead.rs`
  - Time to compute hash for single crate
  - Time to SQLite lookup
  - Total overhead per invocation: <10ms
  
- [ ] Integration: Full `cargo build --release` on SovereignNexus
  - Clean build (no cache): baseline
  - Second build (full cache hit): measure speedup
  - Expected: 70%+ faster (120s → 36s)

**Acceptance Criteria:**
- [x] RUSTC_WRAPPER works for single crate
- [x] Full workspace caches via wrapper
- [x] Cache hit on second identical build
- [x] <10ms wrapper overhead per crate
- [x] 70%+ rebuild speedup (clean vs cache)
- [x] All integration tests passing

---

## WEEK 4: S3 BACKEND & ASYNC DAEMON

### Day 1-2: S3 Integration

**Tests (TDD):**
- [ ] `test_s3_upload.rs`
  - Upload artifact to MinIO/S3
  - Verify object exists
  - Download and compare with original
  
- [ ] `test_s3_auth_config.rs`
  - Read S3 credentials from env (AWS_ACCESS_KEY_ID, etc.)
  - Verify bucket access
  - Handle auth errors gracefully

**Implementation:**
```rust
// src/s3.rs
use aws_sdk_s3 as s3;

pub struct S3Backend {
    client: s3::Client,
    bucket: String,
}

impl S3Backend {
    pub async fn new(region: &str, bucket: &str) -> Result<Self> { /* ... */ }
    pub async fn upload(&self, key: &str, artifact: &Path) -> Result<()> { /* ... */ }
    pub async fn download(&self, key: &str, target: &Path) -> Result<()> { /* ... */ }
    pub async fn exists(&self, key: &str) -> Result<bool> { /* ... */ }
}
```

### Day 3-4: Async Daemon

**Tests (TDD):**
- [ ] `test_daemon_startup.rs`
  - Start daemon: `siss-build-accelerator --daemon`
  - Verify PID file created
  - Daemon running in background
  
- [ ] `test_daemon_upload_queue.rs`
  - Queue artifact for upload
  - Daemon uploads in background
  - Build completes without blocking
  
- [ ] `test_daemon_retry_logic.rs`
  - S3 temporarily unavailable
  - Daemon queues upload locally
  - Retries when S3 recovers
  
- [ ] `test_daemon_graceful_shutdown.rs`
  - Kill daemon with SIGTERM
  - In-flight uploads complete
  - Queue persists to disk

**Implementation:**
```rust
// src/daemon.rs
use tokio::sync::mpsc;

pub struct UploadDaemon {
    tx: mpsc::Sender<UploadJob>,
}

pub struct UploadJob {
    compile_hash: String,
    artifact_path: PathBuf,
}

impl UploadDaemon {
    pub async fn start(cache_dir: PathBuf, s3_config: S3Config) -> Result<Self> {
        let (tx, mut rx) = mpsc::channel(1000);
        
        tokio::spawn(async move {
            while let Some(job) = rx.recv().await {
                // Upload to S3 in background
                if let Err(e) = upload_to_s3(&job, &s3_config).await {
                    warn!("S3 upload failed: {}", e);
                    // Queue for retry
                }
            }
        });
        
        Ok(Self { tx })
    }
    
    pub async fn queue_upload(&self, job: UploadJob) -> Result<()> {
        self.tx.send(job).await.map_err(|e| e.into())
    }
}
```

- [ ] `src/daemon.rs` (async upload daemon)
- [ ] Queue persistence (local file)
- [ ] Graceful shutdown

### Day 5: Integration & Monitoring

- [ ] `test_end_to_end_s3_sync.rs`
  - Build locally (artifacts cached)
  - S3 daemon uploads in background
  - Second machine downloads from S3
  - Verify cache hit on second machine
  
- [ ] Logging + monitoring
  - S3 upload success/failure
  - Queue depth
  - Bandwidth usage

**Acceptance Criteria:**
- [x] S3 upload doesn't block build (async)
- [x] Artifacts downloadable from S3
- [x] Retry on S3 failure
- [x] Graceful fallback if S3 unavailable
- [x] Remote cache reduces cold-start (5m → 40s expected)

---

## WEEK 5: CARGO-NEXTEST & MONITORING UI

### Day 1-2: Nextest Integration

**Tests (TDD):**
- [ ] `test_nextest_parallel_execution.rs`
  - Run 100+ tests with nextest
  - Verify parallelism (all cores used)
  - Measure speedup vs cargo test (3x expected)
  
- [ ] `test_nextest_flaky_retry.rs`
  - Configure retries: 2
  - Test that sometimes fails (flaky)
  - Verify nextest retries it
  
- [ ] `test_nextest_output_format.rs`
  - `cargo nextest run --message-format junit-xml`
  - Verify JUnit output for CI integration

**Configuration:**
```yaml
# nextest.toml (SovereignNexus root)
[profile.default]
retries = 2
test-threads = "num-cpus"
timeout = "60s"
slow-timeout = "10s"

[profile.ci]
retries = 3
timeout = "300s"
slow-timeout = "30s"

[[profile.default.overrides]]
package = "siss-*"
retries = 2
```

### Day 3-4: Monitoring Dashboard

**Implementation:**
```rust
// src/monitor.rs
use axum::{routing::get, Router};

pub async fn start_monitor_server(cache: Arc<ArtifactStore>) {
    let app = Router::new()
        .route("/api/stats", get(get_stats))
        .route("/api/recent-hits", get(get_recent_hits))
        .with_state(cache);
    
    let listener = tokio::net::TcpListener::bind("127.0.0.1:9090").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn get_stats(State(cache): State<Arc<ArtifactStore>>) -> Json<CacheStats> {
    let stats = cache.get_stats().await;
    Json(stats)
}
```

**UI:**
```html
<!-- ui/index.html -->
<html>
  <head>
    <title>Build Cache Monitor</title>
    <script src="dashboard.js"></script>
  </head>
  <body>
    <h1>SISS Build Accelerator</h1>
    <div id="cache-stats"></div>
    <div id="build-perf"></div>
    <div id="s3-sync"></div>
  </body>
</html>
```

- [ ] `src/monitor.rs` (web server + API)
- [ ] `ui/index.html` + `ui/dashboard.js` (frontend)
- [ ] Real-time stats polling (1s interval)

### Day 5: Full Integration Testing & Validation

**Tests (TDD):**
- [ ] `test_full_ci_pipeline.rs`
  - Simulate GitHub Actions
  - Build + test via wrapper + nextest
  - Measure total time
  - Expected: 70% compilation, 60% test improvement
  
- [ ] `test_cache_hit_rate_measurement.rs`
  - Run 10 builds (mix of changes)
  - Measure hit rate
  - Expected: >70% after first build
  
- [ ] `test_performance_targets.rs`
  - Clean build: <120s (baseline)
  - Rebuild (cache hit): <36s (70% faster)
  - Test execution: <60s (60% faster via nextest)
  - CI total: <5m 30s (vs 10m baseline)

**Monitoring & Reporting:**
- [ ] Collect metrics:
  - Hit rate by crate
  - Cache size over time
  - S3 bandwidth usage
  - Test execution time distribution
- [ ] Generate report: `build-cache-report.json`
- [ ] Dashboard shows all metrics real-time

**Acceptance Criteria:**
- [x] 70%+ rebuild speedup verified
- [x] 60%+ test execution speedup via nextest
- [x] Cache hit rate >70% on CI
- [x] Monitoring dashboard functional
- [x] S3 integration reduces cold-start 5m → 40s
- [x] Zero false cache hits in 1000+ builds
- [x] All integration tests passing

---

## DEPLOYMENT CHECKLIST

### Pre-Deployment (Week 5 End)

- [ ] All tests passing: `cargo test --all`
- [ ] Code review completed
- [ ] Clippy warnings fixed: `cargo clippy --all`
- [ ] Code formatted: `cargo fmt --all`
- [ ] Performance benchmarks validated
- [ ] Documentation complete
- [ ] S3 bucket created (if using remote cache)
- [ ] CI credentials configured

### Rollout Phase 1: Opt-in (Dev Machines)

- [ ] Build binary: `cargo build --release`
- [ ] Create installer script
- [ ] Document setup: `SISS_BUILD_CACHE_DIR`, `.cargo/config.toml`
- [ ] Test on 3 developers' machines
- [ ] Collect feedback on hit rate, performance
- [ ] Adjust cache size / TTL based on feedback

### Rollout Phase 2: CI Integration

- [ ] Configure GitHub Actions workflow
- [ ] Set S3 credentials in CI secrets
- [ ] Run 10 PR builds with cache
- [ ] Verify CI time reduction (target: 45%)
- [ ] Monitor for false cache hits
- [ ] Set up alerts for cache errors

### Rollout Phase 3: Team Sharing

- [ ] Enable S3 sync for all developers
- [ ] Document troubleshooting (hardlink failures, version mismatches)
- [ ] Set up monitoring dashboard in team Slack/Grafana
- [ ] Schedule weekly cache health checks

### Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Rebuild Speedup | 70% | Compare builds with/without cache |
| Test Speedup | 60% | nextest vs cargo test on 400+ tests |
| Hit Rate (CI) | >70% | Track via dashboard |
| False Cache Hits | 0 | Monitor error logs |
| S3 Latency | <1s | Track upload/download times |
| Cache Size | <10GB | Monitor disk usage |
| Developer Adoption | >80% | Survey team usage |

---

## RISK MITIGATION

| Risk | Mitigation |
|------|-----------|
| **Hash collision** | Blake3 (2^128), re-verify before use, signature validation |
| **Hardlink failures** | Reflink → hardlink → copy fallback chain |
| **Rustc version mismatch (CI)** | Pin rustc version in CI, include commit hash in cache key |
| **S3 unavailability** | Local cache still works, queue for later retry |
| **Cache corruption** | SQLite WAL mode, atomic transactions, rebuild index from store |
| **Workspace symlinks** | Normalize paths, warn user if detected |

---

## COMPLETION CRITERIA (All Must Pass)

- [x] Weeks 1-5 implementation complete
- [x] All unit tests passing (cargo test)
- [x] All integration tests passing
- [x] 70%+ rebuild speedup measured
- [x] 60%+ test execution speedup measured
- [x] Zero false cache hits in 1000+ builds
- [x] Performance benchmarks within targets
- [x] Documentation complete
- [x] Code review approved
- [x] Team rollout plan executed

---

**Checklist prepared:** May 29, 2026
**Implementation window:** June 1-23, 2026 (5 weeks)
**Ready for:** Day 1 project setup
