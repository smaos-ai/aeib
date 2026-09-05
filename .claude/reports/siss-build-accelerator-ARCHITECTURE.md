# SISS Build Accelerator: System Architecture
## Visual Design & Component Interactions

---

## 1. SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                   SovereignNexus Cargo Workspace                │
│                                                                 │
│  9 Crates: siss-agent-shell, siss-cockpit, etc.                │
│  400+ Tests | 50+ Library Dependencies                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    $ cargo build --release
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ▼                                     ▼
  [Compilation]                        [Test Execution]
        │                                     │
        ├─ crate-1.rs                       ├─ unit tests
        ├─ crate-2.rs    ──────────┐        ├─ integration tests
        └─ crate-3.rs               │       └─ benchmarks
             │                      │
             └──── RUSTC_WRAPPER ──►│
                   (Hook)           │
                   │                │
    ┌──────────────▼────────────┐  │
    │ siss-build-accelerator    │  │
    │ (Cache Decision Engine)   │  │
    └──────────┬────────────────┘  │
               │                   │
      ┌────────┴──────────┐        │
      │                   │        │
      ▼                   ▼        ▼
   [Local]         [Remote]   [nextest]
   Cache           Cache        Plugin
   │               │            │
   ├─SQLite        ├─S3         └─ Process per test
   ├─Hardlinks     └─Async         Parallel execution
   └─Blake3            Daemon      (60% faster)
```

---

## 2. CACHE HIERARCHY

```
┌────────────────────────────────────────────────────────────────────┐
│                       Build Cache Levels                           │
└────────────────────────────────────────────────────────────────────┘

LEVEL 1: RUSTC_WRAPPER Input Hash
┌─────────────────────────────────────────────────────────────────┐
│ Input:                                                          │
│  • rustc --version (1.79.0-abc123...)                          │
│  • target triple (x86_64-apple-darwin)                         │
│  • crate name (siss-agent-shell)                               │
│  • source files (src/lib.rs, src/main.rs, ...)                │
│  • dependencies (tokio, serde, ...)                            │
│  • feature flags (--features "debug,tracing")                  │
│  • codegen flags (-C opt-level=3)                              │
│  • normalized paths ({HOME}/Projects/SovereignNexus)           │
│                                                                 │
│ Process: blake3_hash(all inputs)                              │
│                                                                 │
│ Output: compile_hash = "a1b2c3d4e5f6..." (64 char hex)       │
└─────────────────────────────────────────────────────────────────┘

LEVEL 2: Merkle Tree Construction (Optional Advanced)
┌─────────────────────────────────────────────────────────────────┐
│ Build Merkle DAG from source tree:                             │
│                                                                 │
│          ┌─────────────────────────┐                           │
│          │   Root Hash             │  (entire crate + deps)    │
│          └──────────┬──────────────┘                           │
│                     │                                           │
│         ┌───────────┴────────────┐                             │
│         │                        │                             │
│    ┌────▼─────┐           ┌─────▼─────┐                       │
│    │ src/     │           │ target/   │  (directory hashes)    │
│    └────┬─────┘           └─────┬─────┘                       │
│         │                       │                              │
│    ┌────▼────┐  ┌─────┐  ┌─────▼─┐                            │
│    │ lib.rs  │  │main │  │ Cargo │  (file hashes)             │
│    └────┬────┘  │.rs  │  │.toml  │                            │
│         │       └─────┘  └───────┘                            │
│    ┌────▼──────────────────────────────────┐                 │
│    │ blake3(lib.rs) = 0xaabbcc...          │  (leaf hash)    │
│    └───────────────────────────────────────┘                 │
│                                                                 │
│ Benefit: Partial cache hits when 1 file changes                │
└─────────────────────────────────────────────────────────────────┘

