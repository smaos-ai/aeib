package com.aeib.verifier;

import org.erdtman.jcs.JsonCanonicalizer;

import java.nio.charset.StandardCharsets;

/**
 * Stateless, immutable implementation of RFC 8785 JSON Canonicalization Scheme.
 */
public final class Rfc8785Canonicalizer implements CanonicalJsonSerializer {

    public static final String ALGORITHM_ID = "RFC 8785 JCS";

    @Override
    public String algorithmId() {
        return ALGORITHM_ID;
    }

    @Override
    public byte[] canonicalize(byte[] json) throws CanonicalizationException {
        if (json == null || json.length == 0) {
            throw new CanonicalizationException("Cannot canonicalize null or empty JSON payload");
        }
        try {
            String jsonStr = new String(json, StandardCharsets.UTF_8);
            JsonCanonicalizer jc = new JsonCanonicalizer(jsonStr);
            return jc.getEncodedString().getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new CanonicalizationException("RFC 8785 canonicalization failed: " + e.getMessage(), e);
        }
    }
}
