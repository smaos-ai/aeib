package com.aeib.verifier;

import com.aeib.crypto.Ed25519ProofEngine;
import com.fasterxml.jackson.databind.JsonNode;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.PublicKey;
import java.util.Arrays;
import java.util.Base64;

/**
 * Orchestrates the linear verification path for AEIB Continuance Receipts:
 *
 *   CLI arguments
 *   → bounded file reads
 *   → strict receipt parsing
 *   → pinned canonicalization
 *   → public-key parsing
 *   → signature and field-binding checks
 *   → explicit result and exit code
 */
public final class ReceiptVerifier {

    public enum VerificationOutcome {
        VALID(0, "The receipt signature verified under the supplied public key."),
        MALFORMED(1, "Malformed receipt / invalid JSON / trailing tokens / missing required fields / invalid key."),
        VERIFICATION_FAILED(2, "Verification failed: signature mismatch / statement tampering / field binding mismatch / non-canonical statement."),
        INTERNAL_ERROR(3, "Internal system error."),
        IO_VIOLATION(4, "File I/O violation (oversized input >50MB or non-regular file).");

        private final int exitCode;
        private final String message;

        VerificationOutcome(int exitCode, String message) {
            this.exitCode = exitCode;
            this.message = message;
        }

        public int exitCode() {
            return exitCode;
        }

        public String message() {
            return message;
        }
    }

    public record VerificationResult(VerificationOutcome outcome, String detail) {
        public int exitCode() {
            return outcome.exitCode();
        }
    }

    private ReceiptVerifier() {}

    /**
     * Executes the linear verification path against file paths.
     *
     * @param receiptPath Path to the receipt JSON file
     * @param pubKeyPath Path to the public key PEM file
     * @return VerificationResult containing the outcome and descriptive detail
     */
    public static VerificationResult verify(Path receiptPath, Path pubKeyPath) {
        // Step 1: Bounded file reads
        byte[] receiptBytes;
        try {
            receiptBytes = ReceiptFileReader.readBounded(receiptPath);
        } catch (ReceiptFileReader.FileReadException e) {
            return new VerificationResult(VerificationOutcome.IO_VIOLATION, "Receipt file error: " + e.getMessage());
        }

        PublicKey publicKey;
        try {
            publicKey = PublicKeyReader.readFromPath(pubKeyPath);
        } catch (ReceiptFileReader.FileReadException e) {
            return new VerificationResult(VerificationOutcome.IO_VIOLATION, "Public key file error: " + e.getMessage());
        } catch (PublicKeyReader.InvalidKeyException e) {
            return new VerificationResult(VerificationOutcome.MALFORMED, "Public key parse error: " + e.getMessage());
        }

        return verify(receiptBytes, publicKey);
    }

    /**
     * Executes the linear verification sequence against in-memory receipt bytes and parsed public key.
     *
     * @param receiptBytes Raw receipt bytes
     * @param publicKey Validated Ed25519 public key
     * @return VerificationResult containing the outcome and descriptive detail
     */
    public static VerificationResult verify(byte[] receiptBytes, PublicKey publicKey) {
        // Step 2: Strict receipt parsing & schema validation
        ReceiptParser.ParsedReceipt parsed;
        try {
            parsed = ReceiptParser.parse(receiptBytes);
        } catch (ReceiptParser.ReceiptParseException e) {
            return new VerificationResult(VerificationOutcome.MALFORMED, e.getMessage());
        }

        // Step 3: Pinned Canonicalization (RFC 8785)
        String statementJsonStr = new String(parsed.statementBytes(), StandardCharsets.UTF_8);
        byte[] reCanonicalBytes;
        try {
            reCanonicalBytes = Jcs.canonicalize(statementJsonStr);
        } catch (Exception e) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "signedStatement does not conform to RFC 8785 canonical JSON: " + e.getMessage());
        }
        if (!Arrays.equals(parsed.statementBytes(), reCanonicalBytes)) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "signedStatement bytes are not strictly RFC 8785 canonical.");
        }

        // Step 4: Statement-to-root field-binding checks
        JsonNode stmt = parsed.statementNode();

        String rootOpId = parsed.operationId();
        String stmtOpId = stmt.path("operationId").asText(null);
        if (!rootOpId.equals(stmtOpId)) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "operationId mismatch between receipt root (" + rootOpId + ") and signed statement (" + stmtOpId + ")");
        }

        long rootEpoch = parsed.epoch();
        long stmtEpoch = stmt.hasNonNull("epoch") ? stmt.get("epoch").asLong() : Long.MIN_VALUE;
        if (rootEpoch != stmtEpoch) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "epoch mismatch between receipt root (" + rootEpoch + ") and signed statement (" + stmtEpoch + ")");
        }

        String rootChainTip = parsed.chainTip();
        String stmtChainTip = stmt.path("chainTip").asText(null);
        if (!rootChainTip.equals(stmtChainTip)) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "chainTip mismatch between receipt root and signed statement");
        }

        String rootKeyId = parsed.keyId();
        String stmtKeyId = stmt.path("keyId").asText(null);
        if (!rootKeyId.equals(stmtKeyId)) {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "keyId mismatch between receipt signature (" + rootKeyId + ") and signed statement (" + stmtKeyId + ")");
        }

        // Step 5: Cryptographic signature verification
        boolean isValid;
        try {
            isValid = Ed25519ProofEngine.verify(parsed.statementBytes(), parsed.signature(), publicKey);
        } catch (GeneralSecurityException e) {
            isValid = false;
        }

        if (isValid) {
            return new VerificationResult(VerificationOutcome.VALID,
                "The receipt signature verified under the supplied public key.");
        } else {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "Signature mismatch or payload tampered.");
        }
    }

    /**
     * Positional payload verification: payload file, base64 signature, base64 public key.
     */
    public static VerificationResult verifyPositional(Path payloadPath, String sigB64, String pubKeyB64) {
        byte[] payloadBytes;
        try {
            payloadBytes = ReceiptFileReader.readBounded(payloadPath);
        } catch (ReceiptFileReader.FileReadException e) {
            return new VerificationResult(VerificationOutcome.IO_VIOLATION, "Payload file error: " + e.getMessage());
        }

        PublicKey publicKey;
        try {
            publicKey = PublicKeyReader.parse(pubKeyB64);
        } catch (PublicKeyReader.InvalidKeyException e) {
            return new VerificationResult(VerificationOutcome.MALFORMED, "Invalid public key: " + e.getMessage());
        }

        byte[] signature;
        try {
            signature = Base64.getDecoder().decode(sigB64);
        } catch (IllegalArgumentException e) {
            return new VerificationResult(VerificationOutcome.MALFORMED, "Invalid base64 signature: " + e.getMessage());
        }

        byte[] canonicalPayload;
        try {
            canonicalPayload = Jcs.canonicalize(new String(payloadBytes, StandardCharsets.UTF_8));
        } catch (Exception e) {
            return new VerificationResult(VerificationOutcome.MALFORMED, "Payload canonicalization error: " + e.getMessage());
        }

        boolean isValid;
        try {
            isValid = Ed25519ProofEngine.verify(canonicalPayload, signature, publicKey);
        } catch (GeneralSecurityException e) {
            isValid = false;
        }

        if (isValid) {
            return new VerificationResult(VerificationOutcome.VALID,
                "The payload signature verified under the supplied public key.");
        } else {
            return new VerificationResult(VerificationOutcome.VERIFICATION_FAILED,
                "Signature mismatch or payload tampered.");
        }
    }
}
