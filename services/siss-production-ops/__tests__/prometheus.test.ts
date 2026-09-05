import { describe, it, expect, beforeEach } from 'vitest';
import {
  initMetrics,
  recordCpuUsage,
  recordMemoryUsage,
  recordRequestCount,
  recordRequestLatency,
  getMetricsExport,
  resetMetrics
} from '../src/lib/prometheus';

describe('Prometheus Metrics', () => {
  beforeEach(() => {
    resetMetrics();
    initMetrics();
  });

  describe('Gauge metrics', () => {
    it('should initialize CPU gauge', () => {
      const metrics = initMetrics();
      expect(metrics.cpuGauge).toBeDefined();
    });

    it('should record CPU usage', async () => {
      recordCpuUsage(45.5);
      const exported = await getMetricsExport();
      expect(exported).toContain('cpu_usage_percent 45.5');
    });

    it('should initialize memory gauge', () => {
      const metrics = initMetrics();
      expect(metrics.memoryGauge).toBeDefined();
    });

    it('should record memory usage', async () => {
      recordMemoryUsage(2048);
      const exported = await getMetricsExport();
      expect(exported).toContain('memory_usage_bytes 2048');
    });

    it('should update gauge value', async () => {
      recordCpuUsage(30);
      recordCpuUsage(60);
      const exported = await getMetricsExport();
      expect(exported).toContain('cpu_usage_percent 60');
    });
  });

  describe('Counter metrics', () => {
    it('should initialize request counter', () => {
      const metrics = initMetrics();
      expect(metrics.requestCounter).toBeDefined();
    });

    it('should increment request count', async () => {
      recordRequestCount();
      const exported = await getMetricsExport();
      expect(exported).toContain('http_requests_total 1');
    });

    it('should increment counter multiple times', async () => {
      recordRequestCount();
      recordRequestCount();
      recordRequestCount();
      const exported = await getMetricsExport();
      expect(exported).toContain('http_requests_total 3');
    });

    it('should track request count with labels', async () => {
      recordRequestCount('GET', '/api/health');
      const exported = await getMetricsExport();
      expect(exported).toContain('http_requests_total{method="GET",path="/api/health"} 1');
    });
  });

  describe('Histogram metrics', () => {
    it('should initialize latency histogram', () => {
      const metrics = initMetrics();
      expect(metrics.latencyHistogram).toBeDefined();
    });

    it('should observe request latency', async () => {
      recordRequestLatency(150);
      const exported = await getMetricsExport();
      expect(exported).toContain('http_request_latency_ms_bucket');
    });

    it('should record multiple latency observations', async () => {
      recordRequestLatency(50);
      recordRequestLatency(150);
      recordRequestLatency(300);
      const exported = await getMetricsExport();
      expect(exported).toContain('http_request_latency_ms_count 3');
    });

    it('should calculate sum of latencies', async () => {
      recordRequestLatency(100);
      recordRequestLatency(200);
      const exported = await getMetricsExport();
      expect(exported).toContain('http_request_latency_ms_sum 300');
    });
  });

  describe('Metrics export format', () => {
    it('should return Prometheus text format', async () => {
      recordCpuUsage(50);
      const exported = await getMetricsExport();
      expect(typeof exported).toBe('string');
    });

    it('should include HELP lines for each metric', async () => {
      initMetrics();
      const exported = await getMetricsExport();
      expect(exported).toContain('# HELP cpu_usage_percent');
      expect(exported).toContain('# HELP memory_usage_bytes');
      expect(exported).toContain('# HELP http_requests_total');
      expect(exported).toContain('# HELP http_request_latency_ms');
    });

    it('should include TYPE lines for each metric', async () => {
      initMetrics();
      const exported = await getMetricsExport();
      expect(exported).toContain('# TYPE cpu_usage_percent gauge');
      expect(exported).toContain('# TYPE memory_usage_bytes gauge');
      expect(exported).toContain('# TYPE http_requests_total counter');
      expect(exported).toContain('# TYPE http_request_latency_ms histogram');
    });
  });
});