LEVEL 3: SQLite Index (Fast Lookup)
┌─────────────────────────────────────────────────────────────────┐
│ Table: artifacts                                               │
│ ┌──────────────┬─────────────────┬──────────┬─────────────┐  │
│ │compile_hash  │artifact_path    │rustc_ver │created_at   │  │
│ ├──────────────┼─────────────────┼──────────┼─────────────┤  │
│ │a1b2c3d4e5f6 │~/.cache/siss/.../lib.rlib│1.79.0   │2026-05-29│
│ │f6e5d4c3b2a1 │~/.cache/siss/.../lib.rmeta│1.79.0   │2026-05-29│
│ │...           │...              │...      │...          │  │
│ └──────────────┴─────────────────┴──────────┴─────────────┘  │
│                                                                 │
│ Query: SELECT artifact_path FROM artifacts WHERE              │
│        compile_hash = 'a1b2c3d4e5f6'                          │
│                                                                 │
│ Speed: <1ms lookup for 10K artifacts                          │
└─────────────────────────────────────────────────────────────────┘

LEVEL 4: Content-Addressed Blob Store
┌─────────────────────────────────────────────────────────────────┐
│ ~/.cache/siss-build-accelerator/store/                          │
│ ├── a1b2c3d4e5f6abc123.../                                    │
│ │   ├── lib.rlib         (hardlinked from multiple targets)   │
│ │   ├── lib.rmeta        (read-only)                          │
│ │   └── metadata.json    { hash: "...", rustc_ver: "..." }    │
│ ├── f6e5d4c3b2a1def456.../                                    │
│ │   └── ...                                                    │
│ └── merkle_proofs/                  (optional)                 │
│     ├── proof_a1b2c3.json                                      │
│     └── proof_f6e5d4.json                                      │
│                                                                 │
│ Key point: One copy per unique hash; hardlinks to multiple    │
│ target/ directories. Zero disk duplication.                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. WRAPPER FLOW & DECISION TREE

```
┌─────────────────────────────────────────────────────────────┐
│            RUSTC_WRAPPER Execution Flow                     │
└─────────────────────────────────────────────────────────────┘

Entry: siss-build-accelerator <rustc_path> <rustc_args>
                 │
                 ▼
        ┌────────────────────┐
        │ Parse rustc args   │
        │ (crate name, flags)│
        └────────┬───────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │ Compute input hash   │
        │ (blake3)             │
        └────────┬─────────────┘
                 │
                 ▼
        ┌──────────────────────┐
        │ Validate rustc ver   │
        │ match cache version? │
        └────────┬─────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼ NO                      ▼ YES
┌─────────────┐         ┌─────────────────┐
│ Query SQLite│         │ Query SQLite    │
│ "NOT found" │         │ Lookup hash     │
│             │         │                 │
│ ↓           │         └────────┬────────┘
│ Run rustc   │                  │
│ (actual)    │         ┌────────┴──────────┐
│             │         │                   │
│             │         ▼ FOUND             ▼ NOT FOUND
│             │    ┌─────────────┐     ┌────────────┐
│             │    │ Restore via:│     │ Run rustc  │
│             │    │ 1. reflink  │     │ (actual)   │
│             │    │ 2. hardlink │     │            │
│             │    │ 3. copy     │     └──────┬─────┘
│             │    │             │            │
│             │    │ ↓ Success   │     ┌──────▼───────┐
│             │    │ Exit 0      │     │ Store result │
│             │    │ (cache hit!)│     │ in cache     │
│             │    └─────────────┘     │              │
│             │                        └──────┬───────┘
│             │                              │
└─────────────┤──────────────────────────────┤
              │                              │
              ▼ (continue if error)          ▼
        ┌──────────────┐           ┌──────────────────┐
        │ Verify exit  │           │ Update SQLite    │
        │ status       │           │ index            │
        └──────┬───────┘           └──────┬───────────┘
               │                          │
               └──────────┬───────────────┘
                          │
                          ▼
                   ┌────────────────────┐
                   │ Queue S3 upload    │
                   │ (async daemon)     │
                   │ [non-blocking]     │
                   └────────┬───────────┘
                            │
                            ▼
                    ┌────────────────────┐
                    │ Return exit status │
                    │ to Cargo           │
                    └────────────────────┘
```

---

## 4. LOCAL CACHE ARCHITECTURE

