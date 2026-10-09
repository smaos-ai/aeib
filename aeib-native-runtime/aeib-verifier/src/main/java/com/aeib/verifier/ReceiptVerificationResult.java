package com.aeib.verifier;

/**
 * Result of executing the ReceiptVerifier cryptographic and canonicalization checks.
 */
public record ReceiptVerificationResult(
    boolean valid,
    String failureReason
) {
    public static ReceiptVerificationResult success() {
        return new ReceiptVerificationResult(true, null);
    }

    public static ReceiptVerificationResult invalid(String reason) {
        return new ReceiptVerificationResult(false, reason);
    }
}
