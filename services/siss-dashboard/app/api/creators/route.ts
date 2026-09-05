import { NextRequest, NextResponse } from 'next/server';
import { creatorService, validators } from '@/lib/services/creator.service';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate required fields
    if (!body.name || !body.email || !body.wallet || !body.stripe_customer_id) {
      return NextResponse.json(
        { error: 'Missing required fields: name, email, wallet, stripe_customer_id' },
        { status: 400 }
      );
    }

    // Validate email
    if (!validators.email(body.email)) {
      return NextResponse.json(
        { error: 'Invalid email format' },
        { status: 400 }
      );
    }

    // Validate wallet
    if (!validators.wallet(body.wallet)) {
      return NextResponse.json(
        { error: 'Invalid wallet address format' },
        { status: 400 }
      );
    }

    const creator = await creatorService.createCreator({
      name: body.name,
      email: body.email,
      wallet: body.wallet,
      stripe_customer_id: body.stripe_customer_id
    });

    return NextResponse.json(creator, { status: 201 });
  } catch (error: any) {
    if (error.message === 'Email already registered') {
      return NextResponse.json(
        { error: error.message },
        { status: 409 }
      );
    }
    if (error.message === 'Wallet already registered') {
      return NextResponse.json(
        { error: error.message },
        { status: 409 }
      );
    }
    return NextResponse.json(
      { error: error.message || 'Failed to create creator' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '100');
    const offset = parseInt(searchParams.get('offset') || '0');

    const creators = await creatorService.getAllCreators(limit, offset);

    return NextResponse.json(creators, { status: 200 });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch creators' },
      { status: 500 }
    );
  }
}
