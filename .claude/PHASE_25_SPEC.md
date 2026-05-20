# Phase 25 Specification: API Routing & Integration Tests
**Date:** May 20, 2026  
**Status:** READY FOR IMPLEMENTATION  
**Duration:** 6 days (spec → routes → tests → ship)  
**Agents:** 2 (one for Axum routes, one for integration tests)

---

## Executive Summary

Phase 25 connects Phase 24's repository layer (projections_repo, correlation_repo) to HTTP endpoints via Axum, then validates with 35+ testcontainers-based integration tests. No new data models. Pure plumbing + verification.

**Blocking dependencies:** None. Phase 24 code is production-ready.  
**New files:** 5 (api/mod.rs, api/routes.rs, api/errors.rs, tests/integration_tests.rs + cargo test setup)  
**Estimated LOC:** 800-1000 (routes + error handling + 35+ tests)

---

## 1. API SPECIFICATION

### 1.1 Endpoint: GET /api/graph/projections/agent_actions

**Purpose:** Fetch recent agent actions with pagination.

**Request:**
```
GET /api/graph/projections/agent_actions?sovereign_id=<UUID>&limit=<1..500>&since=<ISO8601_optional>
```

**Query Parameters:**
| Param | Type | Required | Range | Default | Notes |
|-------|------|----------|-------|---------|-------|
| sovereign_id | UUID | YES | — | — | Fails 400 if invalid UUID |
| limit | i32 | NO | 1..500 | 100 | Capped at 500 server-side |
| since | DateTime | NO | — | now()-1h | ISO 8601 string |

**Response 200 (OK):**
```json
{
  "actions": [
    {
      "action_id": "uuid",
      "behavior_event_id": "uuid",
      "session_id": "uuid",
      "persona_id": "uuid",
      "sovereign_id": "uuid",
      "event_type": "process_payment",
      "tier_before": 50,
      "tier_after": 45,
      "cost_incurred": 1250,
      "lineage_safe": true,
      "scored_at": "2026-05-20T14:30:00Z"
    }
  ],
  "total_count": 1500,
  "has_more": true
}
```

**Response 400 (Bad Request):**
```json
{
  "error": "Invalid sovereign_id: not a valid UUID",
  "code": "INVALID_PARAMETER"
}
```

**Response 500 (Internal Error):**
```json
{
  "error": "Database connection lost",
  "code": "DB_ERROR"
}
```

**Validation rules:**
- `sovereign_id` MUST be valid UUID (strict format)
- `limit` MUST be 1..500, else cap silently to 500
- `since` MUST be valid ISO 8601 or use default
- Always include `origin_sovereign_id IS NOT NULL` guard in repo query
- Empty actions array is valid (returns [])

**Handler logic:**
```rust
#[get("/projections/agent_actions")]
async fn get_agent_actions(
    Query(params): Query<AgentActionsQuery>,
    State(pool): State<PgPool>,
) -> Result<Json<AgentActionsPageResponse>> {
    // Validate sovereign_id is UUID
    // Clamp limit to 500
    // Call projections_repo::fetch_agent_actions()
    // Return 200 or map DB errors to 500
}
```

---

### 1.2 Endpoint: GET /api/graph/projections/anomalies

**Purpose:** Fetch anomalies with optional severity/type filtering.

**Request:**
```
GET /api/graph/projections/anomalies?sovereign_id=<UUID>&severity=<low|medium|high|critical>&anomaly_type=<string>&limit=<1..200>
```

**Query Parameters:**
| Param | Type | Required | Values | Default | Notes |
|-------|------|----------|--------|---------|-------|
| sovereign_id | UUID | YES | — | — | Fails 400 if invalid |
| severity | string | NO | low, medium, high, critical | — | Optional filter |
| anomaly_type | string | NO | — | — | Optional filter (e.g., "dispute_spam") |
| limit | i32 | NO | 1..200 | 50 | Capped at 200 server-side |

