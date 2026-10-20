#!/usr/bin/env node
// Copyright 2026 SovereignNexus Project
// tests/test_smaos_verify_wasm.js — Native WebAssembly Offline Acceptance Suite
//
// Evaluates smaos_verify.wasm via V8 / Node.js native WebAssembly runtime
// using real Ed25519 cryptography (zero mocks).

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const wasmPath = path.resolve(__dirname, "../public_html/smaos_verify.wasm");
if (!fs.existsSync(wasmPath)) {
    console.error(`[!] smaos_verify.wasm not found at ${wasmPath}`);
    process.exit(1);
}

const wasmBytes = fs.readFileSync(wasmPath);

WebAssembly.instantiate(wasmBytes, {}).then(({ instance }) => {
    const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
    const rawPub = publicKey.export({ type: "spki", format: "der" }).slice(-32);
    const pubHex = rawPub.toString("hex");

    const action_id = "act-node-valid-001";
    const intent_hex = "1111111111111111111111111111111111111111111111111111111111111111";
    const intent_bytes = Buffer.from(intent_hex, "hex");
    const verdict = "CONFIRMED";
    const timestamp = "2026-09-18T12:00:00Z";

    const leafContent = Buffer.concat([
        Buffer.from([0x00]),
        Buffer.from(action_id, "utf8"),
        intent_bytes,
        Buffer.from(verdict, "utf8")
    ]);
    const root = crypto.createHash("sha256").update(leafContent).digest();
    const rootHex = root.toString("hex");

    function signReceipt(ts) {
        const signedMsg = Buffer.concat([
            root,
            Buffer.from(action_id, "utf8"),
            Buffer.from(verdict, "utf8"),
            Buffer.from(ts, "utf8")
        ]);
        return crypto.sign(null, signedMsg, privateKey).toString("hex");
    }

    function runVerify(obj) {
        const bytes = Buffer.from(JSON.stringify(obj), "utf8");
        const ptr = instance.exports.allocate(bytes.length);
        new Uint8Array(instance.exports.memory.buffer, ptr, bytes.length).set(bytes);
        const rc = instance.exports.smaos_verify_receipt(ptr, bytes.length);
        instance.exports.deallocate(ptr, bytes.length);
        return rc;
    }

    const baseReceipt = {
        version: "1.0.0",
        action_id,
        leaf_index: 0,
        tree_size: 1,
        timestamp,
        intent_digest: intent_hex,
        verdict,
        root_hash: rootHex,
        inclusion_proof: [],
        signature: signReceipt(timestamp),
        signer_pubkey: pubHex
    };

    console.log("==========================================================");
    console.log("SMAOS_VERIFY.WASM NATIVE WEBASSEMBLY ACCEPTANCE TEST");
    console.log("==========================================================");

    // 1. Valid receipt
    const rcValid = runVerify(baseReceipt);
    console.log("1. Valid receipt verification:               rc =", rcValid, "(Expected: 0)");
    if (rcValid !== 0) throw new Error("Expected rc=0");

    // 2. Tampered signature
    const sigHex = baseReceipt.signature;
    const tamperedSig = sigHex.slice(0, -2) + (sigHex.slice(-2) === "00" ? "ff" : "00");
    const rcBadSig = runVerify({ ...baseReceipt, signature: tamperedSig });
    console.log("2. Tampered Ed25519 signature rejection:     rc =", rcBadSig, "(Expected: -4)");
    if (rcBadSig !== -4) throw new Error("Expected rc=-4");

    // 3. Merkle boundary violation
    const rcBoundary = runVerify({ ...baseReceipt, leaf_index: 5, tree_size: 5 });
    console.log("3. Merkle boundary invariant violation:      rc =", rcBoundary, "(Expected: -2)");
    if (rcBoundary !== -2) throw new Error("Expected rc=-2");

    // 4. Timestamp ancient/future skew violation
    const ts2019 = "2019-01-01T00:00:00Z";
    const rcTimestamp = runVerify({ ...baseReceipt, timestamp: ts2019, signature: signReceipt(ts2019) });
    console.log("4. Out-of-bounds timestamp rejection:        rc =", rcTimestamp, "(Expected: -5)");
    if (rcTimestamp !== -5) throw new Error("Expected rc=-5");

    // 5. Merkle root hash mismatch
    const badRoot = "99".repeat(32);
    const rcMismatch = runVerify({ ...baseReceipt, root_hash: badRoot });
    console.log("5. Merkle root inclusion mismatch rejection: rc =", rcMismatch, "(Expected: -3)");
    if (rcMismatch !== -3) throw new Error("Expected rc=-3");

    // 6. Valid v1.1.0 receipt with attestation closure and relying party verdict
    const d64 = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789";
    const v11Receipt = {
        ...baseReceipt,
        version: "1.1.0",
        relying_party_verdict: "admissible",
        attestation_closure: {
            tokenizer_digest: d64,
            chat_template_digest: d64,
            engine_build_digest: d64,
            numeric_environment_digest: d64
        }
    };
    const rcV11Valid = runVerify(v11Receipt);
    console.log("6. Valid v1.1.0 receipt with attestation:    rc =", rcV11Valid, "(Expected: 0)");
    if (rcV11Valid !== 0) throw new Error("Expected rc=0");

    // 7. Invalid relying party verdict rejection
    const rcBadRpv = runVerify({ ...v11Receipt, relying_party_verdict: "unauthorized_verdict" });
    console.log("7. Invalid relying party verdict rejection:   rc =", rcBadRpv, "(Expected: -1)");
    if (rcBadRpv !== -1) throw new Error("Expected rc=-1");

    // 8. Truncated attestation digest rejection
    const rcBadDigest = runVerify({
        ...v11Receipt,
        attestation_closure: {
            ...v11Receipt.attestation_closure,
            tokenizer_digest: "tooshort"
        }
    });
    console.log("8. Malformed attestation digest rejection:    rc =", rcBadDigest, "(Expected: -1)");
    if (rcBadDigest !== -1) throw new Error("Expected rc=-1");

    console.log("==========================================================");
    console.log("ALL REAL WASM ACCEPTANCE TESTS PASSED (rc=0)!");
    console.log("==========================================================");
    process.exit(0);
}).catch(err => {
    console.error("[!] Test failure:", err);
    process.exit(1);
});
