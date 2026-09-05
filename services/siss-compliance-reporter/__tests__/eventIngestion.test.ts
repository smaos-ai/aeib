import { describe, it, expect, beforeEach } from 'vitest';
import { EventIngestionService } from '../src/lib/eventIngestion';
import { ComplianceEvent, EventSource, ComplianceFramework } from '../src/lib/types';

describe('EventIngestion', () => {
  let service: EventIngestionService;

  beforeEach(() => {
    service = new EventIngestionService();
  });

  describe('Event Creation from All 7 Sources', () => {
    it('should ingest EU AI Act transparency event', () => {
      const event = service.createEvent({
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Provide user transparency on AI decision-making',
        status: 'compliant',
        severity: 'high',
        evidence: { documentId: 'doc-001', reviewDate: '2026-09-01' }
      });

      expect(event.source).toBe(EventSource.EU_AI);
      expect(event.framework).toBe(ComplianceFramework.EU_AI_ACT);
      expect(event.id).toBeDefined();
      expect(event.timestamp).toBeInstanceOf(Date);
    });

    it('should ingest Basel III capital adequacy event', () => {
      const event = service.createEvent({
        source: EventSource.BASEL,
        framework: ComplianceFramework.BASEL_III,
        requirement: 'Maintain CET1 ratio above 10.5%',
        status: 'compliant',
        severity: 'critical',
        evidence: { cet1Ratio: 11.2, leverageRatio: 5.1 }
      });

      expect(event.source).toBe(EventSource.BASEL);
      expect(event.severity).toBe('critical');
    });

    it('should ingest SOC 2 controls event', () => {
      const event = service.createEvent({
        source: EventSource.SOC_2,
        framework: ComplianceFramework.SOC_2,
        requirement: 'Maintain availability >99.9%',
        status: 'compliant',
        severity: 'high',
        evidence: { uptime: 99.95, controlsAudited: true }
      });

      expect(event.framework).toBe(ComplianceFramework.SOC_2);
    });

    it('should ingest GDPR data processing event', () => {
      const event = service.createEvent({
        source: EventSource.GDPR,
        framework: ComplianceFramework.GDPR,
        requirement: 'Execute Data Processing Agreement with processor',
        status: 'compliant',
        severity: 'high',
        evidence: { dpaSignedDate: '2026-06-15', processorName: 'DataProcessor Inc' }
      });

      expect(event.source).toBe(EventSource.GDPR);
    });

    it('should ingest PCI-DSS card data event', () => {
      const event = service.createEvent({
        source: EventSource.PCI,
        framework: ComplianceFramework.PCI_DSS,
        requirement: 'Encrypt cardholder data at rest and in transit',
        status: 'compliant',
        severity: 'critical',
        evidence: { encryptionMethod: 'AES-256', tlsVersion: '1.3' }
      });

      expect(event.severity).toBe('critical');
    });

    it('should ingest AML/KYC screening event', () => {
      const event = service.createEvent({
        source: EventSource.AML,
        framework: ComplianceFramework.AML_KYC,
        requirement: 'Screen customers against OFAC list',
        status: 'compliant',
        severity: 'high',
        evidence: { screeningDate: '2026-09-05', matchCount: 0 }
      });

      expect(event.framework).toBe(ComplianceFramework.AML_KYC);
    });

    it('should ingest Environmental emissions event', () => {
      const event = service.createEvent({
        source: EventSource.ENV,
        framework: ComplianceFramework.ENVIRONMENTAL,
        requirement: 'Scope 1 emissions below 500 tCO2e',
        status: 'compliant',
        severity: 'medium',
        evidence: { scope1: 450, scope2: 1200, scope3: 2500 }
      });

      expect(event.framework).toBe(ComplianceFramework.ENVIRONMENTAL);
    });
  });

  describe('Batch Event Processing', () => {
    it('should ingest 100+ events concurrently', async () => {
      const events: Omit<ComplianceEvent, 'id' | 'timestamp'>[] = [];

      for (let i = 0; i < 150; i++) {
        const sources = Object.values(EventSource);
        events.push({
          source: sources[i % sources.length],
          framework: ComplianceFramework.EU_AI_ACT,
          requirement: `Requirement ${i}`,
          status: Math.random() > 0.1 ? 'compliant' : 'non-compliant',
          severity: 'high',
          evidence: { index: i },
          metadata: { batchId: 'batch-001' }
        } as any);
      }

      const ingested = await service.ingestBatch(events as any);
      expect(ingested).toHaveLength(150);
      expect(ingested.every(e => e.id)).toBe(true);
    });

    it('should handle concurrent ingestion at 10+ events per second', async () => {
      const startTime = Date.now();
      const eventCount = 50;
      const promises = [];

      for (let i = 0; i < eventCount; i++) {
        promises.push(
          service.createEvent({
            source: EventSource.EU_AI,
            framework: ComplianceFramework.EU_AI_ACT,
            requirement: `Requirement ${i}`,
            status: 'compliant',
            severity: 'high',
            evidence: { index: i }
          })
        );
      }

      await Promise.all(promises);
      const duration = Date.now() - startTime;
      const eventsPerSecond = (eventCount / duration) * 1000;

      expect(eventsPerSecond).toBeGreaterThan(10);
    });
  });

  describe('Event Retrieval and Filtering', () => {
    beforeEach(() => {
      service.createEvent({
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        status: 'compliant',
        severity: 'high',
        evidence: {}
      });

      service.createEvent({
        source: EventSource.BASEL,
        framework: ComplianceFramework.BASEL_III,
        requirement: 'CET1',
        status: 'non-compliant',
        severity: 'critical',
        evidence: {}
      });
    });

    it('should retrieve all events', () => {
      const events = service.getAllEvents();
      expect(events.length).toBeGreaterThanOrEqual(2);
    });

    it('should filter events by framework', () => {
      const events = service.getEventsByFramework(ComplianceFramework.EU_AI_ACT);
      expect(events.every(e => e.framework === ComplianceFramework.EU_AI_ACT)).toBe(true);
    });

    it('should filter events by source', () => {
      const events = service.getEventsBySource(EventSource.BASEL);
      expect(events.every(e => e.source === EventSource.BASEL)).toBe(true);
    });

    it('should filter events by status', () => {
      const events = service.getEventsByStatus('non-compliant');
      expect(events.every(e => e.status === 'non-compliant')).toBe(true);
    });

    it('should filter events by severity', () => {
      const events = service.getEventsBySeverity('critical');
      expect(events.every(e => e.severity === 'critical')).toBe(true);
    });
  });

  describe('Event Statistics', () => {
    beforeEach(() => {
      for (let i = 0; i < 5; i++) {
        service.createEvent({
          source: EventSource.EU_AI,
          framework: ComplianceFramework.EU_AI_ACT,
          requirement: `Requirement ${i}`,
          status: i < 4 ? 'compliant' : 'non-compliant',
          severity: i % 2 === 0 ? 'high' : 'critical',
          evidence: {}
        });
      }
    });

    it('should calculate event statistics', () => {
      const stats = service.getStatistics();
      expect(stats.totalEvents).toBe(5);
      expect(stats.compliantCount).toBe(4);
      expect(stats.nonCompliantCount).toBe(1);
    });

    it('should calculate framework distribution', () => {
      const distribution = service.getFrameworkDistribution();
      expect(distribution[ComplianceFramework.EU_AI_ACT]).toBe(5);
    });

    it('should calculate severity distribution', () => {
      const distribution = service.getSeverityDistribution();
      expect(distribution['high']).toBe(3);
      expect(distribution['critical']).toBe(2);
    });
  });

  describe('Event Persistence', () => {
    it('should persist events to storage', async () => {
      const event = service.createEvent({
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Test requirement',
        status: 'compliant',
        severity: 'high',
        evidence: { test: true }
      });

      await service.persistEvent(event);
      const retrieved = await service.getEventById(event.id);

      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe(event.id);
    });

    it('should retrieve event by ID', async () => {
      const event = service.createEvent({
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Test',
        status: 'compliant',
        severity: 'high',
        evidence: {}
      });

      await service.persistEvent(event);
      const retrieved = await service.getEventById(event.id);

      expect(retrieved?.id).toBe(event.id);
      expect(retrieved?.requirement).toBe('Test');
    });
  });

  describe('Event Validation', () => {
    it('should validate event before ingestion', () => {
      const validEvent = {
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Valid requirement',
        status: 'compliant' as const,
        severity: 'high' as const,
        evidence: {}
      };

      expect(() => service.createEvent(validEvent)).not.toThrow();
    });

    it('should reject invalid framework', () => {
      const invalidEvent = {
        source: EventSource.EU_AI,
        framework: 'invalid-framework' as any,
        requirement: 'Test',
        status: 'compliant' as const,
        severity: 'high' as const,
        evidence: {}
      };

      expect(() => service.createEvent(invalidEvent)).toThrow();
    });

    it('should reject missing required fields', () => {
      const incompleteEvent = {
        source: EventSource.EU_AI,
        framework: ComplianceFramework.EU_AI_ACT
      };

      expect(() => service.createEvent(incompleteEvent as any)).toThrow();
    });
  });
});
