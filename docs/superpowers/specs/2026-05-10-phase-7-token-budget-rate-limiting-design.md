# Phase 7: Token Budget & Rate Limiting Design

**Date:** 2026-05-10  
**Author:** SovereignNexus Architecture  
**Status:** Draft  
**Phase:** 7 (Resource Governance)

---

## 1. Overview

Phase 7 adds **resource governance** to SISS: token budget allocation, rate limit enforcement, and constraint propagation through delegation chains. This prevents resource exhaustion, enables hierarchical cost allocation, and enforces fair usage across multi-agent systems.

**Key Problem:** In Phase 6, delegated agents can call refresh unlimited times. We need:
- Per-session **token consumption limits** (budget)
- Rate constraints from delegation ceiling (inherited, immutable)
- Atomicity: budget decrements must be transactional
- Fail-safe: reject refresh if budget exhausted

**Design Philosophy:**
- **Token budgets are immutable at delegation time** (like ceilings)
- **Constraints are inherited and enforced** at every refresh
- **Budget is consumed on token issuance**, not refresh (pay-to-play)
- **Cascading limits:** parent budget ≥ child budget (transitive enforcement)
- **Fail-closed:** If budget unknown, deny refresh (safety over optimism)

---

## 2. Core Concepts

### 2.1 Token Budget

A **token budget** is the maximum number of tokens (or "units") a session can be issued during its lifetime.

- **Root session:** Initialized with large budget (e.g., 1,000,000 units per 24h)
- **Delegated session:** Receives subset of parent's budget at delegation time
- **Immutable:** Cannot be renegotiated mid-session
- **Atomic decrement:** On successful refresh, budget decreases by token cost

**Structure:**
```rust
pub struct SessionBudget {
    pub initial_budget: i64,      // Total allocated at session creation
    pub remaining_budget: i64,    // What's left after consumption
    pub consumed_budget: i64,     // Total consumed to date
    pub last_reset_at: DateTime<Utc>, // For periodic reset (future: hourly/daily)
}
```

### 2.2 Rate Limiting & Constraints

**Rate limits** are constraints on how frequently an agent can consume tokens.

**Examples:**
```json
{
  "rate_limit": "1000/min",           // Max 1000 tokens per minute
  "burst_size": 100,                  // Allow up to 100 at once
  "min_interval_ms": 100,             // Min 100ms between requests
  "concurrent_sessions": 5             // Max 5 active child sessions
}
```

**Key Rules:**
- Limits are inherited from delegation ceiling (cannot be relaxed)
- If child requests violates inherited limit → 429 (Too Many Requests)
- Limits are checked **before** token issuance
- Violations are logged but don't revoke session (soft enforcement for ops compatibility)

### 2.3 Token Cost Model

Each refresh issuance consumes **tokens** based on:

```
token_cost = base_cost + tier_cost + attestation_cost

base_cost        = 100 (fixed cost per token)
tier_cost        = (2 - attestation_tier) * 50
                   (tier 1: +50, tier 2: +0, tier 3: -50)
attestation_cost = count(attestations) * 10
                   (more attestations = more expensive to validate)
```

**Example:**
- Root agent, tier 1, 3 attestations: 100 + 50 + 30 = **180 tokens**
- Delegated agent, tier 2, 1 attestation: 100 + 0 + 10 = **110 tokens**

---

## 3. Data Model

### 3.1 Sessions Table Extensions

**Existing fields (Phase 6):**
```sql
parent_session_id UUID REFERENCES sessions(id),
delegated_by_agent_id UUID REFERENCES personas(id),
delegation_ceiling_envelope JSONB,  -- {max_tier, delegations, constraints}
```

**New Phase 7 fields:**
```sql
token_budget_initial i64 NOT NULL DEFAULT 1000000,
token_budget_remaining i64 NOT NULL DEFAULT 1000000,
token_budget_consumed i64 NOT NULL DEFAULT 0,
token_budget_reset_at TIMESTAMPTZ DEFAULT NOW(),
rate_limits JSONB,  -- {rate_limit, burst_size, min_interval_ms, concurrent_sessions}
last_refresh_at TIMESTAMPTZ,  -- For rate limit enforcement
```

