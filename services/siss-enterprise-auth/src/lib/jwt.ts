import * as crypto from 'crypto';
import * as jwt from 'jsonwebtoken';

interface TokenPayload {
  userId: string;
  email?: string;
  mfaEnabled?: boolean;
  sessionId?: string;
  exp?: number;
  jti?: string; // JWT ID for uniqueness
}

export class JWTManager {
  private privateKey: crypto.KeyObject;
  private publicKey: crypto.KeyObject;
  private revokedTokens: Set<string> = new Set();
  private rotatedTokens: Set<string> = new Set();

  constructor() {
    // Generate RSA key pair for JWT signing (RS256)
    const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
    });
    this.privateKey = privateKey;
    this.publicKey = publicKey;
  }

  generateAccessToken(payload: TokenPayload): string {
    const exp = payload.exp ?? Math.floor(Date.now() / 1000) + 15 * 60; // 15 minutes or custom
    const tokenPayload = {
      ...payload,
      exp,
      type: 'access'
    };
    return jwt.sign(tokenPayload, this.privateKey, { algorithm: 'RS256' });
  }

  generateRefreshToken(payload: TokenPayload): string {
    const exp = Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60; // 7 days
    const tokenPayload = {
      ...payload,
      exp,
      type: 'refresh'
    };
    return jwt.sign(tokenPayload, this.privateKey, { algorithm: 'RS256' });
  }

  verifyAccessToken(token: string): TokenPayload {
    try {
      if (this.revokedTokens.has(token)) {
        throw new Error('Token has been revoked');
      }
      const decoded = jwt.verify(token, this.publicKey, {
        algorithms: ['RS256']
      }) as TokenPayload;
      return decoded;
    } catch (error) {
      throw new Error(`Token verification failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  verifyRefreshToken(token: string): TokenPayload {
    try {
      if (this.revokedTokens.has(token)) {
        throw new Error('Token has been revoked');
      }
      const decoded = jwt.verify(token, this.publicKey, {
        algorithms: ['RS256']
      }) as TokenPayload;
      return decoded;
    } catch (error) {
      throw new Error(`Refresh token verification failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  rotateRefreshToken(oldToken: string): string {
    // Verify the old token before rotating
    const payload = this.verifyRefreshToken(oldToken);
    // Mark old token as rotated
    this.rotatedTokens.add(oldToken);
    // Generate new token with same data but unique jti
    return this.generateRefreshToken({
      userId: payload.userId,
      sessionId: payload.sessionId,
      jti: crypto.randomBytes(16).toString('hex') // Ensure uniqueness
    });
  }

  revokeToken(token: string): void {
    try {
      // Verify the token exists and is valid before revoking
      jwt.verify(token, this.publicKey, { algorithms: ['RS256'] });
      this.revokedTokens.add(token);
    } catch (error) {
      throw new Error(`Cannot revoke invalid token: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  isTokenRevoked(token: string): boolean {
    return this.revokedTokens.has(token);
  }

  isTokenRotated(token: string): boolean {
    return this.rotatedTokens.has(token);
  }

  getPublicKey(): string {
    return this.publicKey.export({ format: 'pem', type: 'spki' }).toString();
  }
}
