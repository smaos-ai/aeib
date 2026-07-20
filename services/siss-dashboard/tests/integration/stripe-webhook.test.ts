import { describe, it, expect, beforeAll } from 'vitest';
import axios from 'axios';
import crypto from 'crypto';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000/api';
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || 'test_secret';

describe('Stripe Webhook Integration', () => {
  let creatorId: string;

  beforeAll(async () => {
    // Create test creator
    const creatorData = {
      name: 'Stripe Webhook Test',
      email: 'stripe-test@example.com',
      wallet: '0x4234567890123456789012345678901234567890',
      stripe_customer_id: 'cus_stripe_001'
    };

    const response = await axios.post(`${API_URL}/creators`, creatorData);
    creatorId = response.data.id;
  });

  function generateWebhookSignature(payload: string, secret: string): string {
    const timestamp = Math.floor(Date.now() / 1000);
    const signedContent = `${timestamp}.${payload}`;
    const signature = crypto
      .createHmac('sha256', secret)
      .update(signedContent)
      .digest('hex');
    return `t=${timestamp},v1=${signature}`;
  }

  it('test_stripe_webhook_handling: should process charge.succeeded webhook', async () => {
    const payload = JSON.stringify({
      id: 'evt_test_001',
      type: 'charge.succeeded',
      data: {
        object: {
          id: 'ch_test_001',
          customer: 'cus_stripe_001',
          amount: 50000, // $500.00
          currency: 'usd',
          description: 'Test payment',
          created: Math.floor(Date.now() / 1000)
        }
      }
    });

    const signature = generateWebhookSignature(payload, STRIPE_WEBHOOK_SECRET);

    const response = await axios.post(
      `${API_URL}/webhooks/stripe`,
      payload,
      {
        headers: {
          'Stripe-Signature': signature,
          'Content-Type': 'application/json'
        }
      }
    );

    expect(response.status).toBe(200);
    expect(response.data.received).toBe(true);
  });

  it('should reject webhook with invalid signature', async () => {
    const payload = JSON.stringify({
      id: 'evt_invalid',
      type: 'charge.succeeded',
      data: {
        object: {
          id: 'ch_invalid',
          customer: 'cus_stripe_001',
          amount: 10000,
          currency: 'usd'
        }
      }
    });

    try {
      await axios.post(
        `${API_URL}/webhooks/stripe`,
        payload,
        {
          headers: {
            'Stripe-Signature': 't=123456789,v1=invalidsignature',
            'Content-Type': 'application/json'
          }
        }
      );
      expect.fail('Should have rejected invalid signature');
    } catch (error: any) {
      expect(error.response.status).toBe(401);
    }
  });

  it('should create royalty entry from charge.succeeded webhook', async () => {
    const payload = JSON.stringify({
      id: 'evt_royalty_001',
      type: 'charge.succeeded',
      data: {
        object: {
          id: 'ch_royalty_001',
          customer: 'cus_stripe_001',
          amount: 25000, // $250.00
          currency: 'usd',
          created: Math.floor(Date.now() / 1000)
        }
      }
    });

    const signature = generateWebhookSignature(payload, STRIPE_WEBHOOK_SECRET);

    // Send webhook
    await axios.post(
      `${API_URL}/webhooks/stripe`,
      payload,
      {
        headers: {
          'Stripe-Signature': signature,
          'Content-Type': 'application/json'
        }
      }
    );

    // Wait for async processing
    await new Promise(resolve => setTimeout(resolve, 500));

    // Verify royalty was created
    const royaltiesResponse = await axios.get(
      `${API_URL}/creators/${creatorId}/royalties`
    );

    const webhookRoyalty = royaltiesResponse.data.entries.find(
      (entry: any) => entry.webhook_event_id === 'evt_royalty_001'
    );

    expect(webhookRoyalty).toBeDefined();
    expect(webhookRoyalty.amount).toBe(250.00);
  });

  it('should handle payment_intent.succeeded event', async () => {
    const payload = JSON.stringify({
      id: 'evt_intent_001',
      type: 'payment_intent.succeeded',
      data: {
        object: {
          id: 'pi_test_001',
          customer: 'cus_stripe_001',
          amount_received: 75000, // $750.00
          currency: 'usd',
          created: Math.floor(Date.now() / 1000),
          charges: {
            data: [
              {
                id: 'ch_intent_001',
                amount: 75000
              }
            ]
          }
        }
      }
    });

    const signature = generateWebhookSignature(payload, STRIPE_WEBHOOK_SECRET);

    const response = await axios.post(
      `${API_URL}/webhooks/stripe`,
      payload,
      {
        headers: {
          'Stripe-Signature': signature,
          'Content-Type': 'application/json'
        }
      }
    );

    expect(response.status).toBe(200);
  });

  it('should idempotently handle duplicate webhook events', async () => {
    const payload = JSON.stringify({
      id: 'evt_duplicate_001',
      type: 'charge.succeeded',
      data: {
        object: {
          id: 'ch_duplicate_001',
          customer: 'cus_stripe_001',
          amount: 30000, // $300.00
          currency: 'usd',
          created: Math.floor(Date.now() / 1000)
        }
      }
    });

    const signature = generateWebhookSignature(payload, STRIPE_WEBHOOK_SECRET);

    // Send twice
    const response1 = await axios.post(
      `${API_URL}/webhooks/stripe`,
      payload,
      {
        headers: {
          'Stripe-Signature': signature,
          'Content-Type': 'application/json'
        }
      }
    );

    const response2 = await axios.post(
      `${API_URL}/webhooks/stripe`,
      payload,
      {
        headers: {
          'Stripe-Signature': signature,
          'Content-Type': 'application/json'
        }
      }
    );

    expect(response1.status).toBe(200);
    expect(response2.status).toBe(200);

    // Verify only one royalty entry was created
    await new Promise(resolve => setTimeout(resolve, 500));
    const royaltiesResponse = await axios.get(
      `${API_URL}/creators/${creatorId}/royalties`
    );

    const duplicateEntries = royaltiesResponse.data.entries.filter(
      (entry: any) => entry.webhook_event_id === 'evt_duplicate_001'
    );

    expect(duplicateEntries).toHaveLength(1);
  });
});
