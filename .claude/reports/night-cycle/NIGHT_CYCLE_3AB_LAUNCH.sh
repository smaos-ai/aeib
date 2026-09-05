#!/bin/bash

# Night Cycle: Project Lick Phase 3A-3B Launch
# Run this in tmux to spawn both agents in parallel
# Usage: chmod +x NIGHT_CYCLE_3AB_LAUNCH.sh && ./NIGHT_CYCLE_3AB_LAUNCH.sh

echo "🚀 Launching Night Cycle: Project Lick Phase 3A-3B"
echo "Timeline: 9pm → 6am (9 hours)"
echo ""

# Create tmux sessions for both agents (if not already created)
tmux new-session -d -s night-lick-1 -x 200 -y 50
tmux new-session -d -s night-lick-2 -x 200 -y 50

# Agent 1: Phase 3A - Confidence Scoring Engine
echo "📍 Spawning night-lick-1 (Phase 3A: Confidence Scoring)..."
tmux send-keys -t night-lick-1 "cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-1-confidence && clear && echo 'Phase 3A: Confidence Scoring Engine' && echo 'Timeline: 9pm-3am (6 hours)' && echo '' && echo 'Tests to implement:' && echo '1. test_source_trust_weights_vary_by_type' && echo '2. test_corroboration_increases_confidence' && echo '3. test_contradiction_marks_fact_stale' && echo '4. test_temporal_decay_with_ebbinghaus' && echo '5. test_confidence_calculation_deterministic' && echo '' && cargo test --test confidence_scorer -- --nocapture" Enter

# Agent 2: Phase 3B - Graph Integration & Search Wiring
echo "📍 Spawning night-lick-2 (Phase 3B: Graph Integration)..."
tmux send-keys -t night-lick-2 "cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-2-graph && clear && echo 'Phase 3B: Graph Integration & Search Wiring' && echo 'Timeline: 9pm-3am (6 hours)' && echo '' && echo 'Tests to implement:' && echo '1. test_relationship_extraction_finds_relevant_pairs' && echo '2. test_graph_insertion_maintains_bidirectional_links' && echo '3. test_graph_traversal_returns_ranked_neighbors' && echo '4. test_search_ranking_incorporates_graph_relevance' && echo '5. test_graph_integration_deterministic' && echo '' && cargo test --test graph_builder -- --nocapture" Enter

# Display status
echo ""
echo "✓ Both agents spawned in parallel."
echo ""
echo "Monitor progress:"
echo "  tmux attach -t night-lick-1"
echo "  tmux attach -t night-lick-2"
echo ""
echo "Specs available:"
echo "  .claude/specs/PHASE_3A_CONFIDENCE_SCORING.md"
echo "  .claude/specs/PHASE_3B_GRAPH_INTEGRATION.md"
echo ""
echo "Expected completion: 6:00am (May 28)"
echo "Check balance: https://console.anthropic.com"
echo ""
