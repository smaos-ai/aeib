# Market Vision — Daily Briefing Generation Engine
## Executive Intelligence Synthesis v1.0

**Date:** 2026-06-04  
**Phase:** 3 Beta Launches (Aug 1+)  
**Status:** Specification Phase  
**Target Completion:** August 15, 2026  

---

## 1. Purpose & Mission

**Core Function:** Generate daily briefings for Sovereign agents synthesizing market data, policy constraints, governance forecasts, and anomalies.

**Why This Works:**
- Agents need context before making decisions (AP2 settlements, market actions)
- Current dashboards are passive; Market Vision is **active intelligence**
- TimeCapsule forecasts policy → Market Vision applies to market context
- Briefings are **personalized by tier + domain** (trader sees trading constraints; NGO sees settlement windows)

**Success Metric (by Sept 15):**
- 100K+ personalized briefings generated/day (one per active sovereign)
- <2 sec latency per briefing generation
- 95%+ accuracy vs. human market analysts
- Used by 50+ Ukraine/Israel sovereigns for daily planning

---

## 2. Architecture & Design

### 2.1 Briefing Components

Every Market Vision briefing contains 5 sections:

```
┌─────────────────────────────────────────────────┐
│ Market Vision Daily Briefing                    │
│ Generated: 2026-06-04 06:00 UTC (30min before  │
│           market open)                          │
├─────────────────────────────────────────────────┤
│                                                 │
│ Section 1: GOVERNANCE SNAPSHOT                  │
│ ├─ Current tier + trust level                   │
│ ├─ Daily action budget remaining               │
│ ├─ Policy constraints (forecasted for today)   │
│ └─ Any governance alerts from overnight         │
│                                                 │
│ Section 2: MARKET CONTEXT                       │
│ ├─ Asset price changes (24h, 7d)               │
│ ├─ Volume + volatility metrics                  │
│ ├─ Sector-specific signals                      │
│ └─ Geopolitical impact (Ukraine, Israel)       │
│                                                 │
│ Section 3: DECISION WINDOWS                     │
│ ├─ Settlement approval windows (TimeCapsule)   │
│ ├─ AP2 transaction limits (by time + tier)     │
│ ├─ Escalation paths + timeline                 │
│ └─ Confidence in constraints (forecast score)  │
│                                                 │
│ Section 4: ANOMALIES & ALERTS                   │
│ ├─ Detected behavioral anomalies               │
│ ├─ Policy drift flags                          │
│ ├─ Adversarial attack detections               │
│ └─ Recommended actions                         │
│                                                 │
│ Section 5: RECOMMENDATIONS                      │
│ ├─ Optimal action windows (game-theoretic)     │
│ ├─ Risk/reward by action type                  │
│ ├─ Peer benchmark (anonymized)                 │
│ └─ Explainability: "why this recommendation"   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 2.2 Data Sources

Market Vision aggregates from:

1. **TimeCapsule (Forecaster)** — Policy constraints + windows
2. **Behavioral Firewall (Policy Engine)** — Current governance state
3. **Market Data Feeds** — Real-time asset prices, volume, volatility
4. **Anomaly Detection** — Observed behavioral/market anomalies
5. **Sovereign Baseline** — Historical tier/trust/action patterns
6. **Geopolitical Context** — Ukraine/Israel alert levels, energy prices, market shocks

### 2.3 Briefing Generation Pipeline

```
┌─────────────────────────────────────┐
│ 1. Fetch Sovereign Context           │
│    └─ Tier, domain, history, locale │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 2. Forecast Today's Policy           │
│    └─ TimeCapsule forecast @ 00:00  │
│    └─ Extract constraints for sector │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 3. Fetch Current Market Data         │
│    └─ Asset prices, volumes         │
│    └─ Volatility, sector signals     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 4. Detect Anomalies                  │
│    └─ Behavioral (sovereign's)      │
│    └─ Market (sector-wide)          │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 5. Game-Theoretic Recommendation     │
│    └─ Optimal action windows        │
│    └─ Risk/reward scoring           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 6. Generate Briefing                 │
│    └─ Markdown + JSON export        │
│    └─ Cryptographic signature       │
└──────────────┬──────────────────────┘
               ↓
         Deliver to Sovereign
```

---

## 3. Core Components

### 3.1 Governance Snapshot Generator

**Purpose:** Extract current + forecasted governance constraints.

```rust
pub struct GovernanceSnapshot {
    pub tier: u32,                      // 1-10
    pub trust_level: u32,               // 0-100
    pub daily_budget: SettlementBudget,
    pub current_constraints: Vec<Constraint>,
    pub forecasted_constraints: Vec<ForecastedConstraint>,
    pub active_alerts: Vec<String>,     // "Tier 7+ AP2 holds active"
    pub governance_confidence: f32,     // 0.0-1.0 (from TimeCapsule forecast)
}

pub struct Constraint {
    pub constraint_type: ConstraintType,
    pub applies_until: SystemTime,
    pub description: String,
    pub enforcement: String,            // "Auto-deny" vs "Require approval"
}

pub enum ConstraintType {
    SettlementLimit { max_usd: u64 },
    TierRequirement { min_tier: u32 },
    TimeWindow { start_hour_utc: u8, end_hour_utc: u8 },
    GeoRestriction { allowed_regions: Vec<String> },
    RateLimit { max_per_hour: u32 },
}

pub struct ForecastedConstraint {
    pub constraint: Constraint,
    pub forecast_confidence: f32,       // From TimeCapsule
    pub start_timestamp: SystemTime,    // When this constraint activates
}

pub async fn generate_governance_snapshot(
    sovereign_id: Uuid,
    timestamp: SystemTime,
    policy_engine: &PolicyEngine,
    forecaster: &TimeCapsuleForecaster,
) -> Result<GovernanceSnapshot, SnapshotError> {
    // 1. Fetch current tier + trust
    let tier = policy_engine.get_tier(sovereign_id).await?;
    let trust = policy_engine.get_trust_level(sovereign_id).await?;
    
    // 2. Forecast policy for next 24 hours
    let constraints_today = forecaster.forecast_constraints(sovereign_id, timestamp).await?;
    
    // 3. Get active alerts from behavioral firewall
    let alerts = policy_engine.get_active_alerts(sovereign_id).await?;
    
    Ok(GovernanceSnapshot {
        tier,
        trust_level: trust,
        current_constraints: extract_current_constraints(&constraints_today),
        forecasted_constraints: constraints_today,
        active_alerts: alerts,
        governance_confidence: forecaster.confidence_score(),
    })
}
```

**Example Output:**

```
Governance Snapshot for Tier 6 NGO (Ukraine):
├─ Current Tier: 6 (Trust: 92/100)
├─ Daily Settlement Budget: $50K remaining (of $200K)
├─ Current Constraints:
│  ├─ AP2 settlements <$100K: Auto-approve
│  ├─ AP2 settlements $100K-$500K: 24h human review
│  └─ Time window: 06:00-18:00 UTC (humanitarian hours)
├─ Forecasted for Today (confidence: 0.88):
│  ├─ No new policy changes expected
│  └─ Escalation path: Direct to Policy Council (7 hours average)
└─ Active Alerts:
   └─ None
```

---

### 3.2 Market Context Synthesizer

**Purpose:** Aggregate market data + compute sector-specific context.

```rust
pub struct MarketContext {
    pub timestamp: SystemTime,
    pub assets: Vec<AssetSnapshot>,
    pub sector_signals: Vec<SectorSignal>,
    pub volatility_regime: VolatilityRegime,
    pub geopolitical_impact: GeopoliticalImpact,
}

pub struct AssetSnapshot {
    pub asset_id: String,              // e.g., "BTC", "EUR/USD", "AMZN"
    pub price: f64,
    pub change_24h: f64,               // percentage
    pub change_7d: f64,
    pub volume: f64,
    pub volatility: f32,               // 0-1, 0=stable, 1=extreme
}

pub enum VolatilityRegime {
    Low,       // <1% daily moves, opportunities slow
    Moderate,  // 1-3% moves, normal conditions
    High,      // 3-7% moves, risk/reward balanced
    Extreme,   // >7% moves, black swan territory
}

pub struct GeopoliticalImpact {
    pub ukraine_status: AlertLevel,    // Green/Yellow/Red
    pub israel_status: AlertLevel,
    pub energy_prices: f64,            // WTI crude USD/barrel
    pub market_risk_premium: f32,      // VIX equivalent
    pub expected_volatility: f32,      // Forecast for next 24h
}

pub enum AlertLevel {
    Green,   // <5% expected impact
    Yellow,  // 5-20% expected impact
    Red,     // >20% expected impact
}

pub async fn synthesize_market_context(
    timestamp: SystemTime,
    market_feed: &MarketDataFeed,
    geopolitical_api: &GeopoliticalContext,
) -> Result<MarketContext, ContextError> {
    // 1. Fetch latest market data
    let assets = market_feed.fetch_assets(&["BTC", "USD", "AMZN", "EUR/USD"]).await?;
    
    // 2. Compute sector signals (momentum, mean reversion, volatility clusters)
    let sectors = compute_sector_signals(&assets);
    
    // 3. Assess volatility regime
    let vol_regime = assess_volatility_regime(&assets);
    
    // 4. Fetch geopolitical context
    let geo = geopolitical_api.current_status(timestamp).await?;
    
    Ok(MarketContext {
        timestamp,
        assets: assets.into(),
        sector_signals: sectors,
        volatility_regime: vol_regime,
        geopolitical_impact: geo,
    })
}
```

**Example Output:**

```
Market Context (2026-06-04 06:00 UTC):
├─ Asset Snapshot:
│  ├─ BTC: $45,200 (+5.2% 24h, -0.8% 7d, vol=0.34)
│  └─ EUR/USD: 1.095 (-1.1% 24h, +2.3% 7d, vol=0.18)
├─ Sector Signals:
│  ├─ Energy: High momentum (Brent +8.2% week)
│  └─ Tech: Mean reversion setup (oversold 7d)
├─ Volatility Regime: High (3.2% avg daily moves)
└─ Geopolitical:
   ├─ Ukraine: Yellow (missile activity up 15%)
   ├─ Israel: Yellow (border tensions rising)
   └─ Market Risk Premium: 0.18 (elevated, expect 4-5% volatility today)
```

---

### 3.3 Decision Window Calculator

**Purpose:** Compute optimal action windows based on policy + market constraints.

```rust
pub struct DecisionWindow {
    pub window_id: Uuid,
    pub action_type: ActionType,       // Settlement, Trade, Escalation, etc.
    pub start_time: SystemTime,
    pub end_time: SystemTime,
    pub approval_probability: f32,     // 0.0-1.0 (likelihood of approval)
    pub expected_settlement_time: Duration,
    pub reason: String,
    pub confidence: f32,
}

pub enum ActionType {
    Settlement,
    Trade,
    Escalation,
    DataAccess,
    ResourceCreation,
}

pub async fn calculate_decision_windows(
    governance: &GovernanceSnapshot,
    market: &MarketContext,
    forecaster: &TimeCapsuleForecaster,
    sovereign_id: Uuid,
) -> Result<Vec<DecisionWindow>, WindowError> {
    let mut windows = Vec::new();
    
    // Window 1: Settlements within daily budget
    if governance.daily_budget.remaining > 1000 {
        let (approval_prob, settlement_time) = 
            forecaster.settlement_approval_window(governance).await?;
        
        windows.push(DecisionWindow {
            window_id: Uuid::new_v4(),
            action_type: ActionType::Settlement,
            start_time: SystemTime::now(),
            end_time: SystemTime::now() + Duration::from_secs(86400),  // 24h
            approval_probability: approval_prob,
            expected_settlement_time: settlement_time,
            reason: "Within daily budget and tier 6 approval window".to_string(),
            confidence: governance.governance_confidence,
        });
    }
    
    // Window 2: Escalations (always open, but approval slow)
    windows.push(DecisionWindow {
        window_id: Uuid::new_v4(),
        action_type: ActionType::Escalation,
        start_time: SystemTime::now(),
        end_time: SystemTime::now() + Duration::from_secs(86400),
        approval_probability: 0.5,  // 50% chance of approval
        expected_settlement_time: Duration::from_secs(7 * 3600),  // 7 hours
        reason: "Escalation always available; average 7h approval + governance review".to_string(),
        confidence: 0.75,
    });
    
    Ok(windows)
}
```

**Example Output:**

```
Decision Windows for 2026-06-04:
├─ Settlement Window:
│  ├─ Open: 2026-06-04 06:00 - 18:00 UTC
│  ├─ Approval Probability: 0.95 (within budget + time window)
│  ├─ Expected Time: 2 minutes (auto-approve for <$10K)
│  └─ Remaining Budget: $50,000
├─ Escalation Window:
│  ├─ Open: 24 hours
│  ├─ Approval Probability: 0.50
│  ├─ Expected Time: 7 hours (policy council review)
│  └─ Cost: 1% AP2 fee (policy escalation tax)
└─ No Trading Window Today:
   └─ Reason: Geopolitical alert level Red; markets volatile >5%
```

---

### 3.4 Anomaly & Alert Synthesizer

**Purpose:** Aggregate detected anomalies + generate actionable alerts.

```rust
pub struct AnomalySummary {
    pub behavioral_anomalies: Vec<BehavioralAnomaly>,
    pub market_anomalies: Vec<MarketAnomaly>,
    pub policy_drift_alerts: Vec<PolicyDriftAlert>,
    pub security_alerts: Vec<SecurityAlert>,
    pub total_risk_score: f32,         // 0.0-1.0
}

pub struct BehavioralAnomaly {
    pub anomaly_type: String,          // "Intent shift", "Request rate spike"
    pub severity: AlertSeverity,
    pub detection_time: SystemTime,
    pub description: String,
    pub recommended_action: String,
}

pub struct MarketAnomaly {
    pub anomaly_type: String,          // "Flash crash", "Volatility spike"
    pub affected_assets: Vec<String>,
    pub anomaly_score: f32,
    pub impact_on_decisions: String,
}

pub struct PolicyDriftAlert {
    pub drift_score: f32,              // From TimeCapsule
    pub affected_decision_types: Vec<ActionType>,
    pub severity: AlertSeverity,
    pub recommendation: String,
}

pub struct SecurityAlert {
    pub alert_type: String,            // From AntiYouCapsule
    pub triggered_count: u32,
    pub action_recommendations: String,
}

pub enum AlertSeverity {
    Info,      // Monitor, no action needed
    Warning,   // Review before major decisions
    Critical,  // Take action immediately
}

pub async fn synthesize_anomalies(
    sovereign_id: Uuid,
    anti_you: &AntiYouCapsuleEngine,
    timecapsule: &TimeCapsuleForecaster,
    behavioral_firewall: &BehavioralFirewall,
) -> Result<AnomalySummary, AnomalyError> {
    // 1. Fetch behavioral anomalies from firewall
    let behavioral = behavioral_firewall.get_anomalies(sovereign_id).await?;
    
    // 2. Fetch security detections from AntiYouCapsule
    let security = anti_you.recent_detections(sovereign_id).await?;
    
    // 3. Fetch policy drift from TimeCapsule
    let drift = timecapsule.recent_drift_alerts(sovereign_id).await?;
    
    // 4. Compute total risk score (weighted sum)
    let total_risk = compute_total_risk(&behavioral, &security, &drift);
    
    Ok(AnomalySummary {
        behavioral_anomalies: behavioral,
        security_alerts: security,
        policy_drift_alerts: drift,
        total_risk_score: total_risk,
        ..Default::default()
    })
}
```

---

### 3.5 Game-Theoretic Recommendation Engine

**Purpose:** Suggest optimal actions based on governance + market state + game theory.

```rust
pub struct Recommendation {
    pub recommendation_id: Uuid,
    pub action: String,                // "Execute settlement now (90% approval window)"
    pub rationale: String,
    pub risk_level: f32,               // 0.0-1.0
    pub reward_potential: f32,         // 0.0-1.0
    pub optimal_timing: Option<(SystemTime, SystemTime)>,  // (start, end)
    pub confidence: f32,
    pub alternative_actions: Vec<String>,
}

pub async fn generate_recommendations(
    governance: &GovernanceSnapshot,
    market: &MarketContext,
    windows: &[DecisionWindow],
    anomalies: &AnomalySummary,
    sovereign_profile: &SovereignProfile,
) -> Result<Vec<Recommendation>, RecommendationError> {
    let mut recommendations = Vec::new();
    
    // Recommendation 1: Settlement timing
    if let Some(settlement_window) = windows.iter().find(|w| w.action_type == ActionType::Settlement) {
        if anomalies.total_risk_score < 0.3 && settlement_window.approval_probability > 0.8 {
            recommendations.push(Recommendation {
                action: "Execute settlement now: 90%+ approval, low risk".to_string(),
                rationale: "Within approval window, anomaly score low, governance stable".to_string(),
                risk_level: 0.1,
                reward_potential: 0.8,  // Funding NGO operations
                optimal_timing: Some((settlement_window.start_time, settlement_window.end_time)),
                confidence: 0.92,
                ..Default::default()
            });
        }
    }
    
    // Recommendation 2: Escalation strategy
    if governance.tier < 7 && market.volatility_regime == VolatilityRegime::Moderate {
        recommendations.push(Recommendation {
            action: "Consider tier escalation: Market conditions favorable for advancement".to_string(),
            rationale: "Tier 7 unlocks larger settlements; market not in extreme vol regime".to_string(),
            risk_level: 0.3,
            reward_potential: 0.6,
            confidence: 0.65,
            ..Default::default()
        });
    }
    
    // Recommendation 3: Risk mitigation
    if anomalies.total_risk_score > 0.5 {
        recommendations.push(Recommendation {
            action: "Defer major decisions: Multiple anomalies detected".to_string(),
            rationale: "Policy drift, behavioral anomalies, market volatility elevated".to_string(),
            risk_level: 0.8,
            reward_potential: 0.0,
            confidence: 0.85,
            alternative_actions: vec!["Wait 6 hours for clarity".to_string()],
        });
    }
    
    Ok(recommendations)
}
```

---

## 4. Implementation Plan

### Phase 3b: Briefing Generation (Weeks 3-4, Aug 15-29)

**Week 3: Core Components (3.1-3.3)**
- [ ] `siss-market-vision/src/governance_snapshot.rs` — 400 LOC
  - 10 unit tests
- [ ] `siss-market-vision/src/market_context.rs` — 350 LOC
  - 10 unit tests
- [ ] `siss-market-vision/src/decision_windows.rs` — 300 LOC
  - 8 unit tests

**Week 4: Recommendation & Output (3.4-3.5)**
- [ ] `siss-market-vision/src/anomaly_synthesizer.rs` — 300 LOC
  - 8 unit tests
- [ ] `siss-market-vision/src/recommendation_engine.rs` — 350 LOC
  - 10 unit tests
- [ ] `siss-market-vision/src/briefing_formatter.rs` — 250 LOC
  - Markdown + JSON output
  - Ed25519 signing
  - 8 unit tests

**Success Criteria:**
- [ ] All 54 tests passing
- [ ] <2 sec latency per briefing
- [ ] 100K+ concurrent briefing generation
- [ ] Market data integration complete

---

## 5. Test Suite

### Unit Tests (54 total)

**governance_snapshot.rs (10 tests)**
```
✓ test_snapshot_includes_tier_trust
✓ test_daily_budget_tracking
✓ test_current_constraints_extraction
✓ test_forecasted_constraints_from_timecapsule
✓ test_active_alerts_aggregation
✓ test_snapshot_with_no_alerts
✓ test_snapshot_serialization
... [3 more]
```

**market_context.rs (10 tests)**
```
✓ test_asset_snapshot_pricing
✓ test_volatility_regime_classification
✓ test_sector_signal_detection
✓ test_geopolitical_impact_scoring
✓ test_market_data_feed_integration
... [5 more]
```

**decision_windows.rs (8 tests)**
```
✓ test_settlement_window_calculation
✓ test_escalation_window_always_open
✓ test_approval_probability_scoring
✓ test_settlement_time_estimation
... [4 more]
```

**anomaly_synthesizer.rs (8 tests)**
```
✓ test_behavioral_anomaly_aggregation
✓ test_market_anomaly_detection
✓ test_policy_drift_alert_synthesis
✓ test_security_alert_compilation
✓ test_total_risk_score_computation
... [3 more]
```

**recommendation_engine.rs (10 tests)**
```
✓ test_settlement_timing_recommendation
✓ test_escalation_strategy_recommendation
✓ test_risk_mitigation_recommendation
✓ test_peer_benchmark_comparison
✓ test_confidence_scoring
... [5 more]
```

**briefing_formatter.rs (8 tests)**
```
✓ test_markdown_generation
✓ test_json_export
✓ test_ed25519_signing
✓ test_briefing_completeness
... [4 more]
```

### Integration Tests (10 tests)

```
✓ test_end_to_end_briefing_generation
✓ test_timecapsule_integration
✓ test_behavioral_firewall_integration
✓ test_anti_you_integration
✓ test_100k_concurrent_briefings_per_day
✓ test_latency_lt_2_sec_p99
✓ test_market_feed_failure_graceful_degradation
✓ test_daily_cron_execution
... [2 more]
```

---

## 6. Success Criteria & Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **Latency** | <2 sec p99 per briefing | Benchmark |
| **Accuracy** | 95%+ vs. human analysts | Comparison study |
| **Concurrent Generation** | 100K+ briefings/day | Load test |
| **Feature Completeness** | All 5 sections present | QA checklist |
| **Test Coverage** | 64+ tests (54 unit + 10 int) | Test report |
| **Market Data Integration** | 95%+ uptime | SLA monitoring |
| **Personalization** | 100% (by tier + domain) | Spot checks |

---

## 7. Briefing Example Output

```markdown
# Market Vision Daily Briefing
## Tier 6 NGO (Ukraine) — 2026-06-04

Generated: 2026-06-04 06:00 UTC | Confidence: 0.88 | Risk Level: Medium

---

### 1. Governance Snapshot
- **Current Status:** Tier 6 | Trust 92/100
- **Daily Settlement Budget:** $50,000 remaining
- **Forecasted Constraints:** No changes expected (confidence 0.88)
- **Active Alerts:** None
- **Escalation Path:** Direct to Policy Council (avg 7h)

### 2. Market Context
- **Volatility Regime:** High (3.2% avg daily)
- **BTC:** $45,200 (+5.2% 24h)
- **USD/EUR:** 1.095 (-1.1% 24h)
- **Geopolitical:** Ukraine Yellow, Israel Yellow
- **Market Risk Premium:** 0.18 (elevated)

### 3. Decision Windows
#### Settlement Window
- **Open:** 06:00-18:00 UTC (humanitarian hours)
- **Approval Probability:** 0.95
- **Expected Time:** 2 min (auto-approve <$10K)
- **Action:** EXECUTE NOW if ready

#### Escalation Window
- **Open:** 24 hours
- **Approval Probability:** 0.50
- **Expected Time:** 7 hours
- **Cost:** 1% AP2 fee

### 4. Anomalies & Alerts
- **Behavioral:** None detected
- **Market:** Volatility spike in energy sector (+8.2% Brent)
- **Policy Drift:** No new changes (stable policy)
- **Security:** No threats detected
- **Risk Score:** 0.22 (Low)

### 5. Recommendations
1. **Execute settlements now** (confidence 0.92)
   - Within approval window | Budget available | Low risk
2. **Monitor energy sector** (confidence 0.78)
   - Ukraine-relevant; price volatility up 8.2%
3. **Defer escalation** (confidence 0.65)
   - Market volatility elevated; wait for clarity

---

**Briefing Signature:** Ed25519 signed by Market Vision (immutable audit trail)
**Next Update:** 2026-06-05 06:00 UTC
```

---

## 8. Governance Gates

**Gate 1 (Aug 1):** Spec approved, data sources confirmed → proceed to Week 3

**Gate 2 (Aug 22):** Unit tests 54/54 passing, latency <2 sec → proceed to integration

**Gate 3 (Aug 29):** Integration tests 10/10 passing, briefing accuracy validated → proceed to beta

---

**Prepared for:** Phase 3 Beta Launches (Aug 1+)  
**Architecture Lock:** Real-time synthesis pipeline, personalization engine, game-theoretic recommendations  
**Next Phase:** Sovereign Radar integration (infrastructure for briefing distribution)
