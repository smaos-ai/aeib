let alertHistory = [];
export function initAlerts() {
    alertHistory = [];
}
export function evaluateLatencyAlert(p95Latency, threshold) {
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
export function evaluateErrorRateAlert(errorRate, threshold) {
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
export function evaluateComplianceAlert(complianceScore, threshold) {
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
export function getAlertHistory() {
    return [...alertHistory];
}
export function clearAlertHistory() {
    alertHistory = [];
}
//# sourceMappingURL=alerts.js.map