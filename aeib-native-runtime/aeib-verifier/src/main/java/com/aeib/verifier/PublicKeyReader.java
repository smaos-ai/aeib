package com.aeib.verifier;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

/**
 * Parses and validates Ed25519 public keys from documented X.509 PEM or Base64 formats.
 */
public final class PublicKeyReader {

    private PublicKeyReader() {}

    /**
     * Reads public key from file using bounded file read, then parses the Ed25519 public key.
     *
     * @param path Path to the public key file
     * @return Validated Ed25519 PublicKey
     * @throws ReceiptFileReader.FileReadException if file read violates boundedness or regular-file check
     * @throws InvalidKeyException if public key format is invalid or not Ed25519
     */
    public static PublicKey readFromPath(Path path) throws ReceiptFileReader.FileReadException, InvalidKeyException {
        byte[] bytes = ReceiptFileReader.readBounded(path);
        String text = new String(bytes, StandardCharsets.UTF_8);
        return parse(text);
    }

    /**
     * Parses an Ed25519 public key from PEM string or raw Base64.
     *
     * @param text PEM formatted or Base64 string
     * @return Validated Ed25519 PublicKey
     * @throws InvalidKeyException if format is invalid or not Ed25519
     */
    public static PublicKey parse(String text) throws InvalidKeyException {
        if (text == null || text.isBlank()) {
            throw new InvalidKeyException("Public key text is empty");
        }
        String clean = text.trim();
        if (clean.contains("BEGIN PUBLIC KEY")) {
            clean = clean.replace("-----BEGIN PUBLIC KEY-----", "")
                         .replace("-----END PUBLIC KEY-----", "")
                         .replaceAll("\\s+", "");
        } else {
            clean = clean.replaceAll("\\s+", "");
        }

        byte[] keyBytes;
        try {
            keyBytes = Base64.getDecoder().decode(clean);
        } catch (IllegalArgumentException e) {
            throw new InvalidKeyException("Invalid base64 encoding in public key: " + e.getMessage(), e);
        }

        try {
            KeyFactory kf = KeyFactory.getInstance("Ed25519");
            return kf.generatePublic(new X509EncodedKeySpec(keyBytes));
        } catch (Exception e) {
            throw new InvalidKeyException("Failed to decode Ed25519 public key: " + e.getMessage(), e);
        }
    }

    public static class InvalidKeyException extends Exception {
        public InvalidKeyException(String message) {
            super(message);
        }

        public InvalidKeyException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
