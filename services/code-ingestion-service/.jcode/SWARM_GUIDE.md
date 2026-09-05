# jcode Swarm Orchestration Guide

## ✅ Status: Ready to Deploy

**jcode v0.12.0 installed** at `/opt/homebrew/bin/jcode`

**Swarm Configuration:** `.jcode/swarm.config.json`
**Coordinator Instructions:** `.jcode/coordinator-prompt.md`

---

## Quick Start: Launch the Refactor Swarm

### 1. Start jcode Server (Terminal A)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/services/code-ingestion-service
jcode serve --config .jcode/swarm.config.json
```

This starts the jcode event bus, read-tracking system, and message broker on `localhost:4747`.

### 2. Spawn the Coordinator (Terminal B)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/services/code-ingestion-service
jcode spawn-agent \
  --role coordinator \
  --swarm arxiv-ingestion-refactor \
  --prompt .jcode/coordinator-prompt.md \
  --model claude-opus-4-7
```

The Coordinator will immediately:
- Load the swarm configuration
- Spawn 4 worker agents (architect, test_writer, implementer, validator)
- Begin orchestrating their execution
- Broadcast messages and manage state via the jcode event bus

### 3. Monitor Swarm Execution (Terminal C - Optional)
```bash
jcode monitor --swarm arxiv-ingestion-refactor
```

Shows real-time:
- Worker statuses (pending, in-progress, completed)
- Message events (code-shifts, broadcasts)
- File changes being tracked
- Test results as they arrive

---

## What Happens Automatically

### Phase 1: Architect Designs (Parallel Start)
1. Architect reads `ArxivIngestionService.java`
2. Designs new exception hierarchy and retry strategy
3. Updates the code with improvements
4. **Broadcasts:** "I've updated ArxivIngestionService. New exceptions: ArxivAPIException, RateLimitException, ParsingException"

### Phase 2: Implementer & Test-Writer Respond (Code-Shift Events)
1. **Code-Shift Event Fires:** jcode detects architect's changes to `ArxivIngestionService.java`
2. **Implementer Notified:** Pulls new signature, finds all 2 callers (IngestionController, IngestionScheduler), updates them
3. **Test-Writer Notified:** Writes failing tests for new exception scenarios, validates they pass

### Phase 3: Validator Reviews (Serialized)
1. Validator reads all changes made by architect, implementer, test_writer
2. Enforces java-architecture rules (uses `.claude/skills/java-architecture/reference.md`)
3. Checks:
   - ✅ Signature compliance
   - ✅ Exception handling completeness
   - ✅ Test coverage
   - ✅ No dead code
   - ✅ No regressions
4. **Signs off:** "✅ APPROVED: Ready to merge"

### Phase 4: Synthesis Report
Coordinator rolls up final report:
```
SWARM SYNTHESIS REPORT
======================
Refactor: ArxivIngestionService Error Handling

Workers Completed: 4/4 ✅
Test Suite: PASSED (42/42 tests) ✅
Validator Sign-Off: APPROVED ✅
Regressions: ZERO ✅

Changes Made:
- Updated ArxivIngestionService with 3 new exception types
- Updated 2 callers (IngestionController, IngestionScheduler)
- Added 6 new integration tests
- Estimated blast radius: LOW (isolated to service layer)

Ready for merge.
```

---

## Real-Time Monitoring

### View Swarm State
```bash
jcode status --swarm arxiv-ingestion-refactor
```

### View Message Events
```bash
jcode logs --swarm arxiv-ingestion-refactor --follow
```

### View Code Changes Being Tracked
```bash
jcode diff --swarm arxiv-ingestion-refactor
```

### Manually Send a Message to All Workers
```bash
jcode broadcast --swarm arxiv-ingestion-refactor --message "Run your integration tests now"
```

---

## Stopping the Swarm

### Graceful Shutdown (Finish Current Tasks)
```bash
jcode shutdown --swarm arxiv-ingestion-refactor --graceful
```

Workers complete their current task, then swarm exits. All changes are preserved.

### Hard Shutdown (Emergency)
```bash
jcode kill --swarm arxiv-ingestion-refactor
```

Terminates immediately. Use only if a worker is stuck.

---

## Swarm Configuration Reference

**Coordinator Model:** `claude-opus-4-7` (orchestration & synthesis)
**Worker Models:**
- Architect: Opus 4.7 (complex design)
- Test-Writer: Sonnet 4.6 (test generation)
- Implementer: Sonnet 4.6 (caller updates)
- Validator: Opus 4.7 (review & enforcement)

**Skills Available to All Workers:**
- `java-architecture` — Structural dependency map
- `knowledge-retrieval` — Local knowledge base search

**Memory Usage:** ~117 MB for 4 concurrent agents (vs 2 GB+ for traditional setups)

**Typical Execution Time:** 8-15 minutes (depending on code complexity and test count)

---

## Advanced: Parallel Swarms

You can run **multiple swarms simultaneously** on the same repository:

```bash
# Terminal C
jcode spawn-agent --role coordinator \
  --swarm feature-payment-api \
  --prompt .jcode/coordinator-payment.md

# Terminal D (different feature)
jcode spawn-agent --role coordinator \
  --swarm refactor-chunk-storage \
  --prompt .jcode/coordinator-chunking.md
```

jcode's read-tracking and code-shifting events automatically alert Agent A in feature-payment-api if Agent B in refactor-chunk-storage modifies code A has read. Conflicts are resolved dynamically without blocking.

---

## Architecture Benefits vs. git worktree

| Aspect | git worktree | jcode |
|--------|-------------|-------|
| Isolation | Separate branches (high latency) | Same repo, real-time events |
| Conflict Detection | Merge conflicts (post-hoc) | Code-shift events (real-time) |
| Conflict Resolution | Manual merge (human) | Agent-driven (autonomous) |
| Memory/Agent | 2GB+ (Python/Node) | 117MB (Rust) |
| Parallelization | Sequential merges | True parallel velocity |
| Messaging | None (isolated) | Native cross-agent bus |

---

## Troubleshooting

### Worker Stuck (No Progress)
```bash
jcode debug --agent architect --swarm arxiv-ingestion-refactor
```

Shows the agent's current context, pending tasks, and why it might be blocked.

### Event Bus Lag (Delayed Code-Shifts)
```bash
jcode perf --metric event-latency
```

Typical: <100ms per event. If > 1s, check system load.

### Test Failures During Swarm
```bash
jcode test --swarm arxiv-ingestion-refactor --filter "ArxivIngestionService"
```

Runs specific test subset to isolate failures.

---

## Next Steps

1. **Run the swarm:** Follow "Quick Start" above
2. **Monitor execution:** Open a second terminal with `jcode monitor`
3. **Review synthesis report:** Wait for coordinator to complete
4. **Merge changes:** If validator approves, commit to main

Good luck! 🚀
