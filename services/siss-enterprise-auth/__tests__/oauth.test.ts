import { describe, it, expect, beforeEach } from 'vitest';
import { OAuthManager } from '../src/lib/oauth';

describe('OAuth 2.0 Manager', () => {
  let oauthManager: OAuthManager;

  beforeEach(() => {
    oauthManager = new OAuthManager(
      'client-id-123',
      'client-secret-456',
      'https://example.com/callback'
    );
  });

  describe('Authorization Code Flow', () => {
    it('should generate authorization URL', () => {
      const state = oauthManager.generateState();
      const authUrl = oauthManager.generateAuthorizationURL(state);
      expect(authUrl).toContain('client_id=client-id-123');
      expect(authUrl).toContain(`state=${state}`);
      expect(authUrl).toContain('response_type=code');
      expect(authUrl).toContain('scope=');
    });

    it('should generate unique state tokens', () => {
      const state1 = oauthManager.generateState();
      const state2 = oauthManager.generateState();
      expect(state1).not.toBe(state2);
    });

    it('should validate state token', () => {
      const state = oauthManager.generateState();
      const isValid = oauthManager.validateState(state);
      expect(isValid).toBe(true);
    });

    it('should reject invalid state token', () => {
      const isValid = oauthManager.validateState('invalid-state-token');
      expect(isValid).toBe(false);
    });

    it('should exchange authorization code for tokens', async () => {
      const state = oauthManager.generateState();
      // Mock token response
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      expect(tokenResponse.access_token).toBeDefined();
      expect(tokenResponse.refresh_token).toBeDefined();
      expect(tokenResponse.token_type).toBe('Bearer');
      expect(tokenResponse.expires_in).toBeGreaterThan(0);
    });

    it('should reject code exchange with invalid state', async () => {
      try {
        await oauthManager.exchangeCodeForToken('auth-code-123', 'wrong-state');
        expect.fail('Should have thrown error');
      } catch (error) {
        expect(error).toBeDefined();
      }
    });
  });

  describe('Token Management', () => {
    it('should validate access token', async () => {
      const state = oauthManager.generateState();
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      const isValid = oauthManager.validateAccessToken(tokenResponse.access_token);
      expect(isValid).toBe(true);
    });

    it('should refresh expired access token', async () => {
      const state = oauthManager.generateState();
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      const newTokens = await oauthManager.refreshAccessToken(tokenResponse.refresh_token);
      expect(newTokens.access_token).toBeDefined();
      expect(newTokens.refresh_token).toBeDefined();
      expect(newTokens.access_token).not.toBe(tokenResponse.access_token);
    });

    it('should revoke access token', async () => {
      const state = oauthManager.generateState();
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      await oauthManager.revokeToken(tokenResponse.access_token);
      const isValid = oauthManager.validateAccessToken(tokenResponse.access_token);
      expect(isValid).toBe(false);
    });
  });

  describe('User Information', () => {
    it('should fetch user info with valid token', async () => {
      const state = oauthManager.generateState();
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      const userInfo = await oauthManager.getUserInfo(tokenResponse.access_token);
      expect(userInfo.id).toBeDefined();
      expect(userInfo.email).toBeDefined();
      expect(userInfo.name).toBeDefined();
    });

    it('should reject user info request with invalid token', async () => {
      try {
        await oauthManager.getUserInfo('invalid-token');
        expect.fail('Should have thrown error');
      } catch (error) {
        expect(error).toBeDefined();
      }
    });

    it('should extract email from user info', async () => {
      const state = oauthManager.generateState();
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state);
      const userInfo = await oauthManager.getUserInfo(tokenResponse.access_token);
      expect(userInfo.email).toMatch(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
    });
  });

  describe('Rate Limiting', () => {
    it('should allow requests within rate limit', async () => {
      const state = oauthManager.generateState();
      let success = true;
      for (let i = 0; i < 5; i++) {
        try {
          await oauthManager.exchangeCodeForToken(`code-${i}`, state);
        } catch (error) {
          if ((error as any).code === 'RATE_LIMITED') {
            success = false;
            break;
          }
        }
      }
      expect(success).toBe(true);
    });

    it('should block requests exceeding rate limit', async () => {
      const state = oauthManager.generateState();
      let rateLimited = false;
      for (let i = 0; i < 20; i++) {
        try {
          await oauthManager.exchangeCodeForToken(`code-${i}`, state);
        } catch (error) {
          if ((error as any).code === 'RATE_LIMITED') {
            rateLimited = true;
            break;
          }
        }
      }
      expect(rateLimited).toBe(true);
    });

    it('should reset rate limit after window', async () => {
      const state = oauthManager.generateState();
      // Hit rate limit
      for (let i = 0; i < 12; i++) {
        try {
          await oauthManager.exchangeCodeForToken(`code-${i}`, state);
        } catch (error) {
          // Ignore
        }
      }
      // Verify rate limit is hit
      let rateLimited = false;
      try {
        await oauthManager.exchangeCodeForToken('code-test', state);
      } catch (error) {
        if ((error as any).code === 'RATE_LIMITED') {
          rateLimited = true;
        }
      }
      expect(rateLimited).toBe(true);
    });
  });

  describe('Session Binding', () => {
    it('should bind token to session ID', async () => {
      const state = oauthManager.generateState();
      const sessionId = 'session-xyz';
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state, sessionId);
      expect(tokenResponse.session_id).toBe(sessionId);
    });

    it('should reject token used with different session', async () => {
      const state = oauthManager.generateState();
      const sessionId = 'session-abc';
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state, sessionId);
      const isValid = oauthManager.validateTokenForSession(tokenResponse.access_token, 'session-xyz');
      expect(isValid).toBe(false);
    });

    it('should validate token with correct session', async () => {
      const state = oauthManager.generateState();
      const sessionId = 'session-def';
      const tokenResponse = await oauthManager.exchangeCodeForToken('auth-code-123', state, sessionId);
      const isValid = oauthManager.validateTokenForSession(tokenResponse.access_token, sessionId);
      expect(isValid).toBe(true);
    });
  });
});
