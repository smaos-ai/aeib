"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildMerkleRoot = buildMerkleRoot;
exports.verifyChain = verifyChain;
const crypto_1 = require("crypto");
function hashRecord(record) {
    const payload = `${record.creator_id}:${record.amount_cents}:${record.creator_payout_cents}:${record.platform_fee_cents}`;
    return (0, crypto_1.createHash)('sha256').update(payload).digest('hex');
}
function hashPair(a, b) {
    return (0, crypto_1.createHash)('sha256').update(a + b).digest('hex');
}
function buildMerkleRoot(records) {
    if (records.length === 0)
        return '';
    let hashes = records.map(hashRecord);
    while (hashes.length > 1) {
        const next = [];
        for (let i = 0; i < hashes.length; i += 2) {
            const right = i + 1 < hashes.length ? hashes[i + 1] : hashes[i];
            next.push(hashPair(hashes[i], right));
        }
        hashes = next;
    }
    return hashes[0];
}
function verifyChain(records) {
    if (records.length === 0)
        return true;
    return records.every(r => r.merkle_proof_hash === hashRecord(r));
}
//# sourceMappingURL=merkle.js.map