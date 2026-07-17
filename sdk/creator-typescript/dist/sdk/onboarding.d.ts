/**
 * Creator Onboarding Module
 * Handles creator profile validation and registration
 */
import { OnboardingProfile, ValidationResult, OnboardingResponse, RoyaltyPreference } from './types';
export declare class CreatorOnboarding {
    /**
     * Validate creator onboarding profile
     * @param profile Creator onboarding profile to validate
     * @returns ValidationResult with valid flag and error messages
     */
    validateProfile(profile: OnboardingProfile): ValidationResult;
    /**
     * Register validated creator profile
     * @param profile Creator onboarding profile to register
     * @returns OnboardingResponse with creator_id and status
     */
    registerProfile(profile: OnboardingProfile): Promise<OnboardingResponse>;
    /**
     * Get valid royalty preference options
     * @returns Array of valid royalty preferences
     */
    getValidRoyaltyPreferences(): RoyaltyPreference[];
}
//# sourceMappingURL=onboarding.d.ts.map