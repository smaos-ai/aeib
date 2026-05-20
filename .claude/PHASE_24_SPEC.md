# PHASE 24 SPEC — Real-Time Observability & Anomaly Intelligence

**Date:** May 20, 2026  
**Status:** Ready for implementation  
**Pattern:** Test-First (failing tests → green implementation)  
**Workflow:** Writer session → PR → Reviewer session  
**Target:** All features complete + 30+ tests passing

---

## Phase 24 Scope

Complete the observability layer by building real-time projection views, dashboard integration, anomaly correlation, and recovery lifecycle tracking.

### Features (3 total)

1. **Real-Time Projection Views** — Query interface for observability data
2. **Cockpit Dashboard Updates** — UI integration with live metrics
3. **Anomaly Correlation Engine** — Cross-reference patterns + severity scoring

---

## Feature 1: Real-Time Projection Views

### Goal
Expose observability data via `/api/graph/projections/*` endpoints. Support querying agent actions, anomalies, and recovery status in real-time with <100ms latency.

### Data Contracts

#### Endpoint: `GET /api/graph/projections/agent_actions`

**Query Parameters:**
```
sovereign_id: UUID (required)
session_id: UUID (optional, filter by session)
since: DateTime (optional, default: last 1h)
limit: i32 (optional, default: 100, max: 500)
```

**Response Schema:**
```rust
pub struct AgentActionProjection {
    pub action_id: Uuid,                      // AgentActionNode.id
    pub behavior_event_id: Uuid,              // From properties
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,                   // 'process_payment', 'dispute_created', etc.
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,                   // Tokens spent
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

pub struct AgentActionsPageResponse {
    pub actions: Vec<AgentActionProjection>,
    pub total_count: i64,
    pub has_more: bool,
}
```

**Example Request:**
```bash
GET /api/graph/projections/agent_actions?sovereign_id=s123&since=2026-05-20T11:00:00Z&limit=50
```

**Example Response:**
```json
{
  "actions": [
    {
      "action_id": "aac1...",
      "behavior_event_id": "be1...",
      "session_id": "sess...",
      "persona_id": "p1...",
      "sovereign_id": "s123",
      "event_type": "process_payment",
      "tier_before": 60,
      "tier_after": 55,
      "cost_incurred": 500,
      "lineage_safe": true,
      "scored_at": "2026-05-20T12:34:56Z"
    }
  ],
  "total_count": 150,
  "has_more": true
}
```

---

#### Endpoint: `GET /api/graph/projections/anomalies`

**Query Parameters:**
```
sovereign_id: UUID (required)
severity: String (optional, enum: ['low', 'medium', 'high', 'critical'])
anomaly_type: String (optional, enum: ['dispute_spam', 'timeout_spam', 'revocation_pattern'])
since: DateTime (optional, default: last 7d)
limit: i32 (optional, default: 50, max: 200)
```

**Response Schema:**
```rust
pub struct AnomalyProjection {
    pub anomaly_id: Uuid,                     // AnomalyEventNode.id
    pub anomaly_db_id: Uuid,                  // From properties (idempotency key)
    pub sovereign_id: Uuid,
    pub persona_id: Uuid,                     // NEW: extracted from SovereignNode → PersonaNode
    pub anomaly_type: String,                 // 'dispute_spam', etc.
    pub severity: String,                     // 'low', 'medium', 'high', 'critical'
    pub event_count: i64,                     // Events in window
    pub window_hours: i64,
    pub evidence: serde_json::Value,          // Raw evidence data
    pub detected_at: DateTime<Utc>,
    pub recovery_triggered: bool,              // NEW: Did this trigger recovery?
    pub recovery_tier_impact: Option<i16>,    // NEW: What tier change resulted?
}

pub struct AnomaliesPageResponse {
    pub anomalies: Vec<AnomalyProjection>,
    pub total_count: i64,
    pub has_more: bool,
    pub active_recovery_count: i32,           // How many agents in recovery?
}
```

