# GitNexus Impact Analysis Workflow (Phase 1)

**Purpose:** Enable safe commits by verifying blast radius before CapsuleCommitActor submission  
**Scope:** All 5 agent worktrees (Agent A–E)  
**Status:** Integrated with Phase 1 commit protocol

---

## Quick Start

### Before You Commit

```bash
cd .claude/worktrees/agent-{X}

# 1. Identify modified symbols from git diff
git diff --name-only

# 2. For each modified symbol, run impact analysis
gitnexus impact {symbol_name} --direction upstream --depth 3

# 3. Check result
#    - Risk Level: Low/Medium/High/Critical
#    - Confidence: >= 0.80 (proceed) | < 0.80 (inconclusive)
#    - Caller Count: <= 10 (safe) | > 10 (requires review)

# 4. Decision Tree
if risk_level == Critical || confidence < 0.80:
    echo "⚠ ESCALATE TO EVAL COURT"
    # Stop. Do not commit. Contact team lead.
elif caller_count > 10:
    echo "⚠ MEDIUM RISK: Review callers before committing"
    # Safe to commit, but monitor downstream
else:
    echo "✓ SAFE TO COMMIT"
    # Proceed to capsule generation + CapsuleCommitActor
```

---

## Detailed Workflow

### Step 1: Index Status Check

Before any impact analysis, verify GitNexus index is fresh:

```bash
cd /Users/andriileukhin/Documents/SovereignNexus

# Check index age
gitnexus status

# If stale: re-analyze (runs once per session)
npx gitnexus analyze
# Expected: 24632 symbols indexed, 40041 relationships, 199 execution flows
```

### Step 2: Identify Affected Symbols

From your worktree, list changed files:

```bash
cd .claude/worktrees/agent-{X}

git diff --name-only HEAD~1 HEAD
# Output:
# crates/siss-gatekeeper/src/policy.rs
# crates/siss-gatekeeper/src/lib.rs
```

Extract symbol names from diff:

```bash
git diff HEAD~1 HEAD | grep "^+.*fn \|^+.*pub struct \|^+.*impl " | \
  sed 's/.*fn \|.*pub struct \|.*impl //' | sed 's/(.*//g'
# Output:
# enforce_access_policy
# verify_credentials
```

### Step 3: Run Impact Analysis for Each Symbol

For each affected symbol:

```bash
# Format: gitnexus impact {symbol} --direction upstream --depth {1-3}
gitnexus impact enforce_access_policy --direction upstream --depth 3

# Expected Output:
# {
#   "symbol": "enforce_access_policy",
#   "risk_level": "MEDIUM",
#   "caller_count": 7,
#   "confidence": 0.92,
#   "affected_process_count": 2,
#   "upstream_callers": [
#     { "symbol": "create_session", "depth": 1, "confidence": 0.95 },
#     { "symbol": "middleware_auth", "depth": 1, "confidence": 0.89 }
#   ]
# }
```

### Step 4: Interpret Results

#### Risk Levels

| Level | Definition | Action |
|-------|-----------|--------|
| **Low** | ≤ 3 callers, ≤ 5 affected processes | ✓ Safe to commit |
| **Medium** | 4–10 callers, 6–10 affected processes | ✓ Safe, monitor downstream |
| **High** | 11–20 callers, 11–20 affected processes | ⚠ Review callers; escalate if confidence < 0.80 |
| **Critical** | > 20 callers, > 20 affected processes | ✗ HALT; escalate to Eval Court |

#### Confidence Threshold

- **>= 0.80:** GitNexus high confidence; analysis trustworthy
- **< 0.80:** Analysis inconclusive; retry with more context (add @SuppressWarning if needed)

#### Decision Tree

```
For each affected symbol:

1. Risk Level?
   - CRITICAL → ESCALATE TO EVAL COURT (φ+ vote required)
   - HIGH
     ├─ Confidence >= 0.80 → Review callers (are they safe to change?)
     │  ├─ Callers are test-only → SAFE
     │  └─ Callers in production code → ESCALATE
     └─ Confidence < 0.80 → INCONCLUSIVE (stop; retry)
   - MEDIUM → Safe to commit; document in capsule
   - LOW → Safe to commit

2. All symbols cleared?
   - YES → Proceed to capsule generation
   - NO → Fix issues before committing
```

---

## Agent-Specific Examples

### Agent A: Access Control (siss-gatekeeper)

```bash
cd .claude/worktrees/agent-auth

# Modified: enforce_access_policy, verify_credentials
gitnexus impact enforce_access_policy --direction upstream --depth 3
# Expected: MEDIUM risk, 7 callers, confidence 0.92
# Action: ✓ SAFE (callers are auth middleware)

gitnexus impact verify_credentials --direction upstream --depth 3
# Expected: LOW risk, 3 callers, confidence 0.95
# Action: ✓ SAFE
```

### Agent B: Inference Engine (siss-agent-shell/rapid_mlx_integration.rs)

```bash
cd .claude/worktrees/agent-inference

# Modified: infer, infer_fresh, infer_with_snapshot
gitnexus impact infer --direction upstream --depth 3
# Expected: MEDIUM risk, 5 callers, confidence 0.89
# Action: ✓ SAFE (callers are agent shell + executor)

gitnexus impact infer_fresh --direction upstream --depth 3
# Expected: LOW risk, 2 callers, confidence 0.91
# Action: ✓ SAFE
```

### Agent C: Knowledge Graph (siss-sovereign-kg)

