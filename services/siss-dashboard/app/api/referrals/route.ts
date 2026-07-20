import { NextRequest, NextResponse } from 'next/server';
import { referralService } from '@/lib/services/referral.service';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate required fields
    if (!body.referrer_id || !body.referred_creator_id || !body.commission_tier) {
      return NextResponse.json(
        { error: 'Missing required fields: referrer_id, referred_creator_id, commission_tier' },
        { status: 400 }
      );
    }

    const referral = await referralService.createReferral({
      referrer_id: body.referrer_id,
      referred_creator_id: body.referred_creator_id,
      commission_tier: body.commission_tier,
      amount: body.amount || 0
    });

    return NextResponse.json(referral, { status: 201 });
  } catch (error: any) {
    if (error.message === 'Cannot refer yourself') {
      return NextResponse.json(
        { error: error.message },
        { status: 400 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to create referral' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const referrerId = searchParams.get('referrer_id');

    if (!referrerId) {
      return NextResponse.json(
        { error: 'Missing referrer_id parameter' },
        { status: 400 }
      );
    }

    const referrals = await referralService.getReferrals(referrerId);
    return NextResponse.json(referrals, { status: 200 });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch referrals' },
      { status: 500 }
    );
  }
}
