# Phase 23: Multi-View Intelligence Cockpit — Projection Schema Specification

**Date:** 2026-05-11  
**Status:** Specification  
**Authors:** Claude Haiku 4.5  

---

## 1. Executive Summary

The Multi-View Intelligence Cockpit operationalizes Context Cartography by applying three distinct π (projection) operators to the unified intelligence graph (Phase 22). Each projection transforms the same underlying data into different views for the Operator.

**Three projection schemas:**
1. **Root-Cause View (5 Whys)** — Backward lineage from anomaly
2. **Threat Anticipation View** — Forward blast-radius analysis
3. **Rapid SWOT/Scenario View** — Isolated subgraph of sovereigns + settlement status

---

## 2. REST API Endpoint Specifications

### Base URL
```
GET /api/graph/projections/{view_type}
```

### Endpoints

#### 2.1 Root-Cause View
```
GET /api/graph/projections/root-cause/{anomaly_id}?depth=5&include_settlement=true
```

**Query Parameters:**
- `anomaly_id` (required): UUID of TrustAnomalyPatternNode
- `depth` (optional, default=5): Max edge traversal depth (5 Whys = 5 hops)
- `include_settlement` (optional, default=true): Include settlement ledger info
- `cluster_id` (optional): Filter by Leiden cluster ID from GitNexus

**Response:** 200 OK

#### 2.2 Threat Anticipation View
```
GET /api/graph/projections/threat-anticipation/{anomaly_id}?blast_radius_depth=3&include_clusters=true
```

**Query Parameters:**
- `anomaly_id` (required): UUID of TrustAnomalyPatternNode
- `blast_radius_depth` (optional, default=3): Max forward traversal depth
- `include_clusters` (optional, default=true): Include Leiden cluster groupings
- `execution_flow_ids` (optional): Comma-separated flow IDs from GitNexus

**Response:** 200 OK

#### 2.3 Rapid SWOT/Scenario View
```
GET /api/graph/projections/swot-scenario/{source_sovereign_id}?time_window_days=7&settlement_status=all
```

**Query Parameters:**
- `source_sovereign_id` (required): UUID of source SovereignNode
- `time_window_days` (optional, default=7): Only anomalies from last N days
- `settlement_status` (optional, default=all): Filter by settlement (pending|settled|disputed|all)
- `include_probation_state` (optional, default=true): Include probation/quarantine status

**Response:** 200 OK

---

## 3. JSON Response Schemas

### 3.1 Root-Cause View Response

```json
{
  "anomaly_id": "uuid",
  "view_type": "root-cause",
  "generated_at": "2026-05-11T10:30:00Z",
  "root_cause_chain": [
    {
      "depth": 0,
      "node": {
        "id": "uuid",
        "type": "TrustAnomalyPatternNode",
        "properties": {
          "source_id": "uuid",
          "target_id": "uuid",
          "occurrence_count": 3,
          "latest_score": 15,
          "dominant_cause": "decay_collapse",
          "first_detected": "2026-05-10T10:00:00Z",
          "last_detected": "2026-05-11T09:00:00Z"
        }
      },
      "incoming_edge": null
    },
    {
      "depth": 1,
      "node": {
        "id": "uuid",
        "type": "SovereignNode",
        "properties": {
          "sovereign_id": "uuid",
          "status": "probation",
          "tier": 2
        }
      },
      "incoming_edge": {
        "type": "EXHIBITS",
        "confidence": 1.0,
        "created_at": "2026-05-11T10:15:00Z"
      }
    },
    {
      "depth": 2,
      "node": {
        "id": "uuid",
        "type": "RecoveryNode",
        "properties": {
          "event_type": "probation_to_recovery",
          "weeks_elapsed": 2,
          "timestamp": "2026-05-05T10:00:00Z"
        }
      },
      "incoming_edge": {
        "type": "DEPENDS_ON",
        "confidence": 0.95,
        "evidence": { "rule": "recovery_tracking" }
      }
    }
  ],
  "settlement_info": {
    "source_sovereign_settlement_status": "pending",
    "target_sovereign_settlement_status": "settled",
    "total_tokens_at_risk": 5000
  },
  "gitNexus_enrichment": {
    "leiden_cluster_id": "cluster_42",
    "cluster_members_count": 7,
    "execution_flow_ids": ["flow-001", "flow-002"]
  }
}
```

### 3.2 Threat Anticipation View Response

