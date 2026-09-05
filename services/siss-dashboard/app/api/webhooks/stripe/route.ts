import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { PrismaClient } from '@prisma/client';
import { creatorService } from '@/lib/services/creator.service';

const prisma = new PrismaClient();

function verifyStripeSignature(
  payload: string,
  signature: string,
  secret: string
): boolean {
  try {
    const parts = signature.split(',');
    const timestamp = parts[0].split('=')[1];
    const providedSignature = parts[1].split('=')[1];

    const signedContent = `${timestamp}.${payload}`;
    const computedSignature = crypto
      .createHmac('sha256', secret)
      .update(signedContent)
      .digest('hex');

    return crypto.timingSafeEqual(
      Buffer.from(providedSignature),
      Buffer.from(computedSignature)
    );
  } catch (error) {
    return false;
  }
}

async function handleChargeSucceeded(
  chargeId: string,
  customerId: string,
  amount: number,
  eventId: string
) {
  // Find creator by Stripe customer ID
  const creator = await prisma.creator.findFirst({
    where: { stripe_customer_id: customerId }
  });

  if (!creator) {
    console.log(`Creator not found for Stripe customer: ${customerId}`);
    return;
  }

  // Record royalty (convert from cents to dollars)
  const amountInDollars = amount / 100;

  await creatorService.recordRoyalty({
    creator_id: creator.id,
    amount: amountInDollars,
    fee_percentage: 5,
    timestamp: new Date(),
    status: 'completed',
    webhook_event_id: eventId
  });
}

async function handlePaymentIntentSucceeded(
  customerId: string,
  amountReceived: number,
  eventId: string
) {
  const creator = await prisma.creator.findFirst({
    where: { stripe_customer_id: customerId }
  });

  if (!creator) {
    console.log(`Creator not found for Stripe customer: ${customerId}`);
    return;
  }

  const amountInDollars = amountReceived / 100;

  await creatorService.recordRoyalty({
    creator_id: creator.id,
    amount: amountInDollars,
    fee_percentage: 5,
    timestamp: new Date(),
    status: 'completed',
    webhook_event_id: eventId
  });
}

export async function POST(request: NextRequest) {
  try {
    const signature = request.headers.get('stripe-signature');

    if (!signature) {
      return NextResponse.json(
        { error: 'Missing Stripe signature' },
        { status: 401 }
      );
    }

    const payload = await request.text();
    const secret = process.env.STRIPE_WEBHOOK_SECRET || '';

    // Verify signature
    if (!verifyStripeSignature(payload, signature, secret)) {
      return NextResponse.json(
        { error: 'Invalid signature' },
        { status: 401 }
      );
    }

    const event = JSON.parse(payload);

    // Handle different event types
    switch (event.type) {
      case 'charge.succeeded':
        await handleChargeSucceeded(
          event.data.object.id,
          event.data.object.customer,
          event.data.object.amount,
          event.id
        );
        break;

      case 'payment_intent.succeeded':
        await handlePaymentIntentSucceeded(
          event.data.object.customer,
          event.data.object.amount_received,
          event.id
        );
        break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    return NextResponse.json({ received: true }, { status: 200 });
  } catch (error: any) {
    console.error('Webhook error:', error);
    return NextResponse.json(
      { error: error.message || 'Webhook processing failed' },
      { status: 500 }
    );
  }
}
