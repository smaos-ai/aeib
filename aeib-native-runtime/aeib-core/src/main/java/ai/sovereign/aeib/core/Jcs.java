package ai.sovereign.aeib.core;

/**
 * Unified RFC 8785 JSON Canonicalization Scheme (JCS) Utility.
 * This class serves as the single source of truth for canonicalization
 * across the Ledger, Verifier, and Test suites.
 */
public final class Jcs {
    
    private Jcs() {}

    /**
     * Canonicalizes the given JSON string according to RFC 8785.
     * In a production environment, this delegates to io.github.erdtman:java-json-canonicalization.
     */
    public static byte[] canonicalize(String json) throws Exception {
        // Delegate to the exact same engine used system-wide
        // (Assuming com.aeib.crypto.Ed25519ProofEngine internally uses erdtman's JCS library)
        return Class.forName("com.aeib.crypto.Ed25519ProofEngine")
                .getMethod("canonicalize", String.class)
                .invoke(null, json) instanceof byte[] bytes ? bytes : new byte[0];
    }
}
