import { PrismaClient } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

const prisma = new PrismaClient();

export interface CreateCreatorInput {
  name: string;
  email: string;
  wallet: string;
  stripe_customer_id: string;
}

export interface RoyaltyInput {
  creator_id: string;
  amount: number;
  fee_percentage?: number;
  timestamp: Date;
  status: 'pending' | 'completed' | 'failed';
  webhook_event_id?: string;
}

// Validation helpers
export const validators = {
  email: (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  },

  wallet: (wallet: string): boolean => {
    // Ethereum address validation (0x followed by 40 hex characters)
    return /^0x[a-fA-F0-9]{40}$/.test(wallet);
  },

  name: (name: string): boolean => {
    return name && name.trim().length > 0 && name.length <= 255;
  }
};

export const creatorService = {
  // Create a new creator
  async createCreator(input: CreateCreatorInput) {
    // Validate inputs
    if (!validators.name(input.name)) {
      throw new Error('Invalid creator name');
    }
    if (!validators.email(input.email)) {
      throw new Error('Invalid email format');
    }
    if (!validators.wallet(input.wallet)) {
      throw new Error('Invalid wallet address format');
    }

    // Check for duplicates
    const existing = await prisma.creator.findUnique({
      where: { email: input.email }
    });

    if (existing) {
      throw new Error('Email already registered');
    }

    const existingWallet = await prisma.creator.findUnique({
      where: { wallet: input.wallet }
    });

    if (existingWallet) {
      throw new Error('Wallet already registered');
    }

    return prisma.creator.create({
      data: {
        name: input.name,
        email: input.email,
        wallet: input.wallet,
        stripe_customer_id: input.stripe_customer_id
      }
    });
  },

  // Get creator by ID
  async getCreator(id: string) {
    const creator = await prisma.creator.findUnique({
      where: { id }
    });

    if (!creator) {
      throw new Error('Creator not found');
    }

    return creator;
  },

  // Get all creators
  async getAllCreators(limit = 100, offset = 0) {
    return prisma.creator.findMany({
      take: limit,
      skip: offset,
      orderBy: { created_at: 'desc' }
    });
  },

  // Record a royalty entry
  async recordRoyalty(input: RoyaltyInput) {
    // Verify creator exists
    const creator = await prisma.creator.findUnique({
      where: { id: input.creator_id }
    });

    if (!creator) {
      throw new Error('Creator not found');
    }

    const feePercentage = input.fee_percentage || 5;
    const grossAmount = new Decimal(input.amount);
    const feeAmount = grossAmount.mul(new Decimal(feePercentage)).div(new Decimal(100));
    const netAmount = grossAmount.sub(feeAmount);

    // Check for duplicate webhook event (idempotency)
    if (input.webhook_event_id) {
      const existing = await prisma.royalty.findUnique({
        where: { webhook_event_id: input.webhook_event_id }
      });

      if (existing) {
        return existing; // Return existing entry
      }
    }

    return prisma.royalty.create({
      data: {
        creator_id: input.creator_id,
        amount: grossAmount,
        fee_percentage: new Decimal(feePercentage),
        net_amount: netAmount,
        timestamp: input.timestamp,
        status: input.status,
        webhook_event_id: input.webhook_event_id
      }
    });
  },

  // Get royalties for a creator
  async getCreatorRoyalties(creatorId: string) {
    const royalties = await prisma.royalty.findMany({
      where: { creator_id: creatorId },
      orderBy: { timestamp: 'desc' }
    });

    if (!royalties.length) {
      return {
        creator_id: creatorId,
        total_amount: 0,
        total_gross: 0,
        total_fees: 0,
        total_net: 0,
        entries: [],
        monthly_breakdown: {}
      };
    }

    // Calculate totals
    const totals = royalties.reduce(
      (acc, royalty) => ({
        gross: acc.gross.add(royalty.amount),
        fees: acc.fees.add(royalty.amount.sub(royalty.net_amount)),
        net: acc.net.add(royalty.net_amount)
      }),
      {
        gross: new Decimal(0),
        fees: new Decimal(0),
        net: new Decimal(0)
      }
    );

    // Build monthly breakdown
    const monthlyBreakdown: Record<string, number> = {};
    royalties.forEach(royalty => {
      const month = royalty.timestamp.toISOString().substring(0, 7); // YYYY-MM
      if (!monthlyBreakdown[month]) {
        monthlyBreakdown[month] = 0;
      }
      monthlyBreakdown[month] += royalty.net_amount.toNumber();
    });

    return {
      creator_id: creatorId,
      total_amount: totals.net.toNumber(),
      total_gross: totals.gross.toNumber(),
      total_fees: totals.fees.toNumber(),
      total_net: totals.net.toNumber(),
      entries: royalties.map(r => ({
        id: r.id,
        amount: r.net_amount.toNumber(),
        gross_amount: r.amount.toNumber(),
        fee_amount: r.amount.sub(r.net_amount).toNumber(),
        timestamp: r.timestamp,
        status: r.status,
        webhook_event_id: r.webhook_event_id
      })),
      monthly_breakdown: monthlyBreakdown
    };
  },

  // Update royalty status
  async updateRoyaltyStatus(
    creatorId: string,
    royaltyId: string,
    status: 'pending' | 'completed' | 'failed'
  ) {
    const royalty = await prisma.royalty.findUnique({
      where: { id: royaltyId }
    });

    if (!royalty || royalty.creator_id !== creatorId) {
      throw new Error('Royalty not found');
    }

    return prisma.royalty.update({
      where: { id: royaltyId },
      data: { status }
    });
  },

  // Get royalty by ID
  async getRoyalty(creatorId: string, royaltyId: string) {
    const royalty = await prisma.royalty.findUnique({
      where: { id: royaltyId }
    });

    if (!royalty || royalty.creator_id !== creatorId) {
      throw new Error('Royalty not found');
    }

    return {
      id: royalty.id,
      creator_id: royalty.creator_id,
      amount: royalty.net_amount.toNumber(),
      gross_amount: royalty.amount.toNumber(),
      fee_amount: royalty.amount.sub(royalty.net_amount).toNumber(),
      timestamp: royalty.timestamp,
      status: royalty.status,
      webhook_event_id: royalty.webhook_event_id
    };
  },

  // Create settlement batch
  async createSettlement(creatorIds: string[], totalAmount: Decimal) {
    const batch_id = `settlement_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    return prisma.settlement.create({
      data: {
        batch_id,
        creator_ids: creatorIds,
        total_amount: totalAmount,
        status: 'pending'
      }
    });
  },

  // Get settlement by batch ID
  async getSettlement(batchId: string) {
    return prisma.settlement.findUnique({
      where: { batch_id: batchId }
    });
  },

  // Update settlement status
  async updateSettlementStatus(
    batchId: string,
    status: 'pending' | 'processing' | 'completed' | 'failed',
    txHash?: string
  ) {
    const data: any = { status };
    if (status === 'completed') {
      data.settled_at = new Date();
    }
    if (txHash) {
      data.tx_hash = txHash;
    }

    return prisma.settlement.update({
      where: { batch_id: batchId },
      data
    });
  }
};
