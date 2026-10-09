package com.aeib.verifier;

import java.nio.file.Path;
import java.util.Objects;

/**
 * Validated immutable arguments passed to ReceiptVerifier.
 */
public record VerifierArguments(
    Path receiptPath,
    Path publicKeyPath
) {
    public VerifierArguments {
        Objects.requireNonNull(receiptPath, "receiptPath must not be null");
        Objects.requireNonNull(publicKeyPath, "publicKeyPath must not be null");
    }
}