```
┌────────────────────────────────────────────────────────────────┐
│           ~/.cache/siss-build-accelerator/                     │
└────────────────────────────────────────────────────────────────┘

Directory Structure:
├── index.sqlite                    (Fast lookup)
│   └── Columns: compile_hash | artifact_path | rustc_ver
│
├── store/                          (Content-addressed blob store)
│   ├── a1b2c3d4e5f6.../
│   │   ├── lib.rlib               ← Hardlinked/reflinked from target/
│   │   ├── lib.rmeta
│   │   ├── lib.so
│   │   └── metadata.json          { hash, rustc_ver, timestamp }
│   │
│   ├── f6e5d4c3b2a1.../
│   │   └── [similar structure]
│   │
│   └── merkle_proofs/             (Optional: for audit trail)
│       ├── proof_a1b2c3d4.json    (Merkle tree structure)
│       └── proof_f6e5d4c3.json
│
├── daemon.pid                      (Background uploader PID)
├── config.toml                     (Cache settings)
└── logs/
    ├── access.log                  (Hit/miss events)
    └── sync.log                    (S3 upload status)

Disk Usage Example (SovereignNexus):
├── store/: 3.2 GB (4,200 unique artifacts)
├── index.sqlite: 8 MB (query index)
└── Total: 3.2 GB (vs. 12 GB without deduplication)

Retention Policy:
├── Cache TTL: 30 days (auto-cleanup)
├── Size limit: 10 GB (LRU eviction)
└── Last-access tracking: For LRU sorting
```

---

## 5. DISTRIBUTED CACHE (S3) ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────┐
│              S3 Backend Sync (Optional)                      │
└──────────────────────────────────────────────────────────────┘

S3 Bucket Structure: s3://nexus-build-cache/

├── artifacts/                      (Compiled rlib/rmeta files)
│   ├── {compile_hash_prefix}/
│   │   ├── lib.rlib
│   │   ├── lib.rmeta
│   │   └── metadata.json
│   │
│   └── [4000+ artifacts]
│
├── merkle_proofs/                  (Proof serialization for audit)
│   ├── proof_{hash}.json
│   └── [batched proofs]
│
└── index/                          (Optional: SQLite snapshot)
    └── artifacts.sqlite.gz

Cache Sync Flow:

Local Build (Developer)
         │
         ▼
   Store in SQLite + local blob
         │
         ├─ Queue async upload ────→ [S3 daemon]
         │                                │
         │                                ▼
         │                         Put to S3 (100-300ms)
         │                                │
         ▼                                ▼
   Return to Cargo            Update S3 index
         │
         ├──────── Next build on CI ─────→
                      │
                      ▼
                Check local cache
                      │
              (miss)  ▼ (hit)
                │        └─ Restore
                │            Return
                ▼
         Check S3 cache (5s network RTT)
                │
         (hit)  ▼ (miss)
          │      └─ Download
          │      │  Restore
          ▼      │
         Compile │
              │  │
              └──┴─ Store locally

Performance:
├── Local cache hit: <10µs
├── Local cache miss + S3 hit: ~1s (download) + 10µs (restore)
├── S3 miss (compile): ~120s (clean build)
└── CI improvement: 5m 30s → 40s (cold), 120s → 35s (incremental)
```

---

## 6. NEXTEST INTEGRATION

```
┌──────────────────────────────────────────────────────┐
│  Test Execution Pipeline (cargo-nextest)            │
└──────────────────────────────────────────────────────┘

Standard Cargo Test:
┌─────────────────────────────────────────┐
│ cargo test                              │
│                                         │
│ 1. Compile all test binaries (serial)  │ 180s
│ 2. Run tests (sequential threads)      │ 150s
│ 3. Collect results                     │ 10s
│                                         │
│ Total: 340s (no parallelism between    │
│        test binaries)                   │
└─────────────────────────────────────────┘
         ▼
    BOTTLENECK: One slow test blocks all others

