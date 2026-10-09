package com.aeib.verifier;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.charset.StandardCharsets;
import java.security.PublicKey;
import java.util.Arrays;
import java.util.Objects;

/**
 * Orchestrates the linear verification path for AEIB Continuance Receipts:
 *
 *   Bounded file reads
 *   → Strict receipt and public-key parsing
 *   → Pinned RFC 8785 canonicalization check
 *   → Statement-to-root field-binding checks
 *   → Ed25519 signature verification
 *   → Structured result mapping
 */
public final class ReceiptVerifier {

    private final CanonicalJsonSerializer canonicalizer;
    private final ReceiptParser parser;

    public ReceiptVerifier() {
        this(new Rfc8785Canonicalizer(), new ReceiptParser());
    }

    public ReceiptVerifier(CanonicalJsonSerializer canonicalizer) {
        this(canonicalizer, new ReceiptParser());
    }

    public ReceiptVerifier(CanonicalJsonSerializer canonicalizer, ReceiptParser parser) {
        this.canonicalizer = Objects.requireNonNull(canonicalizer, "canonicalizer must not be null");
        if (!"RFC 8785 JCS".equals(this.canonicalizer.algorithmId())) {
            throw new IllegalArgumentException("Unsupported canonicalization algorithm: " + this.canonicalizer.algorithmId());
        }
        this.parser = Objects.requireNonNull(parser, "parser must not be null");
    }

    /**
     * Executes verification for the given file arguments.
     *
     * @param arguments Validated receipt and public key paths
     * @return ReceiptVerificationResult indicating valid or invalid with failure reason
     * @throws VerifierInputException on file read, size limit, syntax, or schema violations
     */
    public ReceiptVerificationResult verify(VerifierArguments arguments) throws VerifierInputException {
        Objects.requireNonNull(arguments, "arguments must not be null");

        byte[] receiptBytes = ReceiptFileReader.readLimited(
            arguments.receiptPath(),
            ReceiptFileReader.MAX_RECEIPT_BYTES,
            "receipt"
        );

        byte[] publicKeyBytes = ReceiptFileReader.readLimited(
            arguments.publicKeyPath(),
            ReceiptFileReader.MAX_PUBLIC_KEY_BYTES,
            "public key"
        );

        ParsedReceipt receipt = parser.parse(receiptBytes, canonicalizer);
        PublicKey publicKey = PublicKeyReader.parse(publicKeyBytes);

        return verifyParsed(receipt, publicKey);
    }

    /**
     * Verifies parsed in-memory receipt components against a public key.
     */
    public ReceiptVerificationResult verifyParsed(ParsedReceipt receipt, PublicKey publicKey) {
        Objects.requireNonNull(receipt, "receipt must not be null");
        Objects.requireNonNull(publicKey, "publicKey must not be null");

        // 1. Pinned Canonicalization (RFC 8785)
        byte[] reCanonicalBytes;
        try {
            reCanonicalBytes = canonicalizer.canonicalize(receipt.signedStatement());
        } catch (CanonicalizationException e) {
            return ReceiptVerificationResult.invalid(
                "signedStatement does not conform to RFC 8785 canonical JSON: " + e.getMessage()
            );
        }

        if (!Arrays.equals(receipt.signedStatement(), reCanonicalBytes)) {
            return ReceiptVerificationResult.invalid("signedStatement bytes are not strictly RFC 8785 canonical");
        }

        // 2. Statement-to-root field bindings
        JsonNode stmt = receipt.statementNode();

        String rootOpId = receipt.operationId();
        String stmtOpId = stmt.path("operationId").asText(null);
        if (!rootOpId.equals(stmtOpId)) {
            return ReceiptVerificationResult.invalid(
                "operationId mismatch between receipt root (" + rootOpId + ") and signed statement (" + stmtOpId + ")"
            );
        }

        long rootEpoch = receipt.epoch();
        long stmtEpoch = stmt.hasNonNull("epoch") ? stmt.get("epoch").asLong() : Long.MIN_VALUE;
        if (rootEpoch != stmtEpoch) {
            return ReceiptVerificationResult.invalid(
                "epoch mismatch between receipt root (" + rootEpoch + ") and signed statement (" + stmtEpoch + ")"
            );
        }

        String rootChainTip = receipt.chainTip();
        String stmtChainTip = stmt.path("chainTip").asText(null);
        if (!rootChainTip.equals(stmtChainTip)) {
            return ReceiptVerificationResult.invalid(
                "chainTip mismatch between receipt root (" + rootChainTip + ") and signed statement (" + stmtChainTip + ")"
            );
        }

        String rootKeyId = receipt.keyId();
        String stmtKeyId = stmt.path("keyId").asText(null);
        if (!rootKeyId.equals(stmtKeyId)) {
            return ReceiptVerificationResult.invalid(
                "keyId mismatch between receipt signature (" + rootKeyId + ") and signed statement (" + stmtKeyId + ")"
            );
        }

        // 3. Cryptographic signature verification
        boolean signatureValid = SignatureVerifier.verify(
            receipt.signedStatement(),
            receipt.signature(),
            publicKey
        );

        if (!signatureValid) {
            return ReceiptVerificationResult.invalid("Ed25519 signature verification failed");
        }

        return ReceiptVerificationResult.success();
    }
}
