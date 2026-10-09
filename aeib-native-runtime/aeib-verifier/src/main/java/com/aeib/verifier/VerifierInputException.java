package com.aeib.verifier;

/**
 * Thrown when an input file, format, schema, size, or readability constraint is violated.
 * Maps to verifier exit code 3.
 */
public class VerifierInputException extends Exception {

    public VerifierInputException(String message) {
        super(message);
    }

    public VerifierInputException(String message, Throwable cause) {
        super(message, cause);
    }
}