**Response 200 (OK):**
```json
{
  "anomalies": [
    {
      "anomaly_id": "uuid",
      "anomaly_db_id": "uuid",
      "sovereign_id": "uuid",
      "persona_id": "uuid or null",
      "anomaly_type": "dispute_spam",
      "severity": "high",
      "event_count": 42,
      "window_hours": 24,
      "evidence": { "disputed_txns": 5, "refund_rate": 0.12 },
      "detected_at": "2026-05-20T10:15:00Z",
      "recovery_triggered": true,
      "recovery_tier_impact": 10
    }
  ],
  "total_count": 287,
  "has_more": false,
  "active_recovery_count": 3
}
```

**Validation rules:**
- `severity` values: MUST be in [low, medium, high, critical] or omitted
- `anomaly_type` is free-form string, no validation
- `limit` capped to 200 (different from agent_actions endpoint)
- Empty anomalies array is valid
- `active_recovery_count` MUST be a COUNT(DISTINCT persona_id) WHERE recovery_status='in_recovery'

**Handler logic:**
```rust
#[get("/projections/anomalies")]
async fn get_anomalies(
    Query(params): Query<AnomaliesQuery>,
    State(pool): State<PgPool>,
) -> Result<Json<AnomaliesPageResponse>> {
    // Validate sovereign_id is UUID
    // Validate severity in [low|medium|high|critical] or None
    // Clamp limit to 200
    // Call projections_repo::fetch_anomalies(severity, anomaly_type)
    // Return 200 with active_recovery_count
}
```

---

### 1.3 Endpoint: GET /api/graph/projections/recovery

**Purpose:** Fetch recovery lifecycle status with fail-closed approval lock.

**Request:**
```
GET /api/graph/projections/recovery?sovereign_id=<UUID>&limit=<1..100>
```

**Query Parameters:**
| Param | Type | Required | Range | Default | Notes |
|-------|------|----------|-------|---------|-------|
| sovereign_id | UUID | YES | — | — | Fails 400 if invalid |
| limit | i32 | NO | 1..100 | 25 | Capped at 100 |

**Response 200 (OK):**
```json
{
  "recoveries": [
    {
      "recovery_id": "uuid",
      "persona_id": "uuid",
      "sovereign_id": "uuid",
      "agent_name": "Agent_A",
      "entry_reason": "anomaly_detected",
      "tier_at_entry": 50,
      "tier_current": 40,
      "weeks_elapsed": 2,
      "entry_at": "2026-05-06T10:00:00Z",
      "expected_exit_at": "2026-05-27T10:00:00Z",
      "recovery_status": "active",
      "anomaly_count_in_recovery": 3,
      "last_tier_increase_at": "2026-05-15T14:22:00Z",
      "is_approved": false
    }
  ],
  "total_count": 5,
  "has_more": false
}
```

**Validation rules:**
- `is_approved: false` (FAIL-CLOSED by default)
- Recovery entries with `is_approved=true` are displayed normally
- Recovery entries with `is_approved=false` are LOCKED in UI (component shows 🔒 LOCKED badge)
- Query MUST filter WHERE (properties->>'sovereign_id') IS NOT NULL
- 90-day lookback window on entries
- `weeks_elapsed` calculated as EXTRACT(WEEK FROM NOW() - entry_at)

**Handler logic:**
```rust
#[get("/projections/recovery")]
async fn get_recovery(
    Query(params): Query<RecoveryQuery>,
    State(pool): State<PgPool>,
) -> Result<Json<RecoveryPageResponse>> {
    // Validate sovereign_id
    // Clamp limit to 100
    // Call projections_repo::fetch_recovery()
    // Return 200; UI will handle is_approved=false as locked
}
```

---

### 1.4 Endpoint: GET /api/graph/correlations

**Purpose:** Detect anomaly patterns triggered by event types.

**Request:**
```
GET /api/graph/correlations?sovereign_id=<UUID>&min_sample_size=<10..>&limit=<1..100>
```

**Query Parameters:**
| Param | Type | Required | Range | Default | Notes |
|-------|------|----------|-------|---------|-------|
| sovereign_id | UUID | YES | — | — | Fails 400 if invalid |
| min_sample_size | i32 | NO | 10..1000 | 10 | Min (event, anomaly) pairs for correlation |
| limit | i32 | NO | 1..100 | 25 | Results limit |

