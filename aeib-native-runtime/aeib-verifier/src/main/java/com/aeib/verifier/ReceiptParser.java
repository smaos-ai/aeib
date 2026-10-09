package com.aeib.verifier;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Objects;

/**
 * Strict JSON parser and structural validator for AEIB ContinuityReceipts.
 */
public final class ReceiptParser {

    private final ObjectMapper mapper;

    public ReceiptParser() {
        this.mapper = JsonMapper.builder()
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
            .build();
    }

    /**
     * Parses and strictly validates the receipt JSON payload.
     *
     * @param receiptBytes Raw receipt bytes
     * @param canonicalizer Canonicalizer used if statement is an inline JSON object
     * @return ParsedReceipt record containing validated components
     * @throws VerifierInputException on malformed JSON, trailing tokens, or schema gaps
     */
    public ParsedReceipt parse(byte[] receiptBytes, CanonicalJsonSerializer canonicalizer) throws VerifierInputException {
        Objects.requireNonNull(canonicalizer, "canonicalizer must not be null");

        if (receiptBytes == null || receiptBytes.length == 0) {
            throw new VerifierInputException("Receipt content is empty");
        }

        JsonNode root;
        try (JsonParser parser = mapper.createParser(receiptBytes)) {
            root = mapper.readTree(parser);
            if (root == null || !root.isObject()) {
                throw new VerifierInputException("Receipt root must be a non-empty JSON object");
            }
            if (parser.nextToken() != null) {
                throw new VerifierInputException("Trailing tokens detected after valid JSON payload");
            }
        } catch (VerifierInputException e) {
            throw e;
        } catch (Exception e) {
            throw new VerifierInputException("Malformed JSON in receipt: " + e.getMessage(), e);
        }

        // Required field validation on root
        if (!root.hasNonNull("operationId") || !root.get("operationId").isTextual() || root.get("operationId").asText().isBlank()) {
            throw new VerifierInputException("Receipt missing or invalid required field 'operationId'");
        }
        if (!root.hasNonNull("epoch") || !root.get("epoch").isIntegralNumber()) {
            throw new VerifierInputException("Receipt missing or invalid required field 'epoch'");
        }
        if (!root.hasNonNull("chainTip") || !root.get("chainTip").isTextual()) {
            throw new VerifierInputException("Receipt missing or invalid required field 'chainTip'");
        }
        if (!root.hasNonNull("signature") || !root.get("signature").isObject()) {
            throw new VerifierInputException("Receipt missing or invalid required field 'signature'");
        }

        JsonNode sigNode = root.get("signature");
        if (!sigNode.hasNonNull("ed25519Signature") || !sigNode.get("ed25519Signature").isTextual()) {
            throw new VerifierInputException("Receipt signature missing required field 'ed25519Signature'");
        }
        if (!sigNode.hasNonNull("keyId") || !sigNode.get("keyId").isTextual() || sigNode.get("keyId").asText().isBlank()) {
            throw new VerifierInputException("Receipt signature missing or invalid required field 'keyId'");
        }

        byte[] signature;
        try {
            signature = Base64.getDecoder().decode(sigNode.get("ed25519Signature").asText());
        } catch (IllegalArgumentException e) {
            throw new VerifierInputException("Invalid base64 in signature.ed25519Signature: " + e.getMessage(), e);
        }
        if (signature.length != 64) {
            throw new VerifierInputException("Ed25519 signature must be exactly 64 bytes, got: " + signature.length);
        }

        // Extract and validate statement bytes
        byte[] statementBytes;
        if (root.hasNonNull("signedStatement")) {
            if (!root.get("signedStatement").isTextual()) {
                throw new VerifierInputException("signedStatement must be a base64 string");
            }
            try {
                statementBytes = Base64.getDecoder().decode(root.get("signedStatement").asText());
            } catch (IllegalArgumentException e) {
                throw new VerifierInputException("signedStatement is not valid base64: " + e.getMessage(), e);
            }
        } else if (root.hasNonNull("statement") && root.get("statement").isObject()) {
            try {
                String statementJson = mapper.writeValueAsString(root.get("statement"));
                statementBytes = canonicalizer.canonicalize(statementJson.getBytes(StandardCharsets.UTF_8));
            } catch (Exception e) {
                throw new VerifierInputException("Failed to canonicalize inline statement: " + e.getMessage(), e);
            }
        } else {
            throw new VerifierInputException("Receipt missing signedStatement or statement node");
        }

        JsonNode statementNode;
        try {
            statementNode = mapper.readTree(statementBytes);
            if (statementNode == null || !statementNode.isObject()) {
                throw new VerifierInputException("signedStatement content is not a valid JSON object");
            }
        } catch (VerifierInputException e) {
            throw e;
        } catch (Exception e) {
            throw new VerifierInputException("signedStatement content is not valid JSON: " + e.getMessage(), e);
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
}
