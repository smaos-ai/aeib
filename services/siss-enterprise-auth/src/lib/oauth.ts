import * as crypto from 'crypto';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  session_id?: string;
}

interface UserInfo {
  id: string;
  email: string;
  name: string;
  picture?: string;
}

interface RateLimitEntry {
  count: number;
  resetTime: number;
}

export class OAuthManager {
  private clientId: string;
  private clientSecret: string;
  private redirectUri: string;
  private validStates: Map<string, number> = new Map();
  private tokenSessions: Map<string, string> = new Map(); // token -> sessionId
  private revokedTokens: Set<string> = new Set();
  private rateLimits: Map<string, RateLimitEntry> = new Map();
  private readonly RATE_LIMIT_WINDOW = 60000; // 1 minute
  private readonly RATE_LIMIT_MAX = 10; // 10 requests per window

  constructor(clientId: string, clientSecret: string, redirectUri: string) {
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.redirectUri = redirectUri;
  }

  generateState(): string {
    const state = crypto.randomBytes(32).toString('hex');
    // Store state with 10-minute expiry
    this.validStates.set(state, Date.now() + 10 * 60 * 1000);
    return state;
  }

  validateState(state: string): boolean {
    if (!this.validStates.has(state)) {
      return false;
    }
    const expiry = this.validStates.get(state)!;
    if (Date.now() > expiry) {
      this.validStates.delete(state);
      return false;
    }
    return true;
  }

  generateAuthorizationURL(state: string, scope: string = 'openid profile email'): string {
    const params = new URLSearchParams({
      client_id: this.clientId,
      response_type: 'code',
      redirect_uri: this.redirectUri,
      state,
      scope
    });
    return `https://oauth.example.com/authorize?${params.toString()}`;
  }

  async exchangeCodeForToken(
    code: string,
    state: string,
    sessionId?: string
  ): Promise<TokenResponse> {
    // Check rate limit
    const now = Date.now();
    const clientIP = 'default'; // In real implementation, use actual IP
    const rateLimitKey = `${clientIP}:token-exchange`;

    if (this.rateLimits.has(rateLimitKey)) {
      const entry = this.rateLimits.get(rateLimitKey)!;
      if (now < entry.resetTime) {
        if (entry.count >= this.RATE_LIMIT_MAX) {
          const error = new Error('Rate limit exceeded');
          (error as any).code = 'RATE_LIMITED';
          throw error;
        }
        entry.count++;
      } else {
        // Window expired, reset
        this.rateLimits.set(rateLimitKey, { count: 1, resetTime: now + this.RATE_LIMIT_WINDOW });
      }
    } else {
      // First request
      this.rateLimits.set(rateLimitKey, { count: 1, resetTime: now + this.RATE_LIMIT_WINDOW });
    }

    if (!this.validateState(state)) {
      throw new Error('Invalid or expired state');
    }

    // Generate tokens (simulated)
    const accessToken = crypto.randomBytes(32).toString('hex');
    const refreshToken = crypto.randomBytes(32).toString('hex');

    // Store session binding if provided
    if (sessionId) {
      this.tokenSessions.set(accessToken, sessionId);
    }

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'Bearer',
      expires_in: 3600,
      session_id: sessionId
    };
  }

  validateAccessToken(token: string): boolean {
    if (this.revokedTokens.has(token)) {
      return false;
    }
    // In real implementation, verify JWT signature
    return token && typeof token === 'string' && token.length > 0;
  }

  async refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
    if (!refreshToken || typeof refreshToken !== 'string') {
      throw new Error('Invalid refresh token');
    }

    // Generate new access token
    const newAccessToken = crypto.randomBytes(32).toString('hex');
    const newRefreshToken = crypto.randomBytes(32).toString('hex');

    return {
      access_token: newAccessToken,
      refresh_token: newRefreshToken,
      token_type: 'Bearer',
      expires_in: 3600
    };
  }

  async revokeToken(token: string): Promise<void> {
    this.revokedTokens.add(token);
    this.tokenSessions.delete(token);
  }

  async getUserInfo(accessToken: string): Promise<UserInfo> {
    if (!this.validateAccessToken(accessToken)) {
      throw new Error('Invalid access token');
    }

    // Simulated user info response
    return {
      id: `user-${crypto.randomBytes(8).toString('hex')}`,
      email: `user+${Date.now()}@example.com`,
      name: 'Test User',
      picture: 'https://example.com/photo.jpg'
    };
  }

  validateTokenForSession(token: string, sessionId: string): boolean {
    const boundSession = this.tokenSessions.get(token);
    return boundSession === sessionId;
  }
}
