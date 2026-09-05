import nacl from 'tweetnacl';
import { createHash } from 'crypto';

export interface SignedMessage {
  message: string;
  signature: string;
  publicKey: string;
}

export interface MerkleProof {
  root: string;
  entries: Array<{ hash: string; index: number }>;
}

const keypair = nacl.sign.keyPair();

export const EditorKeys = {
  publicKey: Buffer.from(keypair.publicKey).toString('hex'),
  secretKey: Buffer.from(keypair.secretKey).toString('hex'),
};

export function sign(message: string): SignedMessage {
  const msg = Buffer.from(message);
  const signature = nacl.sign.detached(msg, keypair.secretKey);
  return {
    message,
    signature: Buffer.from(signature).toString('hex'),
    publicKey: Buffer.from(keypair.publicKey).toString('hex'),
  };
}

export function verify(signed: SignedMessage): boolean {
  try {
    const msg = Buffer.from(signed.message);
    const sig = Buffer.from(signed.signature, 'hex');
    const pubKey = Buffer.from(signed.publicKey, 'hex');
    return nacl.sign.detached.verify(msg, sig, pubKey);
  } catch {
    return false;
  }
}

export function sha256(data: string): string {
  return createHash('sha256').update(data).digest('hex');
}

export function generateMerkleProof(entries: string[]): MerkleProof {
  const hashes = entries.map((e, i) => ({ hash: sha256(e), index: i }));
  const root = sha256(hashes.map(h => h.hash).join(''));
  return { root, entries: hashes };
}

export function verifyMerkleChain(entries: string[], proof: MerkleProof): boolean {
  const recomputed = generateMerkleProof(entries);
  return recomputed.root === proof.root;
}
