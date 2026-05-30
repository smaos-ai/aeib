# SISS Build Accelerator: Quick Reference Card
## Implementation & Troubleshooting Guide

---

## CORE CONCEPTS

### 1. Cache Key = blake3(inputs)
```
Hash components (deterministic order):
1. rustc --version --verbose        (e.g., "rustc 1.79.0 (abc123...)")
2. target triple                    (e.g., "x86_64-apple-darwin")
3. crate name                       (e.g., "siss-agent-shell")
4. ALL source file paths (sorted)   (e.g., "src/lib.rs", "src/main.rs")
5. ALL source file contents         (blake3(each file))
6. Dependency rlib/rmeta hashes     (transitive deps)
7. Feature flags (sorted)           (e.g., "--features debug,tracing")
8. Codegen flags (sorted)           (e.g., "-C opt-level=3")
9. Normalized paths                 (/home/alice → {HOME})

Result: compile_hash = 64-char hex string (blake3 256-bit)
```

### 2. Restoration Chain
```
Try 1: reflink(cache_path, target_path)  → APFS/Btrfs/XFS CoW
        └─ Fails? (ENOTSUP)
           ↓
Try 2: hardlink(cache_path, target_path) → Inode-shared (10µs)
        └─ Fails? (EEXDEV = cross-filesystem)
           ↓
Try 3: copy(cache_path, target_path)     → Safe fallback (1ms)
        └─ Success!
```

### 3. Cache Levels
```
Level 1: Input hash computation         (10ms per crate)
Level 2: SQLite lookup                  (<1ms)
Level 3: Hardlink restoration           (10µs)
Level 4: S3 download (if local miss)    (1-5s + 10µs restore)

Total local cache hit: ~10-20ms
Total S3 cache hit: ~1-5s
Miss (full compile): ~30-120s
```

---

## DIRECTORY STRUCTURE

```
crates/siss-build-accelerator/
├── Cargo.toml                          # deps: blake3, rs_merkle, rusqlite, tokio
├── src/
│   ├── main.rs                         # Entry point (RUSTC_WRAPPER)
│   ├── lib.rs                          # Re-exports
│   ├── merkle.rs                       # Merkle tree (optional advanced)
│   ├── hash.rs                         # blake3 hashing + normalization
│   ├── verify.rs                       # Collision detection
│   ├── store.rs                        # SQLite store operations
│   ├── restore.rs                      # Hardlink/reflink/copy logic
│   ├── wrapper.rs                      # Argument parsing
│   ├── s3.rs                           # S3 backend (Week 4)
│   ├── daemon.rs                       # Async upload daemon (Week 4)
│   ├── monitor.rs                      # Web dashboard (Week 5)
│   └── tests/
│       ├── test_hash_determinism.rs    # Week 1
│       ├── test_merkle_proof.rs        # Week 1
│       ├── test_store_ops.rs           # Week 2
│       ├── test_hardlink_restoration.rs # Week 2
│       ├── test_wrapper_e2e.rs         # Week 3
│       ├── test_s3_integration.rs      # Week 4
│       └── test_full_ci_pipeline.rs    # Week 5
└── ui/                                 # (Week 5)
    ├── index.html                      # Dashboard HTML
    └── dashboard.js                    # Real-time stats
```

---

## KEY CONFIGURATIONS

### .cargo/config.toml (SovereignNexus root)
```toml
[build]
rustc-wrapper = "target/release/siss-build-accelerator"

[env]
CARGO_INCREMENTAL = "0"                        # Cache replaces incremental
SISS_BUILD_CACHE_DIR = "{HOME}/.cache/siss-build-accelerator"
SISS_BUILD_ENABLE_REMOTE = "true"              # S3 backend
SISS_BUILD_S3_BUCKET = "s3://nexus-build-cache"
SISS_BUILD_S3_REGION = "eu-west-1"
SISS_BUILD_S3_PREFIX = "artifacts/"
```

### nextest.toml (SovereignNexus root)
```yaml
[profile.default]
retries = 2
test-threads = "num-cpus"
timeout = "60s"
slow-timeout = "10s"

[profile.ci]
retries = 3
timeout = "300s"
```

### Environment Variables (CI)
```bash
export RUSTC_WRAPPER=/path/to/siss-build-accelerator
export CARGO_INCREMENTAL=0
export SISS_BUILD_CACHE_DIR=/tmp/siss-cache
export SISS_BUILD_S3_BUCKET=s3://nexus-build-cache
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
```

