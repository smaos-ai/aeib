"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.govern = govern;
exports.shouldEnforceHumanGate = shouldEnforceHumanGate;
const uuid_1 = require("uuid");
const index_1 = require("./index");
const MICRO_FEE_CENTS = 3; // $0.03 = 3 cents (demo value)
function govern(req) {
    const startTime = Date.now();
    const id = (0, uuid_1.v4)();
    // 1. Run all safety gates
    const gateResults = (0, index_1.runAllGates)(req.modelOutput);
    const allPassed = gateResults.every(g => g.passed);
    // 2. Calculate AP2 split
    const ap2 = (0, index_1.simulatePayout)(MICRO_FEE_CENTS);
    // 3. Build decision object
    const decision = {
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
    decision.signature = (0, index_1.sign)(messageToSign);
    // 5. Generate Merkle proof
    const auditEntries = [
        decision.id,
        messageToSign,
        decision.signature.signature,
        decision.timestamp.toString(),
    ];
    decision.merkleProof = (0, index_1.generateMerkleProof)(auditEntries);
    // 6. Record latency
    decision.latencyMs = Date.now() - startTime;
    return decision;
}
function shouldEnforceHumanGate(decision) {
    // Human gate required if:
    // - Any gate failed (safety violation)
    // - Risk tier is "defense" and confidence < 0.95
    if (!decision.approved)
        return true;
    if (decision.riskTier === 'defense') {
        const minConfidence = Math.min(...decision.safetyGatesResults.map(g => g.confidence));
        if (minConfidence < 0.95)
            return true;
    }
    return false;
}
//# sourceMappingURL=governance.js.map