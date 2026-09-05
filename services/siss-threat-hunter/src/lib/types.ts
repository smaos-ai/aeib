export enum ThreatLevel {
  CRITICAL = 'critical',
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  INFO = 'info'
}

export enum AnomalyType {
  STATISTICAL = 'statistical',
  BEHAVIORAL = 'behavioral',
  SIGNATURE = 'signature',
  RULE_BASED = 'rule-based'
}

export interface SecurityEvent {
  id: string;
  timestamp: Date;
  source: string;
  eventType: string;
  severity: ThreatLevel;
  data: Record<string, unknown>;
  userId?: string;
  resourceId?: string;
}

export interface AnomalyScore {
  eventId: string;
  timestamp: Date;
  isolationForestScore: number;
  svmScore: number;
  combinedScore: number;
  isAnomaly: boolean;
  anomalyType: AnomalyType;
  confidence: number;
}

export interface SecuritySignature {
  id: string;
  name: string;
  pattern: string;
  severity: ThreatLevel;
  description: string;
  enabled: boolean;
}

export interface SignatureMatch {
  id: string;
  signatureId: string;
  eventId: string;
  timestamp: Date;
  severity: ThreatLevel;
  matchedData: Record<string, unknown>;
}

export interface ForensicTimeline {
  incidentId: string;
  events: TimelineEvent[];
  rootCauseId?: string;
  investigationStart: Date;
  investigationEnd?: Date;
}

export interface TimelineEvent {
  eventId: string;
  timestamp: Date;
  eventType: string;
  actor: string;
  action: string;
  target: string;
  result: string;
}

export interface IncidentResponse {
  incidentId: string;
  playbookId: string;
  threatLevel: ThreatLevel;
  actions: PlaybookAction[];
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  createdAt: Date;
  completedAt?: Date;
}

export interface PlaybookAction {
  id: string;
  name: string;
  type: 'isolate' | 'notify' | 'recover' | 'investigate';
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  result?: string;
}

export interface IncidentAlert {
  id: string;
  timestamp: Date;
  incidentId: string;
  threatLevel: ThreatLevel;
  title: string;
  description: string;
  affectedAssets: string[];
  recommended_actions: string[];
}

export interface MLTrainingData {
  features: number[][];
  labels?: number[];
  eventIds: string[];
}

export interface DetectionResult {
  eventId: string;
  timestamp: Date;
  isAnomaly: boolean;
  threatLevel: ThreatLevel;
  anomalyScore: AnomalyScore;
  signatureMatches: SignatureMatch[];
  investigation?: ForensicTimeline;
  responsePlaybook?: IncidentResponse;
  alert?: IncidentAlert;
}

export interface Model {
  type: 'isolation-forest' | 'svm';
  isTrained: boolean;
  trainingTime: number;
  accuracy?: number;
}
