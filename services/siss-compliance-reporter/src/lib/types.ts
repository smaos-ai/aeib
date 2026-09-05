export enum ComplianceFramework {
  EU_AI_ACT = 'eu-ai-act',
  BASEL_III = 'basel-iii',
  SOC_2 = 'soc-2',
  GDPR = 'gdpr',
  PCI_DSS = 'pci-dss',
  AML_KYC = 'aml-kyc',
  ENVIRONMENTAL = 'environmental'
}

export enum EventSource {
  EU_AI = 'eu-ai-act-section-7',
  BASEL = 'basel-iii-capital',
  SOC_2 = 'soc-2-controls',
  GDPR = 'gdpr-data-processing',
  PCI = 'pci-dss-card-data',
  AML = 'aml-kyc-screening',
  ENV = 'environmental-emissions'
}

export interface ComplianceEvent {
  id: string;
  timestamp: Date;
  source: EventSource;
  framework: ComplianceFramework;
  requirement: string;
  status: 'compliant' | 'non-compliant' | 'unknown';
  severity: 'critical' | 'high' | 'medium' | 'low';
  evidence: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface ComplianceGap {
  id: string;
  framework: ComplianceFramework;
  requirement: string;
  requiredLevel: number;
  actualLevel: number;
  gap: number;
  source: EventSource;
  remediation: string;
  deadline?: Date;
}

export interface ComplianceReport {
  id: string;
  generatedAt: Date;
  framework: ComplianceFramework;
  overallScore: number;
  gaps: ComplianceGap[];
  events: ComplianceEvent[];
  signature?: string;
  signatureTimestamp?: Date;
  signedBy?: string;
}

export interface SigningResult {
  signature: string;
  publicKey: string;
  timestamp: Date;
  isValid: boolean;
}

export interface FrameworkMapping {
  framework: ComplianceFramework;
  source: EventSource;
  requirements: Map<string, ComplianceRequirement>;
}

export interface ComplianceRequirement {
  id: string;
  name: string;
  description: string;
  level: number;
  evidenceType: string;
}

export interface TimeSeries {
  framework: ComplianceFramework;
  dataPoints: TimeSeriesPoint[];
}

export interface TimeSeriesPoint {
  timestamp: Date;
  score: number;
  gapCount: number;
  criticalCount: number;
}
