import { randomUUID } from 'crypto';
import { SecurityEvent, SecuritySignature, SignatureMatch, ThreatLevel } from './types';

interface SignatureInput {
  name: string;
  pattern: string;
  severity: ThreatLevel;
  description: string;
}

interface MatchStatistics {
  totalMatches: number;
  bySignature: Record<string, number>;
  bySeverity: Record<ThreatLevel, number>;
}

export class SignatureService {
  private signatures: Map<string, SecuritySignature> = new Map();
  private matchLog: SignatureMatch[] = [];
  private matchStats: Map<string, number> = new Map();

  createSignature(input: SignatureInput): SecuritySignature {
    if (!this.validatePattern(input.pattern)) {
      throw new Error(`Invalid regex pattern: ${input.pattern}`);
    }

    const signature: SecuritySignature = {
      id: randomUUID(),
      name: input.name,
      pattern: input.pattern,
      severity: input.severity,
      description: input.description,
      enabled: true
    };

    this.signatures.set(signature.id, signature);
    return signature;
  }

  matchEvent(event: SecurityEvent): SignatureMatch[] {
    const matches: SignatureMatch[] = [];

    for (const [sigId, signature] of this.signatures) {
      if (!signature.enabled) continue;

      try {
        const regex = new RegExp(signature.pattern, 'gi');
        const eventString = JSON.stringify(event.data || {});

        if (regex.test(eventString)) {
          const match: SignatureMatch = {
            id: randomUUID(),
            signatureId: sigId,
            eventId: event.id,
            timestamp: event.timestamp,
            severity: signature.severity,
            matchedData: event.data || {}
          };

          matches.push(match);
          this.matchLog.push(match);
          this.matchStats.set(sigId, (this.matchStats.get(sigId) || 0) + 1);
        }
      } catch {
        // Invalid regex, skip
      }
    }

    // Sort by severity
    return matches.sort((a, b) => {
      const severityOrder = {
        [ThreatLevel.CRITICAL]: 0,
        [ThreatLevel.HIGH]: 1,
        [ThreatLevel.MEDIUM]: 2,
        [ThreatLevel.LOW]: 3,
        [ThreatLevel.INFO]: 4
      };
      return severityOrder[a.severity] - severityOrder[b.severity];
    });
  }

  matchEventBatch(events: SecurityEvent[]): SignatureMatch[] {
    const allMatches: SignatureMatch[] = [];

    for (const event of events) {
      const matches = this.matchEvent(event);
      allMatches.push(...matches);
    }

    return allMatches;
  }

  disableSignature(id: string): void {
    const sig = this.signatures.get(id);
    if (sig) {
      sig.enabled = false;
    }
  }

  enableSignature(id: string): void {
    const sig = this.signatures.get(id);
    if (sig) {
      sig.enabled = true;
    }
  }

  updateSignature(id: string, updates: Partial<SignatureInput>): void {
    const sig = this.signatures.get(id);
    if (!sig) return;

    if (updates.name) sig.name = updates.name;
    if (updates.description) sig.description = updates.description;
    if (updates.severity) sig.severity = updates.severity;

    if (updates.pattern) {
      if (!this.validatePattern(updates.pattern)) {
        throw new Error(`Invalid regex pattern: ${updates.pattern}`);
      }
      sig.pattern = updates.pattern;
    }
  }

  deleteSignature(id: string): void {
    this.signatures.delete(id);
    this.matchStats.delete(id);
  }

  getSignature(id: string): SecuritySignature | undefined {
    return this.signatures.get(id);
  }

  getAllSignatures(): SecuritySignature[] {
    return Array.from(this.signatures.values());
  }

  getSignatureCount(): number {
    return this.signatures.size;
  }

  validatePattern(pattern: string): boolean {
    try {
      new RegExp(pattern);
      return true;
    } catch {
      return false;
    }
  }

  getMatchStatistics(): MatchStatistics {
    const stats: MatchStatistics = {
      totalMatches: this.matchLog.length,
      bySignature: {},
      bySeverity: {
        [ThreatLevel.CRITICAL]: 0,
        [ThreatLevel.HIGH]: 0,
        [ThreatLevel.MEDIUM]: 0,
        [ThreatLevel.LOW]: 0,
        [ThreatLevel.INFO]: 0
      }
    };

    for (const [sigId, count] of this.matchStats) {
      const sig = this.signatures.get(sigId);
      if (sig) {
        stats.bySignature[sig.name] = count;
        stats.bySeverity[sig.severity] += count;
      }
    }

    return stats;
  }

  getSignatureStatistics(sigId: string): { matchCount: number; lastMatch?: Date } {
    const count = this.matchStats.get(sigId) || 0;
    const matches = this.matchLog.filter(m => m.signatureId === sigId);
    const lastMatch = matches.length > 0 ? matches[matches.length - 1].timestamp : undefined;

    return {
      matchCount: count,
      lastMatch
    };
  }
}
