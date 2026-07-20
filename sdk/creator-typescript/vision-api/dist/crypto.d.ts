export interface SignedMessage {
    message: string;
    signature: string;
    publicKey: string;
}
export interface MerkleProof {
    root: string;
    entries: Array<{
        hash: string;
        index: number;
    }>;
}
export declare const EditorKeys: {
    publicKey: string;
    secretKey: string;
};
export declare function sign(message: string): SignedMessage;
export declare function verify(signed: SignedMessage): boolean;
export declare function sha256(data: string): string;
export declare function generateMerkleProof(entries: string[]): MerkleProof;
export declare function verifyMerkleChain(entries: string[], proof: MerkleProof): boolean;
//# sourceMappingURL=crypto.d.ts.map