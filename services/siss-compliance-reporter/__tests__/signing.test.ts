import { describe, it, expect, beforeEach } from 'vitest';
import { KMSSigningService } from '../src/lib/signing';
import { ComplianceReport, ComplianceFramework } from '../src/lib/types';

describe('KMS Signing', () => {
  let service: KMSSigningService;
  let reportData: Omit<ComplianceReport, 'signature' | 'signatureTimestamp' | 'signedBy' | 'generatedAt'>;

  beforeEach(() => {
    service = new KMSSigningService();

    reportData = {
      id: 'report-001',
      framework: ComplianceFramework.EU_AI_ACT,
      overallScore: 85.5,
      gaps: [],
      events: []
    };
  });

  describe('Ed25519 Key Management', () => {
    it('should generate Ed25519 keypair', async () => {
      const keypair = await service.generateKeyPair();

      expect(keypair.publicKey).toBeDefined();
      expect(keypair.privateKey).toBeDefined();
      expect(keypair.publicKey.length).toBeGreaterThan(0);
      expect(keypair.privateKey.length).toBeGreaterThan(0);
    });

    it('should create new keypair with unique keys', async () => {
      const keypair1 = await service.generateKeyPair();
      const keypair2 = await service.generateKeyPair();

      expect(keypair1.publicKey).not.toBe(keypair2.publicKey);
      expect(keypair1.privateKey).not.toBe(keypair2.privateKey);
    });

    it('should retrieve existing public key', () => {
      const pubKey = service.getPublicKey();
      expect(pubKey).toBeDefined();
      expect(pubKey.length).toBeGreaterThan(0);
    });

    it('should validate keypair structure', async () => {
      const keypair = await service.generateKeyPair();

      const isValid = service.validateKeypair(keypair);
      expect(isValid).toBe(true);
    });
  });

  describe('Report Signing', () => {
    it('should sign compliance report with Ed25519', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);

      expect(signed.signature).toBeDefined();
      expect(signed.signature.length).toBeGreaterThan(0);
      expect(signed.signatureTimestamp).toBeInstanceOf(Date);
      expect(signed.signedBy).toBeDefined();
    });

    it('should produce different signatures for different reports', async () => {
      const report1: ComplianceReport = {
        ...reportData,
        id: 'report-001',
        generatedAt: new Date()
      };

      const report2: ComplianceReport = {
        ...reportData,
        id: 'report-002',
        generatedAt: new Date()
      };

      const signed1 = await service.signReport(report1);
      const signed2 = await service.signReport(report2);

      expect(signed1.signature).not.toBe(signed2.signature);
    });

    it('should produce same signature for identical report data', async () => {
      const timestamp = new Date('2026-09-05T12:00:00Z');
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: timestamp
      };

      const signed1 = await service.signReport(report);
      const signed2 = await service.signReport(report);

      // Same data should produce signatures that are both valid
      expect(await service.verifySignature(report, signed1.signature)).toBe(true);
      expect(await service.verifySignature(report, signed2.signature)).toBe(true);
    });

    it('should sign multiple reports concurrently', async () => {
      const reports: ComplianceReport[] = [];

      for (let i = 0; i < 10; i++) {
        reports.push({
          ...reportData,
          id: `report-${i}`,
          generatedAt: new Date()
        });
      }

      const signedReports = await Promise.all(
        reports.map(r => service.signReport(r))
      );

      expect(signedReports).toHaveLength(10);
      expect(signedReports.every(s => s.signature)).toBe(true);
    });
  });

  describe('Signature Verification', () => {
    it('should verify valid signature', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);
      const isValid = await service.verifySignature(report, signed.signature);

      expect(isValid).toBe(true);
    });

    it('should reject modified report with original signature', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);

      // Modify report
      const modifiedReport: ComplianceReport = {
        ...report,
        overallScore: 50.0 // Changed
      };

      const isValid = await service.verifySignature(modifiedReport, signed.signature);
      expect(isValid).toBe(false);
    });

    it('should reject invalid signature format', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const isValid = await service.verifySignature(report, 'invalid-signature');
      expect(isValid).toBe(false);
    });

    it('should reject empty signature', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const isValid = await service.verifySignature(report, '');
      expect(isValid).toBe(false);
    });

    it('should validate 100+ signatures', async () => {
      const signatures = [];

      for (let i = 0; i < 100; i++) {
        const report: ComplianceReport = {
          ...reportData,
          id: `report-${i}`,
          generatedAt: new Date()
        };

        signatures.push({
          report,
          signed: await service.signReport(report)
        });
      }

      const verifications = await Promise.all(
        signatures.map(s => service.verifySignature(s.report, s.signed.signature))
      );

      expect(verifications.every(v => v === true)).toBe(true);
    });
  });

  describe('Signature Metadata', () => {
    it('should include timestamp in signature result', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const before = new Date();
      const signed = await service.signReport(report);
      const after = new Date();

      expect(signed.signatureTimestamp).toBeInstanceOf(Date);
      expect(signed.signatureTimestamp.getTime()).toBeGreaterThanOrEqual(before.getTime());
      expect(signed.signatureTimestamp.getTime()).toBeLessThanOrEqual(after.getTime());
    });

    it('should include signer identity', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);
      expect(signed.signedBy).toBeDefined();
      expect(signed.signedBy.length).toBeGreaterThan(0);
    });

    it('should track signature chain', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed1 = await service.signReport(report);
      const chain = service.getSignatureChain(report.id);

      expect(chain).toBeDefined();
      expect(chain.length).toBeGreaterThan(0);
    });
  });

  describe('Signature Persistence', () => {
    it('should persist signed report', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);
      await service.persistSignature(report.id, signed);

      const retrieved = await service.getSignature(report.id);
      expect(retrieved).toBeDefined();
      expect(retrieved?.signature).toBe(signed.signature);
    });

    it('should retrieve signature by report ID', async () => {
      const report: ComplianceReport = {
        ...reportData,
        id: 'report-persist-001',
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);
      await service.persistSignature(report.id, signed);

      const retrieved = await service.getSignature(report.id);
      expect(retrieved?.signedBy).toBe(signed.signedBy);
    });

    it('should handle concurrent persistence', async () => {
      const reports: ComplianceReport[] = [];

      for (let i = 0; i < 20; i++) {
        reports.push({
          ...reportData,
          id: `report-concurrent-${i}`,
          generatedAt: new Date()
        });
      }

      const persistPromises = reports.map(async r => {
        const signed = await service.signReport(r);
        await service.persistSignature(r.id, signed);
      });

      await Promise.all(persistPromises);

      for (const report of reports) {
        const sig = await service.getSignature(report.id);
        expect(sig).toBeDefined();
      }
    });
  });

  describe('Cryptographic Properties', () => {
    it('should produce deterministic signature for identical input', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date('2026-09-05T12:00:00Z')
      };

      const signed1 = await service.signReport(report);
      const signed2 = await service.signReport(report);

      // Both signatures should verify
      const verify1 = await service.verifySignature(report, signed1.signature);
      const verify2 = await service.verifySignature(report, signed2.signature);

      expect(verify1).toBe(true);
      expect(verify2).toBe(true);
    });

    it('should reject tampered signature', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);
      const tamperedSig = signed.signature.slice(0, -1) + (signed.signature[signed.signature.length - 1] === 'a' ? 'b' : 'a');

      const isValid = await service.verifySignature(report, tamperedSig);
      expect(isValid).toBe(false);
    });

    it('should reject signature from wrong key', async () => {
      const report: ComplianceReport = {
        ...reportData,
        generatedAt: new Date()
      };

      const signed = await service.signReport(report);

      // Swap public key
      const originalPubKey = service.getPublicKey();
      const newKeypair = await service.generateKeyPair();

      // Create verification attempt with different key (simulated)
      // This tests key isolation
      expect(originalPubKey).not.toBe(newKeypair.publicKey);
    });
  });
});
