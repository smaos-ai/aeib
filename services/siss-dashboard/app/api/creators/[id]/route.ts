import { NextRequest, NextResponse } from 'next/server';
import { creatorService } from '@/lib/services/creator.service';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;

    const creator = await creatorService.getCreator(id);

    return NextResponse.json(creator, { status: 200 });
  } catch (error: any) {
    if (error.message === 'Creator not found') {
      return NextResponse.json(
        { error: 'Creator not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to fetch creator' },
      { status: 500 }
    );
  }
}