**Constraints:**
```sql
CHECK (token_budget_initial >= 0),
CHECK (token_budget_remaining >= 0),
CHECK (token_budget_consumed >= 0),
CHECK (token_budget_initial = token_budget_remaining + token_budget_consumed),
  -- Invariant: initial = remaining + consumed
CHECK (rate_limits IS NULL OR 
       (rate_limits->>'rate_limit') LIKE '%/%'),
  -- Rate limit format: "N/period" (e.g., "1000/min")
```

### 3.2 Delegation Ceiling Envelope Extension

**Current Phase 6:**
```json
{
  "max_tier": 2,
  "delegations": [...],
  "constraints": {...}
}
```

**Phase 7 Enhancement:**
```json
{
  "max_tier": 2,
  "delegations": [...],
  "constraints": {
    "rate_limit": "1000/min",
    "burst_size": 100,
    "min_interval_ms": 100,
    "concurrent_sessions": 5
  },
  "budget_allocation": {
    "total_budget": 500000,
    "allocation_rationale": "Parent allocated 50% of remaining budget"
  }
}
```

### 3.3 Migration: 012_add_phase7_budget_fields.sql

```sql
ALTER TABLE sessions
  ADD COLUMN token_budget_initial i64 NOT NULL DEFAULT 1000000,
  ADD COLUMN token_budget_remaining i64 NOT NULL DEFAULT 1000000,
  ADD COLUMN token_budget_consumed i64 NOT NULL DEFAULT 0,
  ADD COLUMN token_budget_reset_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN rate_limits JSONB,
  ADD COLUMN last_refresh_at TIMESTAMPTZ;

-- Create indexes for budget tracking and rate limiting
CREATE INDEX idx_sessions_budget_remaining ON sessions(id) 
  WHERE token_budget_remaining > 0 AND status = 'active'::session_status;

CREATE INDEX idx_sessions_last_refresh ON sessions(last_refresh_at)
  WHERE status = 'active'::session_status;

-- Add constraint: budget conservation
ALTER TABLE sessions
  ADD CONSTRAINT budget_conservation CHECK (
    token_budget_initial = (token_budget_remaining + token_budget_consumed)
  );
```

---

## 4. Token Budget Algorithm

### 4.1 Budget Computation at Delegation Time

When parent delegates to child:

```
parent_remaining = session.token_budget_remaining
parent_consumed = session.token_budget_consumed

child_budget_allocation = MIN(
  parent_remaining * allocation_ratio,  -- Parent allocates portion of remaining
  max_budget_per_child                  -- Safety cap per child
)

// Immutable: child's ceiling locked to this allocation
child_ceiling.budget_allocation = child_budget_allocation
```

**Safe Defaults:**
- `allocation_ratio = 0.5` (parent allocates 50% of remaining)
- `max_budget_per_child = 250000` (no single child > 250k)

### 4.2 Token Cost Calculation

```rust
fn compute_token_cost(
    attestation_tier: u32,           // 1, 2, 3
    attestation_count: usize,
    is_delegated: bool,
) -> u64 {
    let base_cost = 100;
    let tier_cost = (2 - attestation_tier as i64) * 50;
    let attestation_cost = attestation_count as i64 * 10;
    let delegation_cost = if is_delegated { 50 } else { 0 };
    
    ((base_cost + tier_cost + attestation_cost + delegation_cost) as u64)
        .max(50)  // Minimum cost: 50 tokens
}
```

### 4.3 Budget Consumption (Atomic)

During successful refresh:

```sql
-- Atomic: check budget + decrement in single transaction
UPDATE sessions
SET 
  token_budget_remaining = token_budget_remaining - $1,
  token_budget_consumed = token_budget_consumed + $1,
  last_refresh_at = NOW()
WHERE id = $2
  AND token_budget_remaining >= $1  -- Fail if insufficient
RETURNING token_budget_remaining;
```

**Failure modes:**
- `budget_remaining < token_cost` → return `error_insufficient_budget()`
- Transaction conflict → retry with exponential backoff
- DB error → fail gracefully (best-effort, non-blocking)

---

## 5. Rate Limiting Enforcement

### 5.1 Constraint Parsing

Parse rate limits from ceiling constraints:

