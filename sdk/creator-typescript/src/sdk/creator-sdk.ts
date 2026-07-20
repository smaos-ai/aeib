/**
 * Creator SDK
 * Main SDK class that integrates Substack authentication, creator onboarding,
 * and Axiom Protocol (AP2) royalty settlement
 */

import { SubstackAuthenticator } from './authenticator';
import { CreatorOnboarding } from './onboarding';
import { MicroRoyaltyClient } from './royalty-client';
import { CreatorSDKConfig } from './types';

export class CreatorSDK {
  public authenticator: SubstackAuthenticator;
  public onboarding: CreatorOnboarding;
  public royalties: MicroRoyaltyClient;

  constructor(config: CreatorSDKConfig) {
    if (
      !config.substackClientId ||
      !config.substackClientSecret ||
      !config.axiomBaseUrl ||
      !config.axiomApiKey
    ) {
      throw new Error(
        'Invalid SDK configuration: all required fields must be provided'
      );
    }

    // Initialize Substack authenticator
    this.authenticator = new SubstackAuthenticator({
      clientId: config.substackClientId,
      clientSecret: config.substackClientSecret,
      redirectUri: config.axiomBaseUrl, // Use axiom base URL as default redirect
    });

    // Initialize creator onboarding
    this.onboarding = new CreatorOnboarding();

    // Initialize royalty client
    this.royalties = new MicroRoyaltyClient({
      baseUrl: config.axiomBaseUrl,
      apiKey: config.axiomApiKey,
      timeout: config.timeout || 5000,
    });
  }
}
