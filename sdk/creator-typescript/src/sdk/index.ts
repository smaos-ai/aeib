/**
 * Creator SDK - Public API Surface
 * Exports all SDK components for creator onboarding and AP2 royalty settlement
 */

// Type exports
export type {
  SubstackAuthConfig,
  OAuth2Token,
  SubstackUserProfile,
  RoyaltyPreference,
  OnboardingProfile,
  ValidationResult,
  OnboardingResponse,
  RoyaltySettlement,
  SettlementHistoryResponse,
  SettlementQueryOptions,
  RoyaltyRate,
  MicroRoyaltyClientConfig,
  CreatorSDKConfig,
} from './types';

// Class exports
export { SubstackAuthenticator } from './authenticator';
export { CreatorOnboarding } from './onboarding';
export { MicroRoyaltyClient } from './royalty-client';
export { CreatorSDK } from './creator-sdk';
