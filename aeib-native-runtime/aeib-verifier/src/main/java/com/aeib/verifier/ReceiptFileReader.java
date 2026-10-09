package com.aeib.verifier;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Enforces regular-file and byte-limit invariants for untrusted verifier inputs.
 */
public final class ReceiptFileReader {

    public static final long MAX_RECEIPT_BYTES = 1L * 1024L * 1024L; // 1 MiB
    public static final long MAX_PUBLIC_KEY_BYTES = 64L * 1024L;     // 64 KiB

    private ReceiptFileReader() {}

    /**
     * Reads file bytes up to the specified byte bound, enforcing regular-file invariants.
     *
     * @param path File path to read
     * @param maximumBytes Maximum permitted bytes
     * @param description Human-readable description for error messages
     * @return Bounded byte array
     * @throws VerifierInputException if file does not exist, is not regular, is a symlink, or exceeds bounds
     */
    public static byte[] readLimited(
        Path path,
        long maximumBytes,
        String description
    ) throws VerifierInputException {
        if (path == null) {
            throw new VerifierInputException(description + " path is null");
        }
        if (!Files.exists(path)) {
            throw new VerifierInputException(description + " does not exist: " + path);
        }
        if (Files.isSymbolicLink(path)) {
            throw new VerifierInputException(description + " is a symbolic link: " + path);
        }
        if (!Files.isRegularFile(path)) {
            throw new VerifierInputException(description + " is not a regular file: " + path);
        }

        try {
            long size = Files.size(path);
            if (size > maximumBytes) {
                throw new VerifierInputException(
                    description + " exceeds maximum permitted size (" + size + " > " + maximumBytes + " bytes)"
                );
            }

            try (InputStream in = Files.newInputStream(path);
                 ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                long totalBytes = 0;
                int read;
                while ((read = in.read(buffer)) != -1) {
                    totalBytes += read;
                    if (totalBytes > maximumBytes) {
                        throw new VerifierInputException(
                            description + " stream content exceeds maximum permitted size of " + maximumBytes + " bytes"
                        );
                    }
                    out.write(buffer, 0, read);
                }
                return out.toByteArray();
            }
        } catch (VerifierInputException e) {
            throw e;
        } catch (IOException e) {
            throw new VerifierInputException("Could not read " + description + ": " + e.getMessage(), e);
        }
    }
}
