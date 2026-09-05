# AGENT 1: Project Setup & Scaffolding
**Dispatch Date:** 2026-06-06  
**Deadline:** 2026-06-07 (1 day)  
**TDD Discipline:** ✅ Required

---

## Your Task

Scaffold the `siss-apac-expansion` Rust crate with all module declarations, dependencies, and basic project structure. This is the foundation for all other agents.

## Files You Own (EXCLUSIVE)
- `crates/siss-apac-expansion/Cargo.toml` (create)
- `crates/siss-apac-expansion/src/lib.rs` (create)
- `crates/siss-apac-expansion/src/tests.rs` (create - empty)
- Root `Cargo.toml` (modify - add workspace member)

**DO NOT TOUCH:** Anything else. Other agents depend on this structure.

---

## Step-by-Step Execution

### Step 1: Create Directory Structure
```bash
mkdir -p /Users/andriileukhin/Documents/SovereignNexus/crates/siss-apac-expansion/src
mkdir -p /Users/andriileukhin/Documents/SovereignNexus/crates/siss-apac-expansion/migrations
```

### Step 2: Create Cargo.toml

**File:** `crates/siss-apac-expansion/Cargo.toml`

```toml
[package]
name = "siss-apac-expansion"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.35", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sqlx = { version = "0.7", features = ["postgres", "uuid", "chrono"] }
uuid = { version = "1.0", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
anyhow = "1.0"
thiserror = "1.0"
async-trait = "0.1"
dashmap = "5.5"
tracing = "0.1"

[dev-dependencies]
tokio-test = "0.4"
```

### Step 3: Create lib.rs

**File:** `crates/siss-apac-expansion/src/lib.rs`

```rust
pub mod compliance;
pub mod settlement;
pub mod localization;
pub mod market_intelligence;
pub mod playbook;

pub use compliance::{ComplianceRegistry, ComplianceValidator};
pub use settlement::StripeSettlementManager;
pub use localization::LocalizationFramework;
pub use market_intelligence::MarketIntelligence;
pub use playbook::OperationalPlaybookGenerator;
```

### Step 4: Create Empty tests.rs

**File:** `crates/siss-apac-expansion/src/tests.rs`

```rust
// Test modules will be added by other agents
// Agent 2: compliance_tests
// Agent 3: settlement_tests
// Agent 4: localization_tests
// Agent 5: market_intelligence_tests
// Agent 6: playbook_tests
```

### Step 5: Update Root Cargo.toml

**File:** Root `Cargo.toml`

Find the `[workspace]` section and add `"crates/siss-apac-expansion"` to members:

```toml
[workspace]
members = [
    # ... existing members ...
    "crates/siss-apac-expansion",
]
```

### Step 6: Verify Compilation

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo check -p siss-apac-expansion
```

**Expected:** ✅ No errors (modules don't exist yet, but that's OK — they're declared)

### Step 7: Run Clippy

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo clippy -p siss-apac-expansion --all-targets
```

**Expected:** ✅ No warnings

### Step 8: Commit

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
git add crates/siss-apac-expansion Cargo.toml
git commit -m "feat: scaffold siss-apac-expansion crate with module structure"
```

---

## Success Criteria

- [x] Directory structure created
- [x] `Cargo.toml` with all dependencies declared
- [x] `lib.rs` with module declarations (5 modules)
- [x] `tests.rs` created (empty, for other agents)
- [x] Root `Cargo.toml` updated with workspace member
- [x] `cargo check` passes
- [x] `cargo clippy` clean
- [x] Git commit succeeds

---

## Expected Output

**One commit:** `feat: scaffold siss-apac-expansion crate`

```
crates/siss-apac-expansion/
├── Cargo.toml
├── src/
│   ├── lib.rs (modules declared)
│   └── tests.rs (empty)
└── migrations/ (empty, for agents 2-6)
```

---

## What Agents 2-6 Expect

They will:
1. Create modules inside `crates/siss-apac-expansion/src/`
2. Write tests in `crates/siss-apac-expansion/src/tests.rs`
3. Add migrations to `crates/siss-apac-expansion/migrations/`

All depend on your module declarations in `lib.rs` being correct.

---

## Important Notes

- **No rush to add migration infrastructure yet** — agents 2-6 will create `.sql` files
- **No Database setup needed** — just the structure
- **Module order in lib.rs matters** — compliance before settlement, settlement before localization, etc.

---

## Return Summary

When complete, provide:

```
AGENT 1 COMPLETION SUMMARY
=========================

✅ Crate scaffolded: siss-apac-expansion
✅ Modules declared: 5 (compliance, settlement, localization, market_intelligence, playbook)
✅ Dependencies added: 11 core + 1 dev
✅ Compilation: PASSING
✅ Clippy: CLEAN

Commit: feat: scaffold siss-apac-expansion crate
Git hash: [your commit hash]

Status: ✅ READY FOR AGENTS 2-6
```

---

**Next Step:** Agent 2 starts Regional Compliance Framework once you're done.