```rust
pub struct RateLimitConstraints {
    pub rate_limit: Option<String>,        // "1000/min", "10000/hour", etc.
    pub burst_size: Option<u64>,           // Max tokens in burst
    pub min_interval_ms: Option<u64>,      // Min ms between requests
    pub concurrent_sessions: Option<u32>,  // Max child sessions
}

fn parse_rate_limit(constraint_str: &str) -> Result<(u64, Duration), String> {
    // Parse "1000/min" → (1000, Duration::minutes(1))
    let parts: Vec<&str> = constraint_str.split('/').collect();
    if parts.len() != 2 {
        return Err("invalid_rate_limit_format".to_string());
    }
    
    let limit = parts[0].parse::<u64>()?;
    let period = match parts[1] {
        "sec" | "s" => Duration::seconds(1),
        "min" => Duration::minutes(1),
        "hour" | "h" => Duration::hours(1),
        "day" | "d" => Duration::days(1),
        _ => return Err("unknown_period".to_string()),
    };
    
    Ok((limit, period))
}
```

### 5.2 Rate Limit Checks (Pre-Refresh)

Before issuing token in refresh handler:

```rust
// Step 2.5: Rate limit check (after revocation check, before challenge check)
if let Some(rate_limits) = &db_session.rate_limits {
    if let Err(reason) = check_rate_limits(
        &state.pool,
        session_id,
        &rate_limits,
        &db_session.last_refresh_at,
    ).await {
        // Soft enforcement: log violation, return 429, but don't revoke
        warn!("Rate limit violation: {} for session {}", reason, session_id);
        let response = error_rate_limit_exceeded(reason);
        return (StatusCode::TOO_MANY_REQUESTS, Json(response)).into_response();
    }
}
```

### 5.3 Rate Limit Logic

```rust
async fn check_rate_limits(
    pool: &PgPool,
    session_id: Uuid,
    rate_limits_json: &str,
    last_refresh_at: Option<DateTime<Utc>>,
) -> Result<(), String> {
    let constraints: RateLimitConstraints = serde_json::from_str(rate_limits_json)?;
    
    // Check min interval
    if let Some(min_interval_ms) = constraints.min_interval_ms {
        if let Some(last) = last_refresh_at {
            let elapsed = (Utc::now() - last).num_milliseconds();
            if elapsed < min_interval_ms as i64 {
                return Err(format!(
                    "min_interval_violation: {} ms elapsed, {} required",
                    elapsed, min_interval_ms
                ));
            }
        }
    }
    
    // Check rate limit (tokens per period)
    if let Some(rate_limit_str) = &constraints.rate_limit {
        let (max_tokens, period) = parse_rate_limit(rate_limit_str)?;
        let window_start = Utc::now() - period;
        
        // Count refreshes in window
        let refresh_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM sessions \
             WHERE parent_session_id = $1 \
               AND last_refresh_at > $2"
        )
        .bind(session_id)
        .bind(window_start)
        .fetch_one(pool)
        .await?;
        
        if refresh_count.0 as u64 >= max_tokens {
            return Err(format!(
                "rate_limit_exceeded: {} refreshes in period, {} allowed",
                refresh_count.0, max_tokens
            ));
        }
    }
    
    // Check concurrent sessions
    if let Some(max_concurrent) = constraints.concurrent_sessions {
        let active_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM sessions \
             WHERE parent_session_id = $1 \
               AND status = 'active'::session_status"
        )
        .bind(session_id)
        .fetch_one(pool)
        .await?;
        
        if active_count.0 as u32 >= max_concurrent {
            return Err(format!(
                "concurrent_sessions_exceeded: {} active, {} allowed",
                active_count.0, max_concurrent
            ));
        }
    }
    
    Ok(())
}
```

---

## 6. Refresh Handler Integration

### 6.1 Updated Refresh Flow (12-Step → 13-Step)

**Step 2.5 (NEW): Rate Limit Check**
- Parse rate_limits from db_session.rate_limits
- Check min_interval_ms, rate_limit, concurrent_sessions
- Return 429 (Too Many Requests) if violated
- Soft enforcement: log but don't revoke

**Step 3.5 (NEW): Budget Check**
- Compute token_cost(tier, attestation_count, is_delegated)
- Verify token_budget_remaining >= token_cost
- Return error_insufficient_budget() if < cost

