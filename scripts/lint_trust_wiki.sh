#!/bin/bash
set -e

# Phase 22 Linting Script: Trust Wiki Health Check
# Usage: ./lint_trust_wiki.sh [--dry-run] [--prune] [--report]
# Default: --dry-run (print findings, do not modify)

DRY_RUN=true
PRUNE=false
REPORT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --prune)
            PRUNE=true
            DRY_RUN=false
            shift
            ;;
        --report)
            REPORT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

WIKI_DIR="docs/wiki"
EPISODIC_FILE="$WIKI_DIR/episodic/trust-events.md"
SEMANTIC_FILE="$WIKI_DIR/semantic/trust-anomalies.md"
STATUS_FILE="$WIKI_DIR/working/autoresearch-status.md"

# Ensure wiki directory exists
if [ ! -d "$WIKI_DIR" ]; then
    echo "Error: Wiki directory not found at $WIKI_DIR"
    exit 1
fi

# Ensure episodic file exists
if [ ! -f "$EPISODIC_FILE" ]; then
    echo "Error: Episodic file not found at $EPISODIC_FILE"
    exit 1
fi

# Ensure semantic file exists
if [ ! -f "$SEMANTIC_FILE" ]; then
    echo "Error: Semantic file not found at $SEMANTIC_FILE"
    exit 1
fi

# Initialize report data
TOTAL_EPISODIC=0
RECENT_EPISODIC=0
TOTAL_SEMANTIC=0
CONTRADICTIONS=""
STALE_PATTERNS=""

echo "=== Phase 22 Wiki Linting ==="
echo ""

# Check 1: Prune stale episodic entries (> 30 days old)
echo "[1] Checking for stale episodic entries (> 30 days)..."

THIRTY_DAYS_AGO=$(date -u -d "30 days ago" +"%Y-%m-%d" 2>/dev/null || date -u -v-30d +"%Y-%m-%d")
STALE_COUNT=0
TEMP_EPISODIC=$(mktemp)

while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Extract timestamp from JSON (ISO 8601 format)
    timestamp=$(echo "$line" | grep -o '"timestamp":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$timestamp" ]; then
        event_date=$(echo "$timestamp" | cut -d'T' -f1)
        TOTAL_EPISODIC=$((TOTAL_EPISODIC + 1))

        if [ "$event_date" \> "$THIRTY_DAYS_AGO" ] 2>/dev/null || [ "$event_date" = "$THIRTY_DAYS_AGO" ]; then
            RECENT_EPISODIC=$((RECENT_EPISODIC + 1))
            echo "$line" >> "$TEMP_EPISODIC"
        else
            STALE_COUNT=$((STALE_COUNT + 1))
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] Would delete stale entry: $event_date"
            fi
        fi
    else
        # Malformed line, keep it
        echo "$line" >> "$TEMP_EPISODIC"
    fi
done < "$EPISODIC_FILE"

if [ $STALE_COUNT -gt 0 ]; then
    if [ "$PRUNE" = true ]; then
        mv "$TEMP_EPISODIC" "$EPISODIC_FILE"
        echo "  [PRUNED] Removed $STALE_COUNT stale episodic entries"
    else
        rm "$TEMP_EPISODIC"
        echo "  [FOUND] $STALE_COUNT stale episodic entries (use --prune to delete)"
    fi
else
    rm "$TEMP_EPISODIC"
    echo "  [OK] No stale episodic entries"
fi
echo ""

# Check 2: Detect contradictions (same source/target pair with score swing > 50 within 24 hours)
echo "[2] Checking for contradictions (score swing > 50 within 24h)..."

TEMP_PAIRS=$(mktemp)
CONTRADICTION_COUNT=0

