import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

describe('test_referral_table_schema', () => {
  let referrerId: string;
  let referredCreatorId: string;

  beforeAll(async () => {
    const referrer = await prisma.creator.create({
      data: {
        name: 'Referrer',
        email: `referrer-${Date.now()}@example.com`,
        wallet: `0x${Math.random().toString(16).slice(2).padEnd(40, '0')}`,
        stripe_customer_id: 'cus_ref'
      }
    });
    referrerId = referrer.id;

    const referred = await prisma.creator.create({
      data: {
        name: 'Referred',
        email: `referred-${Date.now()}@example.com`,
        wallet: `0x${Math.random().toString(16).slice(2).padEnd(40, '0')}`,
        stripe_customer_id: 'cus_reffed'
      }
    });
    referredCreatorId = referred.id;
  });

  it('should have referral table with required columns', async () => {
    const referral = await prisma.referral.create({
      data: {
        referrer_id: referrerId,
        referred_creator_id: referredCreatorId,
        commission_tier: 'tier_1',
        amount: 200,
        status: 'active'
      }
    });

    expect(referral).toHaveProperty('id');
    expect(referral).toHaveProperty('referrer_id');
    expect(referral).toHaveProperty('referred_creator_id');
    expect(referral).toHaveProperty('commission_tier');
    expect(referral).toHaveProperty('amount');
    expect(referral).toHaveProperty('status');
    expect(referral).toHaveProperty('created_at');
    expect(referral).toHaveProperty('updated_at');
  });

  it('should enforce referral_id as UUID primary key', async () => {
    const referral = await prisma.referral.create({
      data: {
        referrer_id: referrerId,
        referred_creator_id: referredCreatorId,
        commission_tier: 'tier_2',
        amount: 150,
        status: 'pending'
      }
    });

    expect(typeof referral.id).toBe('string');
    // UUID format: 8-4-4-4-12 hex characters
    expect(referral.id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
  });

  it('should support commission_tier enum values', async () => {
    const tiers = ['tier_1', 'tier_2', 'tier_3'];

    for (const tier of tiers) {
      const referral = await prisma.referral.create({
        data: {
          referrer_id: referrerId,
          referred_creator_id: referredCreatorId,
          commission_tier: tier,
          amount: 200,
          status: 'active'
        }
      });

      expect(referral.commission_tier).toBe(tier);
    }
  });

  it('should track decimal amount correctly', async () => {
    const referral = await prisma.referral.create({
      data: {
        referrer_id: referrerId,
        referred_creator_id: referredCreatorId,
        commission_tier: 'tier_1',
        amount: 123.45,
        status: 'active'
      }
    });

    const fetched = await prisma.referral.findUnique({
      where: { id: referral.id }
    });

    expect(Number(fetched?.amount)).toBeCloseTo(123.45, 2);
  });

  it('should maintain relationship integrity with creators', async () => {
    const referral = await prisma.referral.create({
      data: {
        referrer_id: referrerId,
        referred_creator_id: referredCreatorId,
        commission_tier: 'tier_1',
        amount: 200,
        status: 'active'
      }
    });

    const fetched = await prisma.referral.findUnique({
      where: { id: referral.id },
      include: {
        referrer: true,
        referred_creator: true
      }
    });

    expect(fetched?.referrer.id).toBe(referrerId);
    expect(fetched?.referred_creator.id).toBe(referredCreatorId);
  });

  afterAll(async () => {
    await prisma.referral.deleteMany({});
    await prisma.creator.deleteMany({});
    await prisma.$disconnect();
  });
});