```bash
cd .claude/worktrees/agent-knowledge-graph

# Modified: query_impact, detect_changes
gitnexus impact query_impact --direction upstream --depth 3
# Expected: HIGH risk, 12 callers, confidence 0.94
# Action: ⚠ SAFE (high callers but high confidence; document in capsule)

gitnexus impact detect_changes --direction upstream --depth 3
# Expected: MEDIUM risk, 6 callers, confidence 0.88
# Action: ✓ SAFE
```

### Agent D: AP2 Mandates (siss-ap2-enforcer)

```bash
cd .claude/worktrees/agent-mandates

# Modified: process_payment, authorize_mandate
gitnexus impact process_payment --direction upstream --depth 3
# Expected: CRITICAL risk, 25 callers, confidence 0.85
# Action: ✗ ESCALATE (payment is critical path; requires Eval Court)

# If escalating:
echo "ESCALATION: process_payment modification requires φ+ Eval Court approval"
# Do NOT commit until φ+ votes Safe
```

### Agent E: Orchestration (siss-capsule-commit)

```bash
cd .claude/worktrees/agent-integration

# Modified: ingest_capsule, execute_decisions
gitnexus impact ingest_capsule --direction upstream --depth 3
# Expected: MEDIUM risk, 8 callers, confidence 0.90
# Action: ✓ SAFE (callers are orchestrator + CLI)

gitnexus impact execute_decisions --direction upstream --depth 3
# Expected: LOW risk, 3 callers, confidence 0.93
# Action: ✓ SAFE
```

---

## Escalation Protocol (HIGH/CRITICAL Risk)

### Scenario: φ+ Eval Court Escalation

**Trigger:** HIGH or CRITICAL risk level + confidence >= 0.80

**Process:**

1. **Document the escalation:**
   ```bash
   # In your worktree, create escalation note
   cat > /tmp/escalation_request.md << EOF
   ## Φ+ Eval Court Request
   
   **Symbol:** process_payment
   **Risk Level:** CRITICAL (25 callers)
   **Confidence:** 0.85 (high)
   **Reason:** Payment authorization path; affects multiple agents
   
   **Proposed Change:** Add spending threshold validation
   
   **Question:** Is this modification safe for simultaneous execution?
   EOF
   ```

2. **Escalate via pull request comment** (or team communication):
   - Include escalation_request.md
   - Link to impact analysis
   - Provide git diff

3. **Wait for φ+ vote:**
   - Safe → Proceed to capsule generation
   - Unsafe → Revert changes and redesign

4. **Do not commit until φ+ approves**

---

## Integration with CapsuleCommitActor

After impact analysis clears (no CRITICAL escalations):

```bash
# 1. Generate CommitmentCapsule
# (Already implemented in agent crates)

capsule = CommitmentCapsule {
    affected_symbols: ["enforce_access_policy", "verify_credentials"],
    impact_analysis: {
        enforce_access_policy: { risk: "MEDIUM", confidence: 0.92 },
        verify_credentials: { risk: "LOW", confidence: 0.95 }
    },
    // ... other fields
}

# 2. Submit to CapsuleCommitActor
actor.ingest_capsule(capsule)?

# 3. Receive decision
// → Approved: proceed with commit + push
// → HaltForPhiPlus: wait for φ+ vote
// → Rejected: fix issues + retry
```

---

## Automated Impact Gate (Optional)

To prevent commits with unanalyzed symbols, add pre-commit hook:

```bash
# .git/hooks/pre-commit
#!/bin/bash

SYMBOLS=$(git diff --cached --name-only | \
  grep -E "\.rs$" | \
  xargs grep -h "^fn \|^pub struct \|^impl " | \
  sed 's/.*fn \|.*pub struct \|.*impl //' | sed 's/(.*//g')

for symbol in $SYMBOLS; do
    RISK=$(gitnexus impact "$symbol" --direction upstream --depth 1 | \
           jq -r '.risk_level')
    
    if [ "$RISK" = "CRITICAL" ]; then
        echo "❌ HALT: $symbol has CRITICAL risk. Escalate to Eval Court."
        exit 1
    fi
done

echo "✓ All symbols analyzed and safe"
exit 0
```

---

## FAQ

**Q: What if impact analysis times out?**  
A: Likely index is stale. Run `npx gitnexus analyze` in main repo first.

**Q: Can I commit without running impact analysis?**  
A: Only in emergencies (P1 production incident). Document in PR.

**Q: What if confidence is exactly 0.80?**  
A: That's safe (>= 0.80). Proceed.

**Q: What if a symbol has no callers?**  
A: Low risk. Safe to commit (unused code path).

**Q: Can multiple agents modify the same symbol?**  
A: **NO.** File-orthogonal rule prevents this. If overlap detected, CapsuleCommitActor halts both for φ+ review.

---

## Checklist: Before Every Commit

- [ ] Run `gitnexus impact {symbol} --direction upstream --depth 3` for all affected symbols
- [ ] Check: All risk levels <= MEDIUM (or escalated + φ+ approved)
- [ ] Check: All confidence >= 0.80
- [ ] Check: Caller count <= 20 (or escalated)
- [ ] Generate CommitmentCapsule with impact analysis summary
- [ ] Submit to CapsuleCommitActor
- [ ] Wait for approval (should be immediate for file-orthogonal changes)
- [ ] Commit + push

---

**Owner:** Sovereign Architect  
**Status:** Ready for Phase 1 deployment  
**Enforced in:** All 5 agent worktrees (auth-cluster, inference-cluster, kg-cluster, mandates-cluster, integration-cluster)

