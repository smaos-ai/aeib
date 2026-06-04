import { AP2SettlementRecord, PayoutSimulation } from './types';

export function simulatePayout(amountCents: number): PayoutSimulation {
  const platform = Math.round(amountCents * 0.01);
  const creator = amountCents - platform;
  return { creator, platform };
}

export function verifyPayout(record: AP2SettlementRecord): boolean {
  const { creator, platform } = simulatePayout(record.amount_cents);
  return (
    record.creator_payout_cents === creator &&
    record.platform_fee_cents === platform
  );
}
