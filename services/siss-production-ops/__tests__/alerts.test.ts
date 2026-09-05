import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  initAlerts,
  evaluateLatencyAlert,
  evaluateErrorRateAlert,
  evaluateComplianceAlert,
  AlertCondition,
  getAlertHistory
} from '../src/lib/alerts';

describe('Alert Rules', () => {
  beforeEach(() => {
    initAlerts();
  });

  describe('Latency Alert Rules', () => {
    it('should detect p95 latency breach', () => {
      const latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600];
      const p95 = 570;

      const triggered = evaluateLatencyAlert(p95, 500);
      expect(triggered).toBe(true);
    });

    it('should not trigger when p95 is below threshold', () => {
      const p95 = 450;
      const threshold = 500;

      const triggered = evaluateLatencyAlert(p95, threshold);
      expect(triggered).toBe(false);
    });

    it('should detect edge case at exact threshold', () => {
      const p95 = 500;
      const threshold = 500;

      const triggered = evaluateLatencyAlert(p95, threshold);
      expect(triggered).toBe(false);
    });

    it('should handle very high latencies', () => {
      const p95 = 5000;
      const threshold = 500;

      const triggered = evaluateLatencyAlert(p95, threshold);
      expect(triggered).toBe(true);
    });

    it('should detect breach with custom threshold', () => {
      const p95 = 1200;
      const threshold = 1000;

      const triggered = evaluateLatencyAlert(p95, threshold);
      expect(triggered).toBe(true);
    });
  });

  describe('Error Rate Alert Rules', () => {
    it('should detect error rate breach', () => {
      const errorRate = 2.5; // 2.5%

      const triggered = evaluateErrorRateAlert(errorRate, 1.0);
      expect(triggered).toBe(true);
    });

    it('should not trigger when error rate is below threshold', () => {
      const errorRate = 0.5; // 0.5%

      const triggered = evaluateErrorRateAlert(errorRate, 1.0);
      expect(triggered).toBe(false);
    });

    it('should handle zero error rate', () => {
      const errorRate = 0;

      const triggered = evaluateErrorRateAlert(errorRate, 1.0);
      expect(triggered).toBe(false);
    });

    it('should detect high error rate', () => {
      const errorRate = 10.0; // 10%

      const triggered = evaluateErrorRateAlert(errorRate, 1.0);
      expect(triggered).toBe(true);
    });

    it('should handle custom error threshold', () => {
      const errorRate = 5.0;
      const threshold = 3.0;

      const triggered = evaluateErrorRateAlert(errorRate, threshold);
      expect(triggered).toBe(true);
    });
  });

  describe('Compliance Score Alert Rules', () => {
    it('should detect compliance score drop', () => {
      const score = 75;
      const threshold = 85;

      const triggered = evaluateComplianceAlert(score, threshold);
      expect(triggered).toBe(true);
    });

    it('should not trigger when compliance is above threshold', () => {
      const score = 90;
      const threshold = 85;

      const triggered = evaluateComplianceAlert(score, threshold);
      expect(triggered).toBe(false);
    });

    it('should handle zero compliance score', () => {
      const score = 0;
      const threshold = 85;

      const triggered = evaluateComplianceAlert(score, threshold);
      expect(triggered).toBe(true);
    });

    it('should handle edge case at exact threshold', () => {
      const score = 85;
      const threshold = 85;

      const triggered = evaluateComplianceAlert(score, threshold);
      expect(triggered).toBe(false);
    });

    it('should handle perfect compliance score', () => {
      const score = 100;
      const threshold = 85;

      const triggered = evaluateComplianceAlert(score, threshold);
      expect(triggered).toBe(false);
    });
  });

  describe('Alert History Tracking', () => {
    it('should record alert evaluations', () => {
      evaluateLatencyAlert(600, 500);
      const history = getAlertHistory();
      expect(history.length).toBeGreaterThan(0);
    });

    it('should include alert type in history', () => {
      evaluateLatencyAlert(600, 500);
      const history = getAlertHistory();
      expect(history[0].type).toBeDefined();
    });

    it('should include triggered status in history', () => {
      evaluateLatencyAlert(600, 500);
      const history = getAlertHistory();
      expect(history[0].triggered).toBe(true);
    });

    it('should track multiple alert evaluations', () => {
      evaluateLatencyAlert(600, 500);
      evaluateErrorRateAlert(2.0, 1.0);
      evaluateComplianceAlert(70, 85);

      const history = getAlertHistory();
      expect(history.length).toBe(3);
    });

    it('should maintain chronological order', () => {
      evaluateLatencyAlert(600, 500);
      evaluateErrorRateAlert(2.0, 1.0);

      const history = getAlertHistory();
      expect(history[0].timestamp).toBeLessThanOrEqual(history[1].timestamp);
    });
  });

  describe('Complex Alert Scenarios', () => {
    it('should handle multiple alerts triggering simultaneously', () => {
      const latencyTriggered = evaluateLatencyAlert(600, 500);
      const errorTriggered = evaluateErrorRateAlert(2.0, 1.0);
      const complianceTriggered = evaluateComplianceAlert(70, 85);

      expect(latencyTriggered).toBe(true);
      expect(errorTriggered).toBe(true);
      expect(complianceTriggered).toBe(true);

      const history = getAlertHistory();
      expect(history.length).toBe(3);
    });

    it('should track mixed alert states', () => {
      evaluateLatencyAlert(400, 500); // not triggered
      evaluateErrorRateAlert(2.0, 1.0); // triggered
      evaluateComplianceAlert(90, 85); // not triggered

      const history = getAlertHistory();
      expect(history[0].triggered).toBe(false);
      expect(history[1].triggered).toBe(true);
      expect(history[2].triggered).toBe(false);
    });

    it('should handle repeated evaluations of same alert', () => {
      evaluateLatencyAlert(600, 500);
      evaluateLatencyAlert(650, 500);
      evaluateLatencyAlert(450, 500);

      const history = getAlertHistory();
      expect(history.length).toBe(3);
      expect(history[2].triggered).toBe(false);
    });
  });
});
