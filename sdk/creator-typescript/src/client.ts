import { AP2SettlementRecord, ComplianceCapsule, PayoutSimulation } from './types';
import { simulatePayout } from './settlement';

export class CapsuleClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  private headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
    };
  }

  async govern(input: string): Promise<ComplianceCapsule> {
    const response = await fetch(`${this.baseUrl}/v1/govern`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ input }),
    });
    if (!response.ok) {
      throw new Error(`govern failed: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<ComplianceCapsule>;
  }

  async fetchLedger(creatorId: string): Promise<AP2SettlementRecord[]> {
    const response = await fetch(
      `${this.baseUrl}/v1/ledger?creator_id=${encodeURIComponent(creatorId)}`,
      { method: 'GET', headers: this.headers() }
    );
    if (!response.ok) {
      throw new Error(`fetchLedger failed: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<AP2SettlementRecord[]>;
  }

  async simulatePayout(amount: number): Promise<PayoutSimulation> {
    return simulatePayout(amount);
  }
}
