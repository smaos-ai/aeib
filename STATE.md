# 🧭 Execution State (Auto-Resumable) + Immutable Ledger

## Last Checkpoint
- **Commit:** `fe8a3b6` Phase 45 RED: GitNexus Structural Awareness & LadybugDB - fail-closed invariants
- **Ledger Hash:** `a9f1e8c7d3b2a4f6`…
- **Timestamp:** 2026-05-21T14:45:00Z
- **Phase:** `Phase 45 RED`
- **Tests:** 16 passing (6 unit + 10 integration)
- **Next Step:** Await GREEN phase authorization for implement handlers (Blast Radius, Skill Gen, Pre-Commit, Hybrid Search)

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