```json
{
  "anomaly_id": "uuid",
  "view_type": "threat-anticipation",
  "generated_at": "2026-05-11T10:30:00Z",
  "source_anomaly": {
    "id": "uuid",
    "source_sovereign_id": "uuid",
    "occurrence_count": 5,
    "latest_score": 10
  },
  "blast_radius": {
    "direct_impact": [
      {
        "depth": 1,
        "target_sovereign_id": "uuid",
        "relationship_type": "TRUSTS",
        "confidence": 0.85,
        "risk_level": "high",
        "reason": "direct_trust_edge",
        "settlement_at_risk": 2500
      }
    ],
    "secondary_impact": [
      {
        "depth": 2,
        "target_sovereign_id": "uuid",
        "relationship_type": "TRANSITIVE_TRUSTS",
        "confidence": 0.65,
        "risk_level": "medium",
        "reason": "transitive_through_[intermediate_id]",
        "settlement_at_risk": 1000
      }
    ],
    "total_sovereigns_affected": 12,
    "total_tokens_at_risk": 8500
  },
  "gitNexus_enrichment": {
    "leiden_clusters_affected": ["cluster_42", "cluster_15", "cluster_88"],
    "execution_flows_impacted": ["flow-001", "flow-003", "flow-005"],
    "affected_cluster_member_count": 18
  },
  "recommended_mitigations": [
    {
      "action": "revoke_explicit_trust_edges",
      "target_count": 3,
      "impact": "prevents_further_transitive_spread"
    },
    {
      "action": "accelerate_settlement",
      "target_count": 5,
      "tokens_protected": 5000
    }
  ]
}
```

### 3.3 Rapid SWOT/Scenario View Response

```json
{
  "primary_sovereign_id": "uuid",
  "view_type": "swot-scenario",
  "time_window": "7 days",
  "generated_at": "2026-05-11T10:30:00Z",
  "primary_sovereign": {
    "id": "uuid",
    "status": "active",
    "tier": 3,
    "current_score": 85,
    "recent_anomaly_count": 2,
    "settlement_status": "settled"
  },
  "related_sovereigns": [
    {
      "sovereign_id": "uuid",
      "relationship_to_primary": "TRUSTS",
      "relationship_confidence": 0.90,
      "status": "active",
      "tier": 2,
      "recent_anomaly_count": 0,
      "settlement_status": "pending",
      "settlement_amount": 1500,
      "leiden_cluster": "cluster_42"
    },
    {
      "sovereign_id": "uuid",
      "relationship_to_primary": "TRUSTS",
      "relationship_confidence": 0.72,
      "status": "probation",
      "tier": 1,
      "recent_anomaly_count": 4,
      "settlement_status": "disputed",
      "settlement_amount": 2000,
      "leiden_cluster": "cluster_42"
    }
  ],
  "swot_analysis": {
    "strengths": [
      {
        "type": "settlement_status",
        "description": "Primary has settled all invoices (0 pending)"
      },
      {
        "type": "trust_density",
        "description": "Well-connected cluster with avg confidence 0.81"
      }
    ],
    "weaknesses": [
      {
        "type": "anomaly_clustering",
        "description": "2 sovereigns in cluster show recent anomalies"
      },
      {
        "type": "probation_exposure",
        "description": "Direct trust to probation sovereign (risk: 2000 tokens)"
      }
    ],
    "opportunities": [
      {
        "type": "settlement_acceleration",
        "description": "5 pending settlements (3500 tokens) ready for close-out"
      }
    ],
    "threats": [
      {
        "type": "transitive_anomaly_spread",
        "description": "2 anomalies could cascade through TRUSTS edges"
      }
    ]
  },
  "scenario_projections": [
    {
      "scenario": "settle_all_pending",
      "outcome": "tokens_recovered: 3500, cluster_health_improvement: +8%"
    },
    {
      "scenario": "revoke_probation_edge",
      "outcome": "tokens_protected: 2000, trust_network_reduced: 1 edge"
    }
  ]
}
```

---

## 4. Transformation Pipeline

### Data Flow: Synthesize Pattern → Projection

