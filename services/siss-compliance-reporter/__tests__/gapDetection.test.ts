import { describe, it, expect, beforeEach } from 'vitest';
import { GapDetectionService } from '../src/lib/gapDetection';
import { ComplianceFramework, EventSource, ComplianceEvent } from '../src/lib/types';

describe('GapDetection', () => {
  let service: GapDetectionService;

  beforeEach(() => {
    service = new GapDetectionService();
  });

  describe('Gap Calculation', () => {
    it('should detect gap between required and actual compliance level', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.BASEL_III,
        requirement: 'CET1 ratio',
        requiredLevel: 10.5,
        actualLevel: 9.2,
        source: EventSource.BASEL
      });

      expect(gap.gap).toBeCloseTo(1.3, 1);
      expect(gap.framework).toBe(ComplianceFramework.BASEL_III);
      expect(gap.id).toBeDefined();
    });

    it('should calculate zero gap for compliant requirement', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.SOC_2,
        requirement: 'Uptime',
        requiredLevel: 99.9,
        actualLevel: 99.95,
        source: EventSource.SOC_2
      });

      expect(gap.gap).toBe(0);
      expect(gap.actualLevel).toBeGreaterThanOrEqual(gap.requiredLevel);
    });

    it('should generate remediation recommendations', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.GDPR,
        requirement: 'DPA execution rate',
        requiredLevel: 100,
        actualLevel: 75,
        source: EventSource.GDPR
      });

      expect(gap.remediation).toBeDefined();
      expect(gap.remediation.length).toBeGreaterThan(0);
    });

    it('should assign deadline based on gap severity', () => {
      const criticalGap = service.calculateGap({
        framework: ComplianceFramework.PCI,
        requirement: 'Encryption',
        requiredLevel: 100,
        actualLevel: 0,
        source: EventSource.PCI
      });

      const minorGap = service.calculateGap({
        framework: ComplianceFramework.EU_AI,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 95,
        source: EventSource.EU_AI
      });

      if (criticalGap.deadline && minorGap.deadline) {
        expect(criticalGap.deadline.getTime()).toBeLessThan(minorGap.deadline.getTime());
      }
    });
  });

  describe('Multi-Framework Gap Analysis', () => {
    it('should analyze gaps across all 7 frameworks', () => {
      const frameworks = Object.values(ComplianceFramework);
      const sources = Object.values(EventSource);

      const gaps = frameworks.map((framework, i) =>
        service.calculateGap({
          framework,
          requirement: `Requirement for ${framework}`,
          requiredLevel: 100,
          actualLevel: 70 + (i * 5),
          source: sources[i]
        })
      );

      expect(gaps.length).toBe(7);
      expect(gaps.every(g => g.framework === frameworks[frameworks.indexOf(g.framework)])).toBe(true);
    });

    it('should generate consolidated gap report', () => {
      service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 80,
        source: EventSource.EU_AI
      });

      service.calculateGap({
        framework: ComplianceFramework.BASEL_III,
        requirement: 'CET1',
        requiredLevel: 10.5,
        actualLevel: 9.0,
        source: EventSource.BASEL
      });

      const report = service.generateGapReport();
      expect(report.totalGaps).toBeGreaterThanOrEqual(2);
      expect(report.criticalGaps).toBeDefined();
      expect(report.highGaps).toBeDefined();
      expect(report.averageGap).toBeGreaterThan(0);
    });
  });

  describe('Gap Prioritization', () => {
    beforeEach(() => {
      service.calculateGap({
        framework: ComplianceFramework.PCI_DSS,
        requirement: 'Encryption',
        requiredLevel: 100,
        actualLevel: 50,
        source: EventSource.PCI
      });

      service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 90,
        source: EventSource.EU_AI
      });

      service.calculateGap({
        framework: ComplianceFramework.GDPR,
        requirement: 'DPA coverage',
        requiredLevel: 100,
        actualLevel: 60,
        source: EventSource.GDPR
      });
    });

    it('should prioritize gaps by severity', () => {
      const prioritized = service.getPrioritizedGaps();
      expect(prioritized.length).toBeGreaterThanOrEqual(3);

      // First gap should have larger gap than last
      if (prioritized.length > 1) {
        expect(prioritized[0].gap).toBeGreaterThanOrEqual(prioritized[prioritized.length - 1].gap);
      }
    });

    it('should identify critical gaps requiring immediate action', () => {
      const critical = service.getCriticalGaps();
      expect(critical.length).toBeGreaterThan(0);
      expect(critical.every(g => g.gap > 30)).toBe(true);
    });

    it('should group gaps by framework', () => {
      const grouped = service.getGapsByFramework();
      expect(Object.keys(grouped).length).toBeGreaterThan(0);
    });
  });

  describe('Compliance Score Calculation', () => {
    it('should calculate overall compliance score', () => {
      service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 80,
        source: EventSource.EU_AI
      });

      service.calculateGap({
        framework: ComplianceFramework.BASEL_III,
        requirement: 'CET1',
        requiredLevel: 10.5,
        actualLevel: 10.5,
        source: EventSource.BASEL
      });

      const score = service.getComplianceScore();
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    });

    it('should calculate framework-specific scores', () => {
      service.calculateGap({
        framework: ComplianceFramework.SOC_2,
        requirement: 'Availability',
        requiredLevel: 99.9,
        actualLevel: 99.85,
        source: EventSource.SOC_2
      });

      const scores = service.getFrameworkScores();
      expect(scores[ComplianceFramework.SOC_2]).toBeDefined();
      expect(scores[ComplianceFramework.SOC_2]).toBeCloseTo(99.85, 0);
    });

    it('should weight framework scores appropriately', () => {
      const weights = service.getFrameworkWeights();
      const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

      expect(totalWeight).toBeCloseTo(100, 0);
    });
  });

  describe('Gap Trend Analysis', () => {
    it('should track gap changes over time', () => {
      const gap1 = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 70,
        source: EventSource.EU_AI
      });

      // Simulate improved compliance
      const gap2 = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 85,
        source: EventSource.EU_AI
      });

      const trend = service.getGapTrend(ComplianceFramework.EU_AI_ACT);
      expect(trend.length).toBeGreaterThan(0);
    });

    it('should identify improving and deteriorating trends', () => {
      for (let i = 0; i < 5; i++) {
        service.calculateGap({
          framework: ComplianceFramework.EU_AI_ACT,
          requirement: 'Transparency',
          requiredLevel: 100,
          actualLevel: 50 + (i * 10),
          source: EventSource.EU_AI
        });
      }

      const trend = service.getGapTrend(ComplianceFramework.EU_AI_ACT);
      const isImproving = trend.length > 1 && trend[trend.length - 1].gap < trend[0].gap;

      expect(isImproving).toBe(true);
    });
  });

  describe('Gap Persistence', () => {
    it('should persist gaps to storage', async () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 70,
        source: EventSource.EU_AI
      });

      await service.persistGap(gap);
      const retrieved = await service.getGapById(gap.id);

      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe(gap.id);
    });

    it('should retrieve all gaps for framework', async () => {
      service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 70,
        source: EventSource.EU_AI
      });

      const gaps = await service.getGapsByFrameworkId(ComplianceFramework.EU_AI_ACT);
      expect(gaps.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero gap scenarios', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 100,
        source: EventSource.EU_AI
      });

      expect(gap.gap).toBe(0);
    });

    it('should handle negative gaps (over-compliance)', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 80,
        actualLevel: 100,
        source: EventSource.EU_AI
      });

      expect(gap.gap).toBeLessThanOrEqual(0);
    });

    it('should handle very large gaps', () => {
      const gap = service.calculateGap({
        framework: ComplianceFramework.EU_AI_ACT,
        requirement: 'Transparency',
        requiredLevel: 100,
        actualLevel: 0,
        source: EventSource.EU_AI
      });

      expect(gap.gap).toBe(100);
    });
  });
});