**Severity Mapping (Logic in siss-behavioral-firewall):**
```rust
pub fn calculate_severity(event_count: i64, window_hours: i64) -> String {
    let rate = event_count as f64 / window_hours as f64;
    match rate {
        r if r >= 10.0 => "critical",        // 10+ events/hour
        r if r >= 5.0  => "high",            // 5+ events/hour
        r if r >= 2.0  => "medium",          // 2+ events/hour
        _              => "low",
    }
}
```

---

#### Endpoint: `GET /api/graph/projections/recovery`

**Query Parameters:**
```
sovereign_id: UUID (required)
status: String (optional, enum: ['active', 'completed', 'exited'])
min_weeks_elapsed: i32 (optional)
limit: i32 (optional, default: 25)
```

**Response Schema:**
```rust
pub struct RecoveryProjection {
    pub recovery_id: Uuid,                    // Generated UUID for this recovery instance
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub agent_name: String,                   // From PersonaNode
    pub entry_status: String,                 // 'dispute_spam', 'timeout_spam', etc.
    pub tier_at_entry: i16,
    pub tier_current: i16,
    pub weeks_elapsed: u32,
    pub entry_at: DateTime<Utc>,
    pub expected_exit_at: Option<DateTime<Utc>>, // Estimated (entry + 4 weeks)
    pub recovery_status: String,               // 'active', 'completed', 'exited'
    pub anomaly_count_in_recovery: i64,
    pub last_tier_increase_at: Option<DateTime<Utc>>,
}

pub struct RecoveryPageResponse {
    pub recoveries: Vec<RecoveryProjection>,
    pub total_count: i64,
    pub active_recovery_count: i32,
}
```

---

### Implementation: SQL Queries

#### Query 1: Fetch Recent Agent Actions (in `siss-graph-db/src/repo/projections_repo.rs`)

```sql
SELECT 
    ge.id as action_id,
    (ge.properties->>'behavior_event_id')::uuid as behavior_event_id,
    (ge.properties->>'session_id')::uuid as session_id,
    (ge.properties->>'persona_id')::uuid as persona_id,
    (ge.properties->>'sovereign_id')::uuid as sovereign_id,
    (ge.properties->>'event_type') as event_type,
    (ge.properties->>'tier_before')::smallint as tier_before,
    (ge.properties->>'tier_after')::smallint as tier_after,
    (ge.properties->>'cost_incurred')::bigint as cost_incurred,
    (ge.properties->>'lineage_safe')::boolean as lineage_safe,
    (ge.properties->>'scored_at')::timestamptz as scored_at
FROM graph_entities ge
WHERE ge.label = 'AgentActionNode'
  AND (ge.properties->>'sovereign_id')::uuid = $1
  AND (ge.properties->>'scored_at')::timestamptz > $2
ORDER BY ge.created_at DESC
LIMIT $3;
```

#### Query 2: Fetch Recent Anomalies with Recovery Info

```sql
SELECT 
    ge.id as anomaly_id,
    (ge.properties->>'anomaly_db_id')::uuid as anomaly_db_id,
    (ge.properties->>'sovereign_id')::uuid as sovereign_id,
    pn.id as persona_id,  -- Join from SovereignNode → PersonaNode via graph
    (ge.properties->>'anomaly_type') as anomaly_type,
    (ge.properties->>'severity') as severity,
    (ge.properties->>'event_count')::bigint as event_count,
    (ge.properties->>'window_hours')::bigint as window_hours,
    ge.properties->>'evidence' as evidence,
    (ge.properties->>'detected_at')::timestamptz as detected_at,
    CASE WHEN ra.id IS NOT NULL THEN true ELSE false END as recovery_triggered,
    (SELECT (properties->>'tier_at_entry')::smallint 
     FROM recovery_audit ra2 
     WHERE (ra2.properties->>'anomaly_event_id')::uuid = ge.id 
     LIMIT 1) as recovery_tier_impact
FROM graph_entities ge
LEFT JOIN graph_relations gr ON gr.source_id = ge.id AND gr.relation_type = 'DETECTED_IN'
LEFT JOIN graph_entities sn ON sn.id = gr.target_id AND sn.label = 'SovereignNode'
LEFT JOIN graph_relations gr2 ON gr2.source_id = sn.id AND gr2.relation_type = 'OWNS'
LEFT JOIN graph_entities pn ON pn.id = gr2.target_id AND pn.label = 'PersonaNode'
LEFT JOIN recovery_audit ra ON (ra.properties->>'anomaly_event_id')::uuid = ge.id
WHERE ge.label = 'AnomalyEventNode'
  AND (ge.properties->>'sovereign_id')::uuid = $1
  AND (ge.properties->>'detected_at')::timestamptz > NOW() - INTERVAL '7 days'
ORDER BY ge.created_at DESC
LIMIT $2;
```

