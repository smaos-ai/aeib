import { NextRequest, NextResponse } from 'next/server';
import { creatorService } from '@/lib/services/creator.service';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string; royaltyId: string } }
) {
  try {
    const { id, royaltyId } = params;

    const royalty = await creatorService.getRoyalty(id, royaltyId);

    return NextResponse.json(royalty, { status: 200 });
  } catch (error: any) {
    if (error.message === 'Royalty not found') {
      return NextResponse.json(
        { error: 'Royalty not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to fetch royalty' },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string; royaltyId: string } }
) {
  try {
    const { id, royaltyId } = params;
    const body = await request.json();

    if (!body.status) {
      return NextResponse.json(
        { error: 'Missing required field: status' },
        { status: 400 }
      );
    }

    const royalty = await creatorService.updateRoyaltyStatus(id, royaltyId, body.status);

    return NextResponse.json(royalty, { status: 200 });
  } catch (error: any) {
    if (error.message === 'Royalty not found') {
      return NextResponse.json(
        { error: 'Royalty not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to update royalty' },
      { status: 500 }
    );
  }
}