cargo-nextest with RUSTC_WRAPPER:
┌─────────────────────────────────────────┐
│ cargo build --tests (RUSTC_WRAPPER)    │ 60s (cache!)
│ cargo nextest run --retries 2           │ 60s (parallel)
│ Collect results (per-process)           │ 5s
│                                         │
│ Total: 125s (60% faster!)               │
├─────────────────────────────────────────┤
│ Optimization:                           │
│ • Test binaries compiled via cache      │
│ • 400+ tests run in parallel            │
│ • One process per test = true isolation │
│ • Automatic flaky test retry (2x)       │
└─────────────────────────────────────────┘

Timeline (400 tests, 8-core machine):
Time  CPU 0    CPU 1   CPU 2   ... CPU 7
 0s   test_1   test_2  test_3  ... test_8
10s   test_9   test_10 test_11 ... test_16
20s   test_17  test_18 test_19 ... test_24
...
60s   ✓ All tests complete
     (vs. 150s with serial cargo test)
```

---

## 7. MONITORING DASHBOARD

```
┌──────────────────────────────────────────────────────────────┐
│        http://localhost:9090/build-cache-monitor            │
└──────────────────────────────────────────────────────────────┘

Dashboard Layout:

┌─────────────────────────────────────────────────────────────┐
│ SISS Build Accelerator Monitor                     [Refresh] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ CACHE STATISTICS ─────────────────┐                   │
│  │                                    │                   │
│  │ Hit Rate:        68.2%             │                   │
│  │ Total Artifacts: 4,287             │                   │
│  │ Cache Size:      3.2 GB            │                   │
│  │ Last Cleanup:    2 hours ago       │                   │
│  │ S3 Bandwidth:    42 MB/s ↑         │                   │
│  │                                    │                   │
│  └────────────────────────────────────┘                   │
│                                                             │
│  ┌─ RECENT CACHE HITS ────────────────┐                   │
│  │                                    │                   │
│  │ [████████████░░░░░] 68%            │                   │
│  │                                    │                   │
│  │ Last 1h:   42 hits, 18 misses      │                   │
│  │ Last 24h: 310 hits, 145 misses     │                   │
│  │ All time:  8920 hits, 4180 misses  │                   │
│  │                                    │                   │
│  └────────────────────────────────────┘                   │
│                                                             │
│  ┌─ BUILD PERFORMANCE ────────────────┐                   │
│  │                                    │                   │
│  │ Compilation:  12s (cache helps)    │                   │
│  │ ├─ Cached:    8 crates (1s)        │                   │
│  │ └─ Fresh:     1 crate (11s)        │                   │
│  │                                    │                   │
│  │ Tests:        45s (nextest)        │                   │
│  │ ├─ Parallel:  400 tests/60s        │                   │
│  │ └─ vs cargo:  ~150s (3x slower)    │                   │
│  │                                    │                   │
│  │ Total CI:     2m 17s               │                   │
│  │ (Previous:    5m 30s, 58% faster)  │                   │
│  │                                    │                   │
│  └────────────────────────────────────┘                   │
│                                                             │
│  ┌─ S3 SYNC STATUS ───────────────────┐                   │
│  │                                    │                   │
│  │ Remote Artifacts: 2,340            │                   │
│  │ Last Sync:       15 mins ago       │                   │
│  │ Upload Queue:    3 pending         │                   │
│  │ Sync Error Rate: 0.1%              │                   │
│  │                                    │                   │
│  └────────────────────────────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Real-time event feed (below dashboard):
[2026-05-29 14:32:10] HIT: siss-agent-shell (cache_key: a1b2c3...)
[2026-05-29 14:32:11] HIT: siss-cockpit (cache_key: f6e5d4...)
[2026-05-29 14:32:15] MISS: siss-context-cartography (recompile)
[2026-05-29 14:32:42] S3 UPLOAD: 1.2 MB in 890ms (siss-cockpit)
```

---

## 8. FAILURE MODES & DETECTION

```
┌──────────────────────────────────────────────────────────────┐
│        Failure Mode Analysis & Recovery                      │
└──────────────────────────────────────────────────────────────┘