#### Query 3: Fetch Recovery Status

```sql
SELECT 
    ra.id as recovery_id,
    pn.id as persona_id,
    sn.id as sovereign_id,
    (pn.properties->>'agent_name') as agent_name,
    (ra.properties->>'entry_reason') as entry_status,
    (ra.properties->>'tier_at_entry')::smallint as tier_at_entry,
    (ra.properties->>'tier_current')::smallint as tier_current,
    EXTRACT(WEEK FROM NOW() - (ra.properties->>'entry_at')::timestamptz)::integer as weeks_elapsed,
    (ra.properties->>'entry_at')::timestamptz as entry_at,
    ((ra.properties->>'entry_at')::timestamptz + INTERVAL '4 weeks') as expected_exit_at,
    CASE 
        WHEN (ra.properties->>'exit_at')::timestamptz IS NULL THEN 'active'
        WHEN (ra.properties->>'exit_status') = 'approved' THEN 'exited'
        ELSE 'completed'
    END as recovery_status,
    (SELECT COUNT(*) FROM graph_entities ge2 
     WHERE ge2.label = 'AnomalyEventNode' 
       AND (ge2.properties->>'detected_at')::timestamptz > (ra.properties->>'entry_at')::timestamptz) as anomaly_count_in_recovery,
    (ra.properties->>'last_tier_increase_at')::timestamptz as last_tier_increase_at
FROM recovery_audit ra
JOIN graph_relations gr ON gr.source_id = ra.persona_id AND gr.relation_type = 'PERSONA_OF'
JOIN graph_entities pn ON pn.id = gr.target_id AND pn.label = 'PersonaNode'
JOIN graph_relations gr2 ON gr2.source_id = pn.id AND gr2.relation_type = 'OWNED_BY'
JOIN graph_entities sn ON sn.id = gr2.target_id AND sn.label = 'SovereignNode'
WHERE sn.id = $1
  AND ($2::text IS NULL OR (ra.properties->>'status') = $2)
ORDER BY ra.created_at DESC
LIMIT $3;
```

---

### Implementation: Rust Module (`siss-graph-db/src/repo/projections_repo.rs`)

