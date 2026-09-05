interface Panel {
  id: number;
  title: string;
  type: string;
  targets: Array<{ expr: string }>;
  gridPos: { h: number; w: number; x: number; y: number };
}

interface Dashboard {
  title: string;
  refresh: string;
  panels: Panel[];
}

function createPanel(
  id: number,
  title: string,
  expr: string,
  x: number,
  y: number
): Panel {
  return {
    id,
    title,
    type: 'graph',
    targets: [{ expr }],
    gridPos: { h: 8, w: 12, x, y }
  };
}

function createDashboard(title: string, panels: Panel[]): Dashboard {
  return {
    title,
    refresh: '30s',
    panels
  };
}

export function generateSystemHealthDashboard(): string {
  const panels: Panel[] = [
    createPanel(1, 'CPU Usage', 'cpu_usage_percent', 0, 0),
    createPanel(2, 'Memory Usage', 'memory_usage_bytes', 12, 0)
  ];

  const dashboard = createDashboard('System Health', panels);
  return JSON.stringify(dashboard);
}

export function generateAppMetricsDashboard(): string {
  const panels: Panel[] = [
    createPanel(
      1,
      'Request Rate',
      'rate(http_requests_total[1m])',
      0,
      0
    ),
    createPanel(
      2,
      'Request Latency',
      'http_request_latency_ms',
      12,
      0
    )
  ];

  const dashboard = createDashboard('Application Metrics', panels);
  return JSON.stringify(dashboard);
}

export function generateBusinessMetricsDashboard(): string {
  const panels: Panel[] = [
    createPanel(
      1,
      'Error Rate',
      'rate(http_requests_total{status=~"5.."}[1m])',
      0,
      0
    ),
    createPanel(
      2,
      'Compliance Score',
      'compliance_score_percent',
      12,
      0
    )
  ];

  const dashboard = createDashboard('Business Metrics', panels);
  return JSON.stringify(dashboard);
}
