import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { SubstackAuthenticator } from '@/lib/services/substack-authenticator';

describe('test_substack_oauth_extension', () => {
  let authenticator: SubstackAuthenticator;

  beforeAll(() => {
    process.env.SUBSTACK_CLIENT_ID = 'test-client-id';
    process.env.SUBSTACK_CLIENT_SECRET = 'test-client-secret';
    process.env.SUBSTACK_REDIRECT_URI = 'http://localhost:3000/api/auth/substack/callback';
    authenticator = new SubstackAuthenticator();
  });

  it('should generate OAuth authorization URL', () => {
    const authUrl = authenticator.getAuthorizationUrl();
    expect(authUrl).toContain('https://substack.com/oauth/authorize');
    expect(authUrl).toContain('client_id=test-client-id');
    expect(authUrl).toContain('redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fapi%2Fauth%2Fsubstack%2Fcallback');
    expect(authUrl).toContain('response_type=code');
  });

  it('should exchange authorization code for access token', async () => {
    const mockTokenResponse = {
      access_token: 'test-access-token',
      token_type: 'Bearer',
      expires_in: 3600,
      refresh_token: 'test-refresh-token'
    };

    // Mock the fetch call
    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockTokenResponse),
        ok: true
      } as any)
    );

    const result = await authenticator.exchangeCodeForToken('test-auth-code');
    expect(result.access_token).toBe('test-access-token');
    expect(result.refresh_token).toBe('test-refresh-token');
  });

  it('should retrieve Substack user profile using access token', async () => {
    const mockProfile = {
      id: 'substack-user-123',
      name: 'Test Creator',
      email: 'creator@substack.com',
      publication_name: 'Test Publication',
      subscriber_count: 1000
    };

    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockProfile),
        ok: true
      } as any)
    );

    const profile = await authenticator.getUserProfile('test-access-token');
    expect(profile.id).toBe('substack-user-123');
    expect(profile.email).toBe('creator@substack.com');
    expect(profile.name).toBe('Test Creator');
  });

  it('should handle OAuth errors gracefully', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ error: 'invalid_grant' }),
        ok: false,
        status: 400
      } as any)
    );

    expect(async () => {
      await authenticator.exchangeCodeForToken('invalid-code');
    }).rejects.toThrow();
  });
});
