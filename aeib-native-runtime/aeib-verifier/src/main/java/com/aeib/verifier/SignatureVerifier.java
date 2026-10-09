package com.aeib.verifier;

import java.security.GeneralSecurityException;
import java.security.PublicKey;
import java.security.Signature;

/**
 * Verifies Ed25519 cryptographic signatures using standard JDK cryptographic providers.
 */
public final class SignatureVerifier {

    private SignatureVerifier() {}

    /**
     * Verifies the Ed25519 signature over the canonical statement bytes.
     *
     * @param statementBytes Canonical UTF-8 bytes that were signed
     * @param signatureBytes 64-byte Ed25519 signature
     * @param publicKey Ed25519 public key
     * @return true if signature is cryptographically valid under the key, false otherwise
     */
    public static boolean verify(byte[] statementBytes, byte[] signatureBytes, PublicKey publicKey) {
        if (statementBytes == null || signatureBytes == null || publicKey == null) {
            return false;
        }
        if (signatureBytes.length != 64) {
            return false;
        }

        try {
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(publicKey);
            sig.update(statementBytes);
            return sig.verify(signatureBytes);
        } catch (GeneralSecurityException e) {
            return false;
        }
    }
}
