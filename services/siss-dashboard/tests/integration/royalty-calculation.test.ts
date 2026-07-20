import { describe, it, expect, beforeAll } from 'vitest';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000/api';

describe('Royalty Calculation', () => {
  let creatorId: string;

  beforeAll(async () => {
    // Create a test creator
    const creatorData = {
      name: 'Royalty Test Creator',
      email: 'royalty-test@example.com',
      wallet: '0x2234567890123456789012345678901234567890',
      stripe_customer_id: 'cus_royalty_001'
    };

    const creatorResponse = await axios.post(`${API_URL}/creators`, creatorData);
    creatorId = creatorResponse.data.id;
  });

  it('test_royalty_calculation_accurate: should calculate correct royalties for creator', async () => {
    // Record royalty entries
    const royaltyEntries = [
      {
        creator_id: creatorId,
        amount: 100.00,
        timestamp: new Date('2026-06-01'),
        status: 'completed'
      },
      {
        creator_id: creatorId,
        amount: 200.50,
        timestamp: new Date('2026-06-02'),
        status: 'completed'
      },
      {
        creator_id: creatorId,
        amount: 199.50,
        timestamp: new Date('2026-06-03'),
        status: 'completed'
      }
    ];

    // Store royalties
    for (const entry of royaltyEntries) {
      await axios.post(`${API_URL}/creators/${creatorId}/royalties`, entry);
    }

    // Get royalties
    const response = await axios.get(`${API_URL}/creators/${creatorId}/royalties`);

    expect(response.status).toBe(200);
    expect(response.data).toHaveProperty('total_amount');
    expect(response.data).toHaveProperty('entries');

    // Total should be 100 + 200.50 + 199.50 = 500
    expect(response.data.total_amount).toBe(500.00);
    expect(response.data.entries).toHaveLength(3);

    // Verify monthly breakdown
    expect(response.data).toHaveProperty('monthly_breakdown');
    const juneBreakdown = response.data.monthly_breakdown['2026-06'];
    expect(juneBreakdown).toBe(500.00);
  });

  it('should track royalty status transitions', async () => {
    const royaltyData = {
      creator_id: creatorId,
      amount: 150.00,
      timestamp: new Date(),
      status: 'pending'
    };

    const createResponse = await axios.post(
      `${API_URL}/creators/${creatorId}/royalties`,
      royaltyData
    );

    const royaltyId = createResponse.data.id;

    // Verify pending status
    let getResponse = await axios.get(
      `${API_URL}/creators/${creatorId}/royalties/${royaltyId}`
    );
    expect(getResponse.data.status).toBe('pending');

    // Mark as completed
    await axios.patch(
      `${API_URL}/creators/${creatorId}/royalties/${royaltyId}`,
      { status: 'completed' }
    );

    // Verify completion
    getResponse = await axios.get(
      `${API_URL}/creators/${creatorId}/royalties/${royaltyId}`
    );
    expect(getResponse.data.status).toBe('completed');
  });

  it('should handle multiple creators independently', async () => {
    // Create second creator
    const creator2Data = {
      name: 'Second Creator',
      email: 'creator2@example.com',
      wallet: '0x3234567890123456789012345678901234567890',
      stripe_customer_id: 'cus_royalty_002'
    };

    const creator2Response = await axios.post(`${API_URL}/creators`, creator2Data);
    const creator2Id = creator2Response.data.id;

    // Add royalties to second creator
    await axios.post(`${API_URL}/creators/${creator2Id}/royalties`, {
      creator_id: creator2Id,
      amount: 75.00,
      timestamp: new Date(),
      status: 'completed'
    });

    // Verify isolation
    const creator1Response = await axios.get(`${API_URL}/creators/${creatorId}/royalties`);
    const creator2RoyaltyResponse = await axios.get(
      `${API_URL}/creators/${creator2Id}/royalties`
    );

    // Creator1 should have their total, creator2 different
    expect(creator1Response.data.total_amount).toBeGreaterThan(0);
    expect(creator2RoyaltyResponse.data.total_amount).toBe(75.00);
  });

  it('should include fees in royalty calculation', async () => {
    const royaltyData = {
      creator_id: creatorId,
      amount: 1000.00,
      fee_percentage: 5, // 5% platform fee
      timestamp: new Date(),
      status: 'completed'
    };

    await axios.post(`${API_URL}/creators/${creatorId}/royalties`, royaltyData);

    const response = await axios.get(`${API_URL}/creators/${creatorId}/royalties`);

    // Should have both gross and net amounts
    expect(response.data).toHaveProperty('total_gross');
    expect(response.data).toHaveProperty('total_fees');
    expect(response.data).toHaveProperty('total_net');
  });
});
