import { NextRequest, NextResponse } from 'next/server';
import { emailCampaignService } from '@/lib/services/email-campaign.service';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    if (!body.creator_id) {
      return NextResponse.json(
        { error: 'Missing creator_id field' },
        { status: 400 }
      );
    }

    const result = await emailCampaignService.startCampaign(body.creator_id);
    return NextResponse.json(result, { status: 201 });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to start email campaign' },
      { status: 500 }
    );
  }
}
