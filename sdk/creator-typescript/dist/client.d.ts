import { AP2SettlementRecord, ComplianceCapsule, PayoutSimulation } from './types';
export declare class CapsuleClient {
    private readonly baseUrl;
    private readonly apiKey;
    constructor(baseUrl: string, apiKey: string);
    private headers;
    govern(input: string): Promise<ComplianceCapsule>;
    fetchLedger(creatorId: string): Promise<AP2SettlementRecord[]>;
    simulatePayout(amount: number): Promise<PayoutSimulation>;
}
//# sourceMappingURL=client.d.ts.map