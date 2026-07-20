export type GateType = 'XSSPrevention' | 'SQLInjectionPrevention' | 'PromptInjectionPrevention' | 'PIIRedaction' | 'ToxicityThreshold' | 'ConfidentialityClassifier';
export interface SafetyGateResult {
    gate_type: GateType;
    passed: boolean;
    confidence: number;
    reason: string;
}
export interface ComplianceCapsule {
    id: string;
    approved: boolean;
    gateResults: SafetyGateResult[];
    timestamp: number;
}
export interface AP2SettlementRecord {
    id: string;
    creator_id: string;
    amount_cents: number;
    creator_payout_cents: number;
    platform_fee_cents: number;
    timestamp: number;
}
export interface PayoutSimulation {
    creator: number;
    platform: number;
}
//# sourceMappingURL=types.d.ts.map