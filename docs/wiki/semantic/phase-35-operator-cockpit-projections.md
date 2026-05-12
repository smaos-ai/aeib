# Phase 35: Operator Cockpit Projection Layer — π⁺ Forward Projection Schemas

**Status:** DESIGN (2026-05-12)  
**Tests:** 0/12 pending (failing)  
**Implementation:** Ready for Inversion Development

---

## Overview

Phase 35 projects **Semantic tier signals** (Phase 34's crystallized patterns) onto the Operator Cockpit via the **π⁺ (Forward Projection) operator**. The π⁺ operator transforms multidimensional graph intelligence across the G↔V boundary (Graph ↔ Visualization) according to explicit projection schemas that specify format, modality, resolution, and structural dimensionality.

Phase 34 built the intelligence. Phase 35 makes it **operational**: exposing three distinct projection dimensions that translate raw graph nodes into actionable UI dashboards for human operators.

---

## The π⁺ Forward Projection Operator

**Definition:**
```
π⁺: (Graph Entity, Projection Schema) → (REST/GraphQL Response, Operator Context)
```

**Physics:**
- Reads from intelligence graph: High-confidence Semantic tier signals + select Episodic patterns
- Filters: `WHERE tier == "semantic" OR confidence > threshold`
- Transforms: Graph properties → UI schema via projection rules
- Delivers: Structured JSON for visualization, decision support, tactical dashboards

**Projection Rules:**
1. **Dimensionality Reduction:** N-dimensional signal properties → M-dimensional UI fields
2. **Confidence Thresholding:** Only Semantic (or high-confidence Episodic) signals surface
3. **Modality Translation:** Graph edges become causal chains, risk scores, or threat vectors
4. **Temporal Coherence:** Timestamps and decay state preserved for operator decision context

---

## Three Projection Dimensions

### 1. Root-Cause Projection (π⁺_RC)

**Purpose:** Trace anomaly chains backward to their origin node, exposing causality.

**HTTP Endpoint:**
```
GET /api/graph/projections/root-cause/:anomaly_id?depth=5
```

**π⁺_RC Schema:**
```json
{
    "anomaly_id": "<uuid>",
    "detected_at": "2026-05-12T14:32:00Z",
    "anomaly_type": "dispute_spam",
    "sovereign_id": "<uuid>",
    "confidence": 0.92,
    "tier": "semantic",
    "root_cause_chain": [
        {
            "depth": 0,
            "node_id": "<uuid>",
            "label": "AnomalyEventNode",
            "anomaly_type": "dispute_spam",
            "confidence": 0.92,
            "created_at": "2026-05-12T14:32:00Z"
        },
        {
            "depth": 1,
            "node_id": "<uuid>",
            "label": "AnomalyChainNode",
            "chain_type": "timeout_spam→dispute_spam",
            "confidence": 0.87,
            "relationship": "LEADS_TO",
            "created_at": "2026-05-12T10:15:00Z"
        },
        {
            "depth": 2,
            "node_id": "<uuid>",
            "label": "AnomalyEventNode",
            "anomaly_type": "timeout_spam",
            "confidence": 0.89,
            "relationship": "PRECEDED_BY",
            "created_at": "2026-05-12T08:45:00Z"
        }
    ],
    "operator_insight": "Timeouts escalated to disputes; root cause: resource exhaustion detected 30 hours prior"
}
```

**Query Logic:**
- Start from AnomalyEventNode with id=anomaly_id
- Traverse LEADS_TO, EXHIBITS, DEPENDS_ON edges backward (max depth=5, clamped)
- For each node: Include label, properties (confidence, anomaly_type, chain_type), relationship_type
- Filter: Only include nodes where confidence >= 0.70 (Semantic or validated Episodic)
- Order: Chronological from detected anomaly backward to origin

**Tests (4):**
1. `test_root_cause_chain_depth_limit_respected` — Clamped at 5, returns exactly 5 or fewer nodes
2. `test_root_cause_chain_filters_low_confidence_nodes` — Nodes with confidence < 0.70 excluded
3. `test_root_cause_chain_preserves_relationship_edges` — LEADS_TO, EXHIBITS edges labeled correctly
4. `test_root_cause_chain_empty_when_anomaly_not_found` — 404 when anomaly_id not in graph

---

### 2. Threat Anticipation Projection (π⁺_TA)

**Purpose:** Forward-cast high-confidence Episodic patterns before they strike, identifying downstream sovereigns at risk.

**HTTP Endpoint:**
```
GET /api/graph/projections/threat-anticipation/:source_sovereign_id?blast_radius_depth=3
```

**π⁺_TA Schema:**
```json
{
    "source_sovereign_id": "<uuid>",
    "source_sovereign_name": "Sovereign-42",
    "anomaly_patterns": [
        {
            "pattern_id": "<uuid>",
            "pattern_type": "dispute_spam→revocation_pattern",
            "confidence": 0.88,
            "tier": "semantic",
            "occurrence_count": 23,
            "risk_level": "High"
        }
    ],
    "affected_sovereigns": [
        {
            "sovereign_id": "<uuid>",
            "sovereign_name": "Sovereign-15",
            "hybrid_trust_score": 72,
            "settled_invoice_count": 145,
            "tokens_at_risk": 5000000,
            "risk_level": "High",
            "rationale": "Connected via delegation edges; pattern impact radius 2 hops"
        },
        {
            "sovereign_id": "<uuid>",
            "sovereign_name": "Sovereign-8",
            "hybrid_trust_score": 85,
            "settled_invoice_count": 312,
            "tokens_at_risk": 2500000,
            "risk_level": "Medium",
            "rationale": "Secondary blast radius; mitigation via isolation recommended"
        }
    ],
    "total_tokens_at_risk": 7500000,
    "recommendation": "Preemptive isolation of Sovereign-42; monitor Sovereigns 15, 8 for early anomaly signals"
}
```

**Query Logic:**
- Start from sovereign_id=source_sovereign_id
- Identify all high-confidence Semantic anomaly patterns for this sovereign
- For each pattern: Predict forward via delegation edges, peer relationships (max depth=3)
- For each affected sovereign: Fetch (hybrid_trust_score, settled_invoice_count, token_balance)
- Risk Level: High (score < 60 OR pattern_confidence > 0.85), Medium (score 60-80 AND pattern_confidence 0.70-0.85), Low (otherwise)
- Sort by tokens_at_risk DESC

**Tests (4):**
1. `test_threat_anticipation_filters_semantic_patterns_only` — Only tier=="semantic" included
2. `test_threat_anticipation_blast_radius_depth_honored` — Delegates 3 hops max
3. `test_threat_anticipation_tokens_at_risk_calculated_correctly` — Sum of affected sovereigns' balances
4. `test_threat_anticipation_risk_level_threshold_applied` — High/Medium/Low mapping correct

---

### 3. Rapid SWOT Projection (π⁺_SWOT)

**Purpose:** Aggregate system health across Semantic signals using Contact-Isolation structural diversity index.

**HTTP Endpoint:**
```
GET /api/graph/projections/swot-scenario/:source_sovereign_id?time_window_days=7
```

**π⁺_SWOT Schema:**
```json
{
    "source_sovereign_id": "<uuid>",
    "time_window_days": 7,
    "snapshot_at": "2026-05-12T15:00:00Z",
    "strengths": [
        {
            "description": "Strong anomaly detection accuracy (precision=0.89 for dispute_spam)",
            "signal_confidence": 0.89,
            "metric": "precision_last_30d"
        },
        {
            "description": "Stable token settlement rate (12 closed invoices past 7 days)",
            "metric": "settled_invoice_count"
        }
    ],
    "weaknesses": [
        {
            "description": "Elevated timeout_spam pattern (15 events, confidence=0.78)",
            "signal_confidence": 0.78,
            "anomaly_type": "timeout_spam"
        },
        {
            "description": "Trust score degradation (85 → 72 past 14 days)",
            "metric": "hybrid_trust_score_delta"
        }
    ],
    "opportunities": [
        {
            "description": "Recovery tier promotion possible (confidence trajectory 0.70 → 0.88, ready for semantic promotion)",
            "signal_confidence": 0.88,
            "action": "Advance to Semantic tier; expect pattern stabilization"
        }
    ],
    "threats": [
        {
            "description": "Peer contagion risk: Connected sovereigns showing correlated anomalies",
            "risk_level": "Medium",
            "affected_count": 3,
            "pattern_type": "dispute_spam→timeout_spam"
        }
    ],
    "diversity_index": 0.72,
    "diversity_interpretation": "Healthy contact-isolation balance; system exhibits resilience"
}
```

**Query Logic:**
- Start from sovereign_id=source_sovereign_id
- Collect Semantic tier signals + high-confidence Episodic (confidence > 0.75) within time_window_days
- **Strengths:** Metrics with positive trajectory (precision improving, settlement count increasing)
- **Weaknesses:** Anomalies with elevated confidence, declining scores
- **Opportunities:** Signals approaching promotion threshold or recovery milestone
- **Threats:** Peer contagion patterns, cascading risks from neighbors
- **Diversity Index:** (Contact Edges / Isolation Edges) ratio, normalized to [0, 1]
  - 0 = fully isolated (concerning)
  - 0.5 = balanced
  - 1.0 = fully connected (concerning)
  - Target: 0.60–0.80 (healthy resilience)

**Tests (4):**
1. `test_swot_strengths_identified_from_positive_metrics` — Improving precision, settlement counts appear
2. `test_swot_weaknesses_identified_from_anomalies` — High-confidence anomalies listed as weaknesses
3. `test_swot_diversity_index_calculated_correctly` — (Contact / Isolation) ratio normalized
4. `test_swot_empty_when_sovereign_not_found` — 404 when sovereign_id not in graph

---

## Integration with Phase 34

### Graph Data Source
- Phase 34 Semantic tier signals (confidence >= 0.90, tier=="semantic")
- Phase 34 Episodic signals (confidence > threshold, validated patterns)
- Intelligence graph edges: LEADS_TO, EXHIBITS, DEPENDS_ON, PREDICTS, PRECEDED_BY
- Signal properties: confidence, tier, last_seen_at, anomaly_type, chain_type, promoted_at

### Filtering Rule
```sql
WHERE (tier = 'semantic' OR confidence > 0.75)
  AND (created_at > NOW() - interval '30 days' OR tier = 'semantic')
```

All projections prioritize Semantic tier signals; include select Episodic only when high-confidence.

---

## REST Endpoint Handlers

**File:** `crates/siss-agent-card/src/projection_handler.rs` (new)

```rust
pub async fn root_cause_handler(
    State(state): State<AgentCardState>,
    Path(anomaly_id): Path<Uuid>,
    Query(params): Query<RootCauseQuery>,
) -> Result<Json<RootCauseResponse>, ProjectionError>

pub async fn threat_anticipation_handler(
    State(state): State<AgentCardState>,
    Path(source_sovereign_id): Path<Uuid>,
    Query(params): Query<ThreatQuery>,
) -> Result<Json<ThreatAnticipationResponse>, ProjectionError>

pub async fn swot_scenario_handler(
    State(state): State<AgentCardState>,
    Path(source_sovereign_id): Path<Uuid>,
    Query(params): Query<SwotQuery>,
) -> Result<Json<SwotScenarioResponse>, ProjectionError>
```

---

## Test Coverage: 12 Tests

**File:** `crates/siss-agent-card/src/projection_handler.rs` (4 tests)
- HTTP handler tests: request validation, response structure, error handling

**File:** `crates/siss-graph-db/src/repo/projection_repo.rs` (8 tests)
- Query logic: filtering, edge traversal, metric computation, diversity index calculation

**All tests:** FAILING (red), awaiting implementation

---

## Non-Goals (Phase 35)

- No GraphQL endpoint (REST only in Phase 35)
- No real-time WebSocket projections (batch only)
- No custom projection schema definitions (π⁺ schemas locked in)
- No visualization rendering (UI is out-of-scope; projections provide JSON)
- No historical backfill (projections query current state, not time-series)

---

## Phase 36+ Vision

**Cockpit Dashboard Integration:**
- Root-cause chains rendered as interactive causal timelines
- Threat anticipation feeds alert triggers and pre-mitigation recommendations
- SWOT projections power strategic dashboards and risk heatmaps

**Feedback Loop Closure:**
- Operator actions on cockpit feed back as Phase 30 feedback
- Interventions captured as behavioral events
- System learns from operator decisions

---

**Last Updated:** 2026-05-12 | **By:** Claude Haiku 4.5