```rust
use chrono::{DateTime, Utc};
use serde_json::json;
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, serde::Serialize)]
pub struct AgentActionProjection {
    pub action_id: Uuid,
    pub behavior_event_id: Uuid,
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct AgentActionsPageResponse {
    pub actions: Vec<AgentActionProjection>,
    pub total_count: i64,
    pub has_more: bool,
}

pub async fn fetch_agent_actions(
    pool: &PgPool,
    sovereign_id: Uuid,
    since: Option<DateTime<Utc>>,
    limit: Option<i32>,
) -> Result<AgentActionsPageResponse, sqlx::Error> {
    let since = since.unwrap_or_else(|| Utc::now() - chrono::Duration::hours(1));
    let limit = limit.unwrap_or(100).min(500);

    let actions = sqlx::query_as::<_, AgentActionProjection>(
        r#"
        SELECT 
            ge.id as action_id,
            (ge.properties->>'behavior_event_id')::uuid as behavior_event_id,
            (ge.properties->>'session_id')::uuid as session_id,
            (ge.properties->>'persona_id')::uuid as persona_id,
            (ge.properties->>'sovereign_id')::uuid as sovereign_id,
            (ge.properties->>'event_type') as event_type,
            (ge.properties->>'tier_before')::smallint as tier_before,
            (ge.properties->>'tier_after')::smallint as tier_after,
            (ge.properties->>'cost_incurred')::bigint as cost_incurred,
            (ge.properties->>'lineage_safe')::boolean as lineage_safe,
            (ge.properties->>'scored_at')::timestamptz as scored_at
        FROM graph_entities ge
        WHERE ge.label = 'AgentActionNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'scored_at')::timestamptz > $2
        ORDER BY ge.created_at DESC
        LIMIT $3
        "#
    )
    .bind(sovereign_id)
    .bind(since)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    let total_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*) FROM graph_entities ge
        WHERE ge.label = 'AgentActionNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
        "#
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let has_more = actions.len() as i32 >= limit;

    Ok(AgentActionsPageResponse {
        actions,
        total_count,
        has_more,
    })
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct AnomalyProjection {
    pub anomaly_id: Uuid,
    pub anomaly_db_id: Uuid,
    pub sovereign_id: Uuid,
    pub persona_id: Option<Uuid>,
    pub anomaly_type: String,
    pub severity: String,
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,
    pub detected_at: DateTime<Utc>,
    pub recovery_triggered: bool,
    pub recovery_tier_impact: Option<i16>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct AnomaliesPageResponse {
    pub anomalies: Vec<AnomalyProjection>,
    pub total_count: i64,
    pub has_more: bool,
    pub active_recovery_count: i32,
}

pub async fn fetch_anomalies(
    pool: &PgPool,
    sovereign_id: Uuid,
    severity: Option<&str>,
    anomaly_type: Option<&str>,
    limit: Option<i32>,
) -> Result<AnomaliesPageResponse, sqlx::Error> {
    let limit = limit.unwrap_or(50).min(200);

    let anomalies = sqlx::query_as::<_, AnomalyProjection>(
        r#"
        SELECT 
            ge.id as anomaly_id,
            (ge.properties->>'anomaly_db_id')::uuid as anomaly_db_id,
            (ge.properties->>'sovereign_id')::uuid as sovereign_id,
            NULL::uuid as persona_id,  -- TODO: Join from graph
            (ge.properties->>'anomaly_type') as anomaly_type,
            (ge.properties->>'severity') as severity,
            (ge.properties->>'event_count')::bigint as event_count,
            (ge.properties->>'window_hours')::bigint as window_hours,
            ge.properties->'evidence' as evidence,
            (ge.properties->>'detected_at')::timestamptz as detected_at,
            false as recovery_triggered,  -- TODO: Check recovery_audit table
            NULL::smallint as recovery_tier_impact
        FROM graph_entities ge
        WHERE ge.label = 'AnomalyEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
          AND (ge.properties->>'detected_at')::timestamptz > NOW() - INTERVAL '7 days'
          AND ($2::text IS NULL OR (ge.properties->>'severity') = $2)
          AND ($3::text IS NULL OR (ge.properties->>'anomaly_type') = $3)
        ORDER BY ge.created_at DESC
        LIMIT $4
        "#
    )
    .bind(sovereign_id)
    .bind(severity)
    .bind(anomaly_type)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    let total_count: i64 = sqlx::query_scalar(
        r#"
        SELECT COUNT(*) FROM graph_entities ge
        WHERE ge.label = 'AnomalyEventNode'
          AND (ge.properties->>'sovereign_id')::uuid = $1
        "#
    )
    .bind(sovereign_id)
    .fetch_one(pool)
    .await?;

    let active_recovery_count: i32 = sqlx::query_scalar(
        r#"
        SELECT COUNT(DISTINCT (ra.properties->>'persona_id'))::int
        FROM recovery_audit ra
        WHERE (ra.properties->>'exit_at')::timestamptz IS NULL
        "#
    )
    .fetch_one(pool)
    .await?
    .unwrap_or(0);

    let has_more = anomalies.len() as i32 >= limit;

    Ok(AnomaliesPageResponse {
        anomalies,
        total_count,
        has_more,
        active_recovery_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fetch_agent_actions_returns_recent_only() {
        // TODO: Implement
    }

    #[tokio::test]
    async fn test_fetch_anomalies_filters_by_severity() {
        // TODO: Implement
    }

    #[tokio::test]
    async fn test_has_more_flag_accurate() {
        // TODO: Implement
    }
}
```

---

### Axum Routes (`demo-app/src/main.rs`)