**Step 9.5 (NEW): Budget Consumption**
- Atomically decrement token_budget_remaining
- Increment token_budget_consumed
- Update last_refresh_at timestamp

### 6.2 Error Responses

```rust
pub fn error_insufficient_budget() -> AttestationRefreshResponse {
    build_error_response(
        "insufficient_budget".to_string(),
        "Session token budget exhausted; cannot issue new tokens".to_string(),
        vec![
            "Request parent delegation for budget increase".to_string(),
            "Or wait for budget window reset (daily reset at 00:00 UTC)".to_string(),
        ],
        None,
    )
}

pub fn error_rate_limit_exceeded(reason: String) -> AttestationRefreshResponse {
    build_error_response(
        "rate_limit_exceeded".to_string(),
        format!("Rate limit violated: {}", reason),
        vec![
            "Wait before retrying (check min_interval_ms, rate_limit constraints)".to_string(),
            "Or request parent to adjust constraints".to_string(),
        ],
        None,
    )
}
```

---

## 7. Backward Compatibility

### 7.1 Default Behavior

For sessions created **before** Phase 7:
- `token_budget_initial = 1000000` (default large budget)
- `token_budget_remaining = 1000000`
- `rate_limits = NULL` (no constraints)
- **Result:** Unlimited consumption (Phase 5.5 behavior)

For sessions created **after** Phase 7:
- Budget initialized at session creation (Phase 4 handshake)
- Rate limits inherited from root attestation policy (future)
- **Result:** Full governance enforced

### 7.2 Transition Strategy

**Option 1: Soft Rollout**
- Deploy Phase 7 with budget checks
- All existing sessions default to `1000000` (unlimited)
- Gradually lower defaults as operators test
- Monitor 429 rate limit errors in logs

**Option 2: Feature Flag**
- Add `budget_enforcement_enabled` flag to gatekeeper config
- Start disabled, gradually enable per-tenant
- Rollback capability if issues arise

---

## 8. Error Cases & Remediation

| Error | HTTP Status | Reason | Remediation |
|-------|------------|--------|-------------|
| `insufficient_budget` | 403 | Remaining budget < token cost | Request parent to increase allocation |
| `rate_limit_exceeded` | 429 | Min interval, rate, or concurrent limit violated | Wait for window reset or request parent adjustment |
| `budget_malformed` | 400 | Budget numbers invalid (negative, inconsistent) | Admin intervention required |
| `rate_limit_malformed` | 400 | Rate limit constraint unparseable | Admin intervention required |

---

## 9. Implementation Roadmap

### **Task 21: Repository Layer (session_repo.rs)**
- `update_session_budget()`: Atomically decrement remaining, increment consumed
- `fetch_session_budget()`: Get budget state for validation
- `reset_session_budget()`: Daily/hourly reset (future: scheduled job)
- Tests: budget atomicity, constraints, edge cases

### **Task 22: Gatekeeper Builders (refresh.rs)**
- `compute_token_cost()`: Calculate cost based on tier + attestations
- `parse_rate_limit()`: Parse "N/period" format
- `error_insufficient_budget()`: Error response builder
- `error_rate_limit_exceeded()`: Error response builder
- Tests: cost calculation, parsing, response serialization

### **Task 23: Constraint Resolver (NEW: constraint_resolver.rs)**
- `RateLimitConstraints` struct (Serialize/Deserialize)
- `RateLimitError` enum (variants for each violation)
- `validate_constraints()`: Sanity check format
- `check_rate_limits()`: Enforce min_interval, rate_limit, concurrent
- Tests: constraint parsing, violation detection

### **Task 24: Handler Integration (refresh_handler.rs)**
- Step 2.5: Add rate limit check (before challenge check)
- Step 3.5: Add budget check (after proof validation)
- Step 9.5: Add budget consumption (atomic transaction)
- Pass `token_cost` through response (informational)
- Tests: integrated flow, budget enforcement

