import { describe, it, expect } from 'vitest';
import {
  generateSystemHealthDashboard,
  generateAppMetricsDashboard,
  generateBusinessMetricsDashboard
} from '../src/lib/dashboards';

describe('Grafana Dashboard Generation', () => {
  describe('System Health Dashboard', () => {
    it('should generate valid JSON dashboard', () => {
      const dashboard = generateSystemHealthDashboard();
      expect(dashboard).toBeDefined();
      expect(typeof dashboard).toBe('string');
    });

    it('should contain dashboard title', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      expect(parsed.title).toBe('System Health');
    });

    it('should contain CPU usage panel', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      const cpuPanel = parsed.panels.find((p: any) => p.title === 'CPU Usage');
      expect(cpuPanel).toBeDefined();
    });

    it('should contain memory usage panel', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      const memPanel = parsed.panels.find((p: any) => p.title === 'Memory Usage');
      expect(memPanel).toBeDefined();
    });

    it('should have correct metric names in panels', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      const cpuPanel = parsed.panels.find((p: any) => p.title === 'CPU Usage');
      expect(cpuPanel.targets[0].expr).toContain('cpu_usage_percent');
    });

    it('should include dashboard refresh interval', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      expect(parsed.refresh).toBeDefined();
    });
  });

  describe('App Metrics Dashboard', () => {
    it('should generate valid JSON dashboard', () => {
      const dashboard = generateAppMetricsDashboard();
      expect(dashboard).toBeDefined();
      expect(typeof dashboard).toBe('string');
    });

    it('should contain dashboard title', () => {
      const dashboard = generateAppMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      expect(parsed.title).toBe('Application Metrics');
    });

    it('should contain request rate panel', () => {
      const dashboard = generateAppMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      const requestPanel = parsed.panels.find((p: any) => p.title === 'Request Rate');
      expect(requestPanel).toBeDefined();
    });

    it('should contain latency panel', () => {
      const dashboard = generateAppMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      const latencyPanel = parsed.panels.find((p: any) => p.title === 'Request Latency');
      expect(latencyPanel).toBeDefined();
    });

    it('should have histogram metric in latency panel', () => {
      const dashboard = generateAppMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      const latencyPanel = parsed.panels.find((p: any) => p.title === 'Request Latency');
      expect(latencyPanel.targets[0].expr).toContain('http_request_latency_ms');
    });
  });

  describe('Business Metrics Dashboard', () => {
    it('should generate valid JSON dashboard', () => {
      const dashboard = generateBusinessMetricsDashboard();
      expect(dashboard).toBeDefined();
      expect(typeof dashboard).toBe('string');
    });

    it('should contain dashboard title', () => {
      const dashboard = generateBusinessMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      expect(parsed.title).toBe('Business Metrics');
    });

    it('should contain error rate panel', () => {
      const dashboard = generateBusinessMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      const errorPanel = parsed.panels.find((p: any) => p.title === 'Error Rate');
      expect(errorPanel).toBeDefined();
    });

    it('should contain compliance score panel', () => {
      const dashboard = generateBusinessMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      const compliancePanel = parsed.panels.find((p: any) => p.title === 'Compliance Score');
      expect(compliancePanel).toBeDefined();
    });

    it('all dashboards should have valid JSON structure', () => {
      const dashboards = [
        generateSystemHealthDashboard(),
        generateAppMetricsDashboard(),
        generateBusinessMetricsDashboard()
      ];
      dashboards.forEach(d => {
        expect(() => JSON.parse(d)).not.toThrow();
      });
    });
  });

  describe('Dashboard structure requirements', () => {
    it('should have panels array', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      expect(Array.isArray(parsed.panels)).toBe(true);
    });

    it('each panel should have targets', () => {
      const dashboard = generateAppMetricsDashboard();
      const parsed = JSON.parse(dashboard);
      parsed.panels.forEach((panel: any) => {
        expect(Array.isArray(panel.targets)).toBe(true);
        expect(panel.targets.length).toBeGreaterThan(0);
      });
    });

    it('each panel should have id, title, type', () => {
      const dashboard = generateSystemHealthDashboard();
      const parsed = JSON.parse(dashboard);
      parsed.panels.forEach((panel: any) => {
        expect(panel.id).toBeDefined();
        expect(panel.title).toBeDefined();
        expect(panel.type).toBeDefined();
      });
    });

    it('should have at least 2 panels per dashboard', () => {
      const dashboards = [
        generateSystemHealthDashboard(),
        generateAppMetricsDashboard(),
        generateBusinessMetricsDashboard()
      ];
      dashboards.forEach(d => {
        const parsed = JSON.parse(d);
        expect(parsed.panels.length).toBeGreaterThanOrEqual(2);
      });
    });
  });
});
