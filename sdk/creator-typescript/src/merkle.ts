import { createHash } from 'crypto';
import { AP2SettlementRecord } from './types';

function hashRecord(record: AP2SettlementRecord): string {
  const payload = `${record.creator_id}:${record.amount_cents}:${record.creator_payout_cents}:${record.platform_fee_cents}`;
  return createHash('sha256').update(payload).digest('hex');
}

function hashPair(a: string, b: string): string {
  return createHash('sha256').update(a + b).digest('hex');
}

export function buildMerkleRoot(records: AP2SettlementRecord[]): string {
  if (records.length === 0) return '';
  let hashes = records.map(hashRecord);
  while (hashes.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < hashes.length; i += 2) {
      const right = i + 1 < hashes.length ? hashes[i + 1] : hashes[i];
      next.push(hashPair(hashes[i], right));
    }
    hashes = next;
  }
  return hashes[0];
}

export function verifyChain(records: AP2SettlementRecord[]): boolean {
  if (records.length === 0) return true;
  return records.every(r => r.merkle_proof_hash === hashRecord(r));
}
