import { PrismaClient } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

const prisma = new PrismaClient();

export interface CreateReferralInput {
  referrer_id: string;
  referred_creator_id: string;
  commission_tier: 'tier_1' | 'tier_2' | 'tier_3';
  amount: number;
}

export interface ReferralEarnings {
  referrer_id: string;
  total_commissions: number;
  total_referred_creators: number;
  referrals: Array<{
    id: string;
    referred_creator_id: string;
    commission_tier: string;
    commission_earned: number;
  }>;
}

const COMMISSION_TIERS = {
  tier_1: 0.20, // 20%
  tier_2: 0.15, // 15%
  tier_3: 0.10  // 10%
};

export const referralService = {
  /**
   * Calculate commission based on amount and tier
   */
  calculateCommission(amount: number, tier: keyof typeof COMMISSION_TIERS): number {
    const percentage = COMMISSION_TIERS[tier];
    return Number((amount * percentage).toFixed(2));
  },

  /**
   * Create referral relationship
   */
  async createReferral(input: CreateReferralInput) {
    // Verify both creators exist
    const referrer = await prisma.creator.findUnique({
      where: { id: input.referrer_id }
    });

    const referredCreator = await prisma.creator.findUnique({
      where: { id: input.referred_creator_id }
    });

    if (!referrer || !referredCreator) {
      throw new Error('Creator not found');
    }

    // Prevent self-referrals
    if (input.referrer_id === input.referred_creator_id) {
      throw new Error('Cannot refer yourself');
    }

    // Check for existing referral
    const existing = await prisma.referral.findFirst({
      where: {
        referrer_id: input.referrer_id,
        referred_creator_id: input.referred_creator_id
      }
    });

    if (existing) {
      return existing;
    }

    return prisma.referral.create({
      data: {
        referrer_id: input.referrer_id,
        referred_creator_id: input.referred_creator_id,
        commission_tier: input.commission_tier,
        amount: new Decimal(input.amount),
        status: 'pending'
      }
    });
  },

  /**
   * Update referral status
   */
  async updateReferralStatus(
    referralId: string,
    status: 'pending' | 'active' | 'inactive'
  ) {
    return prisma.referral.update({
      where: { id: referralId },
      data: { status }
    });
  },

  /**
   * Get all referrals for a creator (as referrer)
   */
  async getReferrals(referrerId: string) {
    return prisma.referral.findMany({
      where: { referrer_id: referrerId },
      include: {
        referred_creator: {
          select: {
            id: true,
            name: true,
            email: true,
            created_at: true
          }
        }
      },
      orderBy: { created_at: 'desc' }
    });
  },

  /**
   * Calculate total referral earnings for a creator
   */
  async getReferralEarnings(referrerId: string): Promise<ReferralEarnings> {
    const referrals = await prisma.referral.findMany({
      where: { referrer_id: referrerId },
      include: {
        referred_creator: {
          select: {
            id: true
          }
        }
      }
    });

    if (referrals.length === 0) {
      return {
        referrer_id: referrerId,
        total_commissions: 0,
        total_referred_creators: 0,
        referrals: []
      };
    }

    let totalCommissions = 0;
    const referralDetails = [];

    // For each referred creator, calculate their total royalties
    for (const referral of referrals) {
      const royalties = await prisma.royalty.findMany({
        where: {
          creator_id: referral.referred_creator_id,
          status: 'completed'
        }
      });

      const totalRoyalties = royalties.reduce(
        (sum, r) => sum + Number(r.net_amount),
        0
      );

      const commission = this.calculateCommission(
        totalRoyalties,
        referral.commission_tier as keyof typeof COMMISSION_TIERS
      );

      totalCommissions += commission;

      referralDetails.push({
        id: referral.id,
        referred_creator_id: referral.referred_creator_id,
        commission_tier: referral.commission_tier,
        commission_earned: commission
      });
    }

    return {
      referrer_id: referrerId,
      total_commissions: totalCommissions,
      total_referred_creators: referrals.length,
      referrals: referralDetails
    };
  },

  /**
   * Track referred creator who made a royalty sale
   */
  async processReferralCommission(
    referredCreatorId: string,
    royaltyAmount: number
  ) {
    // Find who referred this creator
    const referral = await prisma.referral.findFirst({
      where: {
        referred_creator_id: referredCreatorId,
        status: 'active'
      }
    });

    if (!referral) {
      return null;
    }

    // Update referral amount with new commission
    const commission = this.calculateCommission(
      royaltyAmount,
      referral.commission_tier as keyof typeof COMMISSION_TIERS
    );

    const newAmount = Number(referral.amount) + commission;

    return prisma.referral.update({
      where: { id: referral.id },
      data: {
        amount: new Decimal(newAmount)
      }
    });
  },

  /**
   * Get referral by ID
   */
  async getReferral(referralId: string) {
    return prisma.referral.findUnique({
      where: { id: referralId },
      include: {
        referrer: {
          select: { id: true, name: true, email: true }
        },
        referred_creator: {
          select: { id: true, name: true, email: true }
        }
      }
    });
  }
};
