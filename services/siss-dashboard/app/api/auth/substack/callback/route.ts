import { NextRequest, NextResponse } from 'next/server';
import { SubstackAuthenticator } from '@/lib/services/substack-authenticator';
import { creatorService } from '@/lib/services/creator.service';
import { referralService } from '@/lib/services/referral.service';
import { emailCampaignService } from '@/lib/services/email-campaign.service';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');

    // Handle OAuth errors
    if (error) {
      return NextResponse.json(
        { error: `OAuth error: ${error}` },
        { status: 400 }
      );
    }

    if (!code) {
      return NextResponse.json(
        { error: 'Missing authorization code' },
        { status: 400 }
      );
    }

    // Exchange code for access token
    const authenticator = new SubstackAuthenticator();
    const tokenResponse = await authenticator.exchangeCodeForToken(code);

    // Get user profile
    const profile = await authenticator.getUserProfile(tokenResponse.access_token);

    // Create or update creator
    let creator;
    try {
      creator = await creatorService.createCreator({
        name: profile.name,
        email: profile.email,
        wallet: `0x${profile.id.padEnd(40, '0')}`, // Generate placeholder wallet from Substack ID
        stripe_customer_id: `substack_${profile.id}`
      });
    } catch (err: any) {
      if (err.message === 'Email already registered') {
        // Creator already exists, just log them in
        const existing = await creatorService.getAllCreators(1, 0);
        creator = existing.find((c: any) => c.email === profile.email);
      } else {
        throw err;
      }
    }

    // Start email campaign for new creator
    try {
      await emailCampaignService.startCampaign(creator.id);
    } catch (err: any) {
      console.error('Failed to start email campaign:', err.message);
      // Don't fail the OAuth flow if email campaign fails
    }

    // Handle referral if included in state
    try {
      const stateData = state ? JSON.parse(Buffer.from(state, 'base64').toString()) : null;
      if (stateData?.referrer_id) {
        await referralService.createReferral({
          referrer_id: stateData.referrer_id,
          referred_creator_id: creator.id,
          commission_tier: stateData.tier || 'tier_1',
          amount: 0
        });
      }
    } catch (err: any) {
      console.error('Failed to process referral:', err.message);
      // Don't fail the OAuth flow if referral fails
    }

    // Return success with creator data
    return NextResponse.json(
      {
        success: true,
        creator: {
          id: creator.id,
          name: creator.name,
          email: creator.email
        },
        access_token: tokenResponse.access_token,
        expires_in: tokenResponse.expires_in
      },
      { status: 200 }
    );
  } catch (error: any) {
    console.error('Substack OAuth callback error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to process Substack OAuth callback' },
      { status: 500 }
    );
  }
}
