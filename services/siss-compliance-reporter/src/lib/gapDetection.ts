import { randomUUID } from 'crypto';
import { ComplianceGap, ComplianceFramework, EventSource } from './types';

interface GapInput {
  framework: ComplianceFramework;
  requirement: string;
  requiredLevel: number;
  actualLevel: number;
  source: EventSource;
}

interface GapReport {
  totalGaps: number;
  criticalGaps: ComplianceGap[];
  highGaps: ComplianceGap[];
  averageGap: number;
}

interface GapTrendPoint {
  timestamp: Date;
  gap: number;
  actualLevel: number;
}

export class GapDetectionService {
  private gaps: Map<string, ComplianceGap> = new Map();
  private gapHistory: Map<string, GapTrendPoint[]> = new Map();

  calculateGap(input: GapInput): ComplianceGap {
    const gap = Math.max(0, input.requiredLevel - input.actualLevel);

    const gapRecord: ComplianceGap = {
      id: randomUUID(),
      framework: input.framework,
      requirement: input.requirement,
      requiredLevel: input.requiredLevel,
      actualLevel: input.actualLevel,
      gap,
      source: input.source,
      remediation: this.generateRemediation(input.framework, input.requirement, gap),
      deadline: this.calculateDeadline(gap)
    };

    this.gaps.set(gapRecord.id, gapRecord);
    this.recordTrend(input.framework, gap, input.actualLevel);

    return gapRecord;
  }

  generateGapReport(): GapReport {
    const allGaps = Array.from(this.gaps.values());
    const criticalGaps = allGaps.filter(g => g.gap > 50);
    const highGaps = allGaps.filter(g => g.gap > 20 && g.gap <= 50);
    const averageGap = allGaps.length > 0
      ? allGaps.reduce((sum, g) => sum + g.gap, 0) / allGaps.length
      : 0;

    return {
      totalGaps: allGaps.length,
      criticalGaps,
      highGaps,
      averageGap
    };
  }

  getPrioritizedGaps(): ComplianceGap[] {
    return Array.from(this.gaps.values())
      .sort((a, b) => b.gap - a.gap);
  }

  getCriticalGaps(): ComplianceGap[] {
    return Array.from(this.gaps.values())
      .filter(g => g.gap > 30)
      .sort((a, b) => b.gap - a.gap);
  }

  getGapsByFramework(): Record<ComplianceFramework, ComplianceGap[]> {
    const grouped: Record<ComplianceFramework, ComplianceGap[]> = {} as any;

    for (const gap of this.gaps.values()) {
      if (!grouped[gap.framework]) {
        grouped[gap.framework] = [];
      }
      grouped[gap.framework].push(gap);
    }

    return grouped;
  }

  getComplianceScore(): number {
    const allGaps = Array.from(this.gaps.values());
    if (allGaps.length === 0) return 100;

    const totalGap = allGaps.reduce((sum, g) => sum + g.gap, 0);
    const maxPossibleGap = allGaps.length * 100;

    return Math.max(0, 100 - (totalGap / maxPossibleGap) * 100);
  }

  getFrameworkScores(): Record<ComplianceFramework, number> {
    const scores: Record<ComplianceFramework, number> = {} as any;
    const grouped = this.getGapsByFramework();

    for (const [framework, gaps] of Object.entries(grouped)) {
      const avgGap = gaps.reduce((sum, g) => sum + g.gap, 0) / gaps.length;
      scores[framework as ComplianceFramework] = Math.max(0, 100 - avgGap);
    }

    return scores;
  }

  getFrameworkWeights(): Record<ComplianceFramework, number> {
    const frameworks = Object.values(ComplianceFramework);
    const weight = 100 / frameworks.length;

    const weights: Record<ComplianceFramework, number> = {} as any;
    for (const framework of frameworks) {
      weights[framework] = weight;
    }

    return weights;
  }

  getGapTrend(framework: ComplianceFramework): GapTrendPoint[] {
    const key = `trend-${framework}`;
    return this.gapHistory.get(key) || [];
  }

  private recordTrend(framework: ComplianceFramework, gap: number, actualLevel: number): void {
    const key = `trend-${framework}`;
    if (!this.gapHistory.has(key)) {
      this.gapHistory.set(key, []);
    }

    const trend = this.gapHistory.get(key)!;
    trend.push({
      timestamp: new Date(),
      gap,
      actualLevel
    });
  }

  private generateRemediation(framework: ComplianceFramework, requirement: string, gap: number): string {
    if (gap === 0) {
      return `${requirement} is fully compliant`;
    }

    const gapPercentage = (gap * 100 / 100).toFixed(1);

    const remediations: Record<ComplianceFramework, string> = {
      [ComplianceFramework.EU_AI_ACT]: `Enhance transparency mechanisms by ${gapPercentage}%. Document all AI decision-making processes.`,
      [ComplianceFramework.BASEL_III]: `Increase capital reserves by ${gapPercentage}%. Review risk weighting models and asset composition.`,
      [ComplianceFramework.SOC_2]: `Improve ${requirement} controls by ${gapPercentage}%. Implement additional monitoring and failover systems.`,
      [ComplianceFramework.GDPR]: `Increase DPA coverage to ${100 - gap}%. Execute remaining Data Processing Agreements with processors.`,
      [ComplianceFramework.PCI_DSS]: `Strengthen encryption and access controls by ${gapPercentage}%. Implement quarterly penetration testing.`,
      [ComplianceFramework.AML_KYC]: `Enhance screening procedures by ${gapPercentage}%. Update OFAC watchlist frequency and add more data sources.`,
      [ComplianceFramework.ENVIRONMENTAL]: `Reduce emissions by ${gapPercentage}%. Implement renewable energy sources and efficiency programs.`
    };

    return remediations[framework] || `Address gap of ${gap} in ${requirement}`;
  }

  private calculateDeadline(gap: number): Date {
    const now = new Date();

    // Critical: 7 days
    if (gap > 50) {
      return new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    }

    // High: 30 days
    if (gap > 20) {
      return new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    }

    // Medium: 90 days
    if (gap > 10) {
      return new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000);
    }

    // Low: 180 days
    return new Date(now.getTime() + 180 * 24 * 60 * 60 * 1000);
  }

  async persistGap(gap: ComplianceGap): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Persist to Phase 1 L2 knowledge vectors
    this.gaps.set(gap.id, gap);
  }

  async getGapById(id: string): Promise<ComplianceGap | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve from Phase 1 L2 knowledge vectors
    return this.gaps.get(id);
  }

  async getGapsByFrameworkId(framework: ComplianceFramework): Promise<ComplianceGap[]> {
    // TODO: INTEGRATE Jun 2027 - Query Phase 1 L2 knowledge vectors by framework
    return Array.from(this.gaps.values()).filter(g => g.framework === framework);
  }
}