```rust
use axum::{
    routing::get,
    Json, Router,
};
use siss_graph_db::repo::projections_repo;

async fn agent_actions_handler(
    axum::extract::Query(query): axum::extract::Query<AgentActionsQuery>,
) -> Json<projections_repo::AgentActionsPageResponse> {
    let pool = get_pool(); // From app state
    match projections_repo::fetch_agent_actions(
        &pool,
        query.sovereign_id,
        query.since,
        query.limit,
    )
    .await
    {
        Ok(resp) => Json(resp),
        Err(_) => Json(projections_repo::AgentActionsPageResponse {
            actions: vec![],
            total_count: 0,
            has_more: false,
        }),
    }
}

async fn anomalies_handler(
    axum::extract::Query(query): axum::extract::Query<AnomaliesQuery>,
) -> Json<projections_repo::AnomaliesPageResponse> {
    let pool = get_pool();
    match projections_repo::fetch_anomalies(
        &pool,
        query.sovereign_id,
        query.severity.as_deref(),
        query.anomaly_type.as_deref(),
        query.limit,
    )
    .await
    {
        Ok(resp) => Json(resp),
        Err(_) => Json(projections_repo::AnomaliesPageResponse {
            anomalies: vec![],
            total_count: 0,
            has_more: false,
            active_recovery_count: 0,
        }),
    }
}

pub fn projections_routes() -> Router {
    Router::new()
        .route("/agent_actions", get(agent_actions_handler))
        .route("/anomalies", get(anomalies_handler))
        // .route("/recovery", get(recovery_handler))
}
```

---

## Feature 2: Cockpit Dashboard Updates

### Goal
Integrate projection views into Control Tower UI. Display real-time metrics: agent actions feed, anomaly alerts, recovery progress.

### Components

#### 1. Dashboard State (React/TypeScript in `demo-app/frontend/`)

```typescript
interface AgentActionsState {
  actions: AgentActionProjection[];
  loading: boolean;
  error: string | null;
  lastUpdated: Date;
}

interface DashboardState {
  agentActions: AgentActionsState;
  anomalies: AnomaliesState;
  recovery: RecoveryState;
  autoRefresh: boolean;
  refreshInterval: number; // ms
}
```

#### 2. Real-Time Polling Hook

```typescript
// hooks/useProjections.ts
export function useAgentActions(sovereignId: UUID) {
  const [state, setState] = useState<AgentActionsState>({
    actions: [],
    loading: true,
    error: null,
    lastUpdated: new Date(),
  });

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const resp = await fetch(
          `/api/graph/projections/agent_actions?sovereign_id=${sovereignId}&limit=50`
        );
        const data = await resp.json();
        setState({
          actions: data.actions,
          loading: false,
          error: null,
          lastUpdated: new Date(),
        });
      } catch (err) {
        setState((prev) => ({ ...prev, error: String(err), loading: false }));
      }
    };

    fetchActions();
    const interval = setInterval(fetchActions, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [sovereignId]);

  return state;
}
```

#### 3. Dashboard Components

```typescript
// components/AgentActionsFeed.tsx
export function AgentActionsFeed({ sovereignId }: { sovereignId: UUID }) {
  const { actions, loading, lastUpdated } = useAgentActions(sovereignId);

  return (
    <div className="feed">
      <h2>Agent Actions ({actions.length})</h2>
      <p className="updated">Updated: {lastUpdated.toLocaleTimeString()}</p>
      {loading && <p>Loading...</p>}
      {actions.map((action) => (
        <div key={action.action_id} className="action-card">
          <span className="event-type">{action.event_type}</span>
          <span className="cost">Cost: {action.cost_incurred} tokens</span>
          <span className="tier">
            Tier: {action.tier_before} → {action.tier_after}
          </span>
          <time>{new Date(action.scored_at).toLocaleTimeString()}</time>
        </div>
      ))}
    </div>
  );
}

// components/AnomalyAlerts.tsx
export function AnomalyAlerts({ sovereignId }: { sovereignId: UUID }) {
  const { anomalies, active_recovery_count } = useAnomalies(sovereignId);

  return (
    <div className="alerts">
      <h2>Active Anomalies ({anomalies.length})</h2>
      <p className="recovery-badge">
        {active_recovery_count} agents in recovery
      </p>
      {anomalies.map((anomaly) => (
        <div
          key={anomaly.anomaly_id}
          className={`alert alert--${anomaly.severity}`}
        >
          <span className="type">{anomaly.anomaly_type}</span>
          <span className="count">{anomaly.event_count} events</span>
          <span className="window">{anomaly.window_hours}h window</span>
          {anomaly.recovery_triggered && (
            <span className="recovery-badge">Recovery triggered</span>
          )}
        </div>
      ))}
    </div>
  );
}
```

