package com.aeib.crypto;

import java.nio.charset.StandardCharsets;
import java.security.*;
import org.erdtman.jcs.JsonCanonicalizer;

public class Ed25519ProofEngine {

    /**
     * Strictly follows RFC 8785 to canonicalize the payload before hashing/signing.
     * 
     * @param jsonPayload The JSON string to canonicalize.
     * @return UTF-8 encoded canonical JSON bytes.
     */
    public static byte[] canonicalize(String jsonPayload) {
        try {
            JsonCanonicalizer jc = new JsonCanonicalizer(jsonPayload);
            return jc.getEncodedString().getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new RuntimeException("Failed to canonicalize payload (RFC 8785)", e);
        }
    }

    /**
     * Signs the given data using Ed25519.
     */
    public static byte[] sign(byte[] data, PrivateKey privateKey) throws GeneralSecurityException {
        Signature sig = Signature.getInstance("Ed25519");
        sig.initSign(privateKey);
        sig.update(data);
        return sig.sign();
    }

    /**
     * Verifies the Ed25519 signature of the given data.
     */
    public static boolean verify(byte[] data, byte[] signature, PublicKey publicKey) throws GeneralSecurityException {
        Signature sig = Signature.getInstance("Ed25519");
        sig.initVerify(publicKey);
        sig.update(data);
        return sig.verify(signature);
    }
    
    /**
     * Generates a new Ed25519 key pair for testing/ephemeral usage.
     */
    public static KeyPair generateKeyPair() throws GeneralSecurityException {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("Ed25519");
        return kpg.generateKeyPair();
    }
}
