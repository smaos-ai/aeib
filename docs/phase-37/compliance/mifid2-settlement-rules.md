# MiFID II Settlement & AP2 Integration — SovereignNexus Finance

## MiFID II Compliance Overview

Markets in Financial Instruments Directive II (MiFID II, 2014/65/EU, implemented Jan 2018) requires financial firms to:
1. Execute client orders at best execution (lowest cost, fastest execution)
2. Maintain detailed audit trail of all trading decisions
3. Transparently disclose execution quality vs. benchmarks
4. Implement robust systems + controls to prevent market abuse

SovereignNexus serves as a **governance capsule for trading desk operations**, validating that each order respects best-execution rules before execution.

## Best-Execution Rule Modeling in AP2

### Best Execution Attributes (AP2 Attribute Set)

```rust
pub struct BestExecutionAttributes {
    pub execution_venue: String,          // "LSE", "Euronext", "Dark Pool X"
    pub execution_price: f64,             // Price at which order executed
    pub execution_time_ms: u64,           // Milliseconds to execute
    pub venue_fee_bps: i32,               // Fee in basis points (1 bps = 0.01%)
    pub post_trade_price: f64,            // Benchmark post-trade price (VWAP)
    pub slippage_bps: i32,                // (execution_price - benchmark_price) / benchmark_price * 10000
    pub notification_latency_ms: u64,     // Time to notify client of execution
    pub liquidity_tier: String,           // "Top-Tier", "Secondary", "Illiquid"
}
```

### Best-Execution Policy (AP2 Rules)

```rust
pub fn best_execution_policy(attrs: &BestExecutionAttributes) -> Result<AllowDeny, DenyReason> {
    // RULE 1: Top-tier venues must be used for >90% of volume
    if attrs.execution_venue == "DarkPool" && attrs.post_trade_price < attrs.execution_price {
        return Err(DenyReason::AP2("Dark pool execution worse than public market".into()));
    }
    
    // RULE 2: Slippage must be <5 bps for liquid instruments (LSE top 300)
    if attrs.liquidity_tier == "Top-Tier" && attrs.slippage_bps > 5 {
        return Err(DenyReason::AP2(format!("Slippage {} bps exceeds 5 bps limit", attrs.slippage_bps)));
    }
    
    // RULE 3: Notification latency <100ms (client must know immediately)
    if attrs.notification_latency_ms > 100 {
        return Err(DenyReason::AP2("Notification delay exceeds SLA".into()));
    }
    
    // RULE 4: Fee transparency (venue fee + internal markup ≤ 3 bps for retail)
    if attrs.venue_fee_bps > 3 {
        return Err(DenyReason::AP2("Total fees exceed retail threshold".into()));
    }
    
    Ok(AllowDeny::Allow)
}
```

## MiFID II Audit Trail Requirements

### Article 25: Record-Keeping

Every financial firm must maintain complete, minute-by-minute records of:
- Order details (instrument, venue, price, time)
- Decision chain (who approved, why)
- Execution confirmation
- Best-execution assessment vs. benchmark

**SovereignNexus contribution:** Immutable Merkle-DAG audit chain (Governance Capsule) provides tamper-evident proof of all trading decisions + best-execution attributes + AP2 policy evaluation.

### Audit Export Format (MiFID II EMIR Trade Repository)

```json
{
  "trade_id": "uuid",
  "order_time": "2026-07-31T10:30:45.123Z",
  "execution_time": "2026-07-31T10:30:46.234Z",
  "best_execution_attributes": {
    "execution_venue": "LSE",
    "execution_price": 1234.56,
    "execution_time_ms": 1111,
    "venue_fee_bps": 1,
    "post_trade_price": 1234.62,
    "slippage_bps": 0.5,
    "notification_latency_ms": 45,
    "liquidity_tier": "Top-Tier"
  },
  "ap2_decision": {
    "decision": "Allow",
    "policy_rules_evaluated": ["best_execution", "venue_limit", "fee_cap"],
    "evaluated_at": "2026-07-31T10:30:45.800Z"
  },
  "audit_chain": {
    "merkle_root": "sha256:abc123...",
    "proof_of_execution": "..."
  }
}
```

