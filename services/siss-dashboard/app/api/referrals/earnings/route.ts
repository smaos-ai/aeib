import { NextRequest, NextResponse } from 'next/server';
import { referralService } from '@/lib/services/referral.service';

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

    const earnings = await referralService.getReferralEarnings(referrerId);
    return NextResponse.json(earnings, { status: 200 });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch referral earnings' },
      { status: 500 }
    );
  }
}
