package com.aeib.verifier;

/**
 * Interface defining canonical JSON serialization for AEIB evidence verification.
 * Implementations must be stateless and immutable.
 */
public interface CanonicalJsonSerializer {

    /**
     * Pinned algorithm identifier (e.g. "RFC 8785 JCS").
     */
    String algorithmId();

    /**
     * Canonicalizes UTF-8 JSON bytes according to the pinned algorithm.
     *
     * @param json UTF-8 encoded JSON bytes
     * @return Canonicalized UTF-8 encoded bytes
     * @throws CanonicalizationException if input is malformed or canonicalization fails
     */
    byte[] canonicalize(byte[] json) throws CanonicalizationException;
}
