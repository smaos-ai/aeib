export type ApprovalLevel = 'Low' | 'Medium' | 'High';
export type GateType = 'XSSPrevention' | 'SQLInjectionPrevention' | 'PromptInjectionPrevention' | 'PIIRedaction' | 'ToxicityThreshold' | 'ConfidentialityClassifier';
export interface SafetyGateResult {
    gate_type: GateType;
    passed: boolean;
    confidence: number;
    reason: string;
}
export interface ComplianceCapsule {
    capsule_id: string;
    model_name: string;
    safety_gates: SafetyGateResult[];
    approval_level: ApprovalLevel;
    merkle_root: string;
}
export interface AP2SettlementRecord {
    creator_id: string;
    amount_cents: number;
    creator_payout_cents: number;
    platform_fee_cents: number;
    merkle_proof_hash: string;
}
export interface PayoutSimulation {
    creator: number;
    platform: number;
}
//# sourceMappingURL=types.d.ts.map