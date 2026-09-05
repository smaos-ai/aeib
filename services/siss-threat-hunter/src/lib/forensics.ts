import { randomUUID } from 'crypto';
import { SecurityEvent, ForensicTimeline, TimelineEvent, ThreatLevel, IncidentAlert } from './types';

interface IncidentData {
  id: string;
  events: SecurityEvent[];
  timeline?: ForensicTimeline;
}

export class ForensicsService {
  private incidents: Map<string, IncidentData> = new Map();

  reconstructTimeline(incidentId: string, events: SecurityEvent[]): ForensicTimeline {
    const sortedEvents = [...events].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    const timelineEvents: TimelineEvent[] = sortedEvents.map((event, i) => ({
      eventId: event.id,
      timestamp: event.timestamp,
      eventType: event.eventType,
      actor: event.userId || 'unknown',
      action: event.eventType,
      target: event.resourceId || 'unknown',
      result: 'occurred'
    }));

    return {
      incidentId,
      events: timelineEvents,
      investigationStart: new Date()
    };
  }

  detectSequencePatterns(events: SecurityEvent[]): string[] {
    const patterns: string[] = [];

    for (let i = 0; i < events.length - 1; i++) {
      const current = events[i].eventType;
      const next = events[i + 1].eventType;

      if (current === 'login' && next === 'enumerate_resources') {
        patterns.push('reconnaissance');
      }

      if (current === 'enumerate_resources' && next === 'privilege_escalation') {
        patterns.push('privilege_escalation');
      }

      if (current === 'privilege_escalation' && next === 'data_exfiltration') {
        patterns.push('data_theft');
      }

      if (current === 'privilege_escalation' && next === 'lateral_movement') {
        patterns.push('lateral_movement_after_escalation');
      }
    }

    return patterns;
  }

  detectAnomalousSequences(events: SecurityEvent[]): SecurityEvent[] {
    const anomalies: SecurityEvent[] = [];
    const suspiciousTypes = [
      'privilege_escalation',
      'data_exfiltration',
      'unauthorized_access',
      'lateral_movement',
      'credential_theft'
    ];

    for (let i = 0; i < events.length; i++) {
      if (suspiciousTypes.includes(events[i].eventType)) {
        anomalies.push(events[i]);
      }
    }

    return anomalies;
  }

  findRootCause(events: SecurityEvent[]): SecurityEvent | undefined {
    const sortedEvents = [...events].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    for (const event of sortedEvents) {
      if (event.severity === ThreatLevel.CRITICAL) {
        if (event.eventType.includes('misconfiguration') ||
            event.eventType.includes('vulnerability') ||
            event.eventType.includes('initial_access')) {
          return event;
        }
      }
    }

    return sortedEvents[0];
  }

  traceAttackChain(events: SecurityEvent[]): SecurityEvent[] {
    const stages = [
      'initial_access',
      'lateral_movement',
      'privilege_escalation',
      'exfiltration'
    ];

    const chain: SecurityEvent[] = [];

    for (const stage of stages) {
      const event = events.find(e => e.eventType.includes(stage) || e.eventType === stage);
      if (event) {
        chain.push(event);
      }
    }

    return chain.length > 0 ? chain : events.slice(0, Math.max(1, Math.min(4, events.length)));
  }

  estimateTimeToCompromise(events: SecurityEvent[]): number {
    if (events.length < 2) return 0;

    const sortedEvents = [...events].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    const firstEvent = sortedEvents[0];
    const lastEvent = sortedEvents[sortedEvents.length - 1];

    return lastEvent.timestamp.getTime() - firstEvent.timestamp.getTime();
  }

  collectEvidence(events: SecurityEvent[]): SecurityEvent[] {
    return events.filter(e => e.severity === ThreatLevel.CRITICAL || e.severity === ThreatLevel.HIGH);
  }

  generateForensicReport(incidentId: string, events: SecurityEvent[]): string {
    const timeline = this.reconstructTimeline(incidentId, events);
    const rootCause = this.findRootCause(events);
    const chain = this.traceAttackChain(events);
    const ttc = this.estimateTimeToCompromise(events);

    let report = `# Forensic Investigation Report\n`;
    report += `Incident ID: ${incidentId}\n`;
    report += `Investigation Start: ${timeline.investigationStart.toISOString()}\n`;
    report += `Total Events: ${events.length}\n`;
    report += `\n## Root Cause\n`;
    report += `Type: ${rootCause?.eventType || 'unknown'}\n`;
    report += `Time: ${rootCause?.timestamp.toISOString()}\n`;
    report += `\n## Attack Chain\n`;
    for (let i = 0; i < chain.length; i++) {
      report += `${i + 1}. ${chain[i].eventType} @ ${chain[i].timestamp.toISOString()}\n`;
    }
    report += `\n## Time to Compromise\n`;
    report += `Duration: ${Math.floor(ttc / 1000)} seconds\n`;

    return report;
  }

  generateAlert(input: {
    incidentId: string;
    threatLevel: ThreatLevel;
    events: SecurityEvent[];
    affectedAssets: string[];
  }): IncidentAlert {
    const recommendedActions = this.getRecommendedActions(input.threatLevel);

    return {
      id: randomUUID(),
      timestamp: new Date(),
      incidentId: input.incidentId,
      threatLevel: input.threatLevel,
      title: `${input.threatLevel.toUpperCase()} Severity Incident Detected`,
      description: `Incident ${input.incidentId} with ${input.events.length} security events detected`,
      affectedAssets: input.affectedAssets,
      recommended_actions: recommendedActions
    };
  }

  async persistIncident(incidentId: string, events: SecurityEvent[]): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Persist to Phase 1 L3 permit gates with incident context
    this.incidents.set(incidentId, {
      id: incidentId,
      events,
      timeline: this.reconstructTimeline(incidentId, events)
    });
  }

  async getIncident(incidentId: string): Promise<IncidentData | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve from Phase 1 L3 permit gates
    return this.incidents.get(incidentId);
  }

  async getIncidentTimeline(incidentId: string): Promise<ForensicTimeline | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve timeline from Phase 1 L3 permit gates
    const incident = this.incidents.get(incidentId);
    return incident?.timeline;
  }

  private getRecommendedActions(threatLevel: ThreatLevel): string[] {
    const actions: Record<ThreatLevel, string[]> = {
      [ThreatLevel.CRITICAL]: [
        'Immediately isolate affected systems',
        'Activate incident response team',
        'Preserve forensic evidence',
        'Notify executive leadership',
        'Begin breach notification process'
      ],
      [ThreatLevel.HIGH]: [
        'Isolate affected systems',
        'Initiate investigation',
        'Monitor for lateral movement',
        'Review access logs',
        'Notify security team'
      ],
      [ThreatLevel.MEDIUM]: [
        'Begin investigation',
        'Monitor system behavior',
        'Review relevant logs',
        'Assess impact',
        'Document findings'
      ],
      [ThreatLevel.LOW]: [
        'Log incident',
        'Monitor for patterns',
        'Review system configuration',
        'Document observations'
      ],
      [ThreatLevel.INFO]: [
        'Log for situational awareness',
        'Track for patterns'
      ]
    };

    return actions[threatLevel] || [];
  }
}
