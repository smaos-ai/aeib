"use strict";
/**
 * Creator SDK
 * Main SDK class that integrates Substack authentication, creator onboarding,
 * and Axiom Protocol (AP2) royalty settlement
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.CreatorSDK = void 0;
const authenticator_1 = require("./authenticator");
const onboarding_1 = require("./onboarding");
const royalty_client_1 = require("./royalty-client");
class CreatorSDK {
    constructor(config) {
        if (!config.substackClientId ||
            !config.substackClientSecret ||
            !config.axiomBaseUrl ||
            !config.axiomApiKey) {
            throw new Error('Invalid SDK configuration: all required fields must be provided');
        }
        // Initialize Substack authenticator
        this.authenticator = new authenticator_1.SubstackAuthenticator({
            clientId: config.substackClientId,
            clientSecret: config.substackClientSecret,
            redirectUri: config.axiomBaseUrl, // Use axiom base URL as default redirect
        });
        // Initialize creator onboarding
        this.onboarding = new onboarding_1.CreatorOnboarding();
        // Initialize royalty client
        this.royalties = new royalty_client_1.MicroRoyaltyClient({
            baseUrl: config.axiomBaseUrl,
            apiKey: config.axiomApiKey,
            timeout: config.timeout || 5000,
        });
    }
}
exports.CreatorSDK = CreatorSDK;
//# sourceMappingURL=creator-sdk.js.map