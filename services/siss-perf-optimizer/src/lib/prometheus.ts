interface MetricValue {
  value: number;
  timestamp?: number;
  labels?: Record<string, string>;
}

interface SLOBreach {
  metric: string;
  threshold: number;
  actual: number;
  severity: string;
  timestamp: number;
}

interface Alert {
  threshold: string;
  value: number;
  timestamp: number;
}

export class PrometheusCollector {
  private metrics: Map<string, MetricValue[]> = new Map();
  private sloThresholds: Map<string, number> = new Map();
  private sloBreaches: SLOBreach[] = [];
  private alertThresholds: Map<string, number> = new Map();
  private triggeredAlerts: Alert[] = [];
  private latencies: number[] = [];

  recordQueryLatency(query: string, latency: number, labels?: Record<string, string>): void {
    const key = 'query_latency_ms';
    if (!this.metrics.has(key)) {
      this.metrics.set(key, []);
    }
    this.metrics.get(key)!.push({
      value: latency,
      timestamp: Date.now(),
      labels
    });
    this.latencies.push(latency);

    // Check SLO breach
    this.checkSLOBreach('p95');
    this.checkSLOBreach('p99');

    // Check alerts
    this.checkAlerts('high_latency', latency);
  }

  recordCacheHit(layer: string, key: string): void {
    const metricKey = `cache_hit_${layer}`;
    if (!this.metrics.has(metricKey)) {
      this.metrics.set(metricKey, []);
    }
    this.metrics.get(metricKey)!.push({
      value: 1,
      timestamp: Date.now()
    });

    this.updateCacheHitRatio();
  }

  recordCacheMiss(layer: string, key: string): void {
    const metricKey = `cache_miss_${layer}`;
    if (!this.metrics.has(metricKey)) {
      this.metrics.set(metricKey, []);
    }
    this.metrics.get(metricKey)!.push({
      value: 1,
      timestamp: Date.now()
    });

    this.updateCacheHitRatio();
  }

  recordCacheEviction(layer: string, count: number): void {
    const key = `cache_eviction_${layer}`;
    if (!this.metrics.has(key)) {
      this.metrics.set(key, []);
    }
    this.metrics.get(key)!.push({
      value: count,
      timestamp: Date.now()
    });
  }

  setSLOThreshold(metric: string, threshold: number): void {
    this.sloThresholds.set(metric, threshold);
  }

  getSLOBreaches(): SLOBreach[] {
    return [...this.sloBreaches];
  }

  clearSLOBreaches(): void {
    this.sloBreaches = [];
  }

  setAlertThreshold(metric: string, threshold: number): void {
    this.alertThresholds.set(metric, threshold);
  }

  getTriggeredAlerts(): Alert[] {
    return [...this.triggeredAlerts];
  }

  clearAlerts(): void {
    this.triggeredAlerts = [];
  }

  incrementCounter(name: string, value: number): void {
    const key = name;
    if (!this.metrics.has(key)) {
      this.metrics.set(key, [{ value: 0 }]);
    }
    const values = this.metrics.get(key)!;
    values[values.length - 1].value += value;
  }

  recordGauge(name: string, value: number): void {
    const key = name;
    if (!this.metrics.has(key)) {
      this.metrics.set(key, []);
    }
    this.metrics.get(key)!.push({
      value,
      timestamp: Date.now()
    });
  }

  getMetrics(): string[] {
    const result: string[] = [];
    for (const [key, values] of this.metrics) {
      for (const v of values) {
        result.push(`${key}{${v.labels ? Object.entries(v.labels).map(([k, val]) => `${k}="${val}"`).join(',') : ''}} ${v.value}`);
      }
    }

    // Add percentiles if we have latency data
    if (this.latencies.length > 0) {
      const sorted = [...this.latencies].sort((a, b) => a - b);
      const p50 = sorted[Math.floor(sorted.length * 0.5)];
      const p95 = sorted[Math.floor(sorted.length * 0.95)];
      const p99 = sorted[Math.floor(sorted.length * 0.99)];

      result.push(`p50 ${p50}`);
      result.push(`p95 ${p95}`);
      result.push(`p99 ${p99}`);
    }

    return result;
  }

  exportMetrics(): string {
    const lines: string[] = [];

    for (const [key] of this.metrics) {
      lines.push(`# HELP ${key} Metric ${key}`);
      lines.push(`# TYPE ${key} gauge`);

      const values = this.metrics.get(key)!;
      for (const v of values) {
        const labels = v.labels ? `{${Object.entries(v.labels).map(([k, val]) => `${k}="${val}"`).join(',')}}` : '';
        lines.push(`${key}${labels} ${v.value} ${v.timestamp || Date.now()}`);
      }
    }

    return lines.join('\n');
  }

  getAggregatedMetrics(interval?: string): Record<string, any> {
    const aggregated: Record<string, any> = {};

    if (this.latencies.length > 0) {
      const sorted = [...this.latencies].sort((a, b) => a - b);
      const p50 = sorted[Math.floor(sorted.length * 0.5)];
      const p95 = sorted[Math.floor(sorted.length * 0.95)];
      const p99 = sorted[Math.floor(sorted.length * 0.99)];

      aggregated.p50 = p50;
      aggregated.p95 = p95;
      aggregated.p99 = p99;
      aggregated.avg = sorted.reduce((a, b) => a + b) / sorted.length;
      aggregated.min = sorted[0];
      aggregated.max = sorted[sorted.length - 1];
      aggregated.count = sorted.length;
    }

    return aggregated;
  }

  reset(): void {
    this.metrics.clear();
    this.latencies = [];
    this.sloBreaches = [];
    this.triggeredAlerts = [];
  }

  resetMetric(metricName: string): void {
    this.metrics.delete(metricName);
  }

  private updateCacheHitRatio(): void {
    let hits = 0;
    let misses = 0;

    for (const [key, values] of this.metrics) {
      if (key.startsWith('cache_hit_')) {
        hits += values.length;
      } else if (key.startsWith('cache_miss_')) {
        misses += values.length;
      }
    }

    const total = hits + misses;
    if (total > 0) {
      const ratio = hits / total;
      this.recordGauge('cache_hit_ratio', ratio);

      // Check cache hit ratio alert
      this.checkAlerts('cache_hit_ratio', ratio);
    }
  }

  private checkSLOBreach(metric: string): void {
    const threshold = this.sloThresholds.get(metric);
    if (!threshold || this.latencies.length < 5) return;

    const sorted = [...this.latencies].sort((a, b) => a - b);
    let actual = 0;

    if (metric === 'p50') {
      actual = sorted[Math.floor(sorted.length * 0.5)];
    } else if (metric === 'p95') {
      actual = sorted[Math.floor(sorted.length * 0.95)];
    } else if (metric === 'p99') {
      actual = sorted[Math.floor(sorted.length * 0.99)];
    }

    if (actual > threshold) {
      const breach: SLOBreach = {
        metric,
        threshold,
        actual,
        severity: actual > threshold * 2 ? 'critical' : 'warning',
        timestamp: Date.now()
      };

      // Avoid duplicate breaches
      if (!this.sloBreaches.some(b => b.metric === metric && b.timestamp > Date.now() - 60000)) {
        this.sloBreaches.push(breach);
      }
    }
  }

  private checkAlerts(type: string, value: number): void {
    const threshold = this.alertThresholds.get(type);
    if (!threshold) return;

    const shouldAlert = type === 'high_latency' ? value > threshold : value < threshold;

    if (shouldAlert) {
      this.triggeredAlerts.push({
        threshold: type,
        value,
        timestamp: Date.now()
      });
    }
  }
}
