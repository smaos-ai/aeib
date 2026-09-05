import { describe, it, expect, beforeEach } from 'vitest';
import { ReportingService } from '../src/lib/reporting';
import { EventIngestionService } from '../src/lib/eventIngestion';
import { GapDetectionService } from '../src/lib/gapDetection';
import { KMSSigningService } from '../src/lib/signing';
import { ComplianceFramework, EventSource } from '../src/lib/types';

describe('Reporting', () => {
  let reportService: ReportingService;
  let eventService: EventIngestionService;
  let gapService: GapDetectionService;
  let signingService: KMSSigningService;

  beforeEach(() => {
    reportService = new ReportingService();
    eventService = new EventIngestionService();
    gapService = new GapDetectionService();
    signingService = new KMSSigningService();

    // Seed with sample data
    eventService.createEvent({
      source: EventSource.EU_AI,
      framework: ComplianceFramework.EU_AI_ACT,
      requirement: 'Transparency',
      status: 'compliant',
      severity: 'high',
      evidence: {}
    });

    gapService.calculateGap({
      framework: ComplianceFramework.EU_AI_ACT,
      requirement: 'Transparency',
      requiredLevel: 100,
      actualLevel: 85,
      source: EventSource.EU_AI
    });
  });

  describe('Report Generation', () => {
    it('should generate basic compliance report', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      expect(report.id).toBeDefined();
      expect(report.framework).toBe(ComplianceFramework.EU_AI_ACT);
      expect(report.generatedAt).toBeInstanceOf(Date);
      expect(report.overallScore).toBeGreaterThanOrEqual(0);
      expect(report.overallScore).toBeLessThanOrEqual(100);
    });

    it('should calculate overall compliance score', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: gapService.getPrioritizedGaps()
      });

      expect(report.overallScore).toBeGreaterThan(0);
    });

    it('should include all gaps in report', async () => {
      const gaps = gapService.getPrioritizedGaps();
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps
      });

      expect(report.gaps.length).toBeGreaterThanOrEqual(gaps.length);
    });

    it('should include all events in report', async () => {
      const events = eventService.getAllEvents();
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events,
        gaps: []
      });

      expect(report.events.length).toBe(events.length);
    });
  });

  describe('Multi-Framework Reporting', () => {
    it('should generate reports for all 7 frameworks', async () => {
      const frameworks = Object.values(ComplianceFramework);

      const reports = await Promise.all(
        frameworks.map(framework =>
          reportService.generateReport({
            framework,
            events: eventService.getAllEvents(),
            gaps: []
          })
        )
      );

      expect(reports).toHaveLength(7);
      expect(reports.every(r => r.framework)).toBe(true);
    });

    it('should generate consolidated multi-framework report', async () => {
      const report = await reportService.generateConsolidatedReport({
        events: eventService.getAllEvents(),
        gaps: gapService.getPrioritizedGaps()
      });

      expect(report.frameworks).toBeDefined();
      expect(report.frameworks.length).toBeGreaterThanOrEqual(1);
      expect(report.overallComplianceScore).toBeDefined();
    });

    it('should map framework requirements correctly', async () => {
      const mapping = reportService.getFrameworkMapping(ComplianceFramework.EU_AI_ACT);
      expect(mapping).toBeDefined();
      expect(mapping.requirements.size).toBeGreaterThan(0);
    });
  });

  describe('Signed Report Generation', () => {
    it('should generate and sign report with Ed25519', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const signed = await reportService.signReport(report, signingService);

      expect(signed.signature).toBeDefined();
      expect(signed.signature.length).toBeGreaterThan(0);
      expect(signed.signatureTimestamp).toBeInstanceOf(Date);
    });

    it('should verify signed report', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const signed = await reportService.signReport(report, signingService);
      const isValid = await signingService.verifySignature(report, signed.signature);

      expect(isValid).toBe(true);
    });

    it('should reject modified signed report', async () => {
      let report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const signed = await reportService.signReport(report, signingService);

      // Modify report
      report.overallScore = 50.0;

      const isValid = await signingService.verifySignature(report, signed.signature);
      expect(isValid).toBe(false);
    });
  });

  describe('Report Formatting', () => {
    it('should export report as JSON', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const json = reportService.exportJSON(report);

      expect(typeof json).toBe('string');
      const parsed = JSON.parse(json);
      expect(parsed.id).toBe(report.id);
      expect(parsed.framework).toBe(report.framework);
    });

    it('should export report with signature as JSON', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const signed = await reportService.signReport(report, signingService);
      const reportWithSig = { ...report, ...signed };

      const json = reportService.exportJSON(reportWithSig);
      const parsed = JSON.parse(json);

      expect(parsed.signature).toBeDefined();
      expect(parsed.signatureTimestamp).toBeDefined();
    });

    it('should generate report summary', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: gapService.getPrioritizedGaps()
      });

      const summary = reportService.generateSummary(report);

      expect(summary).toBeDefined();
      expect(summary.length).toBeGreaterThan(0);
      expect(summary).toContain(ComplianceFramework.EU_AI_ACT);
    });
  });

  describe('Report Statistics', () => {
    it('should calculate report metrics', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: gapService.getPrioritizedGaps()
      });

      const metrics = reportService.calculateMetrics(report);

      expect(metrics.compliancePercentage).toBeGreaterThanOrEqual(0);
      expect(metrics.gapCount).toBeGreaterThanOrEqual(0);
      expect(metrics.eventCount).toBeGreaterThanOrEqual(0);
    });

    it('should track compliance over time', async () => {
      const report1 = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      // Simulate time passing
      await new Promise(resolve => setTimeout(resolve, 100));

      const report2 = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const trend = reportService.getComplianceTrend([report1, report2]);

      expect(trend.length).toBe(2);
    });
  });

  describe('Report Persistence', () => {
    it('should persist report to storage', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      await reportService.persistReport(report);
      const retrieved = await reportService.getReportById(report.id);

      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe(report.id);
    });

    it('should retrieve report by ID', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      await reportService.persistReport(report);
      const retrieved = await reportService.getReportById(report.id);

      expect(retrieved?.framework).toBe(ComplianceFramework.EU_AI_ACT);
      expect(retrieved?.overallScore).toBe(report.overallScore);
    });

    it('should retrieve reports by framework', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      await reportService.persistReport(report);
      const reports = await reportService.getReportsByFramework(ComplianceFramework.EU_AI_ACT);

      expect(reports.length).toBeGreaterThanOrEqual(1);
    });

    it('should retrieve latest report for framework', async () => {
      const report1 = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      await reportService.persistReport(report1);

      await new Promise(resolve => setTimeout(resolve, 100));

      const report2 = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      await reportService.persistReport(report2);

      const latest = await reportService.getLatestReport(ComplianceFramework.EU_AI_ACT);

      expect(latest?.id).toBe(report2.id);
    });
  });

  describe('Report Validation', () => {
    it('should validate report structure', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const isValid = reportService.validateReport(report);
      expect(isValid).toBe(true);
    });

    it('should validate signed report', async () => {
      const report = await reportService.generateReport({
        framework: ComplianceFramework.EU_AI_ACT,
        events: eventService.getAllEvents(),
        gaps: []
      });

      const signed = await reportService.signReport(report, signingService);
      const reportWithSig = { ...report, ...signed };

      const isValid = reportService.validateSignedReport(reportWithSig);
      expect(isValid).toBe(true);
    });
  });

  describe('Report Batch Processing', () => {
    it('should generate 20+ reports concurrently', async () => {
      const reports = await Promise.all(
        Array.from({ length: 25 }, () =>
          reportService.generateReport({
            framework: ComplianceFramework.EU_AI_ACT,
            events: eventService.getAllEvents(),
            gaps: []
          })
        )
      );

      expect(reports).toHaveLength(25);
      expect(reports.every(r => r.id)).toBe(true);
    });

    it('should handle batch persistence', async () => {
      const reports = await Promise.all(
        Array.from({ length: 10 }, () =>
          reportService.generateReport({
            framework: ComplianceFramework.EU_AI_ACT,
            events: eventService.getAllEvents(),
            gaps: []
          })
        )
      );

      await reportService.persistBatch(reports);

      const all = await reportService.getAllReports();
      expect(all.length).toBeGreaterThanOrEqual(reports.length);
    });
  });
});
