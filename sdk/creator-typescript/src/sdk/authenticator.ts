/**
 * Substack OAuth2 Authenticator
 * Handles OAuth2 authentication flow with Substack
 */

import {
  SubstackAuthConfig,
  OAuth2Token,
  SubstackUserProfile,
} from './types';

const SUBSTACK_OAUTH_ENDPOINT = 'https://substack.com/oauth/authorize';
const SUBSTACK_TOKEN_ENDPOINT = 'https://substack.com/oauth/token';
const SUBSTACK_USER_ENDPOINT = 'https://substack.com/api/v1/user';

export class SubstackAuthenticator {
  private config: SubstackAuthConfig;
  private currentToken?: OAuth2Token;

  constructor(config: SubstackAuthConfig) {
    if (!config.clientId || !config.clientSecret || !config.redirectUri) {
      throw new Error(
        'Invalid Substack auth config: clientId, clientSecret, and redirectUri are required'
      );
    }
    this.config = config;
  }

  /**
   * Generate OAuth2 authorization URL for user login
   * @returns authorization URL string
   */
  getAuthorizationUrl(): string {
    const params = new URLSearchParams({
      client_id: this.config.clientId,
      response_type: 'code',
      scope: 'user:email',
      redirect_uri: this.config.redirectUri,
    });

    return `${SUBSTACK_OAUTH_ENDPOINT}?${params.toString()}`;
  }

  /**
   * Exchange authorization code for access token
   * @param code Authorization code from OAuth callback
   * @returns OAuth2 token object
   */
  async exchangeCodeForToken(code: string): Promise<OAuth2Token> {
    if (!code) {
      throw new Error('Authorization code is required');
    }

    const body = new URLSearchParams({
      client_id: this.config.clientId,
      client_secret: this.config.clientSecret,
      code: code,
      grant_type: 'authorization_code',
      redirect_uri: this.config.redirectUri,
    });

    const response = await fetch(SUBSTACK_TOKEN_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });

    if (!response.ok) {
      throw new Error(
        `Failed to exchange code for token: ${response.statusText}`
      );
    }

    const token = (await response.json()) as OAuth2Token;
    this.currentToken = token;
    return token;
  }

  /**
   * Fetch authenticated user profile from Substack
   * @param accessToken OAuth2 access token
   * @returns Substack user profile
   */
  async getUserProfile(accessToken: string): Promise<SubstackUserProfile> {
    if (!accessToken) {
      throw new Error('Access token is required');
    }

    const response = await fetch(SUBSTACK_USER_ENDPOINT, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch user profile: ${response.statusText}`);
    }

    const profile = (await response.json()) as SubstackUserProfile;
    return profile;
  }

  /**
   * Refresh access token using refresh token
   * @param refreshToken Refresh token from previous OAuth flow
   * @returns New OAuth2 token object
   */
  async refreshAccessToken(refreshToken: string): Promise<OAuth2Token> {
    if (!refreshToken) {
      throw new Error('Refresh token is required');
    }

    const body = new URLSearchParams({
      client_id: this.config.clientId,
      client_secret: this.config.clientSecret,
      refresh_token: refreshToken,
      grant_type: 'refresh_token',
    });

    const response = await fetch(SUBSTACK_TOKEN_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });

    if (!response.ok) {
      throw new Error(
        `Failed to refresh access token: ${response.statusText}`
      );
    }

    const token = (await response.json()) as OAuth2Token;
    this.currentToken = token;
    return token;
  }

  /**
   * Get current cached token
   * @returns Current OAuth2 token or undefined
   */
  getCurrentToken(): OAuth2Token | undefined {
    return this.currentToken;
  }

  /**
   * Check if current token is expired
   * @returns true if token is expired
   */
  isTokenExpired(): boolean {
    if (!this.currentToken) {
      return true;
    }
    const expirationTime =
      new Date().getTime() + this.currentToken.expires_in * 1000;
    return new Date().getTime() > expirationTime;
  }
}