#### 4. Styling (Tailwind)

```css
/* demo-app/frontend/styles/dashboard.css */
.feed {
  @apply p-6 bg-white rounded-lg shadow;
}

.action-card {
  @apply flex justify-between items-center p-4 border-b hover:bg-gray-50;
}

.event-type {
  @apply font-semibold text-blue-600;
}

.cost {
  @apply text-gray-600 text-sm;
}

.tier {
  @apply text-orange-600;
}

.alerts {
  @apply p-6 bg-white rounded-lg shadow;
}

.alert {
  @apply flex justify-between items-center p-4 border-l-4 mb-2;
}

.alert--low {
  @apply border-blue-500 bg-blue-50;
}

.alert--medium {
  @apply border-yellow-500 bg-yellow-50;
}

.alert--high {
  @apply border-orange-500 bg-orange-50;
}

.alert--critical {
  @apply border-red-500 bg-red-50;
}
```

---

## Feature 3: Anomaly Correlation Engine

### Goal
Cross-reference anomalies with agent actions to detect patterns: "When does Agent_A anomalize? Which job types trigger it?"

### Data Model

```rust
pub struct AnomalyCorrelation {
    pub pattern_id: Uuid,
    pub anomaly_type: String,           // 'dispute_spam'
    pub triggering_event_type: String,  // 'process_payment'
    pub correlation_strength: f64,      // 0.0-1.0
    pub sample_size: i32,               // How many samples?
    pub confidence_95th: f64,           // Statistical confidence
    pub detected_at: DateTime<Utc>,
}

pub async fn correlate_anomalies(
    pool: &PgPool,
    sovereign_id: Uuid,
    min_sample_size: i32,
) -> Result<Vec<AnomalyCorrelation>, sqlx::Error> {
    // SQL: Join AgentActionNode + AnomalyEventNode
    // Group by event_type, anomaly_type
    // Calculate correlation: P(anomaly | event_type)
    // Filter: correlation_strength > 0.5 AND sample_size >= min_sample_size
}
```

### SQL: Correlation Query

```sql
SELECT 
    action.event_type,
    anomaly.anomaly_type,
    COUNT(*) as sample_size,
    SUM(CASE WHEN action.scored_at < anomaly.detected_at + INTERVAL '5 minutes' THEN 1 ELSE 0 END)::float 
        / COUNT(*) as correlation_strength
FROM graph_entities action
JOIN graph_entities anomaly 
  ON (action.properties->>'sovereign_id')::uuid = (anomaly.properties->>'sovereign_id')::uuid
WHERE action.label = 'AgentActionNode'
  AND anomaly.label = 'AnomalyEventNode'
  AND (action.properties->>'sovereign_id')::uuid = $1
  AND action.created_at > NOW() - INTERVAL '30 days'
GROUP BY action.event_type, anomaly.anomaly_type
HAVING COUNT(*) >= $2
  AND SUM(CASE WHEN action.scored_at < anomaly.detected_at + INTERVAL '5 minutes' THEN 1 ELSE 0 END)::float / COUNT(*) > 0.5
ORDER BY correlation_strength DESC;
```

---

## Testing Strategy

### Test File Structure

```
crates/siss-graph-db/src/repo/
├── projections_repo.rs           (Real-time views)
├── projections_repo_tests.rs     (15 tests)
├── correlation_repo.rs           (Anomaly correlation)
└── correlation_repo_tests.rs     (10 tests)
```