**Response 200 (OK):**
```json
{
  "correlations": [
    {
      "pattern_id": "uuid",
      "sovereign_id": "uuid",
      "triggering_event_type": "process_payment",
      "anomaly_type": "dispute_spam",
      "correlation_strength": 0.75,
      "sample_size": 100,
      "confidence_95th": 0.95,
      "detected_at": "2026-05-20T09:00:00Z"
    }
  ],
  "total_count": 23,
  "has_more": false
}
```

**Meaning:**
- `correlation_strength` = 0.75 → 75% of process_payment actions are followed by dispute_spam within 5 minutes
- `sample_size` = 100 → 100 (event, anomaly) pairs in calculation
- `confidence_95th` = 0.95 → 95th percentile confidence (hardcoded in Phase 25)

**Validation rules:**
- `min_sample_size` MUST be >= 10 (enforced at API level)
- Query MUST filter correlation_strength > 0.5 (50%)
- Query MUST use 30-day lookback on action/anomaly data
- Query MUST use 5-minute time window (anomaly BETWEEN action_time AND action_time+5min)
- Sorted by correlation_strength DESC
- Empty correlations array is valid

**Handler logic:**
```rust
#[get("/correlations")]
async fn get_correlations(
    Query(params): Query<CorrelationsQuery>,
    State(pool): State<PgPool>,
) -> Result<Json<CorrelationPageResponse>> {
    // Validate sovereign_id
    // Validate min_sample_size >= 10 else 400 error
    // Clamp limit to 100
    // Call correlation_repo::correlate_anomalies()
    // Return 200
}
```

---

## 2. AXUM ROUTE HANDLER IMPLEMENTATION

### 2.1 Project Structure

```
crates/siss-graph-db/src/
├── api/
│   ├── mod.rs              (router setup, shared extractors)
│   ├── routes.rs           (4 endpoint handlers)
│   └── errors.rs           (ApiError enum + impl IntoResponse)
├── lib.rs                  (export api module)
└── repo/
    ├── projections_repo.rs (no changes from Phase 24)
    └── correlation_repo.rs (no changes from Phase 24)
```

### 2.2 api/errors.rs

```rust
use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

#[derive(Debug)]
pub enum ApiError {
    InvalidUUID(String),
    InvalidParameter(String),
    DbError(String),
    InternalError(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, error_message, code) = match self {
            ApiError::InvalidUUID(msg) => (
                StatusCode::BAD_REQUEST,
                msg,
                "INVALID_PARAMETER",
            ),
            ApiError::InvalidParameter(msg) => (
                StatusCode::BAD_REQUEST,
                msg,
                "INVALID_PARAMETER",
            ),
            ApiError::DbError(msg) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                msg,
                "DB_ERROR",
            ),
            ApiError::InternalError(msg) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                msg,
                "INTERNAL_ERROR",
            ),
        };

        let body = Json(json!({
            "error": error_message,
            "code": code
        }));

        (status, body).into_response()
    }
}

pub type ApiResult<T> = Result<T, ApiError>;
```

### 2.3 api/mod.rs

```rust
pub mod errors;
pub mod routes;

use axum::{
    Router,
    routing::get,
};
use sqlx::PgPool;
use std::sync::Arc;

pub struct AppState {
    pub pool: PgPool,
}

pub fn create_router(pool: PgPool) -> Router {
    let state = Arc::new(AppState { pool });
    
    Router::new()
        .route("/api/graph/projections/agent_actions", get(routes::get_agent_actions))
        .route("/api/graph/projections/anomalies", get(routes::get_anomalies))
        .route("/api/graph/projections/recovery", get(routes::get_recovery))
        .route("/api/graph/correlations", get(routes::get_correlations))
        .with_state(state)
}
```

### 2.4 api/routes.rs (Minimal Example)

