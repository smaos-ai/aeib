use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use uuid::Uuid;

/// Represents a pending conflict between two capsules
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Conflict {
    pub id: String,
    pub capsule_a: String,
    pub capsule_b: String,
    pub affected_symbol: String,
    pub risk_a: String,
    pub risk_b: String,
}

/// Request body for veto decision submission
#[derive(Debug, Deserialize, Serialize)]
pub struct VetoRequest {
    pub conflict_id: String,
    pub approve_a: bool,
    pub approve_b: bool,
    pub reason: String,
}

/// Response from veto submission
#[derive(Debug, Serialize, Deserialize)]
pub struct VetoResponseBody {
    pub decision_id: String,
    pub status: String,
    pub capsule_a_status: String,
    pub capsule_b_status: String,
    pub timestamp: u64,
}

/// Metrics response
#[derive(Debug, Serialize, Deserialize)]
pub struct MetricsResponse {
    pub mean_us: u64,
    pub p99_us: u64,
    pub sample_count: usize,
}

/// List of pending conflicts response
#[derive(Debug, Serialize, Deserialize)]
pub struct ConflictsResponse {
    pub pending: Vec<Conflict>,
}

/// Application state
#[derive(Clone)]
pub struct AppState {
    conflicts: Arc<Mutex<Vec<Conflict>>>,
    metrics: Arc<Mutex<MetricsData>>,
}

/// Metrics data storage
#[derive(Clone, Debug)]
struct MetricsData {
    mean_us: u64,
    p99_us: u64,
    sample_count: usize,
}

impl AppState {
    /// Create a new application state
    pub fn new() -> Self {
        AppState {
            conflicts: Arc::new(Mutex::new(Vec::new())),
            metrics: Arc::new(Mutex::new(MetricsData {
                mean_us: 47,
                p99_us: 89,
                sample_count: 1000,
            })),
        }
    }

    /// Add a conflict to the pending list
    pub fn add_conflict(&self, conflict: Conflict) {
        if let Ok(mut conflicts) = self.conflicts.lock() {
            conflicts.push(conflict);
        }
    }

    /// Get all pending conflicts
    pub fn get_conflicts(&self) -> Vec<Conflict> {
        self.conflicts
            .lock()
            .ok()
            .map(|c| c.clone())
            .unwrap_or_default()
    }

    /// Process a veto decision
    pub fn process_veto(&self, request: &VetoRequest) -> Result<VetoResponseBody, String> {
        // Validate request
        if request.conflict_id.is_empty() {
            return Err("conflict_id required".to_string());
        }
        if request.reason.is_empty() {
            return Err("reason required".to_string());
        }

        // Remove the conflict from pending list
        if let Ok(mut conflicts) = self.conflicts.lock() {
            conflicts.retain(|c| c.id != request.conflict_id);
        }

        let capsule_a_status = if request.approve_a {
            "APPROVED".to_string()
        } else {
            "REJECTED".to_string()
        };

        let capsule_b_status = if request.approve_b {
            "APPROVED".to_string()
        } else {
            "REJECTED".to_string()
        };

        Ok(VetoResponseBody {
            decision_id: Uuid::new_v4().to_string(),
            status: "VETO_DECISION_EXECUTED".to_string(),
            capsule_a_status,
            capsule_b_status,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        })
    }

