/**
 * Vision API Client
 * Handles polling and future WebSocket support for http://localhost:8000/v1/ledger
 */

import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/v1';

export interface Capsule {
  capsule_hash: string;
  risk_level: 'low' | 'medium' | 'high';
  human_approved: boolean;
  ed25519_public_key?: string;
  ed25519_verified?: boolean;
  charge_amount: number;
  split: {
    creator: number;
    data: number;
    planet: number;
    infra: number;
    architect: number;
  };
  timestamp: number;
  merkle_root: string;
}

export interface LedgerResponse {
  transactions: Capsule[];
  current_merkle_root: string;
  total_capsules: number;
}

class VisionAPIClient {
  async fetchLedger(): Promise<LedgerResponse | null> {
    try {
      const response = await axios.get(`${API_BASE}/ledger`, {
        timeout: 5000
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch ledger:', error);
      return null;
    }
  }

  async generateMockLedger(): Promise<LedgerResponse> {
    // Mock data generator for development/demo
    const capsules: Capsule[] = [];
    for (let i = 0; i < 5; i++) {
      const hash = Math.random().toString(16).substr(2, 16);
      const approved = Math.random() > 0.25;
      capsules.push({
        capsule_hash: hash,
        risk_level: this.generateRiskLevel(),
        human_approved: approved,
        ed25519_public_key: approved ? this.generatePublicKey() : undefined,
        ed25519_verified: approved && Math.random() > 0.05,
        charge_amount: approved ? 0.003 : 0,
        split: approved
          ? {
              creator: 0.00178,
              data: 0.00059,
              planet: 0.00030,
              infra: 0.00030,
              architect: 0.00003
            }
          : {
              creator: 0,
              data: 0,
              planet: 0,
              infra: 0,
              architect: 0
            },
        timestamp: Date.now() / 1000,
        merkle_root: Math.random().toString(16).substr(2, 16)
      });
    }
    return {
      transactions: capsules,
      current_merkle_root: Math.random().toString(16).substr(2, 16),
      total_capsules: capsules.length
    };
  }

  private generateRiskLevel(): 'low' | 'medium' | 'high' {
    const rand = Math.random();
    if (rand < 0.60) return 'low';
    if (rand < 0.88) return 'medium';
    return 'high';
  }

  private generatePublicKey(): string {
    return '0x' + Math.random().toString(16).substr(2, 12);
  }
}

export const visionAPIClient = new VisionAPIClient();
