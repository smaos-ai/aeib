import nacl from 'tweetnacl';
import { randomUUID, randomBytes } from 'crypto';
import { ComplianceReport, SigningResult } from './types';

interface Keypair {
  publicKey: Uint8Array;
  secretKey: Uint8Array;
  privateKey?: Uint8Array;
}

interface StoredSignature {
  signature: string;
  signatureTimestamp: Date;
  signedBy: string;
}

export class KMSSigningService {
  private keypair: Keypair;
  private signatureLog: Map<string, StoredSignature> = new Map();
  private signatureChain: Map<string, SigningResult[]> = new Map();

  constructor() {
    // Create a deterministic keypair for testing
    const seed = new Uint8Array(32);
    seed[0] = 42; // Use a constant for deterministic testing
    this.keypair = nacl.sign.keyPair.fromSeed(seed);
  }

  async generateKeyPair(): Promise<Keypair> {
    const kp = nacl.sign.keyPair();
    return {
      publicKey: kp.publicKey,
      secretKey: kp.secretKey,
      privateKey: kp.secretKey
    };
  }

  getPublicKey(): string {
    return Buffer.from(this.keypair.publicKey).toString('hex');
  }

  validateKeypair(keypair: Keypair): boolean {
    return (
      keypair.publicKey instanceof Uint8Array &&
      keypair.secretKey instanceof Uint8Array &&
      keypair.publicKey.length === 32 &&
      keypair.secretKey.length === 64
    );
  }

  async signReport(report: ComplianceReport): Promise<SigningResult> {
    const data = JSON.stringify({
      id: report.id,
      generatedAt: report.generatedAt.toISOString(),
      framework: report.framework,
      overallScore: report.overallScore,
      gaps: report.gaps.length,
      events: report.events.length
    });

    const messageBytes = Buffer.from(data, 'utf-8');
    const signatureBytes = nacl.sign.detached(messageBytes, this.keypair.secretKey);
    const signature = Buffer.from(signatureBytes).toString('hex');

    const timestamp = new Date();
    const publicKey = this.getPublicKey();

    const result: SigningResult = {
      signature,
      publicKey,
      signedBy: publicKey,
      timestamp,
      signatureTimestamp: timestamp,
      isValid: true
    };

    this.recordSignature(report.id, result);

    return result;
  }

  async verifySignature(report: ComplianceReport, signature: string): Promise<boolean> {
    try {
      if (!signature || typeof signature !== 'string' || signature.length === 0) {
        return false;
      }

      const signatureBytes = Buffer.from(signature, 'hex');
      if (signatureBytes.length !== 64) {
        return false;
      }

      const data = JSON.stringify({
        id: report.id,
        generatedAt: report.generatedAt.toISOString(),
        framework: report.framework,
        overallScore: report.overallScore,
        gaps: report.gaps.length,
        events: report.events.length
      });

      const messageBytes = Buffer.from(data, 'utf-8');
      const verified = nacl.sign.detached.verify(
        messageBytes,
        signatureBytes,
        this.keypair.publicKey
      );

      return verified;
    } catch {
      return false;
    }
  }

  getSignatureChain(reportId: string): SigningResult[] {
    return this.signatureChain.get(reportId) || [];
  }

  async persistSignature(reportId: string, result: SigningResult): Promise<void> {
    // TODO: INTEGRATE Jun 2027 - Persist to Phase 1 L2 knowledge vectors with KMS anchor
    this.signatureLog.set(reportId, {
      signature: result.signature,
      signatureTimestamp: result.timestamp,
      signedBy: result.publicKey
    });
  }

  async getSignature(reportId: string): Promise<StoredSignature | undefined> {
    // TODO: INTEGRATE Jun 2027 - Retrieve from Phase 1 L2 knowledge vectors
    return this.signatureLog.get(reportId);
  }

  private recordSignature(reportId: string, result: SigningResult): void {
    if (!this.signatureChain.has(reportId)) {
      this.signatureChain.set(reportId, []);
    }

    const chain = this.signatureChain.get(reportId)!;
    chain.push(result);
  }
}
