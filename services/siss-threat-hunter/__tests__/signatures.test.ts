import { describe, it, expect, beforeEach } from 'vitest';
import { SignatureService } from '../src/lib/signatures';
import { SecurityEvent, ThreatLevel } from '../src/lib/types';

describe('Signature Matching', () => {
  let service: SignatureService;

  beforeEach(() => {
    service = new SignatureService();
  });

  describe('Signature Pattern Matching', () => {
    it('should create new signature', () => {
      const sig = service.createSignature({
        name: 'SQL Injection Attempt',
        pattern: "SELECT.*FROM.*WHERE",
        severity: ThreatLevel.HIGH,
        description: 'Detect SQL injection patterns'
      });

      expect(sig.id).toBeDefined();
      expect(sig.name).toBe('SQL Injection Attempt');
      expect(sig.enabled).toBe(true);
    });

    it('should match event against pattern', () => {
      service.createSignature({
        name: 'SQL Injection',
        pattern: 'SELECT.*FROM.*WHERE',
        severity: ThreatLevel.HIGH,
        description: 'SQL injection'
      });

      const event = createSecurityEvent({
        data: { query: 'SELECT * FROM users WHERE id=1 OR 1=1' }
      });

      const matches = service.matchEvent(event);
      expect(matches.length).toBeGreaterThan(0);
      expect(matches[0].severity).toBe(ThreatLevel.HIGH);
    });

    it('should support 10+ signature patterns', () => {
      const patterns = [
        { name: 'SQL Injection', pattern: 'SELECT.*FROM', severity: ThreatLevel.HIGH },
        { name: 'XSS', pattern: '<script[^>]*>.*?</script>', severity: ThreatLevel.HIGH },
        { name: 'Command Injection', pattern: '(&&|\\||;)\\s*(cat|rm|ls|whoami)', severity: ThreatLevel.CRITICAL },
        { name: 'Path Traversal', pattern: '\\.\\./\\.\\./\\.\\./', severity: ThreatLevel.MEDIUM },
        { name: 'XXE', pattern: '<!ENTITY.*SYSTEM', severity: ThreatLevel.HIGH },
        { name: 'CSRF', pattern: 'CSRF.*token.*invalid', severity: ThreatLevel.MEDIUM },
        { name: 'Brute Force', pattern: 'auth.*fail.*5\\+', severity: ThreatLevel.MEDIUM },
        { name: 'DDoS', pattern: 'request.*rate.*exceed', severity: ThreatLevel.HIGH },
        { name: 'Directory Listing', pattern: 'index.*of', severity: ThreatLevel.LOW },
        { name: 'Information Disclosure', pattern: 'error.*exception.*stack', severity: ThreatLevel.MEDIUM },
        { name: 'Insecure Deserialization', pattern: 'unserialize.*untrusted', severity: ThreatLevel.CRITICAL },
        { name: 'SSRF', pattern: '(localhost|127\\.0\\.0\\.1|192\\.168)', severity: ThreatLevel.HIGH }
      ];

      patterns.forEach(p => {
        service.createSignature({
          name: p.name,
          pattern: p.pattern,
          severity: p.severity,
          description: `${p.name} signature`
        });
      });

      expect(service.getSignatureCount()).toBe(12);
    });

    it('should maintain false positive rate <1%', () => {
      service.createSignature({
        name: 'Attack Pattern',
        pattern: 'admin.*password.*reset',
        severity: ThreatLevel.HIGH,
        description: 'Suspicious admin action'
      });

      let falsePositives = 0;
      const testCount = 1000;

      for (let i = 0; i < testCount; i++) {
        const event = createSecurityEvent({
          data: {
            message: `Normal user action ${i} with regular data processing`
          }
        });

        const matches = service.matchEvent(event);
        if (matches.length > 0) {
          falsePositives++;
        }
      }

      const falsePositiveRate = falsePositives / testCount;
      expect(falsePositiveRate).toBeLessThan(0.01);
    });
  });

  describe('Multi-Pattern Detection', () => {
    it('should detect multiple patterns in single event', () => {
      service.createSignature({
        name: 'Pattern 1',
        pattern: 'SELECT',
        severity: ThreatLevel.HIGH,
        description: 'Pattern 1'
      });

      service.createSignature({
        name: 'Pattern 2',
        pattern: 'DROP',
        severity: ThreatLevel.CRITICAL,
        description: 'Pattern 2'
      });

      const event = createSecurityEvent({
        data: {
          query: 'SELECT * FROM users; DROP TABLE users;'
        }
      });

      const matches = service.matchEvent(event);
      expect(matches.length).toBeGreaterThanOrEqual(2);
    });

    it('should prioritize matches by severity', () => {
      service.createSignature({
        name: 'Low Severity',
        pattern: 'info',
        severity: ThreatLevel.LOW,
        description: 'Low'
      });

      service.createSignature({
        name: 'Critical Severity',
        pattern: 'critical',
        severity: ThreatLevel.CRITICAL,
        description: 'Critical'
      });

      const event = createSecurityEvent({
        data: { message: 'critical info' }
      });

      const matches = service.matchEvent(event);
      if (matches.length > 1) {
        expect(matches[0].severity).toBe(ThreatLevel.CRITICAL);
      }
    });
  });

  describe('Signature Management', () => {
    it('should enable and disable signatures', () => {
      const sig = service.createSignature({
        name: 'Test Signature',
        pattern: 'test',
        severity: ThreatLevel.MEDIUM,
        description: 'Test'
      });

      service.disableSignature(sig.id);
      const event = createSecurityEvent({ data: { message: 'test message' } });

      const matches = service.matchEvent(event);
      expect(matches.length).toBe(0);

      service.enableSignature(sig.id);
      const matches2 = service.matchEvent(event);
      expect(matches2.length).toBeGreaterThan(0);
    });

    it('should update signature pattern', () => {
      const sig = service.createSignature({
        name: 'Original Pattern',
        pattern: 'original',
        severity: ThreatLevel.MEDIUM,
        description: 'Original'
      });

      service.updateSignature(sig.id, {
        name: 'Updated Pattern',
        pattern: 'updated'
      });

      const event1 = createSecurityEvent({ data: { message: 'original' } });
      const event2 = createSecurityEvent({ data: { message: 'updated' } });

      expect(service.matchEvent(event1).length).toBe(0);
      expect(service.matchEvent(event2).length).toBeGreaterThan(0);
    });

    it('should delete signature', () => {
      const sig = service.createSignature({
        name: 'Delete Me',
        pattern: 'delete',
        severity: ThreatLevel.MEDIUM,
        description: 'Delete'
      });

      expect(service.getSignatureCount()).toBe(1);

      service.deleteSignature(sig.id);
      expect(service.getSignatureCount()).toBe(0);
    });

    it('should retrieve signature by ID', () => {
      const sig = service.createSignature({
        name: 'Retrieve Me',
        pattern: 'retrieve',
        severity: ThreatLevel.MEDIUM,
        description: 'Retrieve'
      });

      const retrieved = service.getSignature(sig.id);
      expect(retrieved).toBeDefined();
      expect(retrieved?.name).toBe('Retrieve Me');
    });

    it('should list all signatures', () => {
      service.createSignature({
        name: 'Sig 1',
        pattern: 'pattern1',
        severity: ThreatLevel.LOW,
        description: 'Sig 1'
      });

      service.createSignature({
        name: 'Sig 2',
        pattern: 'pattern2',
        severity: ThreatLevel.HIGH,
        description: 'Sig 2'
      });

      const signatures = service.getAllSignatures();
      expect(signatures.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Regex Pattern Validation', () => {
    it('should validate regex patterns', () => {
      const valid = service.validatePattern('SELECT.*FROM');
      expect(valid).toBe(true);

      const invalid = service.validatePattern('[invalid(');
      expect(invalid).toBe(false);
    });

    it('should create signature with valid pattern', () => {
      expect(() => {
        service.createSignature({
          name: 'Valid',
          pattern: 'test.*pattern',
          severity: ThreatLevel.MEDIUM,
          description: 'Valid'
        });
      }).not.toThrow();
    });

    it('should reject invalid regex patterns', () => {
      expect(() => {
        service.createSignature({
          name: 'Invalid',
          pattern: '[invalid(',
          severity: ThreatLevel.MEDIUM,
          description: 'Invalid'
        });
      }).toThrow();
    });
  });

  describe('Match Statistics', () => {
    it('should track match statistics', () => {
      service.createSignature({
        name: 'Track Me',
        pattern: 'track',
        severity: ThreatLevel.MEDIUM,
        description: 'Track'
      });

      for (let i = 0; i < 10; i++) {
        const event = createSecurityEvent({
          data: { message: 'track this' }
        });
        service.matchEvent(event);
      }

      const stats = service.getMatchStatistics();
      expect(stats.totalMatches).toBeGreaterThanOrEqual(10);
    });

    it('should track matches per signature', () => {
      const sig1 = service.createSignature({
        name: 'Sig 1',
        pattern: 'pattern1',
        severity: ThreatLevel.MEDIUM,
        description: 'Sig 1'
      });

      const sig2 = service.createSignature({
        name: 'Sig 2',
        pattern: 'pattern2',
        severity: ThreatLevel.MEDIUM,
        description: 'Sig 2'
      });

      for (let i = 0; i < 5; i++) {
        service.matchEvent(createSecurityEvent({ data: { message: 'pattern1' } }));
      }

      for (let i = 0; i < 3; i++) {
        service.matchEvent(createSecurityEvent({ data: { message: 'pattern2' } }));
      }

      const stats = service.getSignatureStatistics(sig1.id);
      expect(stats.matchCount).toBeGreaterThanOrEqual(5);
    });
  });

  describe('Event Batch Processing', () => {
    it('should match batch of events', () => {
      service.createSignature({
        name: 'Batch Pattern',
        pattern: 'batch',
        severity: ThreatLevel.MEDIUM,
        description: 'Batch'
      });

      const events = Array.from({ length: 50 }, (_, i) =>
        createSecurityEvent({
          data: { message: i % 2 === 0 ? 'batch process' : 'normal process' }
        })
      );

      const allMatches = service.matchEventBatch(events);
      expect(allMatches.length).toBeGreaterThan(0);
    });

    it('should handle high-throughput matching', () => {
      service.createSignature({
        name: 'High Throughput',
        pattern: 'match',
        severity: ThreatLevel.MEDIUM,
        description: 'High throughput'
      });

      const startTime = Date.now();
      const eventCount = 1000;

      for (let i = 0; i < eventCount; i++) {
        service.matchEvent(
          createSecurityEvent({
            data: { message: `event ${i}` }
          })
        );
      }

      const duration = Date.now() - startTime;
      const throughput = (eventCount / duration) * 1000;

      expect(throughput).toBeGreaterThan(100); // >100 events/sec
    });
  });
});

function createSecurityEvent(overrides: any = {}): SecurityEvent {
  return {
    id: `event-${Date.now()}-${Math.random()}`,
    timestamp: new Date(),
    source: 'test-source',
    eventType: 'test-event',
    severity: ThreatLevel.MEDIUM,
    data: { message: 'test' },
    ...overrides
  };
}
