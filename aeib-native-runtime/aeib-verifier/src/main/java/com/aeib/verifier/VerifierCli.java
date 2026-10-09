package com.aeib.verifier;

import com.aeib.crypto.Ed25519ProofEngine;
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
import java.util.Base64;

/**
 * Standalone offline verifier for AEIB Continuance Receipts.
 */
public class VerifierCli {
    
    private static final long MAX_PAYLOAD_BYTES = 50 * 1024 * 1024;
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
                verifyReceiptFile(receiptPath, pubKeyPath);
                return;
            }

            if (args.length >= 3) {
                verifyPositional(Paths.get(args[0]), args[1], args[2]);
                return;
            }

            printUsageAndExit();

        } catch (Exception e) {
            System.err.println("ERROR: Verification aborted due to exception: " + e.getMessage());
            e.printStackTrace();
            System.exit(3);
        }
    }

    private static void verifyReceiptFile(Path receiptPath, Path pubKeyPath) throws Exception {
        byte[] receiptBytes = readBounded(receiptPath);
        JsonNode root = MAPPER.readTree(receiptBytes);

        JsonNode sigNode = root.path("signature");
        String sigB64 = sigNode.path("ed25519Signature").asText(null);
        if (sigB64 == null) {
            System.err.println("ERROR: Receipt missing signature.ed25519Signature");
            System.exit(1);
        }
        byte[] signature = Base64.getDecoder().decode(sigB64);

        // Statement to verify: prefer signedStatement bytes, otherwise canonicalize statement node
        byte[] statementBytes;
        if (root.has("signedStatement") && !root.get("signedStatement").isNull()) {
            String b64 = root.get("signedStatement").asText();
            try {
                statementBytes = Base64.getDecoder().decode(b64);
            } catch (IllegalArgumentException e) {
                statementBytes = b64.getBytes(StandardCharsets.UTF_8);
            }
        } else if (root.has("statement")) {
            String statementJson = MAPPER.writeValueAsString(root.get("statement"));
            statementBytes = Ed25519ProofEngine.canonicalize(statementJson);
        } else {
            System.err.println("ERROR: Receipt missing signedStatement and statement nodes");
            System.exit(1);
            return;
        }

        PublicKey publicKey = parsePublicKey(pubKeyPath);

        boolean isValid = Ed25519ProofEngine.verify(statementBytes, signature, publicKey);

        if (isValid) {
            System.out.println("VALID: The receipt signature is mathematically confirmed.");
            System.exit(0);
        } else {
            System.err.println("INVALID: Signature mismatch or payload tampered.");
            System.exit(2);
        }
    }

    private static void verifyPositional(Path payloadPath, String sigB64, String pubKeyB64) throws Exception {
        byte[] payloadBytes = readBounded(payloadPath);
        String payload = new String(payloadBytes, StandardCharsets.UTF_8);
        byte[] signature = Base64.getDecoder().decode(sigB64);
        byte[] pubKeyBytes = Base64.getDecoder().decode(pubKeyB64);

        KeyFactory kf = KeyFactory.getInstance("Ed25519");
        PublicKey publicKey = kf.generatePublic(new X509EncodedKeySpec(pubKeyBytes));

        byte[] canonicalizedPayload = Ed25519ProofEngine.canonicalize(payload);
        boolean isValid = Ed25519ProofEngine.verify(canonicalizedPayload, signature, publicKey);

        if (isValid) {
            System.out.println("VALID: The payload signature is mathematically confirmed.");
            System.exit(0);
        } else {
            System.err.println("INVALID: Signature mismatch or payload tampered.");
            System.exit(2);
        }
    }

    private static PublicKey parsePublicKey(Path pubKeyPath) throws Exception {
        byte[] raw = readBounded(pubKeyPath);
        String text = new String(raw, StandardCharsets.UTF_8).trim();

        if (text.contains("BEGIN PUBLIC KEY")) {
            text = text.replace("-----BEGIN PUBLIC KEY-----", "")
                       .replace("-----END PUBLIC KEY-----", "")
                       .replaceAll("\\s+", "");
        }

        byte[] keyBytes = Base64.getDecoder().decode(text);
        KeyFactory kf = KeyFactory.getInstance("Ed25519");
        return kf.generatePublic(new X509EncodedKeySpec(keyBytes));
    }

    private static byte[] readBounded(Path path) throws Exception {
        try (InputStream in = Files.newInputStream(path);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            long totalBytes = 0;
            int read;
            while ((read = in.read(buffer)) != -1) {
                totalBytes += read;
                if (totalBytes > MAX_PAYLOAD_BYTES) {
                    System.err.println("ERROR: File exceeds 50MB bound: " + path);
                    System.exit(4);
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
