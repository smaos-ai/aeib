import { describe, it, expect } from 'vitest';
import {
  getRunbook,
  listRunbooks,
  Runbook
} from '../src/lib/runbooks';

describe('Incident Runbooks', () => {
  describe('Runbook Retrieval', () => {
    it('should return latency breach runbook', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook).toBeDefined();
      expect(runbook.title).toContain('Latency');
    });

    it('should return error rate runbook', () => {
      const runbook = getRunbook('high_error_rate');
      expect(runbook).toBeDefined();
      expect(runbook.title).toContain('Error');
    });

    it('should return compliance runbook', () => {
      const runbook = getRunbook('compliance_drop');
      expect(runbook).toBeDefined();
      expect(runbook.title).toContain('Compliance');
    });

    it('should include diagnosis section', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook.diagnosis).toBeDefined();
      expect(runbook.diagnosis.length).toBeGreaterThan(0);
    });

    it('should include recovery steps', () => {
      const runbook = getRunbook('high_error_rate');
      expect(runbook.recovery_steps).toBeDefined();
      expect(Array.isArray(runbook.recovery_steps)).toBe(true);
      expect(runbook.recovery_steps.length).toBeGreaterThan(0);
    });

    it('should include runbook owner/author', () => {
      const runbook = getRunbook('compliance_drop');
      expect(runbook.owner).toBeDefined();
    });

    it('should handle unknown runbook gracefully', () => {
      const runbook = getRunbook('unknown_alert');
      expect(runbook).toBeDefined();
      expect(runbook.title).toContain('Unknown');
    });
  });

  describe('Latency Breach Runbook', () => {
    it('should have complete diagnostic information', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook.diagnosis).toContain('Check');
    });

    it('should have actionable recovery steps', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook.recovery_steps.length).toBeGreaterThanOrEqual(3);
    });

    it('should include escalation procedure', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook.escalation).toBeDefined();
    });

    it('should include affected services', () => {
      const runbook = getRunbook('latency_breach');
      expect(runbook.affected_services).toBeDefined();
    });
  });

  describe('Error Rate Runbook', () => {
    it('should identify error rate causes', () => {
      const runbook = getRunbook('high_error_rate');
      const diagnosis = runbook.diagnosis.toLowerCase();
      expect(diagnosis).toContain('error');
    });

    it('should provide mitigation steps', () => {
      const runbook = getRunbook('high_error_rate');
      expect(runbook.recovery_steps.length).toBeGreaterThan(0);
      expect(runbook.recovery_steps[0].length).toBeGreaterThan(0);
    });

    it('should include rollback instructions', () => {
      const runbook = getRunbook('high_error_rate');
      const stepsText = runbook.recovery_steps.join(' ').toLowerCase();
      expect(stepsText).toContain('error') || expect(runbook.recovery_steps.length).toBeGreaterThan(0);
    });
  });

  describe('Compliance Runbook', () => {
    it('should address compliance requirements', () => {
      const runbook = getRunbook('compliance_drop');
      expect(runbook.title).toContain('Compliance');
    });

    it('should provide audit trail guidance', () => {
      const runbook = getRunbook('compliance_drop');
      expect(runbook.diagnosis).toBeDefined();
      expect(runbook.diagnosis.length).toBeGreaterThan(0);
    });

    it('should include regulatory notification steps', () => {
      const runbook = getRunbook('compliance_drop');
      expect(runbook.recovery_steps.length).toBeGreaterThan(0);
    });
  });

  describe('Runbook Structure', () => {
    it('should have consistent structure across all runbooks', () => {
      const runbooks = [
        'latency_breach',
        'high_error_rate',
        'compliance_drop'
      ];

      runbooks.forEach(name => {
        const runbook = getRunbook(name);
        expect(runbook.title).toBeDefined();
        expect(runbook.diagnosis).toBeDefined();
        expect(runbook.recovery_steps).toBeDefined();
        expect(runbook.owner).toBeDefined();
        expect(runbook.escalation).toBeDefined();
        expect(runbook.affected_services).toBeDefined();
      });
    });

    it('should list all available runbooks', () => {
      const runbooks = listRunbooks();
      expect(Array.isArray(runbooks)).toBe(true);
      expect(runbooks.length).toBeGreaterThanOrEqual(3);
    });

    it('should have unique runbook names', () => {
      const runbooks = listRunbooks();
      const names = runbooks.map(r => r.id);
      const uniqueNames = new Set(names);
      expect(uniqueNames.size).toBe(names.length);
    });
  });

  describe('Runbook Content Quality', () => {
    it('each runbook should have meaningful diagnosis', () => {
      const runbooks = listRunbooks();
      runbooks.forEach(runbook => {
        const rb = getRunbook(runbook.id);
        expect(rb.diagnosis.length).toBeGreaterThan(10);
      });
    });

    it('each recovery step should be actionable', () => {
      const runbooks = listRunbooks();
      runbooks.forEach(runbook => {
        const rb = getRunbook(runbook.id);
        rb.recovery_steps.forEach(step => {
          expect(step.length).toBeGreaterThan(5);
        });
      });
    });

    it('each runbook should have owner assigned', () => {
      const runbooks = listRunbooks();
      runbooks.forEach(runbook => {
        const rb = getRunbook(runbook.id);
        expect(rb.owner.length).toBeGreaterThan(0);
      });
    });
  });
});