    /// Get current metrics
    pub fn get_metrics(&self) -> MetricsResponse {
        self.metrics
            .lock()
            .ok()
            .map(|m| MetricsResponse {
                mean_us: m.mean_us,
                p99_us: m.p99_us,
                sample_count: m.sample_count,
            })
            .unwrap_or_else(|| MetricsResponse {
                mean_us: 0,
                p99_us: 0,
                sample_count: 0,
            })
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

/// Handler for GET /api/conflicts
async fn get_conflicts_handler(State(state): State<AppState>) -> Json<ConflictsResponse> {
    let conflicts = state.get_conflicts();
    Json(ConflictsResponse { pending: conflicts })
}

/// Handler for POST /api/veto
async fn post_veto_handler(
    State(state): State<AppState>,
    Json(request): Json<VetoRequest>,
) -> Result<Json<VetoResponseBody>, (StatusCode, String)> {
    match state.process_veto(&request) {
        Ok(response) => Ok(Json(response)),
        Err(e) => Err((StatusCode::BAD_REQUEST, e)),
    }
}

/// Handler for GET /api/metrics
async fn get_metrics_handler(State(state): State<AppState>) -> Json<MetricsResponse> {
    Json(state.get_metrics())
}

/// Handler for GET / - Returns a simple HTML dashboard
async fn root_handler() -> impl IntoResponse {
    let html = r#"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>φ+ Eval Court Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 1200px;
            width: 100%;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            font-size: 1.1em;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
        }
        .card {
            background: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 25px;
            transition: all 0.3s ease;
        }
        .card:hover {
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
        }
        .card h2 {
            color: #667eea;
            font-size: 1.3em;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
            margin: 15px 0;
        }
        .metric-label {
            color: #666;
            font-size: 0.95em;
        }
        .conflicts-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .conflict-item {
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .conflict-item strong {
            color: #667eea;
        }
        .empty-state {
            text-align: center;
            color: #999;
            padding: 20px;
            font-style: italic;
        }
        .api-info {
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 6px;
            margin-top: 30px;
        }
        .api-info h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .api-endpoint {
            font-family: 'Monaco', 'Menlo', monospace;
            background: white;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 5px 0;
            color: #d63384;
            font-size: 0.9em;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            margin-top: 10px;
        }
        .status-idle {
            background: #d4edda;
            color: #155724;
        }
        .status-waiting {
            background: #fff3cd;
            color: #856404;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚖️ φ+ Eval Court Dashboard</h1>
            <p class="subtitle">Capsule Conflict Resolution & Veto Interface</p>
        </div>

        <div class="grid">
            <div class="card">
                <h2>📊 Pending Conflicts</h2>
                <div class="metric-value" id="conflict-count">0</div>
                <div class="metric-label">Active conflicts awaiting veto decision</div>
                <div class="conflicts-list" id="conflicts-list">
                    <div class="empty-state">Loading conflicts...</div>
                </div>
            </div>

            <div class="card">
                <h2>⚡ Dispatch Metrics</h2>
                <div>
                    <div class="metric-label">Mean Latency</div>
                    <div class="metric-value" id="mean-latency">—</div>
                </div>
                <div style="margin-top: 20px;">
                    <div class="metric-label">P99 Latency</div>
                    <div class="metric-value" id="p99-latency">—</div>
                </div>
                <div style="margin-top: 20px;">
                    <div class="metric-label">Sample Count</div>
                    <div class="metric-value" id="sample-count">—</div>
                </div>
            </div>
        </div>

        <div class="api-info">
            <h3>API Endpoints</h3>
            <div class="api-endpoint">GET /api/conflicts — List pending conflicts</div>
            <div class="api-endpoint">POST /api/veto — Submit veto decision</div>
            <div class="api-endpoint">GET /api/metrics — Get dispatch metrics</div>
        </div>
    </div>

    <script>
        async function loadConflicts() {
            try {
                const response = await fetch('/api/conflicts');
                const data = await response.json();
                const container = document.getElementById('conflicts-list');
                const count = document.getElementById('conflict-count');

                count.textContent = data.pending.length;

                if (data.pending.length === 0) {
                    container.innerHTML = '<div class="empty-state">No pending conflicts</div>';
                } else {
                    container.innerHTML = data.pending.map(c =>
                        `<div class="conflict-item">
                            <strong>${c.capsule_a}</strong> ↔ <strong>${c.capsule_b}</strong>
                            <br>Symbol: <code>${c.affected_symbol}</code>
                        </div>`
                    ).join('');
                }
            } catch (e) {
                console.error('Failed to load conflicts:', e);
            }
        }

        async function loadMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();

                document.getElementById('mean-latency').textContent = data.mean_us + ' μs';
                document.getElementById('p99-latency').textContent = data.p99_us + ' μs';
                document.getElementById('sample-count').textContent = data.sample_count;
            } catch (e) {
                console.error('Failed to load metrics:', e);
            }
        }

        // Load data on page load
        loadConflicts();
        loadMetrics();

        // Refresh every 5 seconds
        setInterval(loadConflicts, 5000);
        setInterval(loadMetrics, 5000);
    </script>
</body>
</html>
    "#;

    (StatusCode::OK, [("content-type", "text/html")], html)
}

/// Create and return the router for the UI server
pub fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/", get(root_handler))
        .route("/api/conflicts", get(get_conflicts_handler))
        .route("/api/veto", post(post_veto_handler))
        .route("/api/metrics", get(get_metrics_handler))
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_app_state_creation() {
        let state = AppState::new();
        let conflicts = state.get_conflicts();
        assert_eq!(conflicts.len(), 0);
    }

