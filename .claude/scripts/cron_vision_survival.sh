#!/bin/bash

# Vision Survival Protocol — Nightly Cron Entry
# Add to crontab with: crontab -e
# Then add line: 0 3 * * * /Users/andriileukhin/Documents/SovereignNexus/.claude/scripts/cron_vision_survival.sh
#
# This runs every day at 3:00 AM

PROJECT_ROOT="/Users/andriileukhin/Documents/SovereignNexus"
RUST_LOG="info"
LOG_DIR="$HOME/.claude/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Set environment
export SISS_WORKSPACE="$PROJECT_ROOT"
export RUST_LOG

# Change to project root
cd "$PROJECT_ROOT" || exit 1

# Run Night Shift survival protocol binary
echo "=== Vision Survival Protocol started at $(date) ===" >> "$LOG_DIR/vision_survival.log"
cargo run -p siss-night-cycle --bin vision_survival_protocol --release 2>&1 | tee -a "$LOG_DIR/vision_survival.log"
SYNC_EXIT_CODE=$?

# Log result
if [ $SYNC_EXIT_CODE -eq 0 ]; then
    echo "=== Vision Survival Protocol completed successfully at $(date) ===" >> "$LOG_DIR/vision_survival.log"
else
    echo "=== Vision Survival Protocol FAILED with exit code $SYNC_EXIT_CODE at $(date) ===" >> "$LOG_DIR/vision_survival.log"
fi

exit $SYNC_EXIT_CODE
