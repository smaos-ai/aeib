/**
 * Creator Onboarding Module
 * Handles creator profile validation and registration
 */

import {
  OnboardingProfile,
  ValidationResult,
  OnboardingResponse,
  RoyaltyPreference,
} from './types';

const VALID_ROYALTY_PREFERENCES: RoyaltyPreference[] = [
  'daily',
  'weekly',
  'monthly',
  'quarterly',
];

// Email regex pattern for basic validation
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Ethereum address regex (42 hex characters including 0x prefix)
const ETH_ADDRESS_REGEX = /^0x[a-fA-F0-9]{40}$/;

export class CreatorOnboarding {
  /**
   * Validate creator onboarding profile
   * @param profile Creator onboarding profile to validate
   * @returns ValidationResult with valid flag and error messages
   */
  validateProfile(profile: OnboardingProfile): ValidationResult {
    const errors: string[] = [];

    // Validate name
    if (!profile.name || profile.name.trim().length === 0) {
      errors.push('name is required and cannot be empty');
    } else if (profile.name.length < 2) {
      errors.push('name must be at least 2 characters');
    } else if (profile.name.length > 256) {
      errors.push('name must not exceed 256 characters');
    }

    // Validate email
    if (!profile.email || profile.email.trim().length === 0) {
      errors.push('email is required');
    } else if (!EMAIL_REGEX.test(profile.email)) {
      errors.push('email format is invalid');
    }

    // Validate wallet address
    if (!profile.wallet || profile.wallet.trim().length === 0) {
      errors.push('wallet address is required');
    } else if (!ETH_ADDRESS_REGEX.test(profile.wallet)) {
      errors.push('wallet must be a valid Ethereum address (0x + 40 hex chars)');
    }

    // Validate royalty preference
    if (
      !profile.royaltyPreference ||
      !VALID_ROYALTY_PREFERENCES.includes(profile.royaltyPreference)
    ) {
      errors.push(
        `royalty preference must be one of: ${VALID_ROYALTY_PREFERENCES.join(', ')}`
      );
    }

    // Validate substackUserId
    if (!profile.substackUserId || profile.substackUserId.trim().length === 0) {
      errors.push('substackUserId is required');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Register validated creator profile
   * @param profile Creator onboarding profile to register
   * @returns OnboardingResponse with creator_id and status
   */
  async registerProfile(profile: OnboardingProfile): Promise<OnboardingResponse> {
    // Validate before registering
    const validation = this.validateProfile(profile);
    if (!validation.valid) {
      throw new Error(
        `Profile validation failed: ${validation.errors.join('; ')}`
      );
    }

    // In a real implementation, this would call an API endpoint
    // For now, we'll simulate the API call
    const payload = {
      name: profile.name,
      email: profile.email,
      wallet: profile.wallet.toLowerCase(),
      royalty_preference: profile.royaltyPreference,
      substack_user_id: profile.substackUserId,
    };

    const response = await fetch(
      'https://api.axiom.network/v1/creators/onboard',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(
        `Failed to register profile: ${response.statusText}`
      );
    }

    const result = (await response.json()) as OnboardingResponse;
    return result;
  }

  /**
   * Get valid royalty preference options
   * @returns Array of valid royalty preferences
   */
  getValidRoyaltyPreferences(): RoyaltyPreference[] {
    return [...VALID_ROYALTY_PREFERENCES];
  }
}
