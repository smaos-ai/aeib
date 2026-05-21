# 🧭 Execution State (Auto-Resumable) + Immutable Ledger

## Last Checkpoint
- **Commit:** `31b94bf`
- **Ledger Hash:** `576cbf296cdfcc35`…
- **Timestamp:** 2026-05-21T01:50:58Z
- **Phase:** `phase-26-task-1(green)`
- **Tests:** false
- **Next Step:** (Edit before closing)

## Active Constraints
- Protocol v2 (diff-only, @file scoping, cargo test -q)
- TDD mandatory (tests first, implementation second)
- CLAUDE.md Correctness Doctrine (Plan Mode for multi-file)
- GitNexus impact analysis required before editing any symbol
- Test suite must pass 100% before commit

## Ledger System
- **EXEC_LOG.json:** Append-only Merkle chain of all phases (diff hashes, test results, timestamps)
- **Replay CLI:** `claude-replay.sh <commit_or_index>` — deterministically restores and verifies historical state
- **Cryptographic Verification:** Every commit hash-linked, test-gated, immutable

## Session Resume Checklist
1. Read STATE.md FIRST (includes ledger hash)
2. Check EXEC_LOG.json for full causal chain
3. Use `claude-replay.sh <index>` to restore historical phase if needed
4. Apply Protocol v2: diff-only, @file scoping, cargo test -q
5. Run `cargo test -q` before proposing completion
6. Commit triggers auto-update of ledger + STATE.md

## Cached Artifacts
- @docs/architecture/ — full system design
- @EXEC_LOG.json — immutable execution ledger
- @.claude/skills/ — specialized execution packs
- @docs/wiki/ — semantic memory