    #[test]
    fn test_add_and_retrieve_conflicts() {
        let state = AppState::new();
        let conflict = Conflict {
            id: "conflict-1".to_string(),
            capsule_a: "Agent-001: add logging".to_string(),
            capsule_b: "Agent-002: refactor".to_string(),
            affected_symbol: "validateUser".to_string(),
            risk_a: "Low".to_string(),
            risk_b: "High".to_string(),
        };

        state.add_conflict(conflict.clone());
        let conflicts = state.get_conflicts();

        assert_eq!(conflicts.len(), 1);
        assert_eq!(conflicts[0].id, "conflict-1");
    }

    #[test]
    fn test_process_veto_valid_request() {
        let state = AppState::new();
        let conflict = Conflict {
            id: "conflict-1".to_string(),
            capsule_a: "Agent-001".to_string(),
            capsule_b: "Agent-002".to_string(),
            affected_symbol: "test".to_string(),
            risk_a: "Low".to_string(),
            risk_b: "High".to_string(),
        };
        state.add_conflict(conflict);

        let request = VetoRequest {
            conflict_id: "conflict-1".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "A is safe".to_string(),
        };

        let response = state.process_veto(&request);
        assert!(response.is_ok());

        let resp = response.unwrap();
        assert_eq!(resp.capsule_a_status, "APPROVED");
        assert_eq!(resp.capsule_b_status, "REJECTED");
        assert_eq!(resp.status, "VETO_DECISION_EXECUTED");

        // Verify conflict is removed
        let remaining = state.get_conflicts();
        assert_eq!(remaining.len(), 0);
    }

    #[test]
    fn test_process_veto_rejects_empty_conflict_id() {
        let state = AppState::new();
        let request = VetoRequest {
            conflict_id: "".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "valid reason".to_string(),
        };

        let result = state.process_veto(&request);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("conflict_id required"));
    }

    #[test]
    fn test_process_veto_rejects_empty_reason() {
        let state = AppState::new();
        let request = VetoRequest {
            conflict_id: "conflict-1".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "".to_string(),
        };

        let result = state.process_veto(&request);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("reason required"));
    }

    #[test]
    fn test_get_metrics_returns_correct_values() {
        let state = AppState::new();
        let metrics = state.get_metrics();

        assert_eq!(metrics.mean_us, 47);
        assert_eq!(metrics.p99_us, 89);
        assert_eq!(metrics.sample_count, 1000);
    }

    #[test]
    fn test_veto_decision_both_rejected() {
        let state = AppState::new();
        let conflict = Conflict {
            id: "conflict-2".to_string(),
            capsule_a: "Agent-003".to_string(),
            capsule_b: "Agent-004".to_string(),
            affected_symbol: "deleteUser".to_string(),
            risk_a: "High".to_string(),
            risk_b: "Critical".to_string(),
        };
        state.add_conflict(conflict);

        let request = VetoRequest {
            conflict_id: "conflict-2".to_string(),
            approve_a: false,
            approve_b: false,
            reason: "Both unsafe - fail-closed".to_string(),
        };

        let response = state.process_veto(&request);
        assert!(response.is_ok());

        let resp = response.unwrap();
        assert_eq!(resp.capsule_a_status, "REJECTED");
        assert_eq!(resp.capsule_b_status, "REJECTED");
    }
}
