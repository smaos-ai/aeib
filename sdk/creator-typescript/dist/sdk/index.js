"use strict";
/**
 * Creator SDK - Public API Surface
 * Exports all SDK components for creator onboarding and AP2 royalty settlement
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.CreatorSDK = exports.MicroRoyaltyClient = exports.CreatorOnboarding = exports.SubstackAuthenticator = void 0;
// Class exports
var authenticator_1 = require("./authenticator");
Object.defineProperty(exports, "SubstackAuthenticator", { enumerable: true, get: function () { return authenticator_1.SubstackAuthenticator; } });
var onboarding_1 = require("./onboarding");
Object.defineProperty(exports, "CreatorOnboarding", { enumerable: true, get: function () { return onboarding_1.CreatorOnboarding; } });
var royalty_client_1 = require("./royalty-client");
Object.defineProperty(exports, "MicroRoyaltyClient", { enumerable: true, get: function () { return royalty_client_1.MicroRoyaltyClient; } });
var creator_sdk_1 = require("./creator-sdk");
Object.defineProperty(exports, "CreatorSDK", { enumerable: true, get: function () { return creator_sdk_1.CreatorSDK; } });
//# sourceMappingURL=index.js.map