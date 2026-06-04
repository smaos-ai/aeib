export interface PayoutSimulation {
  creator: number;
  platform: number;
}

export function simulatePayout(amountCents: number): PayoutSimulation {
  // 99% creator, 1% platform
  const platform = Math.round(amountCents * 0.01);
  const creator = amountCents - platform;
  return { creator, platform };
}
