/**
 * Micro Royalty Client
 * Fetches real-time royalty settlements from Axiom Protocol (AP2)
 */

import {
  MicroRoyaltyClientConfig,
  RoyaltySettlement,
  SettlementHistoryResponse,
  SettlementQueryOptions,
  RoyaltyRate,
} from './types';

export class MicroRoyaltyClient {
  private config: MicroRoyaltyClientConfig;
  private timeout: number;

  constructor(config: MicroRoyaltyClientConfig) {
    if (!config.baseUrl || !config.apiKey) {
      throw new Error('Invalid royalty client config: baseUrl and apiKey are required');
    }
    this.config = config;
    this.timeout = config.timeout || 5000; // 5s default timeout
  }

  /**
   * Fetch current royalty settlement for a creator
   * @param creatorId Creator identifier
   * @returns RoyaltySettlement data
   */
  async fetchRoyaltySettlement(creatorId: string): Promise<RoyaltySettlement> {
    if (!creatorId) {
      throw new Error('Creator ID is required');
    }

    const url = `${this.config.baseUrl}/v1/royalties/${creatorId}/current`;

    try {
      const response = await this.fetchWithTimeout(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(
          `Failed to fetch royalty settlement: HTTP ${response.status}`
        );
      }

      const settlement = (await response.json()) as RoyaltySettlement;
      return settlement;
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Unknown error fetching royalty settlement');
    }
  }

  /**
   * Fetch settlement history with pagination
   * @param creatorId Creator identifier
   * @param options Query options (page, limit)
   * @returns SettlementHistoryResponse with array of settlements
   */
  async fetchSettlementHistory(
    creatorId: string,
    options: SettlementQueryOptions
  ): Promise<SettlementHistoryResponse> {
    if (!creatorId) {
      throw new Error('Creator ID is required');
    }

    const params = new URLSearchParams({
      page: options.page.toString(),
      limit: options.limit.toString(),
    });

    const url = `${this.config.baseUrl}/v1/royalties/${creatorId}/history?${params.toString()}`;

    try {
      const response = await this.fetchWithTimeout(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(
          `Failed to fetch settlement history: HTTP ${response.status}`
        );
      }

      const result = (await response.json()) as SettlementHistoryResponse;
      return result;
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Unknown error fetching settlement history');
    }
  }

  /**
   * Fetch real-time royalty rates for a creator
   * @param creatorId Creator identifier
   * @returns RoyaltyRate with base and adjusted rates
   */
  async fetchRoyaltyRates(creatorId: string): Promise<RoyaltyRate> {
    if (!creatorId) {
      throw new Error('Creator ID is required');
    }

    const url = `${this.config.baseUrl}/v1/royalties/${creatorId}/rates`;

    try {
      const response = await this.fetchWithTimeout(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch royalty rates: HTTP ${response.status}`);
      }

      const rates = (await response.json()) as RoyaltyRate;
      return rates;
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Unknown error fetching royalty rates');
    }
  }

  /**
   * Fetch with timeout support
   * @param url URL to fetch
   * @param options Fetch options
   * @returns Fetch response
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      return response;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(
          `Request timeout after ${this.timeout}ms`
        );
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Get client configuration
   * @returns Current client configuration
   */
  getConfig(): Readonly<MicroRoyaltyClientConfig> {
    return Object.freeze({ ...this.config });
  }
}
