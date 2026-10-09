package com.aeib.verifier;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * Validates JSON shape, detects trailing tokens, and validates required fields of AEIB receipts.
 */
public final class ReceiptParser {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private ReceiptParser() {}

    public record ParsedReceipt(
        String operationId,
        long epoch,
        String chainTip,
        String keyId,
        byte[] signature,
        byte[] statementBytes,
        JsonNode statementNode,
        JsonNode rootNode
    ) {}

    /**
     * Parses and strictly validates the receipt JSON payload.
     *
     * @param receiptBytes Raw receipt bytes
     * @return ParsedReceipt record containing extracted and validated components
     * @throws ReceiptParseException if JSON is malformed, has trailing tokens, or lacks required fields
     */
    public static ParsedReceipt parse(byte[] receiptBytes) throws ReceiptParseException {
        if (receiptBytes == null || receiptBytes.length == 0) {
            throw new ReceiptParseException("Receipt content is empty");
        }

        JsonNode root;
        try (JsonParser parser = MAPPER.createParser(receiptBytes)) {
            root = MAPPER.readTree(parser);
            if (root == null) {
                throw new ReceiptParseException("Empty JSON content in receipt");
            }
            if (parser.nextToken() != null) {
                throw new ReceiptParseException("Trailing tokens detected after valid JSON payload");
            }
        } catch (ReceiptParseException e) {
            throw e;
        } catch (Exception e) {
            throw new ReceiptParseException("Malformed JSON in receipt: " + e.getMessage(), e);
        }

        // Required field validation on root
        if (!root.hasNonNull("operationId") || !root.get("operationId").isTextual() || root.get("operationId").asText().isBlank()) {
            throw new ReceiptParseException("Receipt missing or invalid required field 'operationId'");
        }
        if (!root.hasNonNull("epoch") || !root.get("epoch").isIntegralNumber()) {
            throw new ReceiptParseException("Receipt missing or invalid required field 'epoch'");
        }
        if (!root.hasNonNull("chainTip") || !root.get("chainTip").isTextual()) {
            throw new ReceiptParseException("Receipt missing or invalid required field 'chainTip'");
        }
        if (!root.hasNonNull("signature") || !root.get("signature").isObject()) {
            throw new ReceiptParseException("Receipt missing or invalid required field 'signature'");
        }

        JsonNode sigNode = root.get("signature");
        if (!sigNode.hasNonNull("ed25519Signature") || !sigNode.get("ed25519Signature").isTextual()) {
            throw new ReceiptParseException("Receipt signature missing required field 'ed25519Signature'");
        }
        if (!sigNode.hasNonNull("keyId") || !sigNode.get("keyId").isTextual() || sigNode.get("keyId").asText().isBlank()) {
            throw new ReceiptParseException("Receipt signature missing or invalid required field 'keyId'");
        }

        byte[] signature;
        try {
            signature = Base64.getDecoder().decode(sigNode.get("ed25519Signature").asText());
        } catch (IllegalArgumentException e) {
            throw new ReceiptParseException("Invalid base64 in signature.ed25519Signature: " + e.getMessage(), e);
        }
        if (signature.length != 64) {
            throw new ReceiptParseException("Ed25519 signature must be exactly 64 bytes, got: " + signature.length);
        }

        // Extract and validate statement bytes
        byte[] statementBytes;
        if (root.hasNonNull("signedStatement")) {
            if (!root.get("signedStatement").isTextual()) {
                throw new ReceiptParseException("signedStatement must be a base64 string");
            }
            try {
                statementBytes = Base64.getDecoder().decode(root.get("signedStatement").asText());
            } catch (IllegalArgumentException e) {
                throw new ReceiptParseException("signedStatement is not valid base64: " + e.getMessage(), e);
            }
        } else if (root.hasNonNull("statement") && root.get("statement").isObject()) {
            try {
                String statementJson = MAPPER.writeValueAsString(root.get("statement"));
                statementBytes = Jcs.canonicalize(statementJson);
            } catch (Exception e) {
                throw new ReceiptParseException("Failed to canonicalize inline statement: " + e.getMessage(), e);
            }
        } else {
            throw new ReceiptParseException("Receipt missing signedStatement or statement node");
        }

        JsonNode statementNode;
        try {
            statementNode = MAPPER.readTree(statementBytes);
            if (statementNode == null || !statementNode.isObject()) {
                throw new ReceiptParseException("signedStatement content is not a valid JSON object");
            }
        } catch (ReceiptParseException e) {
            throw e;
        } catch (Exception e) {
            throw new ReceiptParseException("signedStatement content is not valid JSON: " + e.getMessage(), e);
        }

        return new ParsedReceipt(
            root.get("operationId").asText(),
            root.get("epoch").asLong(),
            root.get("chainTip").asText(),
            sigNode.get("keyId").asText(),
            signature,
            statementBytes,
            statementNode,
            root
        );
    }

    public static class ReceiptParseException extends Exception {
        public ReceiptParseException(String message) {
            super(message);
        }

        public ReceiptParseException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
