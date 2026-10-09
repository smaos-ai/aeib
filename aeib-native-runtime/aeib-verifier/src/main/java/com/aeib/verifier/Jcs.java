package com.aeib.verifier;

import org.erdtman.jcs.JsonCanonicalizer;

import java.nio.charset.StandardCharsets;

/**
 * Stateless RFC 8785 JSON Canonicalization Scheme (JCS) implementation for the verifier.
 */
public final class Jcs {

    private Jcs() {}

    /**
     * Canonicalizes a JSON string strictly according to RFC 8785.
     *
     * @param json Valid JSON string
     * @return UTF-8 encoded canonical JSON bytes
     * @throws Exception if JSON is malformed or canonicalization fails
     */
    public static byte[] canonicalize(String json) throws Exception {
        JsonCanonicalizer jc = new JsonCanonicalizer(json);
        return jc.getEncodedString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Canonicalizes UTF-8 JSON bytes strictly according to RFC 8785.
     *
     * @param jsonBytes Valid UTF-8 encoded JSON bytes
     * @return UTF-8 encoded canonical JSON bytes
     * @throws Exception if JSON is malformed or canonicalization fails
     */
    public static byte[] canonicalize(byte[] jsonBytes) throws Exception {
        return canonicalize(new String(jsonBytes, StandardCharsets.UTF_8));
    }
}
