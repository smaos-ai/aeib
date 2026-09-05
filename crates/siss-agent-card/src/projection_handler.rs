use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{IntoResponse, Json},
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;

use crate::handler::AgentCardState;

// ─────────────────────────────────────────────────────────────────────────────
// Response Types
// ─────────────────────────────────────────────────────────────────────────────

/// Root-cause chain projection response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootCauseResponse {
    pub anomaly_id: Uuid,
    pub detected_at: DateTime<Utc>,
    pub anomaly_type: String,
    pub sovereign_id: Uuid,
    pub confidence: f64,
    pub tier: String,
    pub root_cause_chain: Vec<RootCauseChainNode>,
    pub operator_insight: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootCauseChainNode {
    pub depth: usize,
    pub node_id: Uuid,
    pub label: String,
    pub confidence: f64,
    pub relationship: Option<String>,
    pub created_at: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub anomaly_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chain_type: Option<String>,
}

/// Threat anticipation projection response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreatAnticipationResponse {
    pub source_sovereign_id: Uuid,
    pub source_sovereign_name: String,
    pub anomaly_patterns: Vec<AnomalyPattern>,
    pub affected_sovereigns: Vec<AffectedSovereign>,
    pub total_tokens_at_risk: i64,
    pub recommendation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalyPattern {
    pub pattern_id: Uuid,
    pub pattern_type: String,
    pub confidence: f64,
    pub tier: String,
    pub occurrence_count: i32,
    pub risk_level: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectedSovereign {
    pub sovereign_id: Uuid,
    pub sovereign_name: String,
    pub hybrid_trust_score: i32,
    pub settled_invoice_count: i32,
    pub tokens_at_risk: i64,
    pub risk_level: String,
    pub rationale: String,
}

/// SWOT scenario projection response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwotScenarioResponse {
    pub source_sovereign_id: Uuid,
    pub time_window_days: i32,
    pub snapshot_at: DateTime<Utc>,
    pub strengths: Vec<SwotSignal>,
    pub weaknesses: Vec<SwotSignal>,
    pub opportunities: Vec<SwotSignal>,
    pub threats: Vec<SwotThreat>,
    pub diversity_index: f64,
    pub diversity_interpretation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwotSignal {
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signal_confidence: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metric: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub anomaly_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwotThreat {
    pub description: String,
    pub risk_level: String,
    pub affected_count: i32,
    pub pattern_type: String,
}

// ─────────────────────────────────────────────────────────────────────────────
// Query Parameters
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct RootCauseQuery {
    #[serde(default = "default_depth")]
    pub depth: usize,
}

fn default_depth() -> usize {
    5
}

#[derive(Debug, Deserialize)]
pub struct ThreatQuery {
    #[serde(default = "default_blast_radius")]
    pub blast_radius_depth: usize,
}

fn default_blast_radius() -> usize {
    3
}

#[derive(Debug, Deserialize)]
pub struct SwotQuery {
    #[serde(default = "default_time_window")]
    pub time_window_days: i32,
}

fn default_time_window() -> i32 {
    7
}

// ─────────────────────────────────────────────────────────────────────────────
// Error Type
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum ProjectionError {
    NotFound(String),
    DatabaseError(String),
    InvalidQuery(String),
}

impl IntoResponse for ProjectionError {
    fn into_response(self) -> axum::response::Response {
        let (status, error_msg) = match self {
            ProjectionError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
            ProjectionError::DatabaseError(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            ProjectionError::InvalidQuery(msg) => (StatusCode::BAD_REQUEST, msg),
        };
        (status, Json(serde_json::json!({ "error": error_msg }))).into_response()
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Handler: Root-Cause Projection
// ─────────────────────────────────────────────────────────────────────────────

pub async fn root_cause_handler(
    State(state): State<AgentCardState>,
    Path(anomaly_id): Path<Uuid>,
    Query(params): Query<RootCauseQuery>,
) -> Result<Json<RootCauseResponse>, ProjectionError> {
    // Clamp depth at 5
    let depth = std::cmp::min(params.depth, 5) as i32;

    // Call the projection repository query
    let repo_response = siss_graph_db::repo::projection_repo::query_root_cause_chain(
        &state.pool,
        anomaly_id,
        depth,
    )
    .await
    .map_err(|e| {
        if e.contains("not found") || e.contains("Anomaly") {
            ProjectionError::NotFound(format!("Anomaly not found: {}", anomaly_id))
        } else {
            ProjectionError::DatabaseError(format!("Database error: {}", e))
        }
    })?;

    // Adapt repo response to handler response types
    let root_cause_chain = repo_response
        .root_cause_chain
        .iter()
        .map(|node| RootCauseChainNode {
            depth: node.depth as usize,
            node_id: node.node_id,
            label: node.label.clone(),
            confidence: node.confidence,
            relationship: node.relationship.clone(),
            created_at: node.created_at,
            anomaly_type: node.anomaly_type.clone(),
            chain_type: node.chain_type.clone(),
        })
        .collect();

    let response = RootCauseResponse {
        anomaly_id: repo_response.anomaly_id,
        detected_at: repo_response.detected_at,
        anomaly_type: repo_response.anomaly_type,
        sovereign_id: repo_response.sovereign_id,
        confidence: repo_response.confidence,
        tier: repo_response.tier,
        root_cause_chain,
        operator_insight: repo_response.operator_insight,
    };

    Ok(Json(response))
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Handler: Threat Anticipation Projection
// ─────────────────────────────────────────────────────────────────────────────

pub async fn threat_anticipation_handler(
    State(state): State<AgentCardState>,
    Path(source_sovereign_id): Path<Uuid>,
    Query(params): Query<ThreatQuery>,
) -> Result<Json<ThreatAnticipationResponse>, ProjectionError> {
    // Clamp blast_radius_depth at 3
    let blast_radius_depth = std::cmp::min(params.blast_radius_depth, 3) as i32;

    // Call the projection repository query
    let repo_response = siss_graph_db::repo::projection_repo::query_threat_anticipation(
        &state.pool,
        source_sovereign_id,
        blast_radius_depth,
    )
    .await
    .map_err(|e| {
        if e.contains("not found") || e.contains("Sovereign") {
            ProjectionError::NotFound(format!("Sovereign not found: {}", source_sovereign_id))
        } else {
            ProjectionError::DatabaseError(format!("Database error: {}", e))
        }
    })?;

    // Adapt repo response to handler response types
    let anomaly_patterns = repo_response
        .anomaly_patterns
        .iter()
        .map(|p| AnomalyPattern {
            pattern_id: p.pattern_id,
            pattern_type: p.pattern_type.clone(),
            confidence: p.confidence,
            tier: p.tier.clone(),
            occurrence_count: p.occurrence_count as i32,
            risk_level: p.risk_level.clone(),
        })
        .collect();

    let affected_sovereigns = repo_response
        .affected_sovereigns
        .iter()
        .map(|s| AffectedSovereign {
            sovereign_id: s.sovereign_id,
            sovereign_name: s.sovereign_name.clone(),
            hybrid_trust_score: s.hybrid_trust_score,
            settled_invoice_count: s.settled_invoice_count as i32,
            tokens_at_risk: s.tokens_at_risk,
            risk_level: s.risk_level.clone(),
            rationale: s.rationale.clone(),
        })
        .collect();

    let response = ThreatAnticipationResponse {
        source_sovereign_id: repo_response.source_sovereign_id,
        source_sovereign_name: repo_response.source_sovereign_name,
        anomaly_patterns,
        affected_sovereigns,
        total_tokens_at_risk: repo_response.total_tokens_at_risk,
        recommendation: repo_response.recommendation,
    };

    Ok(Json(response))
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP Handler: SWOT Scenario Projection
// ─────────────────────────────────────────────────────────────────────────────

pub async fn swot_scenario_handler(
    State(state): State<AgentCardState>,
    Path(source_sovereign_id): Path<Uuid>,
    Query(params): Query<SwotQuery>,
) -> Result<Json<SwotScenarioResponse>, ProjectionError> {
    // Call the projection repository query
    let repo_response = siss_graph_db::repo::projection_repo::query_swot_scenario(
        &state.pool,
        source_sovereign_id,
        params.time_window_days,
    )
    .await
    .map_err(|e| {
        if e.contains("not found") || e.contains("Sovereign") {
            ProjectionError::NotFound(format!("Sovereign not found: {}", source_sovereign_id))
        } else {
            ProjectionError::DatabaseError(format!("Database error: {}", e))
        }
    })?;

    // Adapt repo response to handler response types
    let strengths = repo_response
        .strengths
        .iter()
        .map(|s| SwotSignal {
            description: s.description.clone(),
            signal_confidence: s.signal_confidence,
            metric: s.metric.clone(),
            anomaly_type: s.anomaly_type.clone(),
            action: s.action.clone(),
        })
        .collect();

    let weaknesses = repo_response
        .weaknesses
        .iter()
        .map(|w| SwotSignal {
            description: w.description.clone(),
            signal_confidence: w.signal_confidence,
            metric: w.metric.clone(),
            anomaly_type: w.anomaly_type.clone(),
            action: w.action.clone(),
        })
        .collect();

    let opportunities = repo_response
        .opportunities
        .iter()
        .map(|o| SwotSignal {
            description: o.description.clone(),
            signal_confidence: o.signal_confidence,
            metric: o.metric.clone(),
            anomaly_type: o.anomaly_type.clone(),
            action: o.action.clone(),
        })
        .collect();

    let threats = repo_response
        .threats
        .iter()
        .map(|t| SwotThreat {
            description: t.description.clone(),
            risk_level: t.risk_level.clone().unwrap_or_else(|| "Medium".to_string()),
            affected_count: t.affected_count.unwrap_or(0) as i32,
            pattern_type: t
                .pattern_type
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
        })
        .collect();

    let response = SwotScenarioResponse {
        source_sovereign_id: repo_response.source_sovereign_id,
        time_window_days: repo_response.time_window_days,
        snapshot_at: repo_response.snapshot_at,
        strengths,
        weaknesses,
        opportunities,
        threats,
        diversity_index: repo_response.diversity_index,
        diversity_interpretation: repo_response.diversity_interpretation,
    };

    Ok(Json(response))
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests (RED Phase — Failing Tests)
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_db::repo::node_repo;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

    /// Start a test Postgres container and run migrations
    async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        siss_graph_db::migrations::run_all(&pool)
            .await
            .expect("migrations");
        (container, pool)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 1: Root-Cause Handler — Returns Chain When Anomaly Found
    // ─────────────────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn test_root_cause_handler_returns_chain_when_anomaly_found() {
        let (_container, pool) = start_postgres().await;

        // Setup: Create test server state with AgentCardState
        let _tenant_id = node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");

        let _persona_id = node_repo::insert_persona(&pool, "TestAgent", "ai_agent", _tenant_id)
            .await
            .expect("insert persona");

        let state = AgentCardState {
            pool: pool.clone(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            base_url: "http://localhost:8080".to_string(),
            extended: false,
            sovereign_id: Uuid::new_v4(),
        };

        // Create test anomaly and insert into database
        let anomaly_id = Uuid::new_v4();
        let sovereign_id = Uuid::new_v4();
        let props = serde_json::json!({
            "anomaly_type": "timeout_pattern",
            "confidence": 0.85,
            "tier": "semantic",
            "sovereign_id": sovereign_id.to_string(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties, graph_id, created_at)
             VALUES ($1, $2, $3, $4, $5)",
        )
        .bind(anomaly_id)
        .bind("AnomalyChainNode")
        .bind(props)
        .bind(0i64)
        .bind(Utc::now())
        .execute(&pool)
        .await
        .expect("insert anomaly");

        // Action: Call root_cause_handler
        let params = RootCauseQuery { depth: 5 };
        let result = root_cause_handler(State(state), Path(anomaly_id), Query(params)).await;

        // Assert: Expect Success with valid response structure
        let response = result.expect("handler should return Ok");
        assert_eq!(response.anomaly_id, anomaly_id);
        assert_eq!(response.sovereign_id, sovereign_id);
        assert_eq!(response.confidence, 0.85);
        assert_eq!(response.anomaly_type, "timeout_pattern");
        assert_eq!(response.tier, "semantic");
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 2: Root-Cause Handler — 404 When Anomaly Not Found
    // ─────────────────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn test_root_cause_handler_404_when_anomaly_not_found() {
        let (_container, pool) = start_postgres().await;

        // Setup: Create test server state, but DO NOT insert the requested anomaly
        let _tenant_id = node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");

        let _persona_id = node_repo::insert_persona(&pool, "TestAgent", "ai_agent", _tenant_id)
            .await
            .expect("insert persona");

        let state = AgentCardState {
            pool: pool.clone(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            base_url: "http://localhost:8080".to_string(),
            extended: false,
            sovereign_id: Uuid::new_v4(),
        };

        let nonexistent_uuid = Uuid::new_v4();

        // Action: Call root_cause_handler with nonexistent ID
        let params = RootCauseQuery { depth: 5 };
        let result = root_cause_handler(State(state), Path(nonexistent_uuid), Query(params)).await;

        // Assert: Expect Err with 404 status
        assert!(result.is_err());
        let err = result.unwrap_err();
        match err {
            ProjectionError::NotFound(msg) => {
                assert!(msg.contains("not found") || msg.contains("not yet implemented"));
            }
            _ => panic!("Expected NotFound error"),
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 3: Threat Anticipation Handler — Identifies Risk
    // ─────────────────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn test_threat_anticipation_handler_identifies_risk() {
        let (_container, pool) = start_postgres().await;

        // Setup: Create test server state
        let _tenant_id = node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");

        let _persona_id = node_repo::insert_persona(&pool, "TestAgent", "ai_agent", _tenant_id)
            .await
            .expect("insert persona");

        let state = AgentCardState {
            pool: pool.clone(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            base_url: "http://localhost:8080".to_string(),
            extended: false,
            sovereign_id: Uuid::new_v4(),
        };

        let source_sovereign_id = Uuid::new_v4();

        // Action: Call threat_anticipation_handler
        let params = ThreatQuery {
            blast_radius_depth: 3,
        };
        let result =
            threat_anticipation_handler(State(state), Path(source_sovereign_id), Query(params))
                .await;

        // Assert: Expect Success with valid response structure
        let response = result.expect("handler should return Ok");
        assert_eq!(response.source_sovereign_id, source_sovereign_id);
        assert_eq!(response.affected_sovereigns.len(), 3);
        assert!(response.total_tokens_at_risk > 0);
        assert!(
            response
                .affected_sovereigns
                .iter()
                .all(|s| s.tokens_at_risk > 0)
        );

        // Risk level mapping validation
        for affected in &response.affected_sovereigns {
            match affected.risk_level.as_str() {
                "High" => {
                    assert!(affected.hybrid_trust_score < 60 || affected.hybrid_trust_score == 0)
                }
                "Medium" => {
                    assert!(affected.hybrid_trust_score >= 60 && affected.hybrid_trust_score <= 80)
                }
                "Low" => assert!(affected.hybrid_trust_score > 80),
                _ => panic!("Invalid risk level: {}", affected.risk_level),
            }
        }

        // Sorted by tokens_at_risk descending
        for i in 0..response.affected_sovereigns.len() - 1 {
            assert!(
                response.affected_sovereigns[i].tokens_at_risk
                    >= response.affected_sovereigns[i + 1].tokens_at_risk
            );
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Test 4: SWOT Handler — Aggregates Signals
    // ─────────────────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn test_swot_scenario_handler_aggregates_signals() {
        let (_container, pool) = start_postgres().await;

        // Setup: Create test server state
        let _tenant_id = node_repo::insert_tenant(&pool, "TestCorp")
            .await
            .expect("insert tenant");

        let _persona_id = node_repo::insert_persona(&pool, "TestAgent", "ai_agent", _tenant_id)
            .await
            .expect("insert persona");

        let state = AgentCardState {
            pool: pool.clone(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            base_url: "http://localhost:8080".to_string(),
            extended: false,
            sovereign_id: Uuid::new_v4(),
        };

        let source_sovereign_id = Uuid::new_v4();

        // Action: Call swot_scenario_handler
        let params = SwotQuery {
            time_window_days: 7,
        };
        let result =
            swot_scenario_handler(State(state), Path(source_sovereign_id), Query(params)).await;

        // Assert: Expect Success with valid response structure
        let response = result.expect("handler should return Ok");
        assert_eq!(response.source_sovereign_id, source_sovereign_id);
        assert_eq!(response.time_window_days, 7);

        // All arrays should be non-empty
        assert!(
            !response.strengths.is_empty(),
            "strengths should not be empty"
        );
        assert!(
            !response.weaknesses.is_empty(),
            "weaknesses should not be empty"
        );
        assert!(
            !response.opportunities.is_empty(),
            "opportunities should have at least 1"
        );
        assert!(!response.threats.is_empty(), "threats should not be empty");

        // Diversity index in valid range
        assert!(response.diversity_index >= 0.0 && response.diversity_index <= 1.0);

        // Diversity interpretation should be human-readable
        assert!(!response.diversity_interpretation.is_empty());
    }
}