```rust
use axum::{
    extract::{Query, State},
    Json,
};
use serde::Deserialize;
use sqlx::PgPool;
use uuid::Uuid;
use crate::repo::{projections_repo, correlation_repo};
use super::errors::{ApiError, ApiResult};

#[derive(Debug, Deserialize)]
pub struct AgentActionsQuery {
    sovereign_id: String,
    limit: Option<i32>,
    since: Option<String>,
}

#[get("/api/graph/projections/agent_actions")]
pub async fn get_agent_actions(
    Query(params): Query<AgentActionsQuery>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<projections_repo::AgentActionsPageResponse>> {
    // 1. Parse sovereign_id as UUID
    let sovereign_id = Uuid::parse_str(&params.sovereign_id)
        .map_err(|_| ApiError::InvalidUUID(
            format!("Invalid sovereign_id: {}", params.sovereign_id)
        ))?;

    // 2. Validate limit (will be capped to 500 in repo)
    let limit = params.limit.map(|l| l.max(1).min(500));

    // 3. Parse since timestamp if provided
    let since = params.since.and_then(|s| {
        chrono::DateTime::parse_from_rfc3339(&s).ok().map(|dt| dt.with_timezone(&chrono::Utc))
    });

    // 4. Call repo layer
    let response = projections_repo::fetch_agent_actions(&pool, sovereign_id, since, limit)
        .await
        .map_err(|e| ApiError::DbError(format!("Database error: {}", e)))?;

    Ok(Json(response))
}

// Similar handlers for get_anomalies, get_recovery, get_correlations
```

### 2.5 Integration with demo-app main.rs

```rust
// In demo-app/src/main.rs
use siss_graph_db::api;

#[tokio::main]
async fn main() {
    // Initialize Postgres pool
    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL not set");
    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("Failed to connect to database");

    // Create Axum router with API endpoints
    let app = api::create_router(pool.clone());

    // Serve on 0.0.0.0:3000
    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000")
        .await
        .expect("Failed to bind to port 3000");

    axum::serve(listener, app)
        .await
        .expect("Server error");
}
```

---

## 3. INTEGRATION TEST SPECIFICATION

### 3.1 Test Environment Setup (testcontainers)

**File:** `crates/siss-graph-db/tests/integration_tests.rs`

```rust
use testcontainers::{clients::Cli, images::postgres};
use sqlx::postgres::PgPoolOptions;

#[tokio::test]
async fn init_test_db() {
    let docker = Cli::default();
    let postgres_image = postgres::Postgres::default();
    let container = docker.run(postgres_image);
    
    let host_port = container.get_host_port_ipv4(5432);
    let connection_string = format!(
        "postgres://postgres:postgres@127.0.0.1:{}/postgres",
        host_port
    );
    
    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect(&connection_string)
        .await
        .expect("Failed to connect");
    
    // Run migrations...
    // Clear test data...
}
```

**Cargo.toml additions:**
```toml
[dev-dependencies]
testcontainers = "0.15"
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.7", features = ["postgres", "runtime-tokio-native-tls"] }
```

### 3.2 Test Suite Structure

**Total: 35 tests**

#### Group 1: projections_repo tests (12 tests)

```rust
// test_agent_actions_pagination: Verify limit=50 returns exactly 50 rows
// test_agent_actions_limit_capping: Verify limit=1000 capped to 500
// test_agent_actions_empty_result: Empty state with no data returns []
// test_agent_actions_sovereign_guard: WHERE sovereign_id IS NOT NULL enforced
// test_agent_actions_timewindow: since=1h lookback respected
// test_anomalies_severity_filter: severity=high returns only high anomalies
// test_anomalies_recovery_count: active_recovery_count matches COUNT(...)
// test_anomalies_empty_filter: no results when filter matches nothing
// test_recovery_approval_lock: is_approved=false for new entries
// test_recovery_approved_visible: is_approved=true entries displayed
// test_recovery_sovereign_guard: Entries filtered by sovereign_id
// test_recovery_total_count: total_count reflects all records
```

**Example test:**
```rust
#[tokio::test]
async fn test_agent_actions_pagination() {
    let pool = setup_test_db().await;
    
    // Insert 150 test actions
    for i in 0..150 {
        insert_test_action(&pool, i).await;
    }
    
    // Fetch with limit=50
    let result = projections_repo::fetch_agent_actions(
        &pool,
        test_sovereign_id(),
        None,
        Some(50),
    )
    .await
    .expect("fetch failed");
    
    assert_eq!(result.actions.len(), 50, "Should return exactly 50 actions");
    assert_eq!(result.total_count, 150, "total_count should be 150");
    assert!(result.has_more, "has_more should be true");
}
```

