/**
 * Substack OAuth2 Authenticator
 * Handles OAuth2 authentication flow with Substack
 */
import { SubstackAuthConfig, OAuth2Token, SubstackUserProfile } from './types';
export declare class SubstackAuthenticator {
    private config;
    private currentToken?;
    constructor(config: SubstackAuthConfig);
    /**
     * Generate OAuth2 authorization URL for user login
     * @returns authorization URL string
     */
    getAuthorizationUrl(): string;
    /**
     * Exchange authorization code for access token
     * @param code Authorization code from OAuth callback
     * @returns OAuth2 token object
     */
    exchangeCodeForToken(code: string): Promise<OAuth2Token>;
    /**
     * Fetch authenticated user profile from Substack
     * @param accessToken OAuth2 access token
     * @returns Substack user profile
     */
    getUserProfile(accessToken: string): Promise<SubstackUserProfile>;
    /**
     * Refresh access token using refresh token
     * @param refreshToken Refresh token from previous OAuth flow
     * @returns New OAuth2 token object
     */
    refreshAccessToken(refreshToken: string): Promise<OAuth2Token>;
    /**
     * Get current cached token
     * @returns Current OAuth2 token or undefined
     */
    getCurrentToken(): OAuth2Token | undefined;
    /**
     * Check if current token is expired
     * @returns true if token is expired
     */
    isTokenExpired(): boolean;
}
//# sourceMappingURL=authenticator.d.ts.map