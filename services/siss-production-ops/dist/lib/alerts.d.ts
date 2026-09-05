export interface AlertCondition {
    type: 'latency' | 'error_rate' | 'compliance';
    triggered: boolean;
    timestamp: number;
    value: number;
    threshold: number;
}
export declare function initAlerts(): void;
export declare function evaluateLatencyAlert(p95Latency: number, threshold: number): boolean;
export declare function evaluateErrorRateAlert(errorRate: number, threshold: number): boolean;
export declare function evaluateComplianceAlert(complianceScore: number, threshold: number): boolean;
export declare function getAlertHistory(): AlertCondition[];
export declare function clearAlertHistory(): void;
//# sourceMappingURL=alerts.d.ts.map