Failure Mode 1: Hash Collision (Blake3 Collision)
┌─────────────────────────────────────────────────────────┐
│ Symptom: Cache hit, but artifact doesn't match input    │
│                                                         │
│ Detection:                                              │
│  1. Re-hash input files                                │
│  2. Compare with cache key                             │
│  3. Verify artifact metadata signature                 │
│                                                         │
│ Recovery:                                              │
│  • Log collision (potential attack or bug)             │
│  • Invalidate cache entry                              │
│  • Force recompilation                                 │
│  • Alert developer (log warning)                       │
│                                                         │
│ Probability: <1:2^90 (virtually impossible)            │
└─────────────────────────────────────────────────────────┘

Failure Mode 2: Hardlink Across Filesystems
┌─────────────────────────────────────────────────────────┐
│ Symptom: Hardlink fails, fallback to slower copy        │
│                                                         │
│ Detection:                                              │
│  • hardlink() returns EEXDEV (cross-device)            │
│  • Automatically retry with copy                       │
│                                                         │
│ Recovery:                                              │
│  1. Try reflink (APFS/Btrfs) → fastest                 │
│  2. Try hardlink (same filesystem) → fast              │
│  3. Fallback to copy → slower but safe                 │
│                                                         │
│ Mitigation:                                            │
│  • Warn user if cache on different volume             │
│  • Suggest: move cache to same volume                 │
│                                                         │
│ Performance impact: 10µs → 1ms (100x slower)          │
└─────────────────────────────────────────────────────────┘

Failure Mode 3: Rustc ABI Mismatch (CI vs Local)
┌─────────────────────────────────────────────────────────┐
│ Symptom: Build succeeds locally, fails in CI            │
│                                                         │
│ Root Cause:                                             │
│  • Local rustc 1.79.0-abc123                           │
│  • CI rustc 1.79.0-def456 (different commit)           │
│  • ABI-incompatible outputs, cache hit returns wrong   │
│                                                         │
│ Detection:                                              │
│  • Include full rustc version in cache key             │
│  • Validate hash includes commit hash                  │
│                                                         │
│ Recovery:                                              │
│  • CI detects version mismatch                         │
│  • Invalidates cache for that rustc version            │
│  • Forces recompilation                                │
│                                                         │
│ Prevention:                                            │
│  • Pin rustc version in CI (rust-toolchain.toml)      │
│  • Same version on all machines                        │
└─────────────────────────────────────────────────────────┘

Failure Mode 4: S3 Unavailability
┌─────────────────────────────────────────────────────────┐
│ Symptom: S3 upload fails, but build continues          │
│                                                         │
│ Behavior:                                              │
│  • Local build unaffected (local cache works)          │
│  • S3 daemon retries async                             │
│  • Other machines can't access remote cache            │
│                                                         │
│ Recovery:                                              │
│  • Queue artifacts locally (up to 1000)                │
│  • Retry uploads when S3 recovers                      │
│  • Log failed uploads for investigation                │
│                                                         │
│ Impact: Zero for local dev, degraded for team share    │
└─────────────────────────────────────────────────────────┘

Failure Mode 5: Cache Corruption (stale SQLite index)
┌─────────────────────────────────────────────────────────┐
│ Symptom: SQLite query returns wrong artifact path       │
│                                                         │
│ Root Cause:                                             │
│  • Power loss during write → corrupt .sqlite file      │
│  • Missing transaction journal                         │
│                                                         │
│ Detection:                                              │
│  • Artifact file doesn't exist at path                 │
│  • Checksum mismatch on restore                        │
│                                                         │
│ Recovery:                                              │
│  • Use SQLite WAL mode (write-ahead logging)           │
│  • Atomic transactions for all writes                  │
│  • On corruption: rebuild index from store/            │
│                                                         │
│ Impact: High → Mitigated by WAL mode                   │
└─────────────────────────────────────────────────────────┘
```

---

## 9. INTEGRATION POINTS

```
┌──────────────────────────────────────────────────────────────┐
│     How siss-build-accelerator Integrates with CI/CD        │
└──────────────────────────────────────────────────────────────┘

GitHub Actions Integration:

