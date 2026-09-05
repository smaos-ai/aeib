import { randomUUID } from 'crypto';
import { ComplianceEvent, EventSource, ComplianceFramework } from './types';

export class EventIngestionService {
  private events: Map<string, ComplianceEvent> = new Map();
  private eventLog: ComplianceEvent[] = [];

  createEvent(data: Omit<ComplianceEvent, 'id' | 'timestamp'>): ComplianceEvent {
    this.validateEvent(data);

    const event: ComplianceEvent = {
      id: randomUUID(),
      timestamp: new Date(),
      ...data
    };

    this.events.set(event.id, event);
    this.eventLog.push(event);

    return event;
  }

  async ingestBatch(events: Omit<ComplianceEvent, 'id' | 'timestamp'>[]): Promise<ComplianceEvent[]> {
    return events.map(event => this.createEvent(event));
  }

  getAllEvents(): ComplianceEvent[] {
    return Array.from(this.events.values());
  }

  getEventsByFramework(framework: ComplianceFramework): ComplianceEvent[] {
    return Array.from(this.events.values()).filter(e => e.framework === framework);
  }

  getEventsBySource(source: EventSource): ComplianceEvent[] {
    return Array.from(this.events.values()).filter(e => e.source === source);
  }

  getEventsByStatus(status: 'compliant' | 'non-compliant' | 'unknown'): ComplianceEvent[] {
    return Array.from(this.events.values()).filter(e => e.status === status);
  }

  getEventsBySeverity(severity: 'critical' | 'high' | 'medium' | 'low'): ComplianceEvent[] {
    return Array.from(this.events.values()).filter(e => e.severity === severity);
  }

  getStatistics() {
    const events = Array.from(this.events.values());
    return {
      totalEvents: events.length,
      compliantCount: events.filter(e => e.status === 'compliant').length,
      nonCompliantCount: events.filter(e => e.status === 'non-compliant').length,
      unknownCount: events.filter(e => e.status === 'unknown').length
    };
  }

  getFrameworkDistribution(): Record<ComplianceFramework, number> {
    const distribution: Record<ComplianceFramework, number> = {} as any;

    for (const event of this.events.values()) {
      distribution[event.framework] = (distribution[event.framework] || 0) + 1;
    }

    return distribution;
  }

  getSeverityDistribution(): Record<string, number> {
    const distribution: Record<string, number> = {};

    for (const event of this.events.values()) {
      distribution[event.severity] = (distribution[event.severity] || 0) + 1;
    }

    return distribution;
  }

  async persistEvent(event: ComplianceEvent): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Persist to Phase 1 L2 knowledge vectors (pgvector)
    this.events.set(event.id, event);
  }

  async getEventById(id: string): Promise<ComplianceEvent | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve from Phase 1 L2 knowledge vectors
    return this.events.get(id);
  }

  private validateEvent(event: any): void {
    if (!event.source || !Object.values(EventSource).includes(event.source)) {
      throw new Error(`Invalid or missing source: ${event.source}`);
    }

    if (!event.framework || !Object.values(ComplianceFramework).includes(event.framework)) {
      throw new Error(`Invalid or missing framework: ${event.framework}`);
    }

    if (!event.requirement || typeof event.requirement !== 'string') {
      throw new Error('Missing or invalid requirement');
    }

    if (!event.status || !['compliant', 'non-compliant', 'unknown'].includes(event.status)) {
      throw new Error(`Invalid status: ${event.status}`);
    }

    if (!event.severity || !['critical', 'high', 'medium', 'low'].includes(event.severity)) {
      throw new Error(`Invalid severity: ${event.severity}`);
    }

    if (event.evidence === undefined || typeof event.evidence !== 'object') {
      throw new Error('Evidence must be an object');
    }
  }
}
