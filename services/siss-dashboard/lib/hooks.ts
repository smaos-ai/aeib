/**
 * Custom hooks for Vision API data fetching with SWR
 */

import useSWR from 'swr';
import { visionAPIClient, Capsule, LedgerResponse } from './api-client';

export function useLedger(pollInterval: number = 5000) {
  const { data, error, isLoading, mutate } = useSWR(
    'ledger',
    async () => {
      const result = await visionAPIClient.fetchLedger();
      return result || (await visionAPIClient.generateMockLedger());
    },
    {
      refreshInterval: pollInterval,
      revalidateOnFocus: false,
      dedupingInterval: 1000,
      focusThrottleInterval: 300000
    }
  );

  return {
    ledger: data,
    isLoading,
    error,
    mutate
  };
}

export function useCapsuleMetrics(capsules: Capsule[]) {
  const totalCapsules = capsules.length;
  const totalAP2 = capsules.reduce((sum, c) => sum + c.charge_amount, 0);

  const ap2Split = {
    creator: capsules.reduce((sum, c) => sum + c.split.creator, 0),
    data: capsules.reduce((sum, c) => sum + c.split.data, 0),
    planet: capsules.reduce((sum, c) => sum + c.split.planet, 0),
    infra: capsules.reduce((sum, c) => sum + c.split.infra, 0),
    architect: capsules.reduce((sum, c) => sum + c.split.architect, 0)
  };

  const highRiskBlocked = capsules.filter(
    c => c.risk_level === 'high' && !c.human_approved
  ).length;

  const highRiskApproved = capsules.filter(
    c => c.risk_level === 'high' && c.human_approved
  ).length;

  const highRiskTotal = highRiskBlocked + highRiskApproved;
  const approvalRate = highRiskTotal > 0 ? (highRiskApproved / highRiskTotal) * 100 : 100;

  const merkleChain = capsules.map(c => c.merkle_root);
  const uniqueRoots = Array.from(new Set(merkleChain));

  return {
    totalCapsules,
    totalAP2,
    ap2Split,
    highRiskBlocked,
    highRiskApproved,
    approvalRate,
    merkleChain: uniqueRoots,
    capsules
  };
}

export function generatePSIDrift() {
  // Simulate PSI drift with realistic values
  const base = 0.05;
  const spike = Math.random() * 0.20 - 0.10; // -0.1 to +0.1
  return Math.max(0.0, Math.min(0.5, base + spike));
}

export function generatePSIHistory(hours: number = 24) {
  const history = [];
  for (let i = 0; i < hours; i++) {
    history.push({
      time: `${(i < 10 ? '0' : '') + i}:00`,
      psi: Math.max(0.0, 0.05 + Math.random() * 0.15 - 0.075)
    });
  }
  return history;
}
