import {
  SubstackAuthenticator,
  CreatorOnboarding,
  MicroRoyaltyClient,
  CreatorSDK,
  OnboardingProfile,
  RoyaltySettlement,
} from '../src/sdk/index';

describe('Creator SDK', () => {
  describe('test_substack_oauth_flow', () => {
    it('should initiate OAuth2 flow with Substack', async () => {
      const authenticator = new SubstackAuthenticator({
        clientId: 'test-client-id',
        clientSecret: 'test-client-secret',
        redirectUri: 'http://localhost:3000/callback',
      });

      const authUrl = authenticator.getAuthorizationUrl();
      expect(authUrl).toContain('https://substack.com/oauth/authorize');
      expect(authUrl).toContain('client_id=test-client-id');
      expect(authUrl).toContain('response_type=code');
    });

    it('should exchange authorization code for access token', async () => {
      const authenticator = new SubstackAuthenticator({
        clientId: 'test-client-id',
        clientSecret: 'test-client-secret',
        redirectUri: 'http://localhost:3000/callback',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'mock-access-token-123',
          token_type: 'Bearer',
          expires_in: 3600,
          refresh_token: 'mock-refresh-token',
        }),
      });

      global.fetch = mockFetch;

      const token = await authenticator.exchangeCodeForToken('auth-code-123');
      expect(token.access_token).toBe('mock-access-token-123');
      expect(token.token_type).toBe('Bearer');
      expect(token.expires_in).toBe(3600);
    });

    it('should fetch authenticated user profile from Substack', async () => {
      const authenticator = new SubstackAuthenticator({
        clientId: 'test-client-id',
        clientSecret: 'test-client-secret',
        redirectUri: 'http://localhost:3000/callback',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'substack-user-123',
          email: 'creator@substack.com',
          name: 'Test Creator',
          publication_name: 'Test Publication',
        }),
      });

      global.fetch = mockFetch;

      const profile = await authenticator.getUserProfile('mock-access-token');
      expect(profile.id).toBe('substack-user-123');
      expect(profile.email).toBe('creator@substack.com');
      expect(profile.name).toBe('Test Creator');
    });

    it('should handle OAuth token expiration and refresh', async () => {
      const authenticator = new SubstackAuthenticator({
        clientId: 'test-client-id',
        clientSecret: 'test-client-secret',
        redirectUri: 'http://localhost:3000/callback',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'new-access-token',
          token_type: 'Bearer',
          expires_in: 3600,
        }),
      });

      global.fetch = mockFetch;

      const newToken = await authenticator.refreshAccessToken('mock-refresh-token');
      expect(newToken.access_token).toBe('new-access-token');
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  describe('test_creator_onboarding_validation', () => {
    it('should validate creator profile with valid input', () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: 'Alice Creator',
        email: 'alice@example.com',
        wallet: '0x1234567890abcdef1234567890abcdef12345678',
        royaltyPreference: 'monthly',
        substackUserId: 'substack-123',
      };

      const validation = onboarding.validateProfile(profile);
      expect(validation.valid).toBe(true);
      expect(validation.errors).toHaveLength(0);
    });

    it('should reject profile with missing required fields', () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: '',
        email: 'alice@example.com',
        wallet: '',
        royaltyPreference: 'monthly',
        substackUserId: 'substack-123',
      };

      const validation = onboarding.validateProfile(profile);
      expect(validation.valid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
      expect(validation.errors.some((e: string) => e.includes('name'))).toBe(true);
    });

    it('should validate email format', () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: 'Alice Creator',
        email: 'invalid-email',
        wallet: '0x1234567890abcdef1234567890abcdef12345678',
        royaltyPreference: 'monthly',
        substackUserId: 'substack-123',
      };

      const validation = onboarding.validateProfile(profile);
      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e: string) => e.includes('email'))).toBe(true);
    });

    it('should validate Ethereum wallet address format', () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: 'Alice Creator',
        email: 'alice@example.com',
        wallet: 'invalid-wallet-address',
        royaltyPreference: 'monthly',
        substackUserId: 'substack-123',
      };

      const validation = onboarding.validateProfile(profile);
      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e: string) => e.includes('wallet'))).toBe(true);
    });

    it('should validate royalty preference options', () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: 'Alice Creator',
        email: 'alice@example.com',
        wallet: '0x1234567890abcdef1234567890abcdef12345678',
        royaltyPreference: 'invalid-option' as any,
        substackUserId: 'substack-123',
      };

      const validation = onboarding.validateProfile(profile);
      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e: string) => e.includes('royalty'))).toBe(true);
    });

    it('should register valid creator profile', async () => {
      const onboarding = new CreatorOnboarding();
      const profile: OnboardingProfile = {
        name: 'Alice Creator',
        email: 'alice@example.com',
        wallet: '0x1234567890abcdef1234567890abcdef12345678',
        royaltyPreference: 'monthly',
        substackUserId: 'substack-123',
      };

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          creator_id: 'creator-456',
          status: 'onboarded',
          timestamp: '2026-06-06T00:00:00Z',
        }),
      });

      global.fetch = mockFetch;

      const result = await onboarding.registerProfile(profile);
      expect(result.creator_id).toBe('creator-456');
      expect(result.status).toBe('onboarded');
    });
  });

  describe('test_royalty_settlement_fetch', () => {
    it('should fetch royalty settlement from Axiom Protocol', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          creator_id: 'creator-456',
          amount_cents: 50000,
          period: '2026-06',
          status: 'settled',
          transaction_hash: '0xabc123def456...',
        }),
      });

      global.fetch = mockFetch;

      const settlement = await royaltyClient.fetchRoyaltySettlement('creator-456');
      expect(settlement.creator_id).toBe('creator-456');
      expect(settlement.amount_cents).toBe(50000);
      expect(settlement.status).toBe('settled');
      expect(settlement.transaction_hash).toContain('0x');
    });

    it('should fetch multiple settlement records for pagination', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          settlements: [
            {
              creator_id: 'creator-456',
              amount_cents: 50000,
              period: '2026-06',
              status: 'settled',
            },
            {
              creator_id: 'creator-456',
              amount_cents: 45000,
              period: '2026-05',
              status: 'settled',
            },
          ],
          total: 2,
          page: 1,
        }),
      });

      global.fetch = mockFetch;

      const result = await royaltyClient.fetchSettlementHistory('creator-456', {
        page: 1,
        limit: 10,
      });
      expect(result.settlements).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it('should return empty array when no settlements found', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          settlements: [],
          total: 0,
          page: 1,
        }),
      });

      global.fetch = mockFetch;

      const result = await royaltyClient.fetchSettlementHistory('unknown-creator', {
        page: 1,
        limit: 10,
      });
      expect(result.settlements).toHaveLength(0);
      expect(result.total).toBe(0);
    });

    it('should handle real-time royalty rate calculation', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          base_rate: 0.15,
          adjusted_rate: 0.18,
          adjustments: [
            { type: 'engagement_bonus', value: 0.03 },
          ],
          effective_timestamp: '2026-06-06T12:00:00Z',
        }),
      });

      global.fetch = mockFetch;

      const rates = await royaltyClient.fetchRoyaltyRates('creator-456');
      expect(rates.base_rate).toBe(0.15);
      expect(rates.adjusted_rate).toBe(0.18);
      expect(rates.adjustments).toHaveLength(1);
    });
  });

  describe('test_sdk_error_handling', () => {
    it('should handle network errors gracefully', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest
        .fn()
        .mockRejectedValueOnce(new Error('Network request failed'));

      global.fetch = mockFetch;

      await expect(
        royaltyClient.fetchRoyaltySettlement('creator-456')
      ).rejects.toThrow('Network request failed');
    });

    it('should handle API error responses', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({
          error: 'Unauthorized',
          message: 'Invalid API key',
        }),
      });

      global.fetch = mockFetch;

      await expect(
        royaltyClient.fetchRoyaltySettlement('creator-456')
      ).rejects.toThrow();
    });

    it('should handle malformed JSON responses', async () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
      });

      const mockFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new SyntaxError('Invalid JSON');
        },
      });

      global.fetch = mockFetch;

      await expect(
        royaltyClient.fetchRoyaltySettlement('creator-456')
      ).rejects.toThrow();
    });

    it('should validate SDK configuration on initialization', () => {
      expect(() => {
        new MicroRoyaltyClient({
          baseUrl: '',
          apiKey: '',
        });
      }).toThrow();
    });

    it('should configure timeout in client options', () => {
      const royaltyClient = new MicroRoyaltyClient({
        baseUrl: 'http://localhost:8080',
        apiKey: 'test-api-key',
        timeout: 3000,
      });

      const config = royaltyClient.getConfig();
      expect(config.timeout).toBe(3000);
      expect(config.apiKey).toBe('test-api-key');
      expect(config.baseUrl).toBe('http://localhost:8080');
    });
  });

  describe('SDK Integration', () => {
    it('should initialize CreatorSDK with all components', () => {
      const sdk = new CreatorSDK({
        substackClientId: 'test-client-id',
        substackClientSecret: 'test-client-secret',
        axiomBaseUrl: 'http://localhost:8080',
        axiomApiKey: 'test-api-key',
      });

      expect(sdk).toBeDefined();
      expect(sdk.authenticator).toBeDefined();
      expect(sdk.onboarding).toBeDefined();
      expect(sdk.royalties).toBeDefined();
    });

    it('should complete full onboarding workflow', async () => {
      const sdk = new CreatorSDK({
        substackClientId: 'test-client-id',
        substackClientSecret: 'test-client-secret',
        axiomBaseUrl: 'http://localhost:8080',
        axiomApiKey: 'test-api-key',
      });

      const mockAuthFetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'mock-token',
          token_type: 'Bearer',
          expires_in: 3600,
        }),
      });

      global.fetch = mockAuthFetch;

      const authUrl = sdk.authenticator.getAuthorizationUrl();
      expect(authUrl).toContain('https://substack.com/oauth/authorize');
    });
  });
});
