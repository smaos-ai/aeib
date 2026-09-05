import { randomBytes } from 'crypto';
import { v4 as uuidv4 } from 'uuid';
import {
  runAllGates,
  simulatePayout,
  sign,
  sha256,
  generateMerkleProof,
} from './index';

export interface GovernanceRequest {
  query: string;
  modelOutput: string;
  riskTier: 'personal_palantir' | 'enterprise' | 'defense';
  creatorId?: string;
}

export interface GovernanceDecision {
  id: string;
  approved: boolean;
  riskTier: string;
  safetyGatesResults: Array<{
    gate_type: string;
    passed: boolean;
    confidence: number;
    reason: string;
  }>;
  ap2Split: {
    microFeeAmountCents: number;
    creatorPayout: number;
    platformFee: number;
  };
  signature: {
    message: string;
    signature: string;
    publicKey: string;
  };
  merkleProof: {
    root: string;
    entries: Array<{ hash: string; index: number }>;
  };
  timestamp: number;
  latencyMs: number;
}

const MICRO_FEE_CENTS = 3; // $0.03 = 3 cents (demo value)

export function govern(req: GovernanceRequest): GovernanceDecision {
  const startTime = Date.now();
  const id = uuidv4();

  // 1. Run all safety gates
  const gateResults = runAllGates(req.modelOutput);
  const allPassed = gateResults.every(g => g.passed);

  // 2. Calculate AP2 split
  const ap2 = simulatePayout(MICRO_FEE_CENTS);

  // 3. Build decision object
  const decision: GovernanceDecision = {
    id,
    approved: allPassed,
    riskTier: req.riskTier,
    safetyGatesResults: gateResults,
    ap2Split: {
      microFeeAmountCents: MICRO_FEE_CENTS,
      creatorPayout: ap2.creator,
      platformFee: ap2.platform,
    },
    signature: { message: '', signature: '', publicKey: '' },
    merkleProof: { root: '', entries: [] },
    timestamp: Date.now(),
    latencyMs: 0,
  };

  // 4. Sign decision
  const messageToSign = JSON.stringify({
    id: decision.id,
    approved: decision.approved,
    ap2Split: decision.ap2Split,
  });
  decision.signature = sign(messageToSign);

  // 5. Generate Merkle proof
  const auditEntries = [
    decision.id,
    messageToSign,
    decision.signature.signature,
    decision.timestamp.toString(),
  ];
  decision.merkleProof = generateMerkleProof(auditEntries);

  // 6. Record latency
  decision.latencyMs = Date.now() - startTime;

  return decision;
}

export function shouldEnforceHumanGate(decision: GovernanceDecision): boolean {
  // Human gate required if:
  // - Any gate failed (safety violation)
  // - Risk tier is "defense" and confidence < 0.95
  if (!decision.approved) return true;

  if (decision.riskTier === 'defense') {
    const minConfidence = Math.min(...decision.safetyGatesResults.map(g => g.confidence));
    if (minConfidence < 0.95) return true;
  }

  return false;
}
