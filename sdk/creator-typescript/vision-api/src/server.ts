import express, { Express, Request, Response } from 'express';
import { govern, shouldEnforceHumanGate, GovernanceRequest } from './governance';
import { verify } from './crypto';

const app: Express = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Ledger storage (in-memory, ephemeral demo)
const ledger: any[] = [];
const humanGateQueue: any[] = [];

// Health check
app.get('/health', (req: Request, res: Response) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Main governance endpoint
app.post('/v1/govern', (req: Request, res: Response) => {
  try {
    const { query, modelOutput, riskTier = 'personal_palantir', creatorId } = req.body;

    if (!query || !modelOutput) {
      return res.status(400).json({ error: 'query and modelOutput required' });
    }

    const governanceReq: GovernanceRequest = {
      query,
      modelOutput,
      riskTier,
      creatorId,
    };

    const decision = govern(governanceReq);

    // Verify signature
    const isValid = verify(decision.signature);
    if (!isValid) {
      return res.status(500).json({ error: 'Signature verification failed' });
    }

    // Check if human gate needed
    if (shouldEnforceHumanGate(decision)) {
      humanGateQueue.push(decision);
      return res.status(202).json({
        decision,
        humanGateRequired: true,
        humanGateId: decision.id,
        message: 'Decision requires human gate approval',
      });
    }

    // Store in ledger
    ledger.push(decision);

    res.json({
      decision,
      humanGateRequired: false,
      message: 'Governance decision approved and Merkle-rooted',
    });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

// Ledger query endpoint
app.get('/v1/ledger', (req: Request, res: Response) => {
  const { creatorId, limit = 100 } = req.query;
  let results = ledger;

  if (creatorId) {
    results = ledger.filter(d => d.creatorId === creatorId);
  }

  res.json({
    count: results.length,
    entries: results.slice(0, parseInt(limit as string)).map(d => ({
      id: d.id,
      approved: d.approved,
      timestamp: d.timestamp,
      ap2Split: d.ap2Split,
      signature: d.signature.signature.substring(0, 16) + '...',
      merkleRoot: d.merkleProof.root.substring(0, 16) + '...',
      latencyMs: d.latencyMs,
    })),
  });
});

// Human gate endpoint
app.post('/v1/human-gate/:decisionId/approve', (req: Request, res: Response) => {
  const { decisionId } = req.params;
  const decision = humanGateQueue.find(d => d.id === decisionId);

  if (!decision) {
    return res.status(404).json({ error: 'Decision not found in human gate queue' });
  }

  // Move to ledger with human approval marker
  ledger.push({
    ...decision,
    humanApproved: true,
    humanApprovedAt: Date.now(),
  });

  // Remove from queue
  const idx = humanGateQueue.indexOf(decision);
  humanGateQueue.splice(idx, 1);

  res.json({
    message: 'Decision approved by human gate',
    decision: { ...decision, humanApproved: true },
  });
});

// Planet Dashboard — live economics
app.get('/v1/dashboard', (req: Request, res: Response) => {
  const totalTransactions = ledger.length;
  const totalCreatorPayouts = ledger.reduce((sum, d) => sum + d.ap2Split.creatorPayout, 0);
  const totalPlatformFees = ledger.reduce((sum, d) => sum + d.ap2Split.platformFee, 0);
  const avgLatencyMs = ledger.length > 0 ? ledger.reduce((sum, d) => sum + d.latencyMs, 0) / ledger.length : 0;
  const p99LatencyMs = ledger.length > 0 ? Math.max(...ledger.map(d => d.latencyMs)) : 0;

  const failedGates = ledger.filter(d => !d.approved).length;
  const successRate = ledger.length > 0 ? ((ledger.length - failedGates) / ledger.length * 100).toFixed(2) : '100.00';

  res.json({
    title: 'Planet Dashboard — AXIOM Vision API',
    timestamp: new Date().toISOString(),
    economics: {
      totalTransactions,
      totalCreatorPayouts: `$${(totalCreatorPayouts / 100).toFixed(2)}`,
      totalPlatformFees: `$${(totalPlatformFees / 100).toFixed(2)}`,
      creatorPayoutPercent: 99,
      platformFeePercent: 1,
    },
    latency: {
      averageMs: avgLatencyMs.toFixed(2),
      p99Ms: p99LatencyMs,
      targetMs: 500,
      withinSLA: p99LatencyMs <= 500 ? '✅ YES' : '❌ NO',
    },
    governance: {
      successRate: `${successRate}%`,
      failedGates,
      humanGateQueue: humanGateQueue.length,
    },
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`🌍 AXIOM Vision API running at http://localhost:${PORT}`);
  console.log(`📊 Dashboard: http://localhost:${PORT}/v1/dashboard`);
  console.log(`🔐 Latency target: <500ms`);
  console.log(`✍️  Ed25519 signatures enabled`);
  console.log(`⛓️  Merkle proofs enabled`);
});

export default app;
