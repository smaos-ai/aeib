import { NextRequest, NextResponse } from 'next/server';
import { emailCampaignService } from '@/lib/services/email-campaign.service';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const creatorId = searchParams.get('creator_id');

    if (!creatorId) {
      return NextResponse.json(
        { error: 'Missing creator_id parameter' },
        { status: 400 }
      );
    }

    const history = await emailCampaignService.getCampaignHistory(creatorId);
    const metrics = await emailCampaignService.getCampaignMetrics(creatorId);

    return NextResponse.json(
      { history, metrics },
      { status: 200 }
    );
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch campaign history' },
      { status: 500 }
    );
  }
}
