/**
 * Micro Royalty Client
 * Fetches real-time royalty settlements from Axiom Protocol (AP2)
 */
import { MicroRoyaltyClientConfig, RoyaltySettlement, SettlementHistoryResponse, SettlementQueryOptions, RoyaltyRate } from './types';
export declare class MicroRoyaltyClient {
    private config;
    private timeout;
    constructor(config: MicroRoyaltyClientConfig);
    /**
     * Fetch current royalty settlement for a creator
     * @param creatorId Creator identifier
     * @returns RoyaltySettlement data
     */
    fetchRoyaltySettlement(creatorId: string): Promise<RoyaltySettlement>;
    /**
     * Fetch settlement history with pagination
     * @param creatorId Creator identifier
     * @param options Query options (page, limit)
     * @returns SettlementHistoryResponse with array of settlements
     */
    fetchSettlementHistory(creatorId: string, options: SettlementQueryOptions): Promise<SettlementHistoryResponse>;
    /**
     * Fetch real-time royalty rates for a creator
     * @param creatorId Creator identifier
     * @returns RoyaltyRate with base and adjusted rates
     */
    fetchRoyaltyRates(creatorId: string): Promise<RoyaltyRate>;
    /**
     * Fetch with timeout support
     * @param url URL to fetch
     * @param options Fetch options
     * @returns Fetch response
     */
    private fetchWithTimeout;
    /**
     * Get client configuration
     * @returns Current client configuration
     */
    getConfig(): Readonly<MicroRoyaltyClientConfig>;
}
//# sourceMappingURL=royalty-client.d.ts.map