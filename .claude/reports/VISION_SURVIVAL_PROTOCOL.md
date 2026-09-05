# Vision Survival Protocol — Night Shift Vault Sync

## Overview

The **Vision Survival Protocol** is an automated nightly sync module that ensures the SISS vision survives hardware failure by distributing workspace deltas to three encrypted vaults (A, B, C).

## Purpose

Every night at 3 AM (via crontab), the protocol:

1. **Detects mounted encrypted vaults** — scans `/Volumes` for SMAOS_VAULT_A/B/C
2. **Computes workspace checksum** — SHA-256 hash of entire workspace (excluding .git, target, node_modules)
3. **Calculates delta** — identifies files changed since last sync using `git diff`
4. **Identifies critical changes** — flags Genesis Capsule, private keys, patent docs for immediate physical rotation
5. **Syncs to all three vaults** — rsync-based delta sync to maintain efficiency
6. **Verifies vault integrity** — spot-checks for key files in synced vault
7. **Updates manifest** — records sync timestamp, checksum, status, and critical flags in VAULT_MANIFEST.json

## Module Structure

### Core Types

**`VisionSurvivalProtocol`** — Main orchestrator struct
- `detect_vaults()` — Scans for mounted USB drives
- `compute_workspace_checksum()` — SHA-256 hash of workspace tree
- `compute_delta()` — Git-based file diff calculation
- `detect_critical_changes()` — Identifies Genesis/secret/patent files
- `sync_to_vault()` — Rsync-based sync operation
- `verify_vault()` — Integrity check (spot-checks key files)
- `update_manifest()` — Updates VAULT_MANIFEST.json
- `execute()` — Runs full protocol (entry point)

**`SyncCapsule`** — Immutable result record
```rust
pub struct SyncCapsule {
    pub sync_id: Uuid,                      // Unique sync ID
    pub timestamp: DateTime<Utc>,           // Sync timestamp
    pub vault_location: char,               // Primary vault (A, B, or C)
    pub delta_size_bytes: u64,              // Number of files changed
    pub workspace_checksum: String,         // SHA-256 workspace hash
    pub critical_changes: Vec<String>,      // Critical files that changed
    pub status: SyncStatus,                 // Success / PartialSuccess / Failed
}
```

**`SyncStatus`** — Enum for sync outcome
```rust
pub enum SyncStatus {
    Success,
    PartialSuccess { failed_vaults: Vec<char> },
    Failed { reason: String },
}
```

## Usage

### Binary Invocation

```bash
# Manual execution (for testing or on-demand)
cargo run -p siss-night-cycle --bin vision_survival_protocol --release

# With custom workspace path
export SISS_WORKSPACE=/path/to/workspace
cargo run -p siss-night-cycle --bin vision_survival_protocol --release
```

### Crontab Setup

Add to crontab for automatic nightly execution:

```bash
crontab -e
```

Then add this line:

```cron
0 3 * * * /Users/andriileukhin/Documents/SovereignNexus/.claude/scripts/cron_vision_survival.sh
```

This runs the protocol every day at 3:00 AM.

### Monitoring

Check the log file for execution results:

```bash
tail -f ~/.claude/logs/vision_survival.log
```

## Vault Detection Algorithm

The protocol detects vaults by:

1. Scanning `/Volumes` directory
2. Matching vault names: `SMAOS_VAULT_A`, `SMAOS_VAULT_B`, `SMAOS_VAULT_C`
3. Storing mount paths for sync operations

If no vaults are detected, the protocol fails with an error message prompting the user to mount drives.

## Delta Computation

**Method:** Git-based (`git diff --name-only HEAD`)

**Logic:**
- If workspace checksum matches last sync → no delta
- If workspace checksum differs → run `git diff` to find changed files
- Returns list of changed file paths

## Critical Changes Detection

Files containing these patterns are flagged for immediate physical rotation:

- `Genesis`
- `private_key`
- `secret_key`
- `LAYER14`
- `Trust`
- `patent`
- `VAULT_MANIFEST`
- `encryption`
- `authentication`

