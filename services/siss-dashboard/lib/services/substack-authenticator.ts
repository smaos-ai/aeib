export interface SubstackTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
}

export interface SubstackProfile {
  id: string;
  name: string;
  email: string;
  publication_name: string;
  subscriber_count: number;
}

export class SubstackAuthenticator {
  private clientId: string;
  private clientSecret: string;
  private redirectUri: string;
  private authBaseUrl = 'https://substack.com/oauth/authorize';
  private tokenUrl = 'https://substack.com/api/v1/oauth/token';
  private profileUrl = 'https://substack.com/api/v1/user/profile';

  constructor() {
    this.clientId = process.env.SUBSTACK_CLIENT_ID || '';
    this.clientSecret = process.env.SUBSTACK_CLIENT_SECRET || '';
    this.redirectUri = process.env.SUBSTACK_REDIRECT_URI || '';

    if (!this.clientId || !this.clientSecret || !this.redirectUri) {
      throw new Error('Missing Substack OAuth environment variables');
    }
  }

  /**
   * Generate OAuth authorization URL for Substack
   */
  getAuthorizationUrl(state?: string): string {
    const params = new URLSearchParams({
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      response_type: 'code',
      scope: 'publications.read publications.manage publications.create',
      state: state || Math.random().toString(36).substring(7)
    });

    return `${this.authBaseUrl}?${params.toString()}`;
  }

  /**
   * Exchange authorization code for access token
   */
  async exchangeCodeForToken(code: string): Promise<SubstackTokenResponse> {
    const response = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        client_id: this.clientId,
        client_secret: this.clientSecret,
        redirect_uri: this.redirectUri
      }).toString()
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Failed to exchange code: ${error.error || 'Unknown error'}`);
    }

    return response.json();
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshAccessToken(refreshToken: string): Promise<SubstackTokenResponse> {
    const response = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refreshToken,
        client_id: this.clientId,
        client_secret: this.clientSecret
      }).toString()
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Failed to refresh token: ${error.error || 'Unknown error'}`);
    }

    return response.json();
  }

  /**
   * Get Substack user profile using access token
   */
  async getUserProfile(accessToken: string): Promise<SubstackProfile> {
    const response = await fetch(this.profileUrl, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user profile from Substack');
    }

    return response.json();
  }

  /**
   * Validate access token
   */
  async validateToken(accessToken: string): Promise<boolean> {
    try {
      await this.getUserProfile(accessToken);
      return true;
    } catch {
      return false;
    }
  }
}