---

## COMMON TASKS

### Build siss-build-accelerator
```bash
cd crates/siss-build-accelerator
cargo build --release
# Binary: target/release/siss-build-accelerator
```

### Test Everything
```bash
cargo test --lib                           # Unit tests (Week 1-5)
cargo test --test "*"                      # Integration tests
cargo test --all --release                 # Full suite
```

### Run with Cache (Local)
```bash
export RUSTC_WRAPPER=$(pwd)/target/release/siss-build-accelerator
export SISS_BUILD_CACHE_DIR=~/.cache/siss-build-accelerator
cargo build --release                      # Cache hit on 2nd run
```

### Inspect Cache
```bash
ls -lh ~/.cache/siss-build-accelerator/store/    # Artifacts
sqlite3 ~/.cache/siss-build-accelerator/index.sqlite \
  "SELECT compile_hash, artifact_path FROM artifacts LIMIT 10;"
```

### Monitor Dashboard
```bash
# Terminal 1: Run app with monitor enabled
SISS_BUILD_MONITOR_PORT=9090 cargo build --release

# Terminal 2: Open browser
open http://localhost:9090/
```

### Clean Cache
```bash
# Full wipe
rm -rf ~/.cache/siss-build-accelerator/

# Or use API (if monitor running)
curl -X POST http://localhost:9090/api/cache/clear
```

### Test with S3 (MinIO locally)
```bash
# Start MinIO on localhost:9000
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data

# Create bucket
mc alias set minio http://localhost:9000 minioadmin minioadmin
mc mb minio/nexus-build-cache

# Configure wrapper
export SISS_BUILD_S3_BUCKET=s3://nexus-build-cache
export SISS_BUILD_S3_ENDPOINT=http://localhost:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin

# Test upload
cargo build --release
```

---

## TROUBLESHOOTING

### Issue: Cache hit not working (always recompiling)

**Diagnosis:**
```bash
# 1. Verify wrapper is being called
$ RUST_LOG=debug cargo build --release 2>&1 | grep siss-build-accelerator

# 2. Check if hash computation is consistent
$ cargo clean
$ cargo build --release   # Note compile_hash
$ cargo build --release   # Should be same hash

# 3. Check SQLite index
$ sqlite3 ~/.cache/siss-build-accelerator/index.sqlite \
  "SELECT COUNT(*) FROM artifacts;"
```

**Solution:**
- Verify SISS_BUILD_CACHE_DIR is set correctly
- Check rustc version consistency: `rustc --version --verbose`
- Verify source files haven't changed (git status)
- Rebuild cache: `rm -rf ~/.cache/siss-build-accelerator/`

### Issue: Hardlink fails, everything goes slow

**Symptom:** `fallback to copy` in logs, restore takes 1ms instead of 10µs

**Diagnosis:**
```bash
# 1. Check filesystem types
$ df -T ~/.cache/siss-build-accelerator
$ df -T ~/Documents/SovereignNexus

# 2. Test hardlink capability
$ touch /tmp/test && ln /tmp/test /tmp/test2 && echo "hardlink OK"
```

**Solution:**
- **Best:** Move cache to same volume as workspace
  ```bash
  # ~/.cache might be on different filesystem
  # Option 1: Move cache to project
  mv ~/.cache/siss-build-accelerator ~/Documents/SovereignNexus/.cache-accelerator
  export SISS_BUILD_CACHE_DIR=~/Documents/SovereignNexus/.cache-accelerator
  
  # Option 2: Use separate partition/volume
  ln -s /fast-volume/.siss-cache ~/.cache/siss-build-accelerator
  ```

### Issue: Rustc version mismatch (local vs CI)

**Symptom:** Build succeeds locally, fails in CI

**Diagnosis:**
```bash
# Local
$ rustc --version --verbose

# CI (check logs)
# Look for "rustc_version": "..."
```

**Solution:**
```bash
# rust-toolchain.toml (project root)
[toolchain]
channel = "1.79.0"
components = ["rustfmt", "clippy"]
targets = ["x86_64-apple-darwin", "x86_64-unknown-linux-gnu"]

# Or in CI workflow
- uses: dtolnay/rust-toolchain@stable
  with:
    toolchain: 1.79.0
```

### Issue: S3 upload failing

