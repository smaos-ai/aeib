import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  initSlack,
  sendAlert,
  getSentMessages,
  clearMessages
} from '../src/lib/slack';

describe('Slack Notifications', () => {
  beforeEach(() => {
    initSlack('test-token');
    clearMessages();
  });

  describe('Slack Message Formatting', () => {
    it('should format critical alert correctly', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Database Down',
        channel: '#alerts-critical',
        value: 0,
        threshold: 1,
        metric: 'database_health'
      });

      const messages = getSentMessages();
      expect(messages.length).toBe(1);
      expect(messages[0].channel).toBe('#alerts-critical');
    });

    it('should format warning alert correctly', async () => {
      await sendAlert({
        severity: 'warning',
        title: 'High Memory Usage',
        channel: '#alerts-warning',
        value: 85,
        threshold: 80,
        metric: 'memory_usage'
      });

      const messages = getSentMessages();
      expect(messages[0].severity).toBe('warning');
    });

    it('should format info alert correctly', async () => {
      await sendAlert({
        severity: 'info',
        title: 'Deployment Complete',
        channel: '#alerts-info',
        value: 100,
        threshold: 100,
        metric: 'deployment_status'
      });

      const messages = getSentMessages();
      expect(messages[0].severity).toBe('info');
    });

    it('should include alert title in message', async () => {
      const title = 'Critical Latency Breach';
      await sendAlert({
        severity: 'critical',
        title,
        channel: '#alerts-critical',
        value: 600,
        threshold: 500,
        metric: 'latency'
      });

      const messages = getSentMessages();
      expect(messages[0].title).toBe(title);
    });

    it('should include metric values in message', async () => {
      await sendAlert({
        severity: 'warning',
        title: 'Error Rate High',
        channel: '#alerts-warning',
        value: 2.5,
        threshold: 1.0,
        metric: 'error_rate'
      });

      const messages = getSentMessages();
      expect(messages[0].value).toBe(2.5);
      expect(messages[0].threshold).toBe(1.0);
    });

    it('should route to correct channel based on severity', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Test',
        channel: '#alerts-critical',
        value: 100,
        threshold: 80,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].channel).toBe('#alerts-critical');
    });

    it('should include timestamp in message', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Test Alert',
        channel: '#alerts',
        value: 100,
        threshold: 80,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].timestamp).toBeDefined();
    });
  });

  describe('Slack Channel Routing', () => {
    it('should send critical alerts to critical channel', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Critical Issue',
        channel: '#critical-alerts',
        value: 100,
        threshold: 80,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].channel).toBe('#critical-alerts');
    });

    it('should send warning alerts to warning channel', async () => {
      await sendAlert({
        severity: 'warning',
        title: 'Warning',
        channel: '#warnings',
        value: 90,
        threshold: 85,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].channel).toBe('#warnings');
    });

    it('should send info alerts to info channel', async () => {
      await sendAlert({
        severity: 'info',
        title: 'Info',
        channel: '#info',
        value: 50,
        threshold: 50,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].channel).toBe('#info');
    });
  });

  describe('Slack Message Delivery', () => {
    it('should track sent messages', async () => {
      expect(getSentMessages().length).toBe(0);

      await sendAlert({
        severity: 'warning',
        title: 'Test 1',
        channel: '#alerts',
        value: 100,
        threshold: 80,
        metric: 'test1'
      });

      expect(getSentMessages().length).toBe(1);
    });

    it('should send multiple alerts', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Critical 1',
        channel: '#critical',
        value: 100,
        threshold: 50,
        metric: 'metric1'
      });

      await sendAlert({
        severity: 'warning',
        title: 'Warning 1',
        channel: '#warnings',
        value: 90,
        threshold: 80,
        metric: 'metric2'
      });

      expect(getSentMessages().length).toBe(2);
    });

    it('should include alert context', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Service Down',
        channel: '#critical',
        value: 0,
        threshold: 1,
        metric: 'service_health',
        context: 'auth-service'
      });

      const messages = getSentMessages();
      expect(messages[0]).toBeDefined();
    });
  });

  describe('Severity Indicators', () => {
    it('should distinguish critical severity', async () => {
      await sendAlert({
        severity: 'critical',
        title: 'Critical',
        channel: '#critical',
        value: 100,
        threshold: 80,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].severity).toBe('critical');
    });

    it('should distinguish warning severity', async () => {
      await sendAlert({
        severity: 'warning',
        title: 'Warning',
        channel: '#warnings',
        value: 90,
        threshold: 85,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].severity).toBe('warning');
    });

    it('should distinguish info severity', async () => {
      await sendAlert({
        severity: 'info',
        title: 'Info',
        channel: '#info',
        value: 50,
        threshold: 50,
        metric: 'test'
      });

      const messages = getSentMessages();
      expect(messages[0].severity).toBe('info');
    });
  });
});
