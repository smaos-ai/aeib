package com.aeib.verifier;

import com.aeib.crypto.Ed25519ProofEngine;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;

/**
 * Standalone offline verifier for AEIB Continuance Receipts.
 * 
 * Exit code contract:
 *  0: Verification succeeded under supplied public key.
 *  1: Malformed receipt / invalid JSON / trailing tokens / missing required fields / invalid CLI arguments.
 *  2: Verification failed: signature mismatch / statement tampering / field binding mismatch / non-canonical statement.
 *  3: Internal system error / unhandled exception.
 *  4: File I/O violation (oversized input >50MB or non-regular file).
 */
public class VerifierCli {
    
    public static final long MAX_PAYLOAD_BYTES = 50 * 1024 * 1024;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) {
        if (args.length == 0) {
            printUsageAndExit();
        }

        try {
            Path receiptPath = null;
            Path pubKeyPath = null;

            for (int i = 0; i < args.length; i++) {
                if ("--receipt".equals(args[i]) && i + 1 < args.length) {
                    receiptPath = Paths.get(args[++i]);
                } else if ("--pubkey".equals(args[i]) && i + 1 < args.length) {
                    pubKeyPath = Paths.get(args[++i]);
                }
            }

            if (receiptPath != null && pubKeyPath != null) {
                int exitCode = verify(receiptPath, pubKeyPath);
                System.exit(exitCode);
                return;
            }

            if (args.length >= 3) {
                int exitCode = verifyPositional(Paths.get(args[0]), args[1], args[2]);
                System.exit(exitCode);
                return;
            }

            printUsageAndExit();

        } catch (Exception e) {
            System.err.println("ERROR: Verification aborted due to exception: " + e.getMessage());
            System.exit(3);
        }
    }

    public static int verify(Path receiptPath, Path pubKeyPath) {
        try {
            if (!Files.exists(receiptPath) || !Files.isRegularFile(receiptPath) || Files.isSymbolicLink(receiptPath)) {
                System.err.println("ERROR: Receipt file is not a regular file or does not exist: " + receiptPath);
                return 4;
            }
            if (!Files.exists(pubKeyPath) || !Files.isRegularFile(pubKeyPath) || Files.isSymbolicLink(pubKeyPath)) {
                System.err.println("ERROR: Public key file is not a regular file or does not exist: " + pubKeyPath);
                return 4;
            }

            byte[] receiptBytes = readBounded(receiptPath);
            if (receiptBytes == null) {
                return 4;
            }

            // Strict JSON Parsing: reject trailing tokens
            JsonNode root;
            try (JsonParser parser = MAPPER.createParser(receiptBytes)) {
                root = MAPPER.readTree(parser);
                if (root == null) {
                    System.err.println("ERROR: Empty JSON content in receipt.");
                    return 1;
                }
                if (parser.nextToken() != null) {
                    System.err.println("ERROR: Trailing tokens detected after valid JSON payload.");
                    return 1;
                }
            } catch (Exception e) {
                System.err.println("ERROR: Malformed JSON in receipt: " + e.getMessage());
                return 1;
            }

            // Required field validation on root
            if (!root.hasNonNull("operationId") || !root.get("operationId").isTextual() || root.get("operationId").asText().isBlank()) {
                System.err.println("ERROR: Receipt missing or invalid required field 'operationId'.");
                return 1;
            }
            if (!root.hasNonNull("epoch") || !root.get("epoch").isIntegralNumber()) {
                System.err.println("ERROR: Receipt missing or invalid required field 'epoch'.");
                return 1;
            }
            if (!root.hasNonNull("chainTip") || !root.get("chainTip").isTextual()) {
                System.err.println("ERROR: Receipt missing or invalid required field 'chainTip'.");
                return 1;
            }
            if (!root.hasNonNull("signature") || !root.get("signature").isObject()) {
                System.err.println("ERROR: Receipt missing or invalid required field 'signature'.");
                return 1;
            }

            JsonNode sigNode = root.get("signature");
            if (!sigNode.hasNonNull("ed25519Signature") || !sigNode.get("ed25519Signature").isTextual()) {
                System.err.println("ERROR: Receipt signature missing required field 'ed25519Signature'.");
                return 1;
            }
            if (!sigNode.hasNonNull("keyId") || !sigNode.get("keyId").isTextual() || sigNode.get("keyId").asText().isBlank()) {
                System.err.println("ERROR: Receipt signature missing or invalid required field 'keyId'.");
                return 1;
            }

            byte[] signature;
            try {
                signature = Base64.getDecoder().decode(sigNode.get("ed25519Signature").asText());
            } catch (IllegalArgumentException e) {
                System.err.println("ERROR: Invalid base64 in signature.ed25519Signature.");
                return 1;
            }
            if (signature.length != 64) {
                System.err.println("ERROR: Ed25519 signature must be exactly 64 bytes, got: " + signature.length);
                return 1;
            }

            // Extract and validate statement bytes
            byte[] statementBytes;
            if (root.hasNonNull("signedStatement")) {
                if (!root.get("signedStatement").isTextual()) {
                    System.err.println("ERROR: signedStatement must be a base64 string.");
                    return 1;
                }
                try {
                    statementBytes = Base64.getDecoder().decode(root.get("signedStatement").asText());
                } catch (IllegalArgumentException e) {
                    System.err.println("ERROR: signedStatement is not valid base64.");
                    return 1;
                }
            } else if (root.hasNonNull("statement") && root.get("statement").isObject()) {
                String statementJson = MAPPER.writeValueAsString(root.get("statement"));
                statementBytes = Ed25519ProofEngine.canonicalize(statementJson);
            } else {
                System.err.println("ERROR: Receipt missing signedStatement or statement node.");
                return 1;
            }

            // Canonicalization Pinning: Statement must be RFC 8785 canonical
            String statementJsonStr = new String(statementBytes, StandardCharsets.UTF_8);
            byte[] canonicalStatementBytes;
            try {
                canonicalStatementBytes = Ed25519ProofEngine.canonicalize(statementJsonStr);
            } catch (Exception e) {
                System.err.println("INVALID: signedStatement does not conform to RFC 8785 canonical JSON.");
                return 2;
            }
            if (!Arrays.equals(statementBytes, canonicalStatementBytes)) {
                System.err.println("INVALID: signedStatement bytes are not strictly RFC 8785 canonical.");
                return 2;
            }

            // Parse statement and cross-check bindings against receipt root
            JsonNode statementNode;
            try {
                statementNode = MAPPER.readTree(statementBytes);
            } catch (Exception e) {
                System.err.println("INVALID: signedStatement content is not valid JSON.");
                return 2;
            }

            String rootOpId = root.get("operationId").asText();
            String stmtOpId = statementNode.path("operationId").asText(null);
            if (!rootOpId.equals(stmtOpId)) {
                System.err.println("INVALID: operationId mismatch between receipt root (" + rootOpId + ") and signed statement (" + stmtOpId + ").");
                return 2;
            }

            long rootEpoch = root.get("epoch").asLong();
            long stmtEpoch = statementNode.hasNonNull("epoch") ? statementNode.get("epoch").asLong() : Long.MIN_VALUE;
            if (rootEpoch != stmtEpoch) {
                System.err.println("INVALID: epoch mismatch between receipt root (" + rootEpoch + ") and signed statement (" + stmtEpoch + ").");
                return 2;
            }

            String rootChainTip = root.get("chainTip").asText();
            String stmtChainTip = statementNode.path("chainTip").asText(null);
            if (!rootChainTip.equals(stmtChainTip)) {
                System.err.println("INVALID: chainTip mismatch between receipt root and signed statement.");
                return 2;
            }

            String rootKeyId = sigNode.get("keyId").asText();
            String stmtKeyId = statementNode.path("keyId").asText(null);
            if (!rootKeyId.equals(stmtKeyId)) {
                System.err.println("INVALID: keyId mismatch between receipt signature (" + rootKeyId + ") and signed statement (" + stmtKeyId + ").");
                return 2;
            }

            PublicKey publicKey = parsePublicKey(pubKeyPath);
            if (publicKey == null) {
                return 1;
            }

            boolean isValid;
            try {
                isValid = Ed25519ProofEngine.verify(statementBytes, signature, publicKey);
            } catch (java.security.GeneralSecurityException e) {
                isValid = false;
            }
            if (isValid) {
                System.out.println("VALID: The receipt signature verified under the supplied public key.");
                return 0;
            } else {
                System.err.println("INVALID: Signature mismatch or payload tampered.");
                return 2;
            }

        } catch (Exception e) {
            System.err.println("ERROR: Verification exception: " + e.getMessage());
            return 3;
        }
    }

    public static int verifyPositional(Path payloadPath, String sigB64, String pubKeyB64) {
        try {
            if (!Files.exists(payloadPath) || !Files.isRegularFile(payloadPath) || Files.isSymbolicLink(payloadPath)) {
                System.err.println("ERROR: Payload file is not a regular file: " + payloadPath);
                return 4;
            }

            byte[] payloadBytes = readBounded(payloadPath);
            if (payloadBytes == null) {
                return 4;
            }

            String payload = new String(payloadBytes, StandardCharsets.UTF_8);
            byte[] signature = Base64.getDecoder().decode(sigB64);
            byte[] pubKeyBytes = Base64.getDecoder().decode(pubKeyB64);

            KeyFactory kf = KeyFactory.getInstance("Ed25519");
            PublicKey publicKey = kf.generatePublic(new X509EncodedKeySpec(pubKeyBytes));

            byte[] canonicalizedPayload = Ed25519ProofEngine.canonicalize(payload);
            boolean isValid;
            try {
                isValid = Ed25519ProofEngine.verify(canonicalizedPayload, signature, publicKey);
            } catch (java.security.GeneralSecurityException e) {
                isValid = false;
            }

            if (isValid) {
                System.out.println("VALID: The payload signature verified under the supplied public key.");
                return 0;
            } else {
                System.err.println("INVALID: Signature mismatch or payload tampered.");
                return 2;
            }
        } catch (Exception e) {
            System.err.println("ERROR: Positional verification error: " + e.getMessage());
            return 3;
        }
    }

    private static PublicKey parsePublicKey(Path pubKeyPath) {
        try {
            byte[] raw = readBounded(pubKeyPath);
            if (raw == null) {
                return null;
            }
            String text = new String(raw, StandardCharsets.UTF_8).trim();

            if (text.contains("BEGIN PUBLIC KEY")) {
                text = text.replace("-----BEGIN PUBLIC KEY-----", "")
                           .replace("-----END PUBLIC KEY-----", "")
                           .replaceAll("\\s+", "");
            }

            byte[] keyBytes = Base64.getDecoder().decode(text);
            KeyFactory kf = KeyFactory.getInstance("Ed25519");
            return kf.generatePublic(new X509EncodedKeySpec(keyBytes));
        } catch (Exception e) {
            System.err.println("ERROR: Failed to parse public key from " + pubKeyPath + ": " + e.getMessage());
            return null;
        }
    }

    private static byte[] readBounded(Path path) throws Exception {
        if (Files.size(path) > MAX_PAYLOAD_BYTES) {
            System.err.println("ERROR: File exceeds 50MB bound: " + path);
            return null;
        }
        try (InputStream in = Files.newInputStream(path);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            long totalBytes = 0;
            int read;
            while ((read = in.read(buffer)) != -1) {
                totalBytes += read;
                if (totalBytes > MAX_PAYLOAD_BYTES) {
                    System.err.println("ERROR: File exceeds 50MB bound: " + path);
                    return null;
                }
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }

    private static void printUsageAndExit() {
        System.err.println("Usage:");
        System.err.println("  aeib-verifier --receipt <receipt.json> --pubkey <public_key.pem>");
        System.err.println("  aeib-verifier <payload_file> <signature_base64> <public_key_base64>");
        System.exit(1);
    }
}
