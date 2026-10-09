package com.aeib.verifier;

import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

/**
 * Parses and strictly validates Ed25519 public keys.
 *
 * AEIB pins exactly one input format:
 *   PEM-encoded X.509 SubjectPublicKeyInfo containing exactly one Ed25519 public key.
 *
 * Raw 32-byte keys, OpenSSH-format keys, PKCS#8 private keys, certificates,
 * and multiple keys in one file are explicitly rejected.
 */
public final class PublicKeyReader {

    private PublicKeyReader() {}

    /**
     * Parses a PEM-encoded X.509 SubjectPublicKeyInfo containing exactly one Ed25519 public key.
     *
     * @param pemBytes Raw bytes of the PEM file
     * @return Validated Ed25519 PublicKey
     * @throws VerifierInputException if format, algorithm, or encoding is invalid
     */
    public static PublicKey parse(byte[] pemBytes) throws VerifierInputException {
        if (pemBytes == null || pemBytes.length == 0) {
            throw new VerifierInputException("Public key input is empty");
        }

        String text = new String(pemBytes, StandardCharsets.UTF_8).trim();

        // Reject certificates, private keys, OpenSSH keys, and unsupported formats
        if (text.contains("CERTIFICATE")) {
            throw new VerifierInputException("Certificates are not permitted as public key input; provide X.509 SubjectPublicKeyInfo PEM");
        }
        if (text.contains("PRIVATE KEY")) {
            throw new VerifierInputException("Private keys are not permitted as public key input");
        }
        if (text.startsWith("ssh-ed25519") || text.contains("ssh-rsa")) {
            throw new VerifierInputException("OpenSSH public key format is not permitted; provide PEM-encoded X.509 SubjectPublicKeyInfo");
        }

        // Must contain standard PEM header and footer
        int firstBegin = text.indexOf("-----BEGIN PUBLIC KEY-----");
        int lastBegin = text.lastIndexOf("-----BEGIN PUBLIC KEY-----");
        int endIdx = text.indexOf("-----END PUBLIC KEY-----");

        if (firstBegin == -1 || endIdx == -1 || endIdx < firstBegin) {
            throw new VerifierInputException("Public key must be PEM-encoded X.509 SubjectPublicKeyInfo with BEGIN/END PUBLIC KEY markers");
        }
        if (firstBegin != lastBegin) {
            throw new VerifierInputException("Multiple public keys detected in file; exactly one key is permitted");
        }

        String base64Content = text
            .substring(firstBegin + "-----BEGIN PUBLIC KEY-----".length(), endIdx)
            .replaceAll("\\s+", "");

        byte[] spkiBytes;
        try {
            spkiBytes = Base64.getDecoder().decode(base64Content);
        } catch (IllegalArgumentException e) {
            throw new VerifierInputException("Invalid base64 encoding in public key PEM: " + e.getMessage(), e);
        }

        // Standard X.509 SubjectPublicKeyInfo for Ed25519 is 44 bytes
        if (spkiBytes.length == 32) {
            throw new VerifierInputException("Raw 32-byte Ed25519 keys are rejected; provide X.509 SubjectPublicKeyInfo PEM");
        }

        try {
            KeyFactory kf = KeyFactory.getInstance("Ed25519");
            PublicKey key = kf.generatePublic(new X509EncodedKeySpec(spkiBytes));
            String alg = key.getAlgorithm();
            if (!"Ed25519".equalsIgnoreCase(alg) && !"EdDSA".equalsIgnoreCase(alg)) {
                throw new VerifierInputException("Public key algorithm must be Ed25519/EdDSA, got: " + alg);
            }
            return key;
        } catch (Exception e) {
            throw new VerifierInputException("Failed to decode Ed25519 X.509 SubjectPublicKeyInfo: " + e.getMessage(), e);
        }
    }
}
