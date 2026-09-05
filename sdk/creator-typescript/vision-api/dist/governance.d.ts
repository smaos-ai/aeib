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
        entries: Array<{
            hash: string;
            index: number;
        }>;
    };
    timestamp: number;
    latencyMs: number;
}
export declare function govern(req: GovernanceRequest): GovernanceDecision;
export declare function shouldEnforceHumanGate(decision: GovernanceDecision): boolean;
//# sourceMappingURL=governance.d.ts.map