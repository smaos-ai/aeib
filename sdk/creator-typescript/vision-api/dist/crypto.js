"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.EditorKeys = void 0;
exports.sign = sign;
exports.verify = verify;
exports.sha256 = sha256;
exports.generateMerkleProof = generateMerkleProof;
exports.verifyMerkleChain = verifyMerkleChain;
const tweetnacl_1 = __importDefault(require("tweetnacl"));
const crypto_1 = require("crypto");
const keypair = tweetnacl_1.default.sign.keyPair();
exports.EditorKeys = {
    publicKey: Buffer.from(keypair.publicKey).toString('hex'),
    secretKey: Buffer.from(keypair.secretKey).toString('hex'),
};
function sign(message) {
    const msg = Buffer.from(message);
    const signature = tweetnacl_1.default.sign.detached(msg, keypair.secretKey);
    return {
        message,
        signature: Buffer.from(signature).toString('hex'),
        publicKey: Buffer.from(keypair.publicKey).toString('hex'),
    };
}
function verify(signed) {
    try {
        const msg = Buffer.from(signed.message);
        const sig = Buffer.from(signed.signature, 'hex');
        const pubKey = Buffer.from(signed.publicKey, 'hex');
        return tweetnacl_1.default.sign.detached.verify(msg, sig, pubKey);
    }
    catch {
        return false;
    }
}
function sha256(data) {
    return (0, crypto_1.createHash)('sha256').update(data).digest('hex');
}
function generateMerkleProof(entries) {
    const hashes = entries.map((e, i) => ({ hash: sha256(e), index: i }));
    const root = sha256(hashes.map(h => h.hash).join(''));
    return { root, entries: hashes };
}
function verifyMerkleChain(entries, proof) {
    const recomputed = generateMerkleProof(entries);
    return recomputed.root === proof.root;
}
//# sourceMappingURL=crypto.js.map