**Diagnosis:**
```bash
# Check S3 credentials
$ aws s3 ls --region eu-west-1

# Check daemon logs
$ tail -f ~/.cache/siss-build-accelerator/logs/sync.log

# Verify bucket exists
$ aws s3 ls s3://nexus-build-cache/
```

**Solution:**
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>

# Or use ~/.aws/credentials
[default]
aws_access_key_id = <key>
aws_secret_access_key = <secret>
```

### Issue: Cache corruption (SQLite errors)

**Symptom:** `database disk image is malformed` errors

**Solution:**
```bash
# WAL mode should prevent this, but if corrupted:
rm ~/.cache/siss-build-accelerator/index.sqlite*
rm ~/.cache/siss-build-accelerator/index.sqlite-shm
rm ~/.cache/siss-build-accelerator/index.sqlite-wal

# Rebuild index from store/
siss-build-accelerator --rebuild-index

# Or full wipe
rm -rf ~/.cache/siss-build-accelerator/
```

---

## PERFORMANCE EXPECTATIONS

### Typical Build Timeline
```
cargo build --release (9 crates, 50 deps)

COLD BUILD (no cache):
├─ Dependency compilation: 90s
├─ Our crates compilation: 20s
└─ Linking: 10s
   Total: 120s

WARM BUILD (all cached):
├─ Hash computation: 5ms (all inputs)
├─ SQLite lookup: 50ms (9 crates × <1ms)
├─ Hardlink restoration: 90µs (9 crates × 10µs)
├─ Missing dep recompile: 2s (e.g., 1 changed dependency)
└─ Linking: 1s
   Total: 3-5s (97% faster)

PARTIAL BUILD (1 crate changed):
├─ Hash/lookup/restore: 100ms
├─ Changed crate recompile: 5s
├─ Dependent crate recompile: 3s
└─ Linking: 1s
   Total: 9s (70% faster than cold)
```

### Test Execution Timeline
```
cargo nextest run (400 tests)

CARGO TEST (serial):
├─ Compile test binaries: 60s (RUSTC_WRAPPER cache hits)
├─ Run tests (serial threads): 150s (1 test/thread, no parallelism)
└─ Collect results: 10s
   Total: 220s

NEXTEST (parallel):
├─ Compile test binaries: 60s (same, RUSTC_WRAPPER)
├─ Run tests (all cores, 8 CPU): 60s
│  (400 tests ÷ 8 cores ÷ 1-2s per test = parallelization)
└─ Collect results: 5s
   Total: 125s (43% faster)