## Reconciliation & Dispute Resolution

### AP2-Driven Dispute Workflow

When a client disputes an execution (e.g., "This was worse than the benchmark"):

1. **Retrieval:** Query MiFID II audit export for trade_id
2. **Calculation:** Recompute best_execution_attributes
3. **Evaluation:** Run AP2 best_execution_policy on stored attributes
4. **Outcome:**
   - ✅ Policy approved → No breach; advisor explains slippage to client
   - ❌ Policy rejected → Potential breach; advisor refunds slippage amount to client

**Phase 37 contribution:** Finance test harness simulates dispute scenario (Task 3).

## Royalty-Split Settlement Rules (AP2)

### Use Case: Investment Advisory Firms with Affiliate Networks

**Scenario:** Trading desk executes 100 orders, 30 via affiliated execution brokers (receive kickback), 70 via independent venues.

**Rule:** MiFID II requires best execution regardless of venue relationship. Affiliated venues must meet same benchmarks as independent ones.

**AP2 Rule Implementation:**

```rust
pub fn no_affiliate_bias_rule(
    execution_venue: &str,
    is_affiliate: bool,
    slippage_vs_benchmark_bps: i32,
) -> Result<AllowDeny, DenyReason> {
    // Apply same 5 bps slippage limit regardless of affiliate status
    if slippage_vs_benchmark_bps > 5 {
        return Err(DenyReason::AP2(
            format!("Slippage {} exceeds limit (affiliate={}, venue={})",
                    slippage_vs_benchmark_bps, is_affiliate, execution_venue)
        ));
    }
    Ok(AllowDeny::Allow)
}
```

**Royalty Split Transparency:** When affiliate venue is used, audit log must show:
- Affiliate relationship disclosed
- Royalty amount (€X per trade, or Y bps of volume)
- Execution quality equivalent to independent benchmarks (proven by AP2 rule pass)

## MiFID II Compliance Checklist (For Phase 37 Pilot)

- [ ] **Best Execution (Article 27)**
  - [ ] Policy covers all execution venues (Top-tier vs. secondary vs. dark pools)
  - [ ] Slippage monitoring (5 bps threshold for liquid, 10 bps for illiquid)
  - [ ] Venue-specific benchmarks (VWAP for UK/EU equities)
  - [ ] Affiliate venue bias detection (AP2 rule, no preferential treatment)

- [ ] **Record-Keeping (Article 25)**
  - [ ] Order + execution timestamps captured
  - [ ] Decision chain + approval records
  - [ ] Best-execution attributes logged
  - [ ] Audit trail immutable (Merkle-DAG, tamper-evident)

- [ ] **Dispute Resolution**
  - [ ] Client dispute workflow documented
  - [ ] AP2 policy re-evaluation procedure
  - [ ] Refund calculation (for over-charged fees or worse-than-benchmark execution)

- [ ] **EMIR Reporting (if derivatives)**
  - [ ] Derivative trades reported to ESMA Trade Repository
  - [ ] Audit export in TR-compatible format
  - [ ] Timely reporting (T+1 for most instruments)

## Staffing & Budget (Pilot Phase, 90 days)

| Role | Effort | Cost |
|------|--------|------|
| MiFID II compliance specialist | 6 weeks | €10K |
| Fintech architect (AP2 rules modeling) | 8 weeks (shared with other verticals) | €15K (allocated) |
| Legal (MiFID II audit, affiliate disclosures) | 1.5 weeks | €4.5K |
| Testing + audit log validation | 4 weeks (shared across verticals) | €10K (allocated) |
| **Total Finance Only** | | **€39.5K** |