#### Group 2: correlation_repo tests (10 tests)

```rust
// test_correlate_anomalies_basic: Detects simple pattern (process_payment → dispute_spam)
// test_correlate_anomalies_sample_size: Filters out patterns with < 10 samples
// test_correlate_anomalies_strength_threshold: Filters out patterns < 50% correlation
// test_correlate_anomalies_5min_window: Anomalies outside 5-min window ignored
// test_correlate_anomalies_30day_lookback: Data older than 30 days excluded
// test_correlate_anomalies_ordering: Results sorted by correlation_strength DESC
// test_correlate_anomalies_pagination: Limit=100 cap enforced
// test_is_anomaly_prone_event_true: Detects anomaly-prone event type
// test_is_anomaly_prone_event_false: Returns false for benign event
// test_correlate_anomalies_empty_set: No false patterns returned on empty data
```

**Example test:**
```rust
#[tokio::test]
async fn test_correlate_anomalies_strength_threshold() {
    let pool = setup_test_db().await;
    
    // Insert 100 process_payment actions
    // Insert 30 dispute_spam anomalies within 5 min of actions (30% correlation)
    // Insert pattern should be FILTERED OUT (< 50%)
    
    let result = correlation_repo::correlate_anomalies(
        &pool,
        test_sovereign_id(),
        10, // min_sample_size
        None,
    )
    .await
    .expect("correlate failed");
    
    // Should have 0 correlations (30% < 50% threshold)
    assert_eq!(result.correlations.len(), 0);
}
```

#### Group 3: API Route Handler tests (13 tests)

```rust
// test_agent_actions_endpoint_200: Happy path returns 200 + valid JSON
// test_agent_actions_endpoint_limit_capping: limit=1000 capped to 500
// test_agent_actions_endpoint_400_bad_sovereign: Invalid UUID returns 400
// test_agent_actions_endpoint_empty_since: Missing since uses default
// test_anomalies_endpoint_severity_filter: ?severity=high filters correctly
// test_anomalies_endpoint_anomaly_type_filter: ?anomaly_type=dispute_spam works
// test_anomalies_endpoint_active_recovery_count: Includes recovery count
// test_recovery_endpoint_approval_lock: is_approved flag present in response
// test_recovery_endpoint_locked_display: UI receives is_approved=false for new entries
// test_correlations_endpoint_200: Happy path returns 200
// test_correlations_endpoint_min_sample_validation: min_sample_size < 10 → 400
// test_correlations_endpoint_pattern_detection: Detects patterns correctly
// test_concurrent_requests_no_race: 100 concurrent requests don't deadlock
```

**Example test (using axum test utilities):**
```rust
#[tokio::test]
async fn test_agent_actions_endpoint_400_bad_sovereign() {
    let pool = setup_test_db().await;
    let app = api::create_router(pool);
    
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/graph/projections/agent_actions?sovereign_id=not-a-uuid")
                .body(Body::empty())
                .unwrap()
        )
        .await
        .unwrap();
    
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    
    let body = hyper::body::to_bytes(response.into_body())
        .await
        .unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["code"], "INVALID_PARAMETER");
}
```

---

## 4. ERROR HANDLING & EDGE CASES

### 4.1 Validation Rules (Enforced at API Level)

| Check | Rule | Response |
|-------|------|----------|
| sovereign_id format | MUST be valid UUID | 400 INVALID_PARAMETER |
| limit range (agent_actions) | MUST be 1..500 | Silently capped to 500 |
| limit range (anomalies) | MUST be 1..200 | Silently capped to 200 |
| limit range (recovery) | MUST be 1..100 | Silently capped to 100 |
| limit range (correlations) | MUST be 1..100 | Silently capped to 100 |
| severity values | MUST be [low\|medium\|high\|critical] | 400 INVALID_PARAMETER if provided + invalid |
| min_sample_size | MUST be >= 10 | 400 INVALID_PARAMETER |
| since timestamp | MUST be valid ISO 8601 | Silently use default |

### 4.2 Database Error Handling

All DB errors → 500 INTERNAL_SERVER_ERROR with code "DB_ERROR"

