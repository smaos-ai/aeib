/**
 * Creator SDK Type Definitions
 * Defines interfaces for Substack OAuth, creator onboarding, and Axiom Protocol integration
 */
export interface SubstackAuthConfig {
    clientId: string;
    clientSecret: string;
    redirectUri: string;
}
export interface OAuth2Token {
    access_token: string;
    token_type: string;
    expires_in: number;
    refresh_token?: string;
}
export interface SubstackUserProfile {
    id: string;
    email: string;
    name: string;
    publication_name?: string;
    profile_image_url?: string;
}
export type RoyaltyPreference = 'daily' | 'weekly' | 'monthly' | 'quarterly';
export interface OnboardingProfile {
    name: string;
    email: string;
    wallet: string;
    royaltyPreference: RoyaltyPreference;
    substackUserId: string;
}
export interface ValidationResult {
    valid: boolean;
    errors: string[];
}
export interface OnboardingResponse {
    creator_id: string;
    status: string;
    timestamp: string;
}
export interface RoyaltySettlement {
    creator_id: string;
    amount_cents: number;
    period: string;
    status: string;
    transaction_hash: string;
}
export interface SettlementHistoryResponse {
    settlements: RoyaltySettlement[];
    total: number;
    page: number;
}
export interface SettlementQueryOptions {
    page: number;
    limit: number;
}
export interface RoyaltyRate {
    base_rate: number;
    adjusted_rate: number;
    adjustments: Array<{
        type: string;
        value: number;
    }>;
    effective_timestamp: string;
}
export interface MicroRoyaltyClientConfig {
    baseUrl: string;
    apiKey: string;
    timeout?: number;
}
export interface CreatorSDKConfig {
    substackClientId: string;
    substackClientSecret: string;
    axiomBaseUrl: string;
    axiomApiKey: string;
    timeout?: number;
}
//# sourceMappingURL=types.d.ts.map