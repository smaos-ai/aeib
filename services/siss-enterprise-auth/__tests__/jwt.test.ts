import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { JWTManager } from '../src/lib/jwt';
import { createReadStream } from 'fs';

describe('JWT Manager', () => {
  let jwtManager: JWTManager;

  beforeAll(async () => {
    jwtManager = new JWTManager();
  });

  describe('Token Generation', () => {
    it('should generate valid JWT with Ed25519', () => {
      const token = jwtManager.generateAccessToken({
        userId: 'user123',
        email: 'user@example.com',
        mfaEnabled: true
      });
      expect(token).toBeDefined();
      expect(typeof token).toBe('string');
      expect(token.split('.').length).toBe(3);
    });

    it('should include correct payload in token', () => {
      const payload = {
        userId: 'user456',
        email: 'test@example.com',
        mfaEnabled: false
      };
      const token = jwtManager.generateAccessToken(payload);
      const decoded = jwtManager.verifyAccessToken(token);
      expect(decoded.userId).toBe('user456');
      expect(decoded.email).toBe('test@example.com');
      expect(decoded.mfaEnabled).toBe(false);
    });

    it('should set correct expiry for access token (15 min)', () => {
      const token = jwtManager.generateAccessToken({
        userId: 'user789',
        email: 'another@example.com',
        mfaEnabled: true
      });
      const decoded = jwtManager.verifyAccessToken(token);
      const now = Math.floor(Date.now() / 1000);
      const expiryDelta = (decoded.exp as number) - now;
      expect(expiryDelta).toBeGreaterThan(14 * 60);
      expect(expiryDelta).toBeLessThanOrEqual(15 * 60);
    });
  });

  describe('Refresh Token', () => {
    it('should generate valid refresh token', () => {
      const refreshToken = jwtManager.generateRefreshToken({
        userId: 'user999',
        sessionId: 'sess123'
      });
      expect(refreshToken).toBeDefined();
      expect(typeof refreshToken).toBe('string');
      expect(refreshToken.split('.').length).toBe(3);
    });

    it('should set correct expiry for refresh token (7 days)', () => {
      const refreshToken = jwtManager.generateRefreshToken({
        userId: 'user888',
        sessionId: 'sess456'
      });
      const decoded = jwtManager.verifyRefreshToken(refreshToken);
      const now = Math.floor(Date.now() / 1000);
      const expiryDelta = (decoded.exp as number) - now;
      expect(expiryDelta).toBeGreaterThan(6.9 * 24 * 60 * 60);
      expect(expiryDelta).toBeLessThanOrEqual(7 * 24 * 60 * 60);
    });

    it('should rotate refresh token and invalidate old one', () => {
      const oldRefresh = jwtManager.generateRefreshToken({
        userId: 'user111',
        sessionId: 'sess789'
      });
      const newRefresh = jwtManager.rotateRefreshToken(oldRefresh);
      expect(newRefresh).toBeDefined();
      expect(newRefresh).not.toBe(oldRefresh);

      // Verify old token is in rotation log
      expect(jwtManager.isTokenRotated(oldRefresh)).toBe(true);
    });
  });

  describe('Token Verification', () => {
    it('should reject expired token', () => {
      const expiredPayload = {
        userId: 'user222',
        email: 'expired@example.com',
        mfaEnabled: true,
        exp: Math.floor(Date.now() / 1000) - 3600 // 1 hour ago
      };
      const expiredToken = jwtManager.generateAccessToken(expiredPayload);
      expect(() => jwtManager.verifyAccessToken(expiredToken)).toThrow();
    });

    it('should reject malformed token', () => {
      const malformed = 'not.a.jwt.token.here';
      expect(() => jwtManager.verifyAccessToken(malformed)).toThrow();
    });

    it('should reject token with invalid signature', () => {
      const token = jwtManager.generateAccessToken({
        userId: 'user333',
        email: 'sig@example.com',
        mfaEnabled: false
      });
      const parts = token.split('.');
      const tamperedToken = `${parts[0]}.${parts[1]}.invalidsignature`;
      expect(() => jwtManager.verifyAccessToken(tamperedToken)).toThrow();
    });

    it('should reject token with tampered payload', () => {
      const token = jwtManager.generateAccessToken({
        userId: 'user444',
        email: 'tamper@example.com',
        mfaEnabled: true
      });
      const parts = token.split('.');
      const tamperedPayload = Buffer.from(JSON.stringify({
        userId: 'admin',
        email: 'tamper@example.com',
        mfaEnabled: false
      })).toString('base64url');
      const tamperedToken = `${parts[0]}.${tamperedPayload}.${parts[2]}`;
      expect(() => jwtManager.verifyAccessToken(tamperedToken)).toThrow();
    });
  });

  describe('Token Revocation', () => {
    it('should revoke access token', () => {
      const token = jwtManager.generateAccessToken({
        userId: 'user555',
        email: 'revoke@example.com',
        mfaEnabled: true
      });
      jwtManager.revokeToken(token);
      expect(jwtManager.isTokenRevoked(token)).toBe(true);
      expect(() => jwtManager.verifyAccessToken(token)).toThrow();
    });

    it('should not revoke non-existent token', () => {
      const fakeToken = 'header.payload.signature';
      expect(() => jwtManager.revokeToken(fakeToken)).toThrow();
    });
  });
});
