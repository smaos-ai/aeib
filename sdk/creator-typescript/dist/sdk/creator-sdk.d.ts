/**
 * Creator SDK
 * Main SDK class that integrates Substack authentication, creator onboarding,
 * and Axiom Protocol (AP2) royalty settlement
 */
import { SubstackAuthenticator } from './authenticator';
import { CreatorOnboarding } from './onboarding';
import { MicroRoyaltyClient } from './royalty-client';
import { CreatorSDKConfig } from './types';
export declare class CreatorSDK {
    authenticator: SubstackAuthenticator;
    onboarding: CreatorOnboarding;
    royalties: MicroRoyaltyClient;
    constructor(config: CreatorSDKConfig);
}
//# sourceMappingURL=creator-sdk.d.ts.map