### Test Suite (projections_repo_tests.rs)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    // Feature 1: Agent Actions
    #[tokio::test]
    async fn test_fetch_agent_actions_returns_recent_only() {
        // Given: 100 actions, some from 1 hour ago, some from 24 hours ago
        // When: fetch_agent_actions(since: 1h)
        // Then: Return only last hour's actions
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_respects_limit() {
        // Given: 500 actions
        // When: fetch_agent_actions(limit: 100)
        // Then: Return exactly 100, has_more=true
    }

    #[tokio::test]
    async fn test_agent_actions_max_limit_capped() {
        // Given: limit=1000 requested
        // When: fetch_agent_actions(limit: 1000)
        // Then: Return max 500 (capped), has_more=true
    }

    #[tokio::test]
    async fn test_agent_actions_total_count_accurate() {
        // Given: 250 total actions, fetched 50 with limit
        // When: Check total_count field
        // Then: total_count = 250 (not capped)
    }

    #[tokio::test]
    async fn test_fetch_agent_actions_includes_all_fields() {
        // Given: Action with all properties populated
        // When: Fetch
        // Then: All fields (behavior_event_id, tier_before, cost_incurred, etc.) present
    }

    // Feature 1: Anomalies
    #[tokio::test]
    async fn test_fetch_anomalies_filters_by_severity() {
        // Given: Mix of low/medium/high/critical anomalies
        // When: fetch_anomalies(severity: 'high')
        // Then: Return only high+critical
    }

    #[tokio::test]
    async fn test_fetch_anomalies_filters_by_type() {
        // Given: dispute_spam, timeout_spam, revocation_pattern anomalies
        // When: fetch_anomalies(anomaly_type: 'dispute_spam')
        // Then: Return only dispute_spam
    }

    #[tokio::test]
    async fn test_fetch_anomalies_active_recovery_count() {
        // Given: 3 active recoveries, 2 completed
        // When: fetch_anomalies()
        // Then: active_recovery_count = 3
    }

    #[tokio::test]
    async fn test_fetch_anomalies_7day_lookback() {
        // Given: Anomalies from 1d ago, 7d ago, 14d ago
        // When: fetch_anomalies()
        // Then: Return only 1d and 7d (not 14d)
    }

    // Feature 1: Recovery Status
    #[tokio::test]
    async fn test_fetch_recovery_calculates_weeks_elapsed() {
        // Given: Recovery entered 14 days ago
        // When: fetch_recovery()
        // Then: weeks_elapsed = 2
    }

    #[tokio::test]
    async fn test_fetch_recovery_expected_exit_4weeks() {
        // Given: Recovery entered 2 weeks ago
        // When: fetch_recovery()
        // Then: expected_exit_at = entry_at + 4 weeks
    }

    #[tokio::test]
    async fn test_fetch_recovery_status_transitions() {
        // Given: Active recovery (no exit_at), completed recovery (exit_at set)
        // When: fetch_recovery()
        // Then: status correctly 'active' or 'completed'
    }

    #[tokio::test]
    async fn test_fetch_recovery_anomaly_count_filtered() {
        // Given: Recovery from 2w ago, new anomalies detected last week
        // When: fetch_recovery()
        // Then: anomaly_count_in_recovery includes only post-entry anomalies
    }

    // Feature 2: Cockpit Integration (API behavior)
    #[tokio::test]
    async fn test_api_agent_actions_endpoint_200() {
        // Given: Valid sovereign_id
        // When: GET /api/graph/projections/agent_actions?sovereign_id=...
        // Then: 200 OK, JSON response
    }

    #[tokio::test]
    async fn test_api_agent_actions_missing_sovereign_id() {
        // Given: No sovereign_id query param
        // When: GET /api/graph/projections/agent_actions
        // Then: 400 Bad Request
    }

    #[tokio::test]
    async fn test_api_anomalies_endpoint_200() {
        // Given: Valid sovereign_id
        // When: GET /api/graph/projections/anomalies?sovereign_id=...
        // Then: 200 OK
    }
}
```

### Test Suite (correlation_repo_tests.rs)

```rust
#[cfg(test)]
mod correlation_tests {
    use super::*;