while IFS= read -r line; do
    [ -z "$line" ] && continue

    source_id=$(echo "$line" | grep -o '"source_id":"[^"]*"' | cut -d'"' -f4)
    target_id=$(echo "$line" | grep -o '"target_id":"[^"]*"' | cut -d'"' -f4)
    score=$(echo "$line" | grep -o '"score":[0-9]*' | cut -d':' -f2)
    timestamp=$(echo "$line" | grep -o '"timestamp":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$source_id" ] || [ -z "$target_id" ] || [ -z "$score" ]; then
        continue
    fi

    pair="$source_id:$target_id"

    # Check if pair already exists in temp file
    prev_entry=$(grep "^$pair:" "$TEMP_PAIRS" 2>/dev/null || echo "")

    if [ -n "$prev_entry" ]; then
        prev_score=$(echo "$prev_entry" | cut -d':' -f3 | cut -d'|' -f1)
        prev_time=$(echo "$prev_entry" | cut -d':' -f3 | cut -d'|' -f2)

        swing=$((score - prev_score))
        if [ $swing -lt 0 ]; then
            swing=$((-swing))
        fi

        if [ $swing -gt 50 ]; then
            CONTRADICTION_COUNT=$((CONTRADICTION_COUNT + 1))
            CONTRADICTIONS="$CONTRADICTIONS
- source: ${source_id:0:8}..., target: ${target_id:0:8}..., swing: $swing points"
            echo "  [FOUND] Contradiction: $pair, swing=$swing"
        fi
    fi

    echo "$pair:$score|$timestamp" >> "$TEMP_PAIRS"
done < "$EPISODIC_FILE"

rm -f "$TEMP_PAIRS"

if [ $CONTRADICTION_COUNT -eq 0 ]; then
    echo "  [OK] No contradictions detected"
else
    echo "  [FOUND] $CONTRADICTION_COUNT contradictions (see report)"
fi
echo ""

# Check 3: Detect orphaned semantic patterns
echo "[3] Checking for orphaned semantic patterns (> 30 days, no recent events)..."

ORPHANED_COUNT=0

while IFS= read -r line; do
    # Extract source sovereign IDs from semantic file
    case "$line" in
        *"Source Sovereign"*)
            source_id=$(echo "$line" | grep -o "[0-9a-f-]\{36\}" | head -1)

            if [ -n "$source_id" ]; then
                # Check if this source_id appears in recent episodic entries
                if ! grep -q "\"source_id\":\"$source_id\"" "$EPISODIC_FILE"; then
                    ORPHANED_COUNT=$((ORPHANED_COUNT + 1))
                    STALE_PATTERNS="$STALE_PATTERNS
- source: ${source_id:0:8}..."
                    echo "  [FOUND] Orphaned pattern: $source_id (not in recent episodic log)"
                fi
            fi
            ;;
    esac
done < "$SEMANTIC_FILE"

if [ $ORPHANED_COUNT -eq 0 ]; then
    echo "  [OK] No orphaned patterns"
else
    echo "  [FOUND] $ORPHANED_COUNT orphaned patterns (candidates for archival)"
fi
echo ""

# Count semantic patterns
TOTAL_SEMANTIC=$(grep -c "^## Anomaly Pattern:" "$SEMANTIC_FILE" || echo 0)

# Generate health report
if [ "$REPORT" = true ]; then
    echo "[4] Writing health report to $STATUS_FILE..."

    mkdir -p "$WIKI_DIR/working"

    {
        echo "# AutoResearch Health Check — $(date -u +%Y-%m-%d' '%H:%M' UTC')"
        echo ""
        echo "## Summary"
        echo "- Episodic entries: $TOTAL_EPISODIC (last 30 days: $RECENT_EPISODIC)"
        echo "- Semantic patterns: $TOTAL_SEMANTIC"
        echo "- Contradictions detected: $CONTRADICTION_COUNT"
        echo "- Stale patterns: $ORPHANED_COUNT"
        echo ""

        if [ $CONTRADICTION_COUNT -gt 0 ]; then
            echo "## Contradictions"
            echo "$CONTRADICTIONS"
            echo ""
        fi

        if [ $ORPHANED_COUNT -gt 0 ]; then
            echo "## Stale Patterns (≥30 days, no recent events)"
            echo "$STALE_PATTERNS"
            echo ""
        fi

        echo "## Recommendations"
        if [ $CONTRADICTION_COUNT -gt 0 ]; then
            echo "- Investigate contradictions: potential data anomalies or governance actions"
        fi
        if [ $ORPHANED_COUNT -gt 0 ]; then
            echo "- Archive stale patterns if genuinely resolved"
        fi
        if [ $CONTRADICTION_COUNT -eq 0 ] && [ $ORPHANED_COUNT -eq 0 ]; then
            echo "- No issues detected; wiki is healthy"
        fi
        echo ""
        echo "**Next lint:** $(date -u -d "+1 day" +%Y-%m-%d' '%H:%M' UTC' 2>/dev/null || date -u -v+1d +%Y-%m-%d' '%H:%M' UTC')"
    } > "$STATUS_FILE"

    echo "  [OK] Health report written to $STATUS_FILE"
    echo ""
fi

echo "=== Linting Complete ==="
if [ "$DRY_RUN" = true ]; then
    echo "Mode: DRY-RUN (no modifications)"
else
    echo "Mode: PRUNE (modifications applied)"
fi
echo ""
