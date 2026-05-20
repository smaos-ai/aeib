#!/bin/bash
# Phase 32 Wave 2 — parallel dispatch (file-orthogonal)
# Prereq: docs/notebook-cache/ committed (4 artifacts)
# Prereq: Wave 1 Task 1 merged on main (aed62d2+)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CACHE_DIR="docs/notebook-cache"
REQUIRED=(
  dependency_a2ui.md
  error_a2ui.md
  contract_a2ui.md
  state_a2ui.md
)

echo "=== Gate: notebook-cache ==="
for f in "${REQUIRED[@]}"; do
  [[ -f "$CACHE_DIR/$f" ]] || { echo "MISSING: $CACHE_DIR/$f"; exit 1; }
done
echo "OK: 4 cache artifacts present"

echo ""
echo "=== Gate: worktrees (create if missing) ==="
WT_BASE=".claude/worktrees"
mkdir -p "$WT_BASE"

add_worktree() {
  local name="$1" branch="$2"
  local path="$WT_BASE/$name"
  if git worktree list | grep -qF "[$branch]"; then
    echo "EXISTS: $name ($branch)"
  else
    echo "ADD: $name -> $branch"
    git worktree add "$path" -b "$branch"
  fi
}

add_worktree task1-a2ui-forms   worktree-task1-a2ui-forms
add_worktree task2-a2ui-display worktree-task2-a2ui-display
add_worktree task3-a2ui-validator worktree-task3-a2ui-validator

INIT=".claude/WAVE_2_INITIALIZATION.md"
[[ -f "$INIT" ]] || { echo "MISSING: $INIT"; exit 1; }

echo ""
echo "=== Dispatch 3 agents (native terminal, one at a time if API rate-limited) ==="
echo "Copy each block into a separate terminal, or run all three in background."

# Agent 1 — Forms handler (cockpit)
claude -p "Read @.claude/WAVE_2_INITIALIZATION.md @HANDOFF-PHASE32.md @docs/notebook-cache/contract_a2ui.md. WAVE 2 TASK: task1-a2ui-forms. Own ONLY crates/siss-cockpit/src/a2ui/form_handler.rs (+ mod.rs wiring). Exit: cargo check -p siss-cockpit. Commit in worktree; do NOT merge." \
  --worktree task1-a2ui-forms &

# Agent 2 — Cockpit renderer (priority merge first)
claude -p "Read @.claude/WAVE_2_INITIALIZATION.md @HANDOFF-PHASE32.md @docs/notebook-cache/contract_a2ui.md. WAVE 2 TASK: task2-a2ui-display. Own ONLY crates/siss-cockpit/src/a2ui/renderer.rs and related handler wiring per HANDOFF Task 3. Exit: cargo check -p siss-cockpit. Commit in worktree; do NOT merge." \
  --worktree task2-a2ui-display &

# Agent 3 — Agent-side validator
claude -p "Read @.claude/WAVE_2_INITIALIZATION.md @HANDOFF-PHASE32.md @docs/notebook-cache/error_a2ui.md. WAVE 2 TASK: task3-a2ui-validator. Own ONLY crates/siss-agent-shell/src/a2ui/validator.rs. Exit: cargo check -p siss-agent-shell. Commit in worktree; do NOT merge." \
  --worktree task3-a2ui-validator &

wait
echo ""
echo "=== Wave 2 agents finished. Merge order: task2-a2ui-display → task1-a2ui-forms → task3-a2ui-validator ==="