```rust
// Example: Connection pool exhausted
Err(sqlx::Error::PoolTimedOut) 
    → ApiError::DbError("Connection pool exhausted")
    → Status 500, code "DB_ERROR"

// Example: Query syntax error (shouldn't happen in Phase 25)
Err(sqlx::Error::QueryError(_)) 
    → ApiError::InternalError("Query error")
    → Status 500, code "INTERNAL_ERROR"
```

### 4.3 Empty Result Sets

All endpoints return 200 OK with empty arrays when no data matches:

```json
{
  "actions": [],
  "total_count": 0,
  "has_more": false
}
```

---

## 5. DATA VALIDATION & CONTRACTS

### 5.1 Request Parameter Validation

```rust
pub struct AgentActionsQuery {
    pub sovereign_id: String,          // Validated as UUID in handler
    pub limit: Option<i32>,             // Capped to 500
    pub since: Option<String>,          // Validated as ISO 8601
}

pub struct AnomaliesQuery {
    pub sovereign_id: String,           // Validated as UUID
    pub severity: Option<String>,       // Validated in [low|medium|high|critical]
    pub anomaly_type: Option<String>,   // Free-form, no validation
    pub limit: Option<i32>,             // Capped to 200
}

pub struct RecoveryQuery {
    pub sovereign_id: String,           // Validated as UUID
    pub limit: Option<i32>,             // Capped to 100
}

pub struct CorrelationsQuery {
    pub sovereign_id: String,           // Validated as UUID
    pub min_sample_size: Option<i32>,   // Validated >= 10 (error if < 10)
    pub limit: Option<i32>,             // Capped to 100
}
```

### 5.2 Response Data Contracts (FROZEN from Phase 24)

All response types inherit from Phase 24 without modification:
- `AgentActionProjection` → 11 fields
- `AnomalyProjection` → 12 fields (includes recovery_triggered, recovery_tier_impact)
- `RecoveryProjection` → 14 fields (includes is_approved, NEW field)
- `AnomalyCorrelation` → 8 fields

**No schema changes in Phase 25.**

---

## 6. IMPLEMENTATION CHECKLIST

### Day 1: Project Setup
- [ ] Create `crates/siss-graph-db/src/api/` directory
- [ ] Create api/mod.rs, api/routes.rs, api/errors.rs
- [ ] Add Axum + serde + uuid dependencies to Cargo.toml
- [ ] Verify siss-graph-db lib.rs exports api module
- [ ] Compile check: `cargo check -p siss-graph-db`

### Day 2-3: Route Handlers
- [ ] Implement api/errors.rs (ApiError enum + IntoResponse)
- [ ] Implement api/mod.rs (create_router + AppState)
- [ ] Implement api/routes.rs (get_agent_actions handler)
- [ ] Manual test: `curl localhost:3000/api/graph/projections/agent_actions?sovereign_id=<UUID>`
- [ ] Implement remaining 3 handlers (anomalies, recovery, correlations)
- [ ] Verify all 4 endpoints respond 200 OK
- [ ] Clippy check: `cargo clippy -p siss-graph-db`

### Day 4-5: Integration Tests
- [ ] Set up testcontainers in tests/integration_tests.rs
- [ ] Write test fixtures (insert_test_action, insert_test_anomaly, etc.)
- [ ] Write Group 1 tests (projections_repo, 12 tests)
- [ ] Write Group 2 tests (correlation_repo, 10 tests)
- [ ] Write Group 3 tests (route handlers, 13 tests)
- [ ] Run full suite: `cargo test --test integration_tests`
- [ ] Target: 100% pass rate

### Day 6: Verification & Documentation
- [ ] All 35+ tests pass with 0 warnings
- [ ] All endpoints verified with curl/Postman
- [ ] Load test: 100 concurrent requests to /api/graph/projections/agent_actions
- [ ] Verify response latency p95 < 200ms
- [ ] Write API documentation (OpenAPI spec optional)
- [ ] Ship: Merge to main with commit message "Phase 25: API routing + integration tests"

---

## 7. CRITICAL RULES (NON-NEGOTIABLE)

