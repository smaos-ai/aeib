import { register, Gauge, Counter, Histogram, collectDefaultMetrics } from 'prom-client';
let metricsInitialized = false;
let defaultMetricsRegistered = false;
let metrics;
export function initMetrics() {
    if (metricsInitialized) {
        return metrics;
    }
    if (!defaultMetricsRegistered) {
        collectDefaultMetrics();
        defaultMetricsRegistered = true;
    }
    metrics = {
        cpuGauge: new Gauge({
            name: 'cpu_usage_percent',
            help: 'Current CPU usage percentage',
            registers: [register]
        }),
        memoryGauge: new Gauge({
            name: 'memory_usage_bytes',
            help: 'Current memory usage in bytes',
            registers: [register]
        }),
        requestCounter: new Counter({
            name: 'http_requests_total',
            help: 'Total number of HTTP requests',
            labelNames: ['method', 'path'],
            registers: [register]
        }),
        latencyHistogram: new Histogram({
            name: 'http_request_latency_ms',
            help: 'HTTP request latency in milliseconds',
            buckets: [10, 50, 100, 250, 500, 1000, 2500, 5000],
            registers: [register]
        })
    };
    metricsInitialized = true;
    return metrics;
}
export function resetMetrics() {
    metricsInitialized = false;
    defaultMetricsRegistered = false;
    // Clear all custom metrics
    try {
        register.clear();
    }
    catch (e) {
        // Ignore if already cleared
    }
}
export function recordCpuUsage(percent) {
    if (!metricsInitialized)
        initMetrics();
    metrics.cpuGauge.set(percent);
}
export function recordMemoryUsage(bytes) {
    if (!metricsInitialized)
        initMetrics();
    metrics.memoryGauge.set(bytes);
}
export function recordRequestCount(method, path) {
    if (!metricsInitialized)
        initMetrics();
    if (method && path) {
        metrics.requestCounter.labels(method, path).inc();
    }
    else {
        metrics.requestCounter.inc();
    }
}
export function recordRequestLatency(latency) {
    if (!metricsInitialized)
        initMetrics();
    metrics.latencyHistogram.observe(latency);
}
export async function getMetricsExport() {
    return await register.metrics();
}
export function getMetrics() {
    if (!metricsInitialized) {
        initMetrics();
    }
    return metrics;
}
//# sourceMappingURL=prometheus.js.map