### **Task 25: Integration Tests (attestation_refresh_phase7_tests.rs)**
- 15 test cases covering:
  1. Budget consumption on refresh (root session)
  2. Budget consumption on refresh (delegated session)
  3. Budget exhaustion blocks refresh
  4. Budget conservation invariant maintained
  5. Delegated budget allocation (parent allocates 50%)
  6. Rate limit min_interval enforcement
  7. Rate limit rate_limit enforcement (per-minute)
  8. Rate limit concurrent_sessions enforcement
  9. Rate limit violation returns 429 (soft enforcement)
  10. Token cost calculation (tier + attestations)
  11. Token cost increases with more attestations
  12. Token cost decreases for higher tier (tier 2 is cheapest)
  13. Inherited constraints cannot be relaxed
  14. Budget reset on period boundary (future test hook)
  15. Atomic transaction rollback on constraint violation

### **Task 26: Documentation & Operations**
- Phase 7 migration guide
- Budget allocation policy (how parents allocate to children)
- Rate limit tuning guide
- Monitoring & alerting (budget exhaustion, rate limit violations)
- Cost estimation tool (predict budget consumption)

---

## 10. File Changes Summary

| File | Action | Details |
|------|--------|---------|
| `crates/siss-graph-db/src/migrations/012_add_phase7_budget_fields.sql` | CREATE | Budget, rate limit, reset fields + indexes + constraints |
| `crates/siss-graph-db/src/repo/session_repo.rs` | MODIFY | `update_session_budget()`, `fetch_session_budget()`, `reset_session_budget()` |
| `crates/siss-gatekeeper/src/refresh.rs` | MODIFY | Cost calculation, error builders, constraint types |
| `crates/siss-gatekeeper/src/constraint_resolver.rs` | CREATE | Rate limit parsing, validation, checking logic |
| `crates/siss-agent-card/src/refresh_handler.rs` | MODIFY | Steps 2.5, 3.5, 9.5 (rate limits, budget check, consumption) |
| `crates/siss-agent-card/tests/attestation_refresh_phase7_tests.rs` | CREATE | 15 integration + unit tests |

---

## 11. Locked Design Decisions

### ✅ Budget Immutability (Locked)
**Decision:** Token budgets are immutable at delegation time (like ceilings).  
**Rationale:** Enables predictable, auditable resource allocation. No mid-session renegotiation prevents confusion and attack surface.  
**Consequence:** Parent must plan allocation carefully; children cannot request more.

### ✅ Fail-Closed Budget Enforcement (Locked)
**Decision:** If budget is unknown or negative, deny refresh (safety over optimism).  
**Rationale:** Prevent unaccounted resource consumption. Err on the side of denial.  
**Consequence:** Budget exhaustion is recoverable (request parent increase), not catastrophic.

### ✅ Soft Rate Limit Enforcement (Locked)
**Decision:** Rate limit violations return 429 but don't revoke session.  
**Rationale:** Rate limits are operational constraints, not security failures. Allow retry without re-auth.  
**Consequence:** Temporary rate limit violations don't cascade to ancestor revocation.

---

## 12. Future Enhancements (Post-Phase 7)

- **Token pricing:** Variable cost per resource (compute, memory, network)
- **Budget reset windows:** Hourly/daily budgets per period
- **Reservation system:** Pre-allocate budget for critical operations
- **Cost forecasting:** ML-based prediction of future consumption
- **Auction system:** Sessions bid for shared resource pools
- **Federated budgets:** Cross-tenant cost sharing

---

## Verification Plan

```bash
# Schema & migrations
cargo test -p siss-graph-db --lib           # Verify migrations apply
cargo test --test attestation_refresh_phase7_tests  # 15 new tests

# Gatekeeper (builders + constraint resolver)
cargo test -p siss-gatekeeper --lib         # 71 existing + new cost/constraint tests

# Handler integration
cargo test -p siss-agent-card --test attestation_refresh_integration  # Existing tests still pass

# Full suite
cargo check && cargo test                    # Zero errors, all passing
```

---

## References

- **Phase 5:** Attestation Refresh (Stateless Push)
- **Phase 5.5:** Revocation & Pull-Based Refresh
- **Phase 6:** Delegation Chains (DAG + Attenuation)
- **Phase 7:** Token Budget & Rate Limiting (This spec)
- **Future:** Phase 8 (Behavioral Governance), Phase 9 (Federation)