steps:
  - uses: actions/checkout@v4
  
  - uses: dtolnay/rust-toolchain@stable
    with:
      toolchain: 1.79.0        # Pin exact version
  
  - name: Setup build cache
    uses: siss-build-accelerator/setup@v1
    with:
      cache-dir: /tmp/siss-cache
      s3-bucket: s3://nexus-build-cache
      s3-region: eu-west-1
  
  - name: Build
    run: cargo build --release
    env:
      RUSTC_WRAPPER: siss-build-accelerator
      CARGO_INCREMENTAL: "0"      # Cache replaces incremental
  
  - name: Run tests
    run: cargo nextest run --retries 2

Cache Artifacts (uploaded at end of job):
├── /tmp/siss-cache/store/       → S3 artifacts/
├── /tmp/siss-cache/index.sqlite → S3 index/ (optional)
└── Async daemon handles upload automatically

Cost Analysis:
├── Without cache:  5m 30s × $0.008/min = $0.044 per run
├── With cache:     2m 17s × $0.008/min = $0.018 per run
│
├── S3 cost:        3 GB × 100 runs = 300 GB storage/month
│                   = 300 GB × $0.023 = $6.90/month
│                   + requests (negligible)
│
├── Savings:        $0.044 - $0.018 = $0.026 per run
│                   × 100 runs/month = $2.60/month
│
└── ROI: Pay $6.90 S3 storage, save $2.60 CI cost
         (net cost, but faster CI → faster iteration)
```

---

## 10. COMPARISON MATRIX

```
┌──────────────────────────────────────────────────────────────┐
│     siss-build-accelerator vs. Alternatives                 │
└──────────────────────────────────────────────────────────────┘

                     │ Cargo   │ sccache │ kache  │ SISS
                     │ Default │ (Mozilla)│ (Kunobi) │
─────────────────────┼─────────┼─────────┼────────┼──────────
Caching Scope        │ Local   │ Compiler│ Library│ Library
                     │ only    │ output  │ only   │ + Tests
─────────────────────┼─────────┼─────────┼────────┼──────────
Hit Rate             │ ~40%*   │ ~50%    │ ~65%   │ ~70%
(incremental rebuild)│         │         │        │
─────────────────────┼─────────┼─────────┼────────┼──────────
Rebuild Speed        │ 1min    │ 45s     │ 35s    │ 35s
(100 files changed)  │         │         │        │
─────────────────────┼─────────┼─────────┼────────┼──────────
Test Execution       │ 150s    │ 150s    │ 150s   │ 60s
(400 tests)          │ (serial)│ (serial)│ (serial)│ (nextest)
─────────────────────┼─────────┼─────────┼────────┼──────────
Remote Backend       │ N/A     │ S3, Redis│ S3 opt │ S3 + async
─────────────────────┼─────────┼─────────┼────────┼──────────
Hardlink Support     │ N/A     │ No      │ Yes    │ Yes (CoW)
─────────────────────┼─────────┼─────────┼────────┼──────────
SQLite Index         │ N/A     │ No      │ Yes    │ Yes (<1ms)
─────────────────────┼─────────┼─────────┼────────┼──────────
Merkle Tree Proofs   │ N/A     │ No      │ No     │ Yes (audit)
─────────────────────┼─────────┼─────────┼────────┼──────────
Configuration Effort │ 0 min   │ 5 min   │ 5 min  │ 3 min
─────────────────────┼─────────┼─────────┼────────┼──────────
Maintenance Burden   │ None    │ Medium  │ Low    │ Medium
(Mozilla-maintained) │         │ (no doc)│ (active)│ (custom)

* Cargo's incremental compilation is not a true cache;
  artifacts are version-dependent and not portable.
```

---

## KEY DESIGN PRINCIPLES

1. **Zero-copy by default** (hardlink/reflink)
2. **Deterministic hashing** (blake3 across all platforms)
3. **Fast lookup** (SQLite index, <1ms queries)
4. **Async remote sync** (non-blocking, queue-based)
5. **Graceful degradation** (fallback to copy, skip S3 on error)
6. **Collision detection** (verify on every restore)
7. **No rustc source changes** (pure RUSTC_WRAPPER)
8. **Opt-in adoption** (can disable with --no-cache)

---

**Diagram prepared:** May 29, 2026
**Ready for:** Week 1 Merkle tree + blake3 implementation
