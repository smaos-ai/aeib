function createPanel(id, title, expr, x, y) {
    return {
        id,
        title,
        type: 'graph',
        targets: [{ expr }],
        gridPos: { h: 8, w: 12, x, y }
    };
}
function createDashboard(title, panels) {
    return {
        title,
        refresh: '30s',
        panels
    };
}
export function generateSystemHealthDashboard() {
    const panels = [
        createPanel(1, 'CPU Usage', 'cpu_usage_percent', 0, 0),
        createPanel(2, 'Memory Usage', 'memory_usage_bytes', 12, 0)
    ];
    const dashboard = createDashboard('System Health', panels);
    return JSON.stringify(dashboard);
}
export function generateAppMetricsDashboard() {
    const panels = [
        createPanel(1, 'Request Rate', 'rate(http_requests_total[1m])', 0, 0),
        createPanel(2, 'Request Latency', 'http_request_latency_ms', 12, 0)
    ];
    const dashboard = createDashboard('Application Metrics', panels);
    return JSON.stringify(dashboard);
}
export function generateBusinessMetricsDashboard() {
    const panels = [
        createPanel(1, 'Error Rate', 'rate(http_requests_total{status=~"5.."}[1m])', 0, 0),
        createPanel(2, 'Compliance Score', 'compliance_score_percent', 12, 0)
    ];
    const dashboard = createDashboard('Business Metrics', panels);
    return JSON.stringify(dashboard);
}
//# sourceMappingURL=dashboards.js.map