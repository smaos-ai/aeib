export interface AlertCondition {
  type: 'latency' | 'error_rate' | 'compliance';
  triggered: boolean;
  timestamp: number;
  value: number;
  threshold: number;
}

let alertHistory: AlertCondition[] = [];

export function initAlerts(): void {
  alertHistory = [];
}

export function evaluateLatencyAlert(
  p95Latency: number,
  threshold: number
): boolean {
  const triggered = p95Latency > threshold;

  alertHistory.push({
    type: 'latency',
    triggered,
    timestamp: Date.now(),
    value: p95Latency,
    threshold
  });

  return triggered;
}

export function evaluateErrorRateAlert(
  errorRate: number,
  threshold: number
): boolean {
  const triggered = errorRate > threshold;

  alertHistory.push({
    type: 'error_rate',
    triggered,
    timestamp: Date.now(),
    value: errorRate,
    threshold
  });

  return triggered;
}

export function evaluateComplianceAlert(
  complianceScore: number,
  threshold: number
): boolean {
  const triggered = complianceScore < threshold;

  alertHistory.push({
    type: 'compliance',
    triggered,
    timestamp: Date.now(),
    value: complianceScore,
    threshold
  });

  return triggered;
}

export function getAlertHistory(): AlertCondition[] {
  return [...alertHistory];
}

export function clearAlertHistory(): void {
  alertHistory = [];
}
