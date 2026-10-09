package com.aeib.verifier;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.PublicKey;

import static org.junit.jupiter.api.Assertions.*;

public class VerifierCliTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    public void testAllManifestVectors() throws Exception {
        Path vectorsBase = Paths.get("src/test/resources/vectors");
        if (!Files.exists(vectorsBase)) {
            // Fallback for runner working directory variation
            vectorsBase = Paths.get("aeib-verifier/src/test/resources/vectors");
        }
        assertTrue(Files.exists(vectorsBase), "Vectors directory must exist at " + vectorsBase.toAbsolutePath());

        Path manifestPath = vectorsBase.resolve("manifest.json");
        assertTrue(Files.exists(manifestPath), "manifest.json must exist");

        JsonNode manifest = MAPPER.readTree(manifestPath.toFile());
        JsonNode vectors = manifest.get("vectors");
        assertTrue(vectors.isArray(), "Vectors node must be array");
        assertTrue(vectors.size() >= 9, "Must have at least 9 deterministic test vectors");

        for (JsonNode vec : vectors) {
            String name = vec.get("name").asText();
            int expectedExit = vec.get("expectedExitCode").asInt();
            String desc = vec.get("description").asText();

            Path vecDir = vectorsBase.resolve(name);
            Path receiptPath = vecDir.resolve("receipt.json");
            Path pubKeyPath = vecDir.resolve("public.pem");

            assertTrue(Files.exists(receiptPath), "Receipt must exist for vector: " + name);
            assertTrue(Files.exists(pubKeyPath), "Public key must exist for vector: " + name);

            int actualExit = VerifierCli.verify(receiptPath, pubKeyPath);
            assertEquals(expectedExit, actualExit, 
                "Vector [" + name + "] (" + desc + ") expected exit code " + expectedExit + " but got " + actualExit);
        }
    }

    @Test
    public void testNonRegularFileRejection(@TempDir Path tempDir) throws Exception {
        Path validPubKey = findVectorPubKey();
        
        // Directory as receipt path
        Path dirPath = tempDir.resolve("not-a-file");
        Files.createDirectories(dirPath);
        
        int exit = VerifierCli.verify(dirPath, validPubKey);
        assertEquals(4, exit, "Directory input must be rejected with exit code 4");
    }

    @Test
    public void testMissingFileRejection(@TempDir Path tempDir) throws Exception {
        Path validPubKey = findVectorPubKey();
        Path missingPath = tempDir.resolve("does-not-exist.json");

        int exit = VerifierCli.verify(missingPath, validPubKey);
        assertEquals(4, exit, "Missing input file must be rejected with exit code 4");
    }

    @Test
    public void testOversizedInputRejection(@TempDir Path tempDir) throws Exception {
        Path validPubKey = findVectorPubKey();
        Path oversizedFile = tempDir.resolve("oversized_receipt.json");
        
        // Write file with size just exceeding 50MB (50MB + 1 byte)
        long size = 50L * 1024 * 1024 + 1;
        try (OutputStream out = Files.newOutputStream(oversizedFile)) {
            byte[] chunk = new byte[64 * 1024];
            long written = 0;
            while (written < size) {
                int toWrite = (int) Math.min(chunk.length, size - written);
                out.write(chunk, 0, toWrite);
                written += toWrite;
            }
        }

        int exit = VerifierCli.verify(oversizedFile, validPubKey);
        assertEquals(4, exit, "Oversized file (>50MB) must be rejected with exit code 4");
    }

    @Test
    public void testSymlinkRejection(@TempDir Path tempDir) throws Exception {
        Path validPubKey = findVectorPubKey();
        Path validReceipt = findVectorReceipt("valid");
        
        Path symlinkReceipt = tempDir.resolve("symlink_receipt.json");
        try {
            Files.createSymbolicLink(symlinkReceipt, validReceipt.toAbsolutePath());
            int exit = VerifierCli.verify(symlinkReceipt, validPubKey);
            assertEquals(4, exit, "Symlink input must be rejected with exit code 4");
        } catch (UnsupportedOperationException ignored) {
            // Filesystem does not support symlinks in environment
        }
    }

    @Test
    public void testReceiptFileReaderUnit(@TempDir Path tempDir) throws Exception {
        Path smallFile = tempDir.resolve("small.txt");
        Files.writeString(smallFile, "hello aeib", StandardCharsets.UTF_8);

        byte[] bytes = ReceiptFileReader.readBounded(smallFile);
        assertEquals("hello aeib", new String(bytes, StandardCharsets.UTF_8));

        assertThrows(ReceiptFileReader.FileReadException.class, () -> {
            ReceiptFileReader.readBounded(tempDir.resolve("missing.txt"));
        });
    }

    @Test
    public void testReceiptParserUnit() {
        assertThrows(ReceiptParser.ReceiptParseException.class, () -> {
            ReceiptParser.parse("{\"not\": \"a receipt\"}".getBytes(StandardCharsets.UTF_8));
        });

        assertThrows(ReceiptParser.ReceiptParseException.class, () -> {
            ReceiptParser.parse("{\"valid\": 1} trailing".getBytes(StandardCharsets.UTF_8));
        });
    }

    @Test
    public void testPublicKeyReaderUnit() throws Exception {
        Path validPubKey = findVectorPubKey();
        PublicKey pk = PublicKeyReader.readFromPath(validPubKey);
        assertNotNull(pk);
        assertEquals("EdDSA", pk.getAlgorithm());

        assertThrows(PublicKeyReader.InvalidKeyException.class, () -> {
            PublicKeyReader.parse("corrupted-key-bytes");
        });
    }

    @Test
    public void testJcsCanonicalizationUnit() throws Exception {
        String input = "{\"b\": 2, \"a\": 1}";
        byte[] canonical = Jcs.canonicalize(input);
        assertEquals("{\"a\":1,\"b\":2}", new String(canonical, StandardCharsets.UTF_8));
    }

    private Path findVectorPubKey() {
        Path p = Paths.get("src/test/resources/vectors/valid/public.pem");
        if (Files.exists(p)) return p;
        p = Paths.get("aeib-verifier/src/test/resources/vectors/valid/public.pem");
        if (Files.exists(p)) return p;
        throw new IllegalStateException("Could not locate valid/public.pem");
    }

    private Path findVectorReceipt(String name) {
        Path p = Paths.get("src/test/resources/vectors/" + name + "/receipt.json");
        if (Files.exists(p)) return p;
        p = Paths.get("aeib-verifier/src/test/resources/vectors/" + name + "/receipt.json");
        if (Files.exists(p)) return p;
        throw new IllegalStateException("Could not locate vector receipt: " + name);
    }
}
