import { randomUUID } from 'crypto';
import { ComplianceReport, ComplianceEvent, ComplianceGap, ComplianceFramework, FrameworkMapping, ComplianceRequirement, SigningResult } from './types';
import { KMSSigningService } from './signing';

interface GenerateReportInput {
  framework: ComplianceFramework;
  events: ComplianceEvent[];
  gaps: ComplianceGap[];
}

interface ConsolidatedReportInput {
  events: ComplianceEvent[];
  gaps: ComplianceGap[];
}

interface ConsolidatedReport {
  id: string;
  generatedAt: Date;
  frameworks: ComplianceReport[];
  overallComplianceScore: number;
  criticalGapCount: number;
}

interface ReportMetrics {
  compliancePercentage: number;
  gapCount: number;
  eventCount: number;
  criticalCount: number;
  highCount: number;
}

export class ReportingService {
  private reports: Map<string, ComplianceReport> = new Map();
  private frameworkMappings: Map<ComplianceFramework, FrameworkMapping> = new Map();

  constructor() {
    this.initializeFrameworkMappings();
  }

  async generateReport(input: GenerateReportInput): Promise<ComplianceReport> {
    const overallScore = this.calculateScore(input.events, input.gaps);

    const report: ComplianceReport = {
      id: randomUUID(),
      generatedAt: new Date(),
      framework: input.framework,
      overallScore,
      gaps: input.gaps,
      events: input.events
    };

    return report;
  }

  async generateConsolidatedReport(input: ConsolidatedReportInput): Promise<ConsolidatedReport> {
    const frameworks = Object.values(ComplianceFramework);

    const frameworkReports = await Promise.all(
      frameworks.map(fw =>
        this.generateReport({
          framework: fw,
          events: input.events.filter(e => e.framework === fw),
          gaps: input.gaps.filter(g => g.framework === fw)
        })
      )
    );

    const overallScore = frameworkReports.reduce((sum, r) => sum + r.overallScore, 0) / frameworkReports.length;
    const criticalGaps = input.gaps.filter(g => g.gap > 50);

    return {
      id: randomUUID(),
      generatedAt: new Date(),
      frameworks: frameworkReports,
      overallComplianceScore: overallScore,
      criticalGapCount: criticalGaps.length
    };
  }

  async signReport(report: ComplianceReport, signer: KMSSigningService): Promise<SigningResult> {
    return signer.signReport(report);
  }

  exportJSON(report: any): string {
    return JSON.stringify(report, null, 2);
  }

  generateSummary(report: ComplianceReport): string {
    const gapSummary = report.gaps.length > 0
      ? `${report.gaps.length} gaps identified`
      : 'No gaps identified';

    return `${report.framework} Compliance Report: ${report.overallScore.toFixed(1)}% compliant. ${gapSummary}.`;
  }

  calculateMetrics(report: ComplianceReport): ReportMetrics {
    const criticalCount = report.gaps.filter(g => g.gap > 50).length;
    const highCount = report.gaps.filter(g => g.gap > 20 && g.gap <= 50).length;

    return {
      compliancePercentage: report.overallScore,
      gapCount: report.gaps.length,
      eventCount: report.events.length,
      criticalCount,
      highCount
    };
  }

  getComplianceTrend(reports: ComplianceReport[]): Array<{ date: Date; score: number }> {
    return reports.map(r => ({
      date: r.generatedAt,
      score: r.overallScore
    }));
  }

  getFrameworkMapping(framework: ComplianceFramework): FrameworkMapping {
    return this.frameworkMappings.get(framework) || {
      framework,
      source: this.mapFrameworkToSource(framework),
      requirements: new Map()
    };
  }

