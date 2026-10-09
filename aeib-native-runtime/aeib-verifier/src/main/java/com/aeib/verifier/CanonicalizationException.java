package com.aeib.verifier;

/**
 * Exception thrown when canonicalization fails due to syntax or encoding errors.
 */
public class CanonicalizationException extends Exception {

    public CanonicalizationException(String message) {
        super(message);
    }

    public CanonicalizationException(String message, Throwable cause) {
        super(message, cause);
    }
}
