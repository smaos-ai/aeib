use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use siss_sla_monitor::{
    Alert, AlertSeverity, MetricSnapshot, SLAMonitor, SLAStatus, SLAThresholds,
};
use std::sync::Arc;
use std::net::SocketAddr;

#[derive(Clone)]
pub struct AppState {
    monitor: Arc<SLAMonitor>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let monitor = Arc::new(SLAMonitor::new().await.expect("Failed to create SLA Monitor"));
    let state = AppState { monitor };

    let app = Router::new()
        // Dashboard endpoints
        .route("/", get(dashboard_html))
        .route("/api/status", get(get_status))
        .route("/api/alerts", get(get_alerts))
        .route("/api/metrics", get(get_metrics))
        // Alert management
        .route("/api/alerts/:alert_id/acknowledge", post(acknowledge_alert))
        // Manual intervention
        .route("/api/failover", post(trigger_failover))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 9000));
    println!("SLA Monitor Dashboard listening on http://0.0.0.0:9000");

    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .expect("Failed to bind to port 9000");

    axum::serve(listener, app)
        .await
        .expect("Server error");
}

// HTML Dashboard
async fn dashboard_html() -> impl IntoResponse {
    let html = r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SLA Monitoring Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid rgba(255, 255, 255, 0.1); }
        h1 { font-size: 28px; font-weight: 600; }
        .refresh-info { font-size: 12px; color: #888; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .status-card { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; backdrop-filter: blur(10px); transition: all 0.3s ease; }
        .status-card:hover { background: rgba(255, 255, 255, 0.08); border-color: rgba(255, 255, 255, 0.2); }
        .sla-status-card { grid-column: 1 / -1; background: linear-gradient(135deg, rgba(100, 200, 100, 0.1) 0%, rgba(50, 150, 50, 0.1) 100%); border: 2px solid rgba(100, 200, 100, 0.3); }
        .sla-status-card.yellow { background: linear-gradient(135deg, rgba(255, 180, 0, 0.1) 0%, rgba(255, 150, 0, 0.1) 100%); border-color: rgba(255, 180, 0, 0.3); }
        .sla-status-card.red { background: linear-gradient(135deg, rgba(255, 100, 100, 0.1) 0%, rgba(255, 50, 50, 0.1) 100%); border-color: rgba(255, 100, 100, 0.3); }
        .card-title { font-size: 13px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
        .card-value { font-size: 32px; font-weight: 700; margin-bottom: 5px; }
        .card-unit { font-size: 12px; color: #666; }
        .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #4ade80; margin-right: 8px; animation: pulse 2s infinite; }
        .status-indicator.yellow { background: #fbbf24; }
        .status-indicator.red { background: #f87171; animation: pulse-red 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes pulse-red { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .alerts-section { margin-top: 40px; }
        .section-title { font-size: 20px; font-weight: 600; margin-bottom: 20px; padding-left: 5px; }
        .alert-item { background: rgba(255, 255, 255, 0.03); border-left: 4px solid #4ade80; border-radius: 8px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s ease; }
        .alert-item.warning { border-left-color: #fbbf24; background: rgba(255, 180, 0, 0.05); }
        .alert-item.critical { border-left-color: #f87171; background: rgba(255, 50, 50, 0.05); }
        .alert-content { flex: 1; }
        .alert-type { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .alert-message { font-size: 14px; color: #e0e0e0; margin-bottom: 4px; }
        .alert-time { font-size: 11px; color: #555; }
        .alert-actions { display: flex; gap: 10px; }
        button { background: rgba(74, 222, 128, 0.2); border: 1px solid rgba(74, 222, 128, 0.4); color: #4ade80; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; transition: all 0.3s ease; }
        button:hover { background: rgba(74, 222, 128, 0.3); border-color: rgba(74, 222, 128, 0.6); }
        button.danger { background: rgba(248, 113, 113, 0.2); border-color: rgba(248, 113, 113, 0.4); color: #f87171; }
        button.danger:hover { background: rgba(248, 113, 113, 0.3); border-color: rgba(248, 113, 113, 0.6); }
        .no-alerts { text-align: center; padding: 40px 20px; color: #666; font-style: italic; }
        .intervention-section { background: rgba(100, 150, 255, 0.05); border: 1px solid rgba(100, 150, 255, 0.2); border-radius: 12px; padding: 20px; margin-top: 30px; }
        .intervention-title { font-size: 16px; font-weight: 600; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
        .intervention-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .action-btn { background: rgba(100, 150, 255, 0.3); border: 1px solid rgba(100, 150, 255, 0.5); color: #64b5f6; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.3s ease; }
        .action-btn:hover { background: rgba(100, 150, 255, 0.4); border-color: rgba(100, 150, 255, 0.7); }
        .action-btn.restart { background: rgba(248, 113, 113, 0.2); border-color: rgba(248, 113, 113, 0.4); color: #f87171; }
        .action-btn.restart:hover { background: rgba(248, 113, 113, 0.3); border-color: rgba(248, 113, 113, 0.6); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SLA Monitoring Dashboard</h1>
            <div class="refresh-info">
                <span>Last updated: <span id="last-update">--:--:--</span></span>
            </div>
        </header>

        <div class="status-grid">
            <div class="status-card sla-status-card" id="sla-status">
                <div class="card-title">SLA Status</div>
                <div style="display: flex; align-items: center; gap: 15px;">
                    <span class="status-indicator" id="status-light"></span>
                    <span class="card-value" id="status-text">LOADING</span>
                </div>
            </div>

            <div class="status-card">
                <div class="card-title">Uptime</div>
                <div class="card-value" id="uptime">--</div>
                <div class="card-unit">%</div>
            </div>

            <div class="status-card">
                <div class="card-title">P99 Latency</div>
                <div class="card-value" id="latency">--</div>
                <div class="card-unit">µs</div>
            </div>

            <div class="status-card">
                <div class="card-title">Error Rate</div>
                <div class="card-value" id="error-rate">--</div>
                <div class="card-unit">%</div>
            </div>

            <div class="status-card">
                <div class="card-title">Data Loss</div>
                <div class="card-value" id="data-loss">--</div>
                <div class="card-unit">capsules</div>
            </div>
        </div>

        <div class="alerts-section">
            <h2 class="section-title">Recent Alerts (Last 30)</h2>
            <div id="alerts-container">
                <div class="no-alerts">Loading alerts...</div>
            </div>
        </div>

        <div class="intervention-section">
            <div class="intervention-title">Manual Intervention</div>
            <div class="intervention-actions">
                <button class="action-btn" onclick="triggerFailover()">Force Failover</button>
                <button class="action-btn restart" onclick="restartAgents()">Restart Agent Pool</button>
                <button class="action-btn" onclick="runDiagnostics()">Run Diagnostics</button>
            </div>
        </div>
    </div>

    <script>
        let lastUpdateTime = new Date();

        async function updateDashboard() {
            try {
                const statusRes = await fetch('/api/status');
                const status = await statusRes.json();
                updateStatusDisplay(status);

                const alertsRes = await fetch('/api/alerts');
                const alerts = await alertsRes.json();
                updateAlertsDisplay(alerts || []);

                lastUpdateTime = new Date();
                document.getElementById('last-update').textContent =
                    lastUpdateTime.toLocaleTimeString('en-US', { hour12: false });
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }

        function updateStatusDisplay(status) {
            const slaCard = document.getElementById('sla-status');
            const statusLight = document.getElementById('status-light');
            const statusText = document.getElementById('status-text');

            slaCard.classList.remove('yellow', 'red');
            statusLight.classList.remove('yellow', 'red');
            if (status.status === 'yellow') {
                slaCard.classList.add('yellow');
                statusLight.classList.add('yellow');
            } else if (status.status === 'red') {
                slaCard.classList.add('red');
                statusLight.classList.add('red');
            }

            statusText.textContent = status.status.toUpperCase();
            document.getElementById('uptime').textContent = status.uptime_percent.toFixed(2);
            document.getElementById('latency').textContent = status.p99_latency_us;
            document.getElementById('error-rate').textContent = status.error_rate_percent.toFixed(2);
            document.getElementById('data-loss').textContent = status.data_loss_count;
        }

        function updateAlertsDisplay(alerts) {
            const container = document.getElementById('alerts-container');
            if (!alerts || alerts.length === 0) {
                container.innerHTML = '<div class="no-alerts">✓ No active alerts</div>';
                return;
            }
            container.innerHTML = alerts.map((alert, idx) => `
                <div class="alert-item ${alert.severity}">
                    <div class="alert-content">
                        <div class="alert-type">${alert.alert_type}</div>
                        <div class="alert-message">${alert.message}</div>
                        <div class="alert-time">${new Date(alert.timestamp).toLocaleString()}</div>
                    </div>
                    <div class="alert-actions">
                        <button onclick="acknowledgeAlert('${alert.id}')">
                            ${alert.acknowledged ? '✓ Acknowledged' : 'Acknowledge'}
                        </button>
                    </div>
                </div>
            `).join('');
        }

        async function acknowledgeAlert(alertId) {
            try {
                await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
                updateDashboard();
            } catch (error) {
                console.error('Failed to acknowledge alert:', error);
            }
        }

        async function triggerFailover() {
            if (confirm('Are you sure you want to trigger a failover?')) {
                try {
                    const res = await fetch('/api/failover', { method: 'POST' });
                    const data = await res.json();
                    alert(`Failover: ${data.message}`);
                    updateDashboard();
                } catch (error) {
                    alert('Failed to trigger failover');
                }
            }
        }

        function restartAgents() {
            alert('Agent pool restart initiated (not yet implemented)');
        }

        function runDiagnostics() {
            alert('Diagnostics running... (not yet implemented)');
        }

        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>"#;

    (
        StatusCode::OK,
        [("Content-Type", "text/html; charset=utf-8")],
        html,
    )
}

// API: Get current SLA status
async fn get_status(State(state): State<AppState>) -> impl IntoResponse {
    let status = state.monitor.get_status().await;
    Json(status)
}

// API: Get recent alerts
async fn get_alerts(State(state): State<AppState>) -> impl IntoResponse {
    match state.monitor.get_alert_history(30).await {
        Ok(alerts) => (StatusCode::OK, Json(alerts)).into_response(),
        Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, "Failed to retrieve alerts").into_response(),
    }
}

// API: Get current metrics
async fn get_metrics(State(state): State<AppState>) -> impl IntoResponse {
    let status = state.monitor.get_status().await;
    Json(serde_json::json!({
        "uptime_percent": status.uptime_percent,
        "p99_latency_us": status.p99_latency_us,
        "error_rate_percent": status.error_rate_percent,
        "data_loss_count": status.data_loss_count,
    }))
}

// API: Acknowledge an alert
async fn acknowledge_alert(
    State(state): State<AppState>,
    axum::extract::Path(alert_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    match state.monitor.acknowledge_alert(&alert_id).await {
        Ok(_) => (StatusCode::OK, "Alert acknowledged").into_response(),
        Err(_) => (StatusCode::NOT_FOUND, "Alert not found").into_response(),
    }
}

// API: Trigger failover (manual intervention)
async fn trigger_failover(
    State(_state): State<AppState>,
) -> impl IntoResponse {
    // In a real system, this would trigger a failover procedure
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "status": "failover_initiated",
            "message": "Manual failover triggered"
        })),
    )
}