1. **Sovereign isolation:** Every query MUST filter by sovereign_id (passed in URL + enforced at DB level)
2. **Fail-closed recovery:** is_approved field MUST default to false
3. **Memory safety:** React hooks already have AbortController from Phase 24
4. **Limit capping:** Never return more rows than the cap (500/200/100/100)
5. **No breaking changes:** Phase 24 data contracts are FROZEN; Phase 25 only adds routes
6. **Database consistency:** All tests must use isolated testcontainers instances
7. **Error handling:** All 4xx errors on client input validation; all 5xx on server errors

---

## 8. CODE STYLE & PATTERNS

**Module organization:**
```rust
// api/errors.rs: error types only
// api/mod.rs: router setup + shared state
// api/routes.rs: all 4 endpoint handlers
// api/middleware.rs: SKIP for Phase 25 (no auth/logging required yet)
```

**Handler pattern (DRY):**
```rust
#[get("/path")]
async fn handler(
    Query(params): Query<QueryType>,
    State(pool): State<PgPool>,
) -> ApiResult<Json<ResponseType>> {
    // 1. Validate params (UUID, ranges, enums)
    // 2. Call repo function
    // 3. Map errors to ApiError
    // 4. Return Json
}
```

**Test pattern (standard):**
```rust
#[tokio::test]
async fn test_name() {
    let pool = setup_test_db().await;
    // Arrange: insert test data
    // Act: call function under test
    // Assert: verify results
}
```

---

## 9. DEPLOYMENT NOTES

**Environment variables:**
- `DATABASE_URL`: postgresql://user:pass@host:5432/db
- `PORT`: 3000 (default)
- `RUST_LOG`: info (optional, for debugging)

**Docker Compose (for local testing):**
```yaml
version: '3'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
  siss-graph-db-api:
    build: .
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/siss
    ports:
      - "3000:3000"
    depends_on:
      - postgres
```

---

## 10. HANDOFF & NEXT PHASE

**Phase 25 → Phase 26 dependencies:**
- Recovery approval workflow (requires UI approval modal + API endpoint)
- Prometheus metrics integration
- SSE broadcaster for real-time push (optional)
- Cross-sovereign federation patterns

**Files eligible for Phase 26 refactor:**
- Error handling can be simplified once auth middleware is added
- Response types can be generified for pagination (PageResponse<T>)
- Route handlers can be macro-generated once pattern stabilizes

---

## Appendix A: Quick Reference — Endpoint Matrix

| Endpoint | Method | Params | Returns | Limit | Lookback |
|----------|--------|--------|---------|-------|----------|
| /agent_actions | GET | sovereign_id, limit, since | actions[] | 500 | 1h |
| /anomalies | GET | sovereign_id, severity?, anomaly_type?, limit | anomalies[] | 200 | 7d |
| /recovery | GET | sovereign_id, limit | recoveries[] | 100 | 90d |
| /correlations | GET | sovereign_id, min_sample_size?, limit | correlations[] | 100 | 30d |

---

## Appendix B: Test Data Factory

```rust
fn insert_test_action(pool: &PgPool, idx: i32) -> AgentActionProjection {
    AgentActionProjection {
        action_id: Uuid::new_v4(),
        event_type: format!("event_{}", idx),
        tier_before: 50,
        tier_after: 45,
        cost_incurred: 1000 + idx as i64,
        lineage_safe: idx % 2 == 0,
        scored_at: Utc::now() - Duration::minutes(idx as i64),
        // ... other fields
    }
}

fn insert_test_anomaly(pool: &PgPool, idx: i32) -> AnomalyProjection {
    AnomalyProjection {
        anomaly_id: Uuid::new_v4(),
        anomaly_type: "dispute_spam".to_string(),
        severity: match idx % 4 {
            0 => "low",
            1 => "medium",
            2 => "high",
            _ => "critical",
        }.to_string(),
        event_count: idx as i64,
        detected_at: Utc::now() - Duration::minutes((idx as i64) * 5),
        // ... other fields
    }
}
```

---

**Prepared by:** Claude Haiku 4.5  
**For:** Fresh agents (Phase 25 implementation)  
**Status:** READY — Agents can start immediately on Day 1.
