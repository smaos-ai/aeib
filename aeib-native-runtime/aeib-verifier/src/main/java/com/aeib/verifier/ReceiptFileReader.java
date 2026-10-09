package com.aeib.verifier;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Enforces regular-file and byte-limit invariants for untrusted verifier input.
 */
public final class ReceiptFileReader {

    public static final long MAX_FILE_BYTES = 50 * 1024 * 1024; // 50MB

    private ReceiptFileReader() {}

    /**
     * Reads the entire contents of a file bounded by MAX_FILE_BYTES.
     * Rejects non-existent paths, non-regular files, symlinks, and files exceeding MAX_FILE_BYTES.
     *
     * @param path File path to read
     * @return Bounded byte array
     * @throws FileReadException if file does not exist, is not regular, is a symlink, or exceeds bounds
     */
    public static byte[] readBounded(Path path) throws FileReadException {
        return readBounded(path, MAX_FILE_BYTES);
    }

    public static byte[] readBounded(Path path, long maxBytes) throws FileReadException {
        if (path == null) {
            throw new FileReadException("Path must not be null");
        }
        if (!Files.exists(path)) {
            throw new FileReadException("File does not exist: " + path);
        }
        if (Files.isSymbolicLink(path)) {
            throw new FileReadException("Symbolic links are not permitted: " + path);
        }
        if (!Files.isRegularFile(path)) {
            throw new FileReadException("Not a regular file: " + path);
        }

        try {
            long size = Files.size(path);
            if (size > maxBytes) {
                throw new FileReadException("File size (" + size + " bytes) exceeds limit of " + maxBytes + " bytes: " + path);
            }

            try (InputStream in = Files.newInputStream(path);
                 ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                long totalBytes = 0;
                int read;
                while ((read = in.read(buffer)) != -1) {
                    totalBytes += read;
                    if (totalBytes > maxBytes) {
                        throw new FileReadException("Stream content exceeds limit of " + maxBytes + " bytes: " + path);
                    }
                    out.write(buffer, 0, read);
                }
                return out.toByteArray();
            }
        } catch (FileReadException e) {
            throw e;
        } catch (IOException e) {
            throw new FileReadException("I/O error reading file " + path + ": " + e.getMessage(), e);
        }
    }

    public static class FileReadException extends Exception {
        public FileReadException(String message) {
            super(message);
        }

        public FileReadException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