```
synthesize_pattern() writes TrustAnomalyPatternNode + EXHIBITS edge
                    ↓
                Graph dual-write succeeds
                    ↓
         /api/graph/projections/{view_type} query invoked
                    ↓
    SELECT * FROM graph_entities/relationships
            WHERE conditions match projection schema
                    ↓
    Traverse edges (Root-Cause: backward; Threat: forward; SWOT: sideways)
                    ↓
    Enrich with GitNexus (Leiden clusters, execution flows)
                    ↓
    Aggregate settlement/probation/quarantine status
                    ↓
    Return JSON response
```

### Filtering Rules

**Root-Cause View:**
- Include all EXHIBITS, DEPENDS_ON, TRIGGERS edges in backward direction
- Max depth: user-specified (default 5)
- Time window: no restriction (full history)

**Threat Anticipation View:**
- Include all TRUSTS edges in forward direction
- Filter to TRUSTS confidence ≥ 0.5 (configurable)
- Max depth: user-specified (default 3)
- Exclude revoked edges (check revocation_certificate timestamp)

**SWOT/Scenario View:**
- Time window: last N days (default 7)
- Anomaly count: from Phase 22 occurrence_count
- Settlement filter: by status (pending/settled/disputed)
- Include only direct trust relationships (depth 1)

---

## 5. Performance Requirements

| View | Latency SLO | Cache TTL | Query Type |
|------|-------------|-----------|-----------|
| Root-Cause | 500ms p95 | 5 min | Graph traversal (5 hops max) |
| Threat Anticipation | 800ms p95 | 3 min | Graph traversal (3 hops max) + settlement lookup |
| SWOT/Scenario | 300ms p95 | 10 min | Direct SQL query + aggregation |

**View Switching:** Cockpit must switch views in < 200ms (data already cached, UI rendering only)

---

## 6. Caching Strategy

### Layer 1: Query Result Cache (Redis)
- Key: `projection:{view_type}:{anomaly_id}:{query_hash}`
- TTL: Per table above (Root-Cause 5min, Threat 3min, SWOT 10min)
- Invalidation: When synthesize_pattern() writes new TrustAnomalyPatternNode

### Layer 2: Settlement Ledger Cache
- Key: `settlement:{source_id}:{target_id}`
- TTL: 1 hour (settlement status changes infrequently)
- Invalidation: On settlement_ledger table INSERT/UPDATE

### Layer 3: GitNexus Enrichment Cache
- Key: `gitNexus:{sovereign_id}:{cluster_or_flow}`
- TTL: 15 minutes (Leiden algorithm re-runs periodically)
- Invalidation: Manual via GitNexus API webhook

---

## 7. Required Data Models (Backend)

### From Phase 22 Intelligence Graph
- `TrustAnomalyPatternNode` (source_id, target_id, occurrence_count, latest_score, dominant_cause, first_detected, last_detected)
- `SovereignNode` (sovereign_id, status, tier)
- `RecoveryNode`, `ViolationNode`, `ScoringNode` (optional for deep traversals)
- Edges: EXHIBITS, DEPENDS_ON, TRIGGERS, TRUSTS

### From Settlement Ledger (Phase 9)
- `settlement_ledger` table (source_id, target_id, status, amount)

### From GitNexus (External)
- Leiden cluster assignments (community detection)
- Execution flow IDs (execution lineage)

---

## 8. Future Extensions

1. **Real-time SSE streaming** — Push projection updates to cockpit on new synthesize_pattern() writes
2. **Custom projection schemas** — Operator defines ad-hoc projection parameters (depth, filters, aggregations)
3. **Projection composition** — Combine multiple views (e.g., "show SWOT but highlight threats from Root-Cause view")
4. **Audit trail** — Log all projection queries for compliance/investigation

---

## 9. Success Criteria

✓ All three endpoints respond in SLO latency  
✓ JSON response structures match schemas exactly  
✓ Leiden clusters render correctly in UI  
✓ Settlement status refreshes accurately  
✓ View switching completes in < 200ms  
✓ Anomalies older than time_window are excluded  
✓ Revoked trust edges are filtered out  
✓ Cache invalidation prevents stale data  
✓ Operator can seamlessly toggle between three views  

---

## 10. References

- **Phase 22b Spec:** `docs/superpowers/specs/2026-05-11-phase22b-graph-dual-write-design.md`
- **Phase 9 Settlement:** `docs/architecture/` (settlement ledger)
- **GitNexus MCP:** Leiden algorithm, execution flow tracing
- **Intelligence Graph Repo:** `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs`

---

**Specification Ready for:** Plan Mode (UI/UX Design)  
**Date:** 2026-05-11