WITH 2x RETRIES (nextest):
├─ Parallel: 60s
├─ Flaky retries: 10s (if needed)
└─ Total: 70-75s (60% faster than cargo test)
```

---

## METRICS TO TRACK

### Cache Health
| Metric | Expected | Action |
|--------|----------|--------|
| Hit Rate | >70% | <50% → investigate workload |
| Fresh Misses | <5% | >10% → cache eviction issue |
| Corruption Rate | 0% | Any → check WAL mode |
| Avg Query Time | <1ms | >5ms → rebuild index |

### Performance
| Metric | Expected | Action |
|--------|----------|--------|
| Rebuild Speedup | 70% | <50% → check cache hits |
| Test Speedup | 60% | <40% → nextest config |
| CI Cold-Start | 2m 17s | >3m → S3 slow/missing |
| S3 Latency | 100-300ms | >500ms → network issue |

### Infrastructure
| Metric | Expected | Action |
|--------|----------|--------|
| Cache Size | <10GB | >15GB → evict old items |
| S3 Storage | <100GB | >500GB → clean old builds |
| Error Rate | <0.1% | >1% → investigate logs |
| Uptime | >99.9% | Any downtime → fix |

---

## DECISION TREES

### "Should I use RUSTC_WRAPPER?"
```
Are you...
├─ Building Rust projects?           → YES
├─ Running cargo build/test?         → YES
├─ Want faster rebuilds?             → YES
├─ Have Python/JavaScript project?   → NO (use sccache for C++)
│
→ USE RUSTC_WRAPPER ✓
```

### "Do I need S3?"
```
Are you...
├─ Solo developer?                   → Optional (local cache enough)
├─ Team of 2-5?                      → Recommended (shared team cache)
├─ CI/CD pipeline?                   → Strongly recommended
├─ Multiple machines?                → Required
│
→ If team > 2: Enable S3 ✓
```

### "Cache hit but wrong output?"
```
Is there...
├─ Hash collision?                   → EXTREMELY unlikely (<1:2^90)
├─ Rustc version mismatch?           → CHECK rustc --version --verbose
├─ Source file changed?              → CHECK git status
├─ Feature flags different?          → CHECK Cargo.toml
├─ Build script changed?             → CHECK build.rs
│
→ If all match: Cache is correct ✓
→ If mismatch: Invalidate and rebuild
```

---

## WEEK-BY-WEEK CHECKLIST

### Week 1: Merkle Tree
```
[ ] Day 1: Project setup + dependencies
[ ] Day 2-3: Implement blake3 + merkle.rs + tests
[ ] Day 4: Determinism validation (cross-platform)
[ ] Day 5: Documentation + review
→ Merge to main?
```

### Week 2: SQLite Store
```
[ ] Day 1-2: Schema + index + tests
[ ] Day 3: Hardlink/reflink/copy restoration
[ ] Day 4-5: Store operations + lifecycle tests
→ Merge to main?
```

### Week 3: RUSTC_WRAPPER
```
[ ] Day 1-2: Entry point + argument parsing
[ ] Day 3-4: E2E integration tests
[ ] Day 5: Performance benchmarking
→ Merge to main? (optional: use feature flag for early testers)
```

### Week 4: S3 Backend
```
[ ] Day 1-2: S3 integration + tests
[ ] Day 3-4: Async daemon + retry logic
[ ] Day 5: Integration + monitoring
→ Merge to main?
```

### Week 5: Nextest + Dashboard
```
[ ] Day 1-2: Nextest integration
[ ] Day 3-4: Web dashboard
[ ] Day 5: Full validation + performance targets
→ Release as v0.1.0?
```

---

## TESTING CHECKLIST (TDD)

### Unit Tests (Must Pass)
- [ ] Blake3 hash determinism (10K iterations)
- [ ] Merkle tree construction
- [ ] Merkle proof verification
- [ ] SQLite CRUD operations
- [ ] Hardlink/reflink/copy logic
- [ ] Argument parsing
- [ ] S3 upload/download
- [ ] Daemon queue management

### Integration Tests (Must Pass)
- [ ] Full cache hit/miss lifecycle
- [ ] E2E with `cargo build --release`
- [ ] Cross-filesystem fallback
- [ ] S3 integration end-to-end
- [ ] Nextest parallelization
- [ ] Dashboard API endpoints

### Performance Tests (Must Meet Targets)
- [ ] Hash computation: <100ms per crate
- [ ] SQLite lookup: <1ms per artifact
- [ ] Hardlink restore: <10µs
- [ ] Rebuild speedup: >70%
- [ ] Test execution speedup: >60%

---

## DEPLOYMENT CHECKLIST

### Pre-Production
- [ ] All tests passing (unit + integration + perf)
- [ ] Code review approved
- [ ] Clippy warnings fixed
- [ ] Zero false cache hits in 1000+ builds
- [ ] Performance targets validated
- [ ] Documentation complete
- [ ] S3 bucket created (if using remote)
- [ ] CI credentials configured

### Launch
- [ ] Binary built and signed
- [ ] Installer script created
- [ ] Rollout to dev team (opt-in)
- [ ] Gather feedback (1 week)
- [ ] Measure metrics (hit rate, speedup)
- [ ] Enable in CI (Week 2)
- [ ] Full team rollout (Week 3)

---

## USEFUL COMMANDS

```bash
# Build everything
cargo build --release -p siss-build-accelerator

# Run all tests
cargo test --lib
cargo test --all --release

# Bench hash speed
cargo bench --bench blake3_speed

# Check code quality
cargo clippy --all -- -D warnings
cargo fmt --all --check

# Profile a build
RUST_LOG=debug cargo build --release 2>&1 | grep siss

# SQLite inspection
sqlite3 ~/.cache/siss-build-accelerator/index.sqlite \
  "SELECT COUNT(*), SUM(artifact_size) FROM artifacts;"

# Monitor logs
tail -f ~/.cache/siss-build-accelerator/logs/access.log

# S3 sync test
aws s3 sync ~/.cache/siss-build-accelerator/store/ \
  s3://nexus-build-cache/artifacts/

# Kill daemon
pkill -f siss-build-accelerator.*daemon
```

---

**Quick Reference Prepared:** May 29, 2026
**For:** Week 1-5 implementation phase
**Keep nearby during:** Daily coding sessions

