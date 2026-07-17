import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SubstackAuthenticator } from '@/lib/services/substack-authenticator';

describe('test_substack_oauth_extension', () => {
  let authenticator: SubstackAuthenticator;

  beforeEach(() => {
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

  it('should include state parameter in authorization URL', () => {
    const authUrl = authenticator.getAuthorizationUrl('custom-state');
    expect(authUrl).toContain('state=custom-state');
  });

  it('should exchange authorization code for access token', async () => {
    const mockTokenResponse = {
      access_token: 'test-access-token',
      token_type: 'Bearer',
      expires_in: 3600,
      refresh_token: 'test-refresh-token'
    };

    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockTokenResponse),
        ok: true
      } as any)
    );

    const result = await authenticator.exchangeCodeForToken('test-auth-code');
    expect(result.access_token).toBe('test-access-token');
    expect(result.refresh_token).toBe('test-refresh-token');
    expect(result.expires_in).toBe(3600);
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
    expect(profile.publication_name).toBe('Test Publication');
  });

  it('should handle OAuth errors gracefully', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ error: 'invalid_grant' }),
        ok: false,
        status: 400
      } as any)
    );

    await expect(
      authenticator.exchangeCodeForToken('invalid-code')
    ).rejects.toThrow('Failed to exchange code');
  });

  it('should refresh access token', async () => {
    const mockTokenResponse = {
      access_token: 'new-access-token',
      token_type: 'Bearer',
      expires_in: 3600
    };

    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockTokenResponse),
        ok: true
      } as any)
    );

    const result = await authenticator.refreshAccessToken('old-refresh-token');
    expect(result.access_token).toBe('new-access-token');
  });

  it('should validate token successfully', async () => {
    const mockProfile = {
      id: 'user-123',
      name: 'Test',
      email: 'test@example.com',
      publication_name: 'Test Pub',
      subscriber_count: 100
    };

    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockProfile),
        ok: true
      } as any)
    );

    const isValid = await authenticator.validateToken('valid-token');
    expect(isValid).toBe(true);
  });

  it('should return false for invalid token', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ error: 'invalid_token' }),
        ok: false
      } as any)
    );

    const isValid = await authenticator.validateToken('invalid-token');
    expect(isValid).toBe(false);
  });
});