    #[tokio::test]
    async fn test_correlate_anomalies_requires_min_sample_size() {
        // Given: Only 5 samples of event_type='X' with anomaly
        // When: correlate_anomalies(min_sample_size: 10)
        // Then: Don't return this pattern (insufficient samples)
    }

    #[tokio::test]
    async fn test_correlate_anomalies_filters_low_strength() {
        // Given: Pattern with 30% correlation strength
        // When: correlate_anomalies()
        // Then: Don't return (< 0.5 threshold)
    }

    #[tokio::test]
    async fn test_correlate_anomalies_time_window() {
        // Given: Action at T, anomaly at T+3min
        // When: Check if action "triggered" anomaly
        // Then: Yes (within 5-min window)
    }

    #[tokio::test]
    async fn test_correlate_anomalies_30day_window() {
        // Given: Actions from 30d ago, 31d ago
        // When: correlate_anomalies()
        // Then: Include 30d, exclude 31d
    }

    #[tokio::test]
    async fn test_correlate_anomalies_result_ranked() {
        // Given: Multiple patterns with different strengths
        // When: correlate_anomalies()
        // Then: Results ordered by correlation_strength DESC
    }

    #[tokio::test]
    async fn test_correlate_anomalies_confidence_calculation() {
        // Given: 100 samples, 75 with anomaly
        // When: Calculate confidence_95th
        // Then: Validate 95% confidence interval
    }

    #[tokio::test]
    async fn test_correlate_anomalies_empty_on_no_patterns() {
        // Given: No correlated patterns found
        // When: correlate_anomalies()
        // Then: Return empty vec[]
    }

    #[tokio::test]
    async fn test_correlate_anomalies_ignores_unrelated_events() {
        // Given: Many agent actions, few with anomalies
        // When: correlate_anomalies()
        // Then: Only include event_types where correlation > threshold
    }

    #[tokio::test]
    async fn test_correlate_anomalies_handles_null_sovereigns() {
        // Given: Actions with NULL sovereign_id
        // When: correlate_anomalies(sovereign_id)
        // Then: Skip NULL records (sovereign guard)
    }

    #[tokio::test]
    async fn test_correlate_anomalies_multiple_anomaly_types() {
        // Given: Actions correlate with both 'dispute_spam' and 'timeout_spam'
        // When: correlate_anomalies()
        // Then: Return both patterns separately
    }
}
```

---

## Implementation Checklist

### Phase 24 Deliverables

- [ ] **Feature 1: Projection Views**
  - [ ] `projections_repo.rs` (3 endpoints: agent_actions, anomalies, recovery)
  - [ ] SQL queries tested with real data
  - [ ] Axum routes integrated
  - [ ] 12+ tests passing

- [ ] **Feature 2: Dashboard Updates**
  - [ ] React hooks (`useAgentActions`, `useAnomalies`, `useRecovery`)
  - [ ] Components (AgentActionsFeed, AnomalyAlerts, RecoveryStatus)
  - [ ] Styling (Tailwind)
  - [ ] Real-time polling (5-second refresh)
  - [ ] 5+ UI tests

- [ ] **Feature 3: Anomaly Correlation**
  - [ ] `correlation_repo.rs`
  - [ ] Correlation SQL query
  - [ ] Pattern detection + ranking
  - [ ] 10+ tests passing

- [ ] **Documentation**
  - [ ] HANDOFF.md update
  - [ ] API documentation (OpenAPI spec)
  - [ ] Architecture diagram update

- [ ] **Quality Gates**
  - [ ] 35+ tests passing
  - [ ] `cargo clippy` clean
  - [ ] `cargo fmt` clean
  - [ ] No warnings
  - [ ] PR reviewed (Writer/Reviewer)

---

## Success Criteria

✅ All 3 features implemented  
✅ All 35+ tests passing on main  
✅ <100ms latency on projection queries  
✅ Real-time updates via SSE or polling  
✅ Dashboard displays live metrics  
✅ Anomaly patterns detected + ranked  
✅ Zero data loss (idempotency maintained)  
✅ Code review approved  

---

**Prepared for:** Writer session (implementation)  
**Review by:** Reviewer session (independent code review)  
**Status:** Ready to implement
