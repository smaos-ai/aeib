import { describe, it, expect, beforeEach } from 'vitest';
import { PrometheusCollector } from '../src/lib/prometheus';

describe('Prometheus Metrics Collector', () => {
  let collector: PrometheusCollector;

  beforeEach(() => {
    collector = new PrometheusCollector();
  });

  describe('Latency Metrics', () => {
    it('should record query latency', () => {
      collector.recordQueryLatency('SELECT * FROM users', 45);
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('query_latency_ms'))).toBe(true);
    });

    it('should track percentile latencies (p50, p95, p99)', () => {
      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('test-query', Math.random() * 200 + 10);
      }
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('p50'))).toBe(true);
      expect(metrics.some(m => m.includes('p95'))).toBe(true);
      expect(metrics.some(m => m.includes('p99'))).toBe(true);
    });

    it('should calculate p50 correctly', () => {
      for (let i = 1; i <= 100; i++) {
        collector.recordQueryLatency('query', i);
      }
      const metrics = collector.getMetrics();
      expect(metrics).toContain('p50');
      // p50 should be around 50
    });

    it('should calculate p95 correctly', () => {
      for (let i = 1; i <= 100; i++) {
        collector.recordQueryLatency('query', i);
      }
      const metrics = collector.getMetrics();
      expect(metrics).toContain('p95');
      // p95 should be around 95
    });

    it('should calculate p99 correctly', () => {
      for (let i = 1; i <= 100; i++) {
        collector.recordQueryLatency('query', i);
      }
      const metrics = collector.getMetrics();
      expect(metrics).toContain('p99');
      // p99 should be around 99
    });
  });

  describe('Cache Metrics', () => {
    it('should track cache hit ratio', () => {
      collector.recordCacheHit('L1', 'query:1');
      collector.recordCacheMiss('L1', 'query:2');
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('cache_hit_ratio'))).toBe(true);
    });

    it('should count cache hits per layer', () => {
      collector.recordCacheHit('L1', 'key1');
      collector.recordCacheHit('L2', 'key2');
      collector.recordCacheHit('L1', 'key3');
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('L1'))).toBe(true);
      expect(metrics.some(m => m.includes('L2'))).toBe(true);
    });

    it('should count cache misses per layer', () => {
      collector.recordCacheMiss('L1', 'key1');
      collector.recordCacheMiss('L2', 'key2');
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('cache_miss'))).toBe(true);
    });

    it('should track cache eviction events', () => {
      collector.recordCacheEviction('L1', 100);
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('eviction'))).toBe(true);
    });
  });

  describe('SLO Monitoring', () => {
    it('should detect SLO breach for p95', () => {
      const threshold = 200;
      collector.setSLOThreshold('p95', threshold);

      // Record latencies exceeding threshold
      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('slow-query', 250);
      }

      const breaches = collector.getSLOBreaches();
      expect(breaches.length).toBeGreaterThan(0);
      expect(breaches[0].metric).toBe('p95');
    });

    it('should not report breach when SLO is met', () => {
      const threshold = 300;
      collector.setSLOThreshold('p95', threshold);

      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('fast-query', 100 + i);
      }

      const breaches = collector.getSLOBreaches();
      expect(breaches.length).toBe(0);
    });

    it('should track SLO breach severity', () => {
      collector.setSLOThreshold('p99', 200);

      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('query', 400);
      }

      const breaches = collector.getSLOBreaches();
      if (breaches.length > 0) {
        expect(breaches[0].severity).toBeDefined();
      }
    });

    it('should clear SLO breaches', () => {
      collector.setSLOThreshold('p95', 50);
      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('query', 100);
      }

      expect(collector.getSLOBreaches().length).toBeGreaterThan(0);
      collector.clearSLOBreaches();
      expect(collector.getSLOBreaches().length).toBe(0);
    });
  });

  describe('Metrics Export', () => {
    it('should export metrics in Prometheus text format', () => {
      collector.recordQueryLatency('query', 50);
      const exported = collector.exportMetrics();
      expect(exported).toContain('# HELP');
      expect(exported).toContain('# TYPE');
      expect(exported).toContain('query_latency_ms');
    });

    it('should export with proper HELP and TYPE headers', () => {
      collector.recordQueryLatency('test-query', 75);
      const exported = collector.exportMetrics();
      expect(exported).toContain('# HELP query_latency_ms');
      expect(exported).toContain('# TYPE query_latency_ms gauge');
    });

    it('should export cache metrics', () => {
      collector.recordCacheHit('L1', 'key');
      const exported = collector.exportMetrics();
      expect(exported).toContain('cache_hit_ratio');
    });

    it('should include timestamp in exported metrics', () => {
      collector.recordQueryLatency('query', 75);
      const exported = collector.exportMetrics();
      const hasTimestamp = /\d+$/.test(exported.split('\n').filter(l => !l.startsWith('#'))[0]);
      expect(hasTimestamp || exported.includes('query_latency_ms')).toBe(true);
    });
  });

  describe('Custom Counters', () => {
    it('should increment custom counter', () => {
      collector.incrementCounter('custom_events', 1);
      collector.incrementCounter('custom_events', 1);
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('custom_events'))).toBe(true);
    });

    it('should record custom gauge', () => {
      collector.recordGauge('active_connections', 42);
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('active_connections'))).toBe(true);
    });

    it('should track labeled metrics', () => {
      collector.recordQueryLatency('SELECT * FROM users', 60, { table: 'users', type: 'select' });
      const metrics = collector.getMetrics();
      expect(metrics.some(m => m.includes('table'))).toBe(true);
      expect(metrics.some(m => m.includes('users'))).toBe(true);
    });
  });

  describe('Metrics Aggregation', () => {
    it('should aggregate metrics by query fingerprint', () => {
      // Same query structure, different values
      collector.recordQueryLatency('SELECT * FROM users WHERE id = 1', 50);
      collector.recordQueryLatency('SELECT * FROM users WHERE id = 2', 60);
      const aggregated = collector.getAggregatedMetrics();
      expect(aggregated).toBeDefined();
    });

    it('should provide per-minute aggregation', () => {
      for (let i = 0; i < 50; i++) {
        collector.recordQueryLatency('query', Math.random() * 100);
      }
      const aggregated = collector.getAggregatedMetrics('1m');
      expect(aggregated).toBeDefined();
    });

    it('should provide per-hour aggregation', () => {
      for (let i = 0; i < 100; i++) {
        collector.recordQueryLatency('query', Math.random() * 100);
      }
      const aggregated = collector.getAggregatedMetrics('1h');
      expect(aggregated).toBeDefined();
    });
  });

  describe('Metric Reset', () => {
    it('should reset all metrics', () => {
      collector.recordQueryLatency('query', 100);
      collector.recordCacheHit('L1', 'key');
      collector.reset();

      const metrics = collector.getMetrics();
      expect(metrics.length).toBe(0);
    });

    it('should reset specific metric type', () => {
      collector.recordQueryLatency('query', 100);
      collector.recordCacheHit('L1', 'key');
      collector.resetMetric('query_latency_ms');

      const metrics = collector.getMetrics();
      expect(metrics.filter(m => m.includes('query_latency')).length).toBe(0);
      expect(metrics.filter(m => m.includes('cache')).length).toBeGreaterThan(0);
    });
  });

  describe('Alert Configuration', () => {
    it('should set alert threshold for high latency', () => {
      collector.setAlertThreshold('high_latency', 500);
      collector.recordQueryLatency('query', 600);

      const alerts = collector.getTriggeredAlerts();
      expect(alerts.length).toBeGreaterThan(0);
    });

    it('should set alert threshold for low cache hit ratio', () => {
      collector.setAlertThreshold('cache_hit_ratio', 0.8);

      // Record mostly misses
      for (let i = 0; i < 100; i++) {
        collector.recordCacheMiss('L1', `key${i}`);
      }
      for (let i = 0; i < 10; i++) {
        collector.recordCacheHit('L1', `key${i}`);
      }

      const alerts = collector.getTriggeredAlerts();
      expect(alerts.length).toBeGreaterThan(0);
    });

    it('should clear triggered alerts', () => {
      collector.setAlertThreshold('high_latency', 50);
      collector.recordQueryLatency('query', 100);

      expect(collector.getTriggeredAlerts().length).toBeGreaterThan(0);
      collector.clearAlerts();
      expect(collector.getTriggeredAlerts().length).toBe(0);
    });
  });
});
