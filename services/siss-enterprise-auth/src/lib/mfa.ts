import * as speakeasy from 'speakeasy';
import * as crypto from 'crypto';
import * as QRCode from 'qrcode';

interface TOTPSecret {
  secret: string;
  qrCode: string;
  backupCodes: string[];
}

interface WebAuthnChallenge {
  challenge: string;
  options: {
    rp: { name: string; id: string };
    user: { id: string; name: string; displayName: string };
    pubKeyCredParams: Array<{ type: string; alg: number }>;
    timeout: number;
    attestation: string;
    authenticatorSelection: {
      authenticatorAttachment: string;
      residentKey: string;
    };
  };
}

interface ChallengeData {
  challenge: string;
  timestamp: number;
}

interface MFACompletion {
  method: string;
  completedAt: number;
  userId: string;
}

export class MFAManager {
  private webauthnChallenges: Map<string, ChallengeData> = new Map();
  private mfaSessions: Map<string, MFACompletion> = new Map();

  generateTOTPSecret(email: string): TOTPSecret {
    const secret = speakeasy.generateSecret({
      name: `SovereignNexus (${email})`,
      length: 32
    });

    const backupCodes = Array.from({ length: 10 }, () =>
      crypto.randomBytes(4).toString('hex')
    );

    return {
      secret: secret.base32,
      qrCode: secret.qr_code_url || '',
      backupCodes
    };
  }

  generateTOTPCode(secret: string, offsetSeconds: number = 0): string {
    return speakeasy.totp({
      secret,
      encoding: 'base32',
      time: Math.floor(Date.now() / 1000) + offsetSeconds
    });
  }

  verifyTOTPCode(code: string, secret: string, offsetSeconds: number = 0): boolean {
    const currentTime = Math.floor(Date.now() / 1000) + offsetSeconds;
    // Check current and adjacent 30-second windows
    for (let i = -1; i <= 1; i++) {
      const expected = speakeasy.totp({
        secret,
        encoding: 'base32',
        time: currentTime + i * 30
      });
      if (code === expected) {
        return true;
      }
    }
    return false;
  }

  verifyBackupCode(code: string, backupCodes: string[]): boolean {
    return backupCodes.includes(code);
  }

  consumeBackupCode(code: string, backupCodes: string[]): string[] {
    return backupCodes.filter(c => c !== code);
  }

  generateWebAuthnChallenge(email: string, userId: string): WebAuthnChallenge {
    const challenge = crypto.randomBytes(32).toString('base64url');
    const challengeData: ChallengeData = {
      challenge,
      timestamp: Date.now()
    };
    this.webauthnChallenges.set(userId, challengeData);

    return {
      challenge,
      options: {
        rp: {
          name: 'SovereignNexus',
          id: 'example.com'
        },
        user: {
          id: crypto.randomBytes(16).toString('base64url'),
          name: email,
          displayName: email
        },
        pubKeyCredParams: [
          { type: 'public-key', alg: -7 }, // ES256
          { type: 'public-key', alg: -257 } // RS256
        ],
        timeout: 60000,
        attestation: 'direct',
        authenticatorSelection: {
          authenticatorAttachment: 'platform',
          residentKey: 'preferred'
        }
      }
    };
  }

  getChallengeForUser(userId: string): ChallengeData | undefined {
    return this.webauthnChallenges.get(userId);
  }

  clearChallenge(userId: string): void {
    this.webauthnChallenges.delete(userId);
  }

  verifyWebAuthnAssertion(
    assertion: any,
    userId: string
  ): boolean {
    const challenge = this.webauthnChallenges.get(userId);
    if (!challenge) return false;

    try {
      const clientDataJSON = JSON.parse(
        Buffer.from(assertion.response.clientDataJSON, 'base64').toString()
      );

      // Verify challenge matches
      if (clientDataJSON.challenge !== challenge.challenge) {
        return false;
      }

      // Verify challenge is not too old (5 minutes)
      if (Date.now() - challenge.timestamp > 5 * 60 * 1000) {
        return false;
      }

      return true;
    } catch {
      return false;
    }
  }

  recordMFACompletion(
    sessionId: string,
    userId: string,
    method: string
  ): void {
    this.mfaSessions.set(sessionId, {
      method,
      completedAt: Date.now(),
      userId
    });
  }

  getMFACompletion(sessionId: string): MFACompletion | undefined {
    return this.mfaSessions.get(sessionId);
  }

  isMFASessionValid(sessionId: string, maxAgeSeconds: number): boolean {
    const session = this.mfaSessions.get(sessionId);
    if (!session) return false;

    const ageSeconds = (Date.now() - session.completedAt) / 1000;
    // Return false if age exceeds max (session expired)
    return ageSeconds < maxAgeSeconds;
  }

  clearMFASession(sessionId: string): void {
    this.mfaSessions.delete(sessionId);
  }
}
