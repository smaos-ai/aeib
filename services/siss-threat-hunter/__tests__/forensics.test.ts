import { describe, it, expect, beforeEach } from 'vitest';
import { ForensicsService } from '../src/lib/forensics';
import { PlaybookService } from '../src/lib/playbooks';
import { SecurityEvent, ThreatLevel, TimelineEvent } from '../src/lib/types';

describe('Forensics and Incident Response', () => {
  let forensicsService: ForensicsService;
  let playbookService: PlaybookService;

  beforeEach(() => {
    forensicsService = new ForensicsService();
    playbookService = new PlaybookService();
  });

  describe('Event Timeline Reconstruction', () => {
    it('should reconstruct event timeline', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ timestamp: new Date('2026-09-05T10:00:00Z'), eventType: 'login' }),
        createSecurityEvent({ timestamp: new Date('2026-09-05T10:05:00Z'), eventType: 'data_access' }),
        createSecurityEvent({ timestamp: new Date('2026-09-05T10:10:00Z'), eventType: 'logout' })
      ];

      const timeline = forensicsService.reconstructTimeline('incident-001', events);

      expect(timeline.incidentId).toBe('incident-001');
      expect(timeline.events).toHaveLength(3);
      expect(timeline.events[0].eventType).toBe('login');
    });

    it('should detect event sequence patterns', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ eventType: 'login', userId: 'attacker' }),
        createSecurityEvent({ eventType: 'enumerate_resources', userId: 'attacker' }),
        createSecurityEvent({ eventType: 'privilege_escalation', userId: 'attacker' }),
        createSecurityEvent({ eventType: 'data_exfiltration', userId: 'attacker' })
      ];

      const patterns = forensicsService.detectSequencePatterns(events);

      expect(patterns.length).toBeGreaterThan(0);
      expect(patterns.some(p => p.includes('escalation') || p.includes('theft'))).toBe(true);
    });

    it('should identify anomalous event sequence', () => {
      const events = Array.from({ length: 100 }, (_, i) =>
        createSecurityEvent({ eventType: i < 95 ? 'normal_operation' : 'suspicious_activity' })
      );

      const anomalies = forensicsService.detectAnomalousSequences(events);

      expect(anomalies.length).toBeGreaterThan(0);
    });
  });

  describe('Root Cause Analysis', () => {
    it('should identify root cause of incident', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ eventType: 'misconfiguration_detected', severity: ThreatLevel.CRITICAL }),
        createSecurityEvent({ eventType: 'unauthorized_access', severity: ThreatLevel.HIGH }),
        createSecurityEvent({ eventType: 'data_theft', severity: ThreatLevel.CRITICAL })
      ];

      const rootCause = forensicsService.findRootCause(events);

      expect(rootCause).toBeDefined();
      expect(rootCause.eventType).toBe('misconfiguration_detected');
    });

    it('should trace attack chain', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ eventType: 'initial_access', id: 'e1' }),
        createSecurityEvent({ eventType: 'lateral_movement', id: 'e2' }),
        createSecurityEvent({ eventType: 'privilege_escalation', id: 'e3' }),
        createSecurityEvent({ eventType: 'exfiltration', id: 'e4' })
      ];

      const chain = forensicsService.traceAttackChain(events);

      expect(chain.length).toBe(4);
      expect(chain[0].eventType).toBe('initial_access');
      expect(chain[3].eventType).toBe('exfiltration');
    });

    it('should estimate time to compromise', () => {
      const startTime = new Date('2026-09-05T10:00:00Z');
      const events: SecurityEvent[] = [
        createSecurityEvent({ timestamp: startTime, eventType: 'initial_access' }),
        createSecurityEvent({ timestamp: new Date(startTime.getTime() + 5 * 60000), eventType: 'lateral_movement' }),
        createSecurityEvent({ timestamp: new Date(startTime.getTime() + 15 * 60000), eventType: 'exfiltration' })
      ];

      const ttc = forensicsService.estimateTimeToCompromise(events);

      expect(ttc).toBeGreaterThan(0);
      expect(ttc).toBeLessThanOrEqual(15 * 60 * 1000); // 15 minutes max
    });
  });

  describe('Forensic Evidence Collection', () => {
    it('should collect evidence from events', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({
          eventType: 'suspicious_access',
          data: { user: 'attacker', file: '/etc/passwd' }
        }),
        createSecurityEvent({
          eventType: 'data_exfiltration',
          data: { destination: '192.168.1.100', bytes: 1024 }
        })
      ];

      const evidence = forensicsService.collectEvidence(events);

      expect(evidence.length).toBeGreaterThan(0);
      expect(evidence.some(e => e.data.user === 'attacker')).toBe(true);
    });

    it('should generate forensic report', () => {
      const events = Array.from({ length: 10 }, (_, i) =>
        createSecurityEvent({ eventType: `event-${i}` })
      );

      const report = forensicsService.generateForensicReport('incident-001', events);

      expect(report).toBeDefined();
      expect(report).toContain('incident-001');
      expect(report.length).toBeGreaterThan(0);
    });
  });

  describe('Incident Response Playbooks', () => {
    it('should select playbook by threat level', () => {
      playbookService.createPlaybook({
        name: 'Critical Threat Response',
        threatLevel: ThreatLevel.CRITICAL,
        description: 'Immediate isolation and investigation'
      });

      playbookService.createPlaybook({
        name: 'Medium Threat Response',
        threatLevel: ThreatLevel.MEDIUM,
        description: 'Monitor and investigate'
      });

      const criticalPlaybook = playbookService.selectPlaybook(ThreatLevel.CRITICAL);
      const mediumPlaybook = playbookService.selectPlaybook(ThreatLevel.MEDIUM);

      expect(criticalPlaybook).toBeDefined();
      expect(mediumPlaybook).toBeDefined();
      expect(criticalPlaybook?.threatLevel).toBe(ThreatLevel.CRITICAL);
    });

    it('should execute playbook actions', async () => {
      const playbook = playbookService.createPlaybook({
        name: 'Isolation Playbook',
        threatLevel: ThreatLevel.HIGH,
        description: 'Isolate affected systems'
      });

      playbookService.addAction(playbook.id, {
        name: 'Isolate System',
        type: 'isolate',
        status: 'pending'
      });

      playbookService.addAction(playbook.id, {
        name: 'Notify SOC',
        type: 'notify',
        status: 'pending'
      });

      const response = await playbookService.executePlaybook(playbook.id);

      expect(response).toBeDefined();
      expect(response.actions.length).toBeGreaterThanOrEqual(2);
    });

    it('should handle playbook execution failure gracefully', async () => {
      const playbook = playbookService.createPlaybook({
        name: 'Recovery Playbook',
        threatLevel: ThreatLevel.HIGH,
        description: 'Recover from incident'
      });

      playbookService.addAction(playbook.id, {
        name: 'Restore from Backup',
        type: 'recover',
        status: 'pending'
      });

      const response = await playbookService.executePlaybook(playbook.id);

      expect(response.status).toBeDefined();
    });
  });

  describe('Automated Alert Generation', () => {
    it('should generate alert from incident', () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({
          severity: ThreatLevel.CRITICAL,
          eventType: 'unauthorized_access',
          data: { target: 'production_database' }
        })
      ];

      const alert = forensicsService.generateAlert({
        incidentId: 'incident-001',
        threatLevel: ThreatLevel.CRITICAL,
        events,
        affectedAssets: ['db-prod-01']
      });

      expect(alert.id).toBeDefined();
      expect(alert.threatLevel).toBe(ThreatLevel.CRITICAL);
      expect(alert.affectedAssets).toContain('db-prod-01');
    });

    it('should include recommended actions in alert', () => {
      const alert = forensicsService.generateAlert({
        incidentId: 'incident-002',
        threatLevel: ThreatLevel.HIGH,
        events: [],
        affectedAssets: ['web-server-01']
      });

      expect(alert.recommended_actions).toBeDefined();
      expect(alert.recommended_actions.length).toBeGreaterThan(0);
    });
  });

  describe('End-to-End Forensic Investigation', () => {
    it('should execute complete forensic workflow', async () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({
          timestamp: new Date('2026-09-05T10:00:00Z'),
          eventType: 'initial_access',
          severity: ThreatLevel.HIGH,
          userId: 'attacker'
        }),
        createSecurityEvent({
          timestamp: new Date('2026-09-05T10:10:00Z'),
          eventType: 'privilege_escalation',
          severity: ThreatLevel.CRITICAL,
          userId: 'attacker'
        }),
        createSecurityEvent({
          timestamp: new Date('2026-09-05T10:20:00Z'),
          eventType: 'data_exfiltration',
          severity: ThreatLevel.CRITICAL,
          data: { destination: 'external_ip', bytes: 5000 }
        })
      ];

      // Reconstruct timeline
      const timeline = forensicsService.reconstructTimeline('incident-full-test', events);
      expect(timeline.events.length).toBe(3);

      // Find root cause
      const rootCause = forensicsService.findRootCause(events);
      expect(rootCause).toBeDefined();

      // Trace attack chain
      const chain = forensicsService.traceAttackChain(events);
      expect(chain.length).toBe(3);

      // Collect evidence
      const evidence = forensicsService.collectEvidence(events);
      expect(evidence.length).toBeGreaterThan(0);

      // Generate alert
      const alert = forensicsService.generateAlert({
        incidentId: 'incident-full-test',
        threatLevel: ThreatLevel.CRITICAL,
        events,
        affectedAssets: ['server-01']
      });

      expect(alert.threatLevel).toBe(ThreatLevel.CRITICAL);

      // Create and select playbook
      const createdPlaybook = playbookService.createPlaybook({
        name: 'Critical Threat Response',
        threatLevel: ThreatLevel.CRITICAL,
        description: 'Immediate isolation and investigation'
      });

      const playbook = playbookService.selectPlaybook(ThreatLevel.CRITICAL);
      expect(playbook).toBeDefined();

      if (playbook) {
        const response = await playbookService.executePlaybook(playbook.id);
        expect(response).toBeDefined();
      }
    });

    it('should handle 50+ events in investigation', async () => {
      const events = Array.from({ length: 50 }, (_, i) =>
        createSecurityEvent({
          timestamp: new Date(Date.now() + i * 1000),
          eventType: i < 10 ? 'normal_operation' : 'suspicious_activity',
          severity: i < 10 ? ThreatLevel.LOW : ThreatLevel.HIGH
        })
      );

      const timeline = forensicsService.reconstructTimeline('incident-large', events);
      expect(timeline.events.length).toBe(50);

      const anomalies = forensicsService.detectAnomalousSequences(events);
      expect(anomalies.length).toBeGreaterThan(0);

      const chain = forensicsService.traceAttackChain(events);
      expect(chain.length).toBeGreaterThan(0);
    });
  });

  describe('Incident Response Persistence', () => {
    it('should persist incident data', async () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ eventType: 'incident_start' })
      ];

      await forensicsService.persistIncident('incident-persist', events);
      const retrieved = await forensicsService.getIncident('incident-persist');

      expect(retrieved).toBeDefined();
      expect(retrieved?.events.length).toBeGreaterThan(0);
    });

    it('should retrieve incident timeline', async () => {
      const events: SecurityEvent[] = [
        createSecurityEvent({ eventType: 'event1' }),
        createSecurityEvent({ eventType: 'event2' })
      ];

      await forensicsService.persistIncident('incident-timeline', events);
      const timeline = await forensicsService.getIncidentTimeline('incident-timeline');

      expect(timeline).toBeDefined();
      expect(timeline?.events.length).toBe(2);
    });
  });
});

function createSecurityEvent(overrides: any = {}): SecurityEvent {
  return {
    id: `event-${Date.now()}-${Math.random()}`,
    timestamp: new Date(),
    source: 'test-source',
    eventType: 'test-event',
    severity: ThreatLevel.MEDIUM,
    data: {},
    ...overrides
  };
}
