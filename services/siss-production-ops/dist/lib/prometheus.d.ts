import { Gauge, Counter, Histogram } from 'prom-client';
export interface Metrics {
    cpuGauge: Gauge;
    memoryGauge: Gauge;
    requestCounter: Counter;
    latencyHistogram: Histogram;
}
export declare function initMetrics(): Metrics;
export declare function resetMetrics(): void;
export declare function recordCpuUsage(percent: number): void;
export declare function recordMemoryUsage(bytes: number): void;
export declare function recordRequestCount(method?: string, path?: string): void;
export declare function recordRequestLatency(latency: number): void;
export declare function getMetricsExport(): Promise<string>;
export declare function getMetrics(): Metrics;
//# sourceMappingURL=prometheus.d.ts.map