  async persistReport(report: ComplianceReport): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Persist to Phase 1 L2 knowledge vectors
    this.reports.set(report.id, report);
  }

  async persistBatch(reports: ComplianceReport[]): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Batch persist to Phase 1 L2 knowledge vectors
    for (const report of reports) {
      this.reports.set(report.id, report);
    }
  }

  async getReportById(id: string): Promise<ComplianceReport | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve from Phase 1 L2 knowledge vectors
    return this.reports.get(id);
  }

  async getReportsByFramework(framework: ComplianceFramework): Promise<ComplianceReport[]> {
    // TODO: INTEGRATE Jun 2027 - Query Phase 1 L2 knowledge vectors by framework
    return Array.from(this.reports.values()).filter(r => r.framework === framework);
  }

  async getLatestReport(framework: ComplianceFramework): Promise<ComplianceReport | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve latest from Phase 1 L2 knowledge vectors
    const reports = Array.from(this.reports.values())
      .filter(r => r.framework === framework)
      .sort((a, b) => b.generatedAt.getTime() - a.generatedAt.getTime());

    return reports[0];
  }

  async getAllReports(): Promise<ComplianceReport[]> {
    // TODO: INTEGRATE Jun 2027 - Retrieve all from Phase 1 L2 knowledge vectors
    return Array.from(this.reports.values());
  }

  validateReport(report: ComplianceReport): boolean {
    return !!(
      report.id &&
      report.generatedAt &&
      report.framework &&
      typeof report.overallScore === 'number' &&
      Array.isArray(report.gaps) &&
      Array.isArray(report.events)
    );
  }

  validateSignedReport(report: any): boolean {
    return this.validateReport(report) && !!report.signature && !!report.signatureTimestamp;
  }

  private calculateScore(events: ComplianceEvent[], gaps: ComplianceGap[]): number {
    if (events.length === 0) return 100;

    const compliantCount = events.filter(e => e.status === 'compliant').length;
    const eventScore = (compliantCount / events.length) * 50;

    let gapScore = 50;
    if (gaps.length > 0) {
      const totalGap = gaps.reduce((sum, g) => sum + g.gap, 0);
      const avgGap = totalGap / gaps.length;
      gapScore = Math.max(0, 50 - avgGap);
    }

    return eventScore + gapScore;
  }

  private initializeFrameworkMappings(): void {
    const mappings: Record<ComplianceFramework, FrameworkMapping> = {
      [ComplianceFramework.EU_AI_ACT]: {
        framework: ComplianceFramework.EU_AI_ACT,
        source: this.mapFrameworkToSource(ComplianceFramework.EU_AI_ACT),
        requirements: new Map([
          ['transparency', {
            id: 'eu-ai-001',
            name: 'Transparency and Information Provision',
            description: 'Provide clear information on AI decision-making',
            level: 1,
            evidenceType: 'documentation'
          } as ComplianceRequirement],
          ['user-rights', {
            id: 'eu-ai-002',
            name: 'User Rights',
            description: 'Ensure users can exercise their rights',
            level: 1,
            evidenceType: 'process'
          } as ComplianceRequirement],
          ['bias-assessment', {
            id: 'eu-ai-003',
            name: 'Bias and Discrimination Assessment',
            description: 'Monitor and mitigate AI bias',
            level: 2,
            evidenceType: 'audit'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.BASEL_III]: {
        framework: ComplianceFramework.BASEL_III,
        source: this.mapFrameworkToSource(ComplianceFramework.BASEL_III),
        requirements: new Map([
          ['cet1-ratio', {
            id: 'basel-001',
            name: 'CET1 Ratio',
            description: 'Maintain CET1 ratio above 10.5%',
            level: 3,
            evidenceType: 'financial'
          } as ComplianceRequirement],
          ['leverage-ratio', {
            id: 'basel-002',
            name: 'Leverage Ratio',
            description: 'Maintain leverage ratio above 3%',
            level: 3,
            evidenceType: 'financial'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.SOC_2]: {
        framework: ComplianceFramework.SOC_2,
        source: this.mapFrameworkToSource(ComplianceFramework.SOC_2),
        requirements: new Map([
          ['availability', {
            id: 'soc2-001',
            name: 'Availability Control',
            description: 'Maintain service availability >99.9%',
            level: 2,
            evidenceType: 'monitoring'
          } as ComplianceRequirement],
          ['security', {
            id: 'soc2-002',
            name: 'Security Control',
            description: 'Ensure data security protections',
            level: 3,
            evidenceType: 'audit'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.GDPR]: {
        framework: ComplianceFramework.GDPR,
        source: this.mapFrameworkToSource(ComplianceFramework.GDPR),
        requirements: new Map([
          ['dpa-execution', {
            id: 'gdpr-001',
            name: 'Data Processing Agreement',
            description: 'Execute DPA with all processors',
            level: 2,
            evidenceType: 'contract'
          } as ComplianceRequirement],
          ['retention-policy', {
            id: 'gdpr-002',
            name: 'Data Retention Policy',
            description: 'Implement data retention limits',
            level: 2,
            evidenceType: 'policy'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.PCI_DSS]: {
        framework: ComplianceFramework.PCI_DSS,
        source: this.mapFrameworkToSource(ComplianceFramework.PCI_DSS),
        requirements: new Map([
          ['encryption', {
            id: 'pci-001',
            name: 'Cardholder Data Encryption',
            description: 'Encrypt card data at rest and in transit',
            level: 3,
            evidenceType: 'technical'
          } as ComplianceRequirement],
          ['access-control', {
            id: 'pci-002',
            name: 'Access Control',
            description: 'Restrict access to cardholder data',
            level: 3,
            evidenceType: 'audit'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.AML_KYC]: {
        framework: ComplianceFramework.AML_KYC,
        source: this.mapFrameworkToSource(ComplianceFramework.AML_KYC),
        requirements: new Map([
          ['sanctions-screening', {
            id: 'aml-001',
            name: 'Sanctions Screening',
            description: 'Screen customers against OFAC list',
            level: 3,
            evidenceType: 'process'
          } as ComplianceRequirement],
          ['kyc-verification', {
            id: 'aml-002',
            name: 'KYC Verification',
            description: 'Perform customer verification',
            level: 2,
            evidenceType: 'documentation'
          } as ComplianceRequirement]
        ])
      },
      [ComplianceFramework.ENVIRONMENTAL]: {
        framework: ComplianceFramework.ENVIRONMENTAL,
        source: this.mapFrameworkToSource(ComplianceFramework.ENVIRONMENTAL),
        requirements: new Map([
          ['scope1-emissions', {
            id: 'env-001',
            name: 'Scope 1 Emissions',
            description: 'Reduce Scope 1 emissions',
            level: 1,
            evidenceType: 'measurement'
          } as ComplianceRequirement],
          ['renewable-targets', {
            id: 'env-002',
            name: 'Renewable Energy Targets',
            description: 'Achieve renewable energy targets',
            level: 2,
            evidenceType: 'reporting'
          } as ComplianceRequirement]
        ])
      }
    };

    for (const [framework, mapping] of Object.entries(mappings)) {
      this.frameworkMappings.set(framework as ComplianceFramework, mapping);
    }
  }

  private mapFrameworkToSource(framework: ComplianceFramework) {
    const sources: any = {
      [ComplianceFramework.EU_AI_ACT]: 'eu-ai-act-section-7',
      [ComplianceFramework.BASEL_III]: 'basel-iii-capital',
      [ComplianceFramework.SOC_2]: 'soc-2-controls',
      [ComplianceFramework.GDPR]: 'gdpr-data-processing',
      [ComplianceFramework.PCI_DSS]: 'pci-dss-card-data',
      [ComplianceFramework.AML_KYC]: 'aml-kyc-screening',
      [ComplianceFramework.ENVIRONMENTAL]: 'environmental-emissions'
    };
    return sources[framework];
  }
}
