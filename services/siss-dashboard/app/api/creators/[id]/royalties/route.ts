import { NextRequest, NextResponse } from 'next/server';
import { creatorService } from '@/lib/services/creator.service';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;

    // Verify creator exists
    await creatorService.getCreator(id);

    const royalties = await creatorService.getCreatorRoyalties(id);

    return NextResponse.json(royalties, { status: 200 });
  } catch (error: any) {
    if (error.message === 'Creator not found') {
      return NextResponse.json(
        { error: 'Creator not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to fetch royalties' },
      { status: 500 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;
    const body = await request.json();

    // Verify creator exists
    await creatorService.getCreator(id);

    // Validate required fields
    if (!body.amount || !body.timestamp || !body.status) {
      return NextResponse.json(
        { error: 'Missing required fields: amount, timestamp, status' },
        { status: 400 }
      );
    }

    const royalty = await creatorService.recordRoyalty({
      creator_id: id,
      amount: body.amount,
      fee_percentage: body.fee_percentage || 5,
      timestamp: new Date(body.timestamp),
      status: body.status,
      webhook_event_id: body.webhook_event_id
    });

    return NextResponse.json(royalty, { status: 201 });
  } catch (error: any) {
    if (error.message === 'Creator not found') {
      return NextResponse.json(
        { error: 'Creator not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to record royalty' },
      { status: 500 }
    );
  }
}
