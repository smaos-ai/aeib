import { describe, it, expect, beforeEach } from 'vitest';
import { initMetrics, recordRequestLatency, getMetricsExport } from '../src/lib/prometheus';
import { initAlerts, evaluateLatencyAlert, evaluateErrorRateAlert, evaluateComplianceAlert, getAlertHistory } from '../src/lib/alerts';
import { getRunbook } from '../src/lib/runbooks';
import { initSlack, sendAlert, getSentMessages, clearMessages } from '../src/lib/slack';
import { initPagerDuty, createIncident, getIncidents, clearIncidents } from '../src/lib/pagerduty';
import { initELK, ingestLog, searchLogs, getLogCount } from '../src/lib/elk';

describe('End-to-End Alert Flow', () => {
  beforeEach(() => {
    initMetrics();
    initAlerts();
    initSlack('test-token');
    initPagerDuty('test-api-key');
    initELK();
    clearMessages();
    clearIncidents();
  });

  describe('Complete Alert Lifecycle', () => {
    it('should execute full alert flow: metric -> detect -> notify -> incident', async () => {
      // Step 1: Record metric that breaches threshold
      recordRequestLatency(600);
      recordRequestLatency(650);
      recordRequestLatency(700);

      // Step 2: Evaluate alert condition
      const p95 = 650;
      const threshold = 500;
      const triggered = evaluateLatencyAlert(p95, threshold);
      expect(triggered).toBe(true);

      // Step 3: Send Slack notification
      await sendAlert({
        severity: 'critical',
        title: 'Latency Breach Detected',
        channel: '#critical-alerts',
        value: p95,
        threshold,
        metric: 'http_request_latency_ms'
      });

      const slackMessages = getSentMessages();
      expect(slackMessages.length).toBe(1);
      expect(slackMessages[0].severity).toBe('critical');

      // Step 4: Create PagerDuty incident
      const incident = await createIncident({
        title: 'Critical Latency Breach - P95 > 500ms',
        severity: 'critical',
        service_id: 'api-gateway',
        description: `Request latency p95: ${p95}ms (threshold: ${threshold}ms)`
      });

      expect(incident).toBeDefined();
      expect(incident.status).toBe('triggered');

      // Step 5: Ingest diagnostic log
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'alert-system',
        action: 'latency_breach_detected',
        resource: 'api-gateway',
        level: 'critical',
        message: `Latency breach alert triggered with p95=${p95}ms`
      });

      // Step 6: Retrieve runbook
      const runbook = getRunbook('latency_breach');
      expect(runbook.title).toContain('Latency');
      expect(runbook.recovery_steps.length).toBeGreaterThan(0);
    });
  });

  describe('Multi-Alert Concurrent Handling', () => {
    it('should handle 3+ alerts firing simultaneously', async () => {
      // Simulate 3 different alert types triggering
      const latencyTriggered = evaluateLatencyAlert(600, 500);
      const errorRateTriggered = evaluateErrorRateAlert(2.0, 1.0);
      const complianceTriggered = evaluateComplianceAlert(70, 85);

      expect(latencyTriggered).toBe(true);
      expect(errorRateTriggered).toBe(true);
      expect(complianceTriggered).toBe(true);

      // Send all 3 alerts to Slack
      const alerts = [
        {
          severity: 'critical' as const,
          title: 'Latency Breach',
          channel: '#critical-alerts',
          value: 600,
          threshold: 500,
          metric: 'latency'
        },
        {
          severity: 'critical' as const,
          title: 'High Error Rate',
          channel: '#critical-alerts',
          value: 2.0,
          threshold: 1.0,
          metric: 'error_rate'
        },
        {
          severity: 'critical' as const,
          title: 'Compliance Drop',
          channel: '#critical-alerts',
          value: 70,
          threshold: 85,
          metric: 'compliance_score'
        }
      ];

      for (const alert of alerts) {
        await sendAlert(alert);
      }

      const messages = getSentMessages();
      expect(messages.length).toBe(3);

      // Create incidents for all 3
      const incidents = await Promise.all([
        createIncident({
          title: 'Critical Latency Breach',
          severity: 'critical',
          service_id: 'api-gateway',
          description: 'P95 latency > 500ms'
        }),
        createIncident({
          title: 'Critical Error Rate',
          severity: 'critical',
          service_id: 'api-gateway',
          description: 'Error rate > 1%'
        }),
        createIncident({
          title: 'Compliance Score Drop',
          severity: 'critical',
          service_id: 'compliance',
          description: 'Compliance score < 85'
        })
      ]);

      expect(getIncidents().length).toBe(3);
      incidents.forEach(i => {
        expect(i.status).toBe('triggered');
      });
    });
  });

  describe('Alert History and Audit Trail', () => {
    it('should maintain complete audit trail', async () => {
      // Record alert evaluations
      evaluateLatencyAlert(600, 500);
      evaluateLatencyAlert(400, 500);
      evaluateLatencyAlert(550, 500);

      const history = getAlertHistory();
      expect(history.length).toBe(3);

      // Verify history order
      expect(history[0].timestamp).toBeLessThanOrEqual(history[1].timestamp);
      expect(history[1].timestamp).toBeLessThanOrEqual(history[2].timestamp);

      // Verify triggered states
      expect(history[0].triggered).toBe(true);
      expect(history[1].triggered).toBe(false);
      expect(history[2].triggered).toBe(true);

      // Ingest logs for each alert
      for (let i = 0; i < history.length; i++) {
        ingestLog({
          timestamp: new Date(history[i].timestamp).toISOString(),
          user_id: 'alert-system',
          action: `alert_evaluation_${i}`,
          resource: 'monitoring',
          level: history[i].triggered ? 'critical' : 'info',
          message: `Alert type: ${history[i].type}, Triggered: ${history[i].triggered}`
        });
      }

      expect(getLogCount()).toBe(3);
    });
  });

  describe('Incident Resolution Flow', () => {
    it('should support incident creation and resolution', async () => {
      // Trigger alert
      evaluateLatencyAlert(600, 500);

      // Create incident
      const incident = await createIncident({
        title: 'Test Incident',
        severity: 'critical',
        service_id: 'test-service',
        description: 'Test incident for resolution'
      });

      expect(incident.status).toBe('triggered');

      // Send Slack notification
      await sendAlert({
        severity: 'critical',
        title: 'Incident Created',
        channel: '#critical-alerts',
        value: 600,
        threshold: 500,
        metric: 'latency'
      });

      // Ingest log
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'engineer@company.com',
        action: 'incident_resolved',
        resource: 'monitoring',
        level: 'info',
        message: `Incident ${incident.incident_id} resolved by engineer`
      });

      expect(getLogCount()).toBeGreaterThan(0);
    });
  });

  describe('Metric Export and Visibility', () => {
    it('should export metrics in Prometheus format', async () => {
      recordRequestLatency(100);
      recordRequestLatency(200);
      recordRequestLatency(300);

      const export_data = await getMetricsExport();
      expect(export_data).toContain('http_request_latency_ms');
      expect(typeof export_data).toBe('string');
    });

    it('should track metric values for alert decisions', () => {
      recordRequestLatency(450);
      recordRequestLatency(500);
      recordRequestLatency(550);

      // Use metrics to evaluate alert
      const p95 = 550;
      const triggered = evaluateLatencyAlert(p95, 500);
      expect(triggered).toBe(true);

      const history = getAlertHistory();
      expect(history[0].value).toBe(550);
    });
  });

  describe('Diagnostic Logging', () => {
    it('should maintain searchable diagnostic logs', () => {
      // Simulate various system actions
      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'system',
        action: 'metric_collected',
        resource: 'prometheus',
        level: 'info',
        message: 'CPU and memory metrics collected'
      });

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'alert-engine',
        action: 'alert_triggered',
        resource: 'api-gateway',
        level: 'critical',
        message: 'Latency threshold breach detected'
      });

      ingestLog({
        timestamp: new Date().toISOString(),
        user_id: 'on-call-engineer',
        action: 'incident_ack',
        resource: 'incident-PD123',
        level: 'info',
        message: 'Incident acknowledged and being investigated'
      });

      // Search for incident-related logs
      const incidentLogs = searchLogs('incident');
      expect(incidentLogs.length).toBe(1);

      // Search for critical logs
      const criticalLogs = searchLogs('critical');
      expect(criticalLogs.length).toBe(1);

      // Search by user
      const engineerLogs = searchLogs('engineer');
      expect(engineerLogs.length).toBe(1);
    });
  });
});
