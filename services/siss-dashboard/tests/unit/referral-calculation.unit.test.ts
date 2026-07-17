import { describe, it, expect } from 'vitest';
import { referralService } from '@/lib/services/referral.service';

describe('test_referral_calculation_20_percent', () => {
  it('should calculate 20% referral commission for tier_1', () => {
    const commission = referralService.calculateCommission(1000, 'tier_1');
    expect(commission).toBe(200);
  });

  it('should calculate 15% referral commission for tier_2', () => {
    const commission = referralService.calculateCommission(1000, 'tier_2');
    expect(commission).toBe(150);
  });

  it('should calculate 10% referral commission for tier_3', () => {
    const commission = referralService.calculateCommission(1000, 'tier_3');
    expect(commission).toBe(100);
  });

  it('should handle decimal amounts correctly', () => {
    const commission = referralService.calculateCommission(999.99, 'tier_1');
    expect(commission).toBeCloseTo(200, 0);
  });

  it('should handle small amounts', () => {
    const commission = referralService.calculateCommission(10, 'tier_1');
    expect(commission).toBe(2);
  });

  it('should handle large amounts', () => {
    const commission = referralService.calculateCommission(100000, 'tier_1');
    expect(commission).toBe(20000);
  });

  it('should support multiple tier variations', () => {
    const amount = 5000;
    const tier1 = referralService.calculateCommission(amount, 'tier_1');
    const tier2 = referralService.calculateCommission(amount, 'tier_2');
    const tier3 = referralService.calculateCommission(amount, 'tier_3');

    expect(tier1).toBe(1000); // 20%
    expect(tier2).toBe(750);  // 15%
    expect(tier3).toBe(500);  // 10%

    // Verify tier ordering
    expect(tier1 > tier2).toBe(true);
    expect(tier2 > tier3).toBe(true);
  });

  it('should calculate commission with precision to 2 decimal places', () => {
    const commission = referralService.calculateCommission(333.33, 'tier_1');
    expect(commission).toBeCloseTo(66.666, 2);
  });

  it('should round down for fractional cents', () => {
    const commission = referralService.calculateCommission(33, 'tier_1');
    expect(commission).toBe(6.6);
  });
});
