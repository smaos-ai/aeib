import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { referralService } from '@/lib/services/referral.service';
import { PrismaClient } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

const prisma = new PrismaClient();

describe('test_referral_calculation_20_percent', () => {
  let referrerId: string;
  let referredCreatorId: string;

  beforeAll(async () => {
    // Create test creators
    const referrer = await prisma.creator.create({
      data: {
        name: 'Referrer Creator',
        email: 'referrer@example.com',
        wallet: '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        stripe_customer_id: 'cus_referrer'
      }
    });
    referrerId = referrer.id;

    const referred = await prisma.creator.create({
      data: {
        name: 'Referred Creator',
        email: 'referred@example.com',
        wallet: '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        stripe_customer_id: 'cus_referred'
      }
    });
    referredCreatorId = referred.id;
  });

  it('should calculate 20% referral commission correctly', async () => {
    const commission = referralService.calculateCommission(1000, 'tier_1');
    expect(commission).toBe(200); // 20% of 1000
  });

  it('should support different commission tiers', async () => {
    const tier1 = referralService.calculateCommission(1000, 'tier_1');
    const tier2 = referralService.calculateCommission(1000, 'tier_2');
    const tier3 = referralService.calculateCommission(1000, 'tier_3');

    expect(tier1).toBe(200); // 20%
    expect(tier2).toBe(150); // 15%
    expect(tier3).toBe(100); // 10%
  });

  it('should record referral relationship', async () => {
    const referral = await referralService.createReferral({
      referrer_id: referrerId,
      referred_creator_id: referredCreatorId,
      commission_tier: 'tier_1',
      amount: 0 // Initial, no commission yet
    });

    expect(referral.referrer_id).toBe(referrerId);
    expect(referral.referred_creator_id).toBe(referredCreatorId);
    expect(referral.commission_tier).toBe('tier_1');
  });

  it('should calculate cumulative referral earnings', async () => {
    // Create multiple royalty transactions
    await prisma.royalty.create({
      data: {
        creator_id: referredCreatorId,
        amount: new Decimal(1000),
        fee_percentage: new Decimal(5),
        net_amount: new Decimal(950),
        timestamp: new Date(),
        status: 'completed'
      }
    });

    await prisma.royalty.create({
      data: {
        creator_id: referredCreatorId,
        amount: new Decimal(500),
        fee_percentage: new Decimal(5),
        net_amount: new Decimal(475),
        timestamp: new Date(),
        status: 'completed'
      }
    });

    const earnings = await referralService.getReferralEarnings(referrerId);
    expect(earnings.total_commissions).toBe(300); // (1000 + 500) * 0.2
    expect(earnings.total_referred_creators).toBe(1);
  });

  it('should track referral status updates', async () => {
    const referral = await referralService.createReferral({
      referrer_id: referrerId,
      referred_creator_id: referredCreatorId,
      commission_tier: 'tier_1',
      amount: 200
    });

    const updated = await referralService.updateReferralStatus(
      referral.id,
      'active'
    );

    expect(updated.status).toBe('active');
  });

  afterAll(async () => {
    await prisma.referral.deleteMany({});
    await prisma.royalty.deleteMany({});
    await prisma.creator.deleteMany({});
    await prisma.$disconnect();
  });
});