When critical changes are detected, the user is alerted:
```
⚠️  CRITICAL CHANGES DETECTED:
   - docs/Genesis_Capsule.md
   → Rotate Vault B or C within 72 hours to maintain geopolitical resilience.
```

## Sync Process

**Method:** `rsync` with safe options

```bash
rsync -av --delete \
  --exclude=.git \
  --exclude=target \
  --exclude=node_modules \
  <workspace>/ \
  <vault>/smaos/
```

**Key options:**
- `-av` — archive mode with verbose output
- `--delete` — remove files in vault that don't exist in workspace
- Exclusions prevent syncing build artifacts, dependencies, git metadata

**Verification:**
- Checks that key files exist in vault after sync (Cargo.toml, CLAUDE.md)
- Returns size in bytes of synced content

## Manifest Update

After each sync, the protocol updates `VAULT_MANIFEST.json` in each vault:

```json
{
  "last_sync": "2026-05-29T03:00:00Z",
  "last_checksum": "abc123def456...",
  "sync_status": "Success",
  "sync_id": "550e8400-e29b-41d4-a716-446655440000",
  "delta_files": 42,
  "critical_changes": ["docs/Genesis_Capsule.md"]
}
```

## Testing

Four unit tests ensure correctness:

```bash
cargo test -p siss-night-cycle --lib vision_survival_protocol
```

**Tests:**
1. `test_vision_survival_protocol_init` — Struct initialization
2. `test_detect_critical_changes` — Critical file detection
3. `test_sync_capsule_serialization` — JSON serialization
4. `test_hash_directory_excludes_patterns` — Exclusion logic

All tests pass with no warnings.

## Dependencies

- `tokio` — async runtime (from workspace)
- `chrono` — timestamps (from workspace)
- `uuid` — unique sync IDs (from workspace)
- `serde` / `serde_json` — serialization (from workspace)
- `sha2` — SHA-256 hashing (from workspace)

All dependencies are already in the workspace `Cargo.toml`.

## Architecture Notes

**Async/await:** The main `execute()` function is async for future integration with network-based vaults (S3, cloud storage).

**Immutable capsule:** `SyncCapsule` is immutable after creation — prevents silent failures or partial logging.

**Vault independence:** Protocol treats each vault as independent. If Vault B fails, Vaults A and C still sync successfully.

**Error handling:** Uses `Result<T, String>` for simple propagation. Vault failures are logged but don't halt the entire protocol.

## Integration Checklist

- [x] Module created: `crates/siss-night-cycle/src/vision_survival_protocol.rs`
- [x] Exported in lib.rs: `pub mod vision_survival_protocol`
- [x] Binary created: `crates/siss-night-cycle/src/bin/vision_survival_protocol.rs`
- [x] Cron script created: `.claude/scripts/cron_vision_survival.sh`
- [x] Dependencies added: `uuid`, `sha2`
- [x] Tests written and passing: 4/4
- [x] Compilation verified: `cargo check`, `cargo build --release`
- [x] Clippy clean: No warnings

## Deployment

1. **Schedule the cron job:**
   ```bash
   crontab -e
   0 3 * * * /Users/andriileukhin/Documents/SovereignNexus/.claude/scripts/cron_vision_survival.sh
   ```

2. **Prepare vaults** (one-time):
   - Mount USB drives as SMAOS_VAULT_A, SMAOS_VAULT_B, SMAOS_VAULT_C
   - Create VAULT_MANIFEST.json in each vault root

3. **Test execution:**
   ```bash
   SISS_WORKSPACE=/Users/andriileukhin/Documents/SovereignNexus \
   cargo run -p siss-night-cycle --bin vision_survival_protocol --release
   ```

4. **Monitor logs:**
   ```bash
   tail -f ~/.claude/logs/vision_survival.log
   ```

## Future Enhancements

- **Cloud vaults:** Add S3/Cloud Storage support alongside USB
- **Notification system:** Send Slack/email alerts on critical changes
- **Encrypted sync:** Add LUKS/encryption layer for cloud sync
- **Incremental backup:** Track per-file sync status
- **Geopolitical distribution:** Assign vaults to physical locations with metadata

---

**Status:** Production-ready  
**Last Updated:** 2026-05-29  
**Deadline:** Tonight (ready for cron setup)
