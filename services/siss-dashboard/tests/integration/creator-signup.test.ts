import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000/api';

describe('Creator Signup E2E', () => {
  let creatorId: string;

  beforeAll(async () => {
    // Wait for API to be ready
    await new Promise(resolve => setTimeout(resolve, 1000));
  });

  it('test_creator_signup_e2e: should create a new creator with valid data', async () => {
    const creatorData = {
      name: 'Test Creator One',
      email: 'creator1@example.com',
      wallet: '0x1234567890123456789012345678901234567890',
      stripe_customer_id: 'cus_test_001'
    };

    const response = await axios.post(`${API_URL}/creators`, creatorData);

    expect(response.status).toBe(201);
    expect(response.data).toHaveProperty('id');
    expect(response.data.name).toBe(creatorData.name);
    expect(response.data.email).toBe(creatorData.email);
    expect(response.data.wallet).toBe(creatorData.wallet);

    creatorId = response.data.id;
  });

  it('should reject invalid email format', async () => {
    const invalidData = {
      name: 'Invalid Creator',
      email: 'not-an-email',
      wallet: '0x1234567890123456789012345678901234567890',
      stripe_customer_id: 'cus_test_002'
    };

    try {
      await axios.post(`${API_URL}/creators`, invalidData);
      expect.fail('Should have thrown an error');
    } catch (error: any) {
      expect(error.response.status).toBe(400);
      expect(error.response.data).toHaveProperty('error');
    }
  });

  it('should reject invalid wallet address', async () => {
    const invalidData = {
      name: 'Invalid Wallet',
      email: 'wallet@example.com',
      wallet: 'not-a-wallet',
      stripe_customer_id: 'cus_test_003'
    };

    try {
      await axios.post(`${API_URL}/creators`, invalidData);
      expect.fail('Should have thrown an error');
    } catch (error: any) {
      expect(error.response.status).toBe(400);
    }
  });

  it('should reject duplicate email', async () => {
    const creatorData = {
      name: 'Another Name',
      email: 'creator1@example.com', // Same email as first creator
      wallet: '0x1111111111111111111111111111111111111111',
      stripe_customer_id: 'cus_test_004'
    };

    try {
      await axios.post(`${API_URL}/creators`, creatorData);
      expect.fail('Should have thrown an error');
    } catch (error: any) {
      expect(error.response.status).toBe(409); // Conflict
    }
  });

  it('should retrieve creator by ID', async () => {
    const response = await axios.get(`${API_URL}/creators/${creatorId}`);

    expect(response.status).toBe(200);
    expect(response.data.id).toBe(creatorId);
    expect(response.data.email).toBe('creator1@example.com');
  });

  afterAll(async () => {
    // Cleanup is handled by test database
  });
});
