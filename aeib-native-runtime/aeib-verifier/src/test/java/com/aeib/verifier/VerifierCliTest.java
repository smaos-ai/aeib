package com.aeib.verifier;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

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
        Path vectorsBase = findVectorsBase();
        Path manifestPath = vectorsBase.resolve("manifest.json");
        assertTrue(Files.exists(manifestPath), "manifest.json must exist at " + manifestPath.toAbsolutePath());

        JsonNode manifest = MAPPER.readTree(manifestPath.toFile());
        JsonNode vectors = manifest.get("vectors");
        assertTrue(vectors.isArray(), "Vectors node must be array");
        assertTrue(vectors.size() >= 13, "Must have at least 13 deterministic test vectors");

        for (JsonNode vec : vectors) {
            String id = vec.get("id").asText();
            int expectedExit = vec.get("expectedExitCode").asInt();
            String desc = vec.get("description").asText();

            Path receiptPath = vectorsBase.resolve(vec.get("receipt").asText());
            Path pubKeyPath = vectorsBase.resolve(vec.get("publicKey").asText());

            int actualExit = VerifierCli.execute(
                "--receipt", receiptPath.toString(),
                "--pubkey", pubKeyPath.toString()
            );

            assertEquals(expectedExit, actualExit,
                "Vector [" + id + "] (" + desc + ") expected exit code " + expectedExit + " but got " + actualExit);
        }
    }

    @Test
    public void testUsageErrorsEmitExitCodeOne() {
        // Missing --pubkey option
        int exit1 = VerifierCli.execute("--receipt", "some/path.json");
        assertEquals(1, exit1, "Missing required option must yield exit code 1");

        // Missing --receipt option
        int exit2 = VerifierCli.execute("--pubkey", "some/key.pem");
        assertEquals(1, exit2, "Missing required option must yield exit code 1");

        // Unknown option
        int exit3 = VerifierCli.execute("--unknown-flag", "--receipt", "a", "--pubkey", "b");
        assertEquals(1, exit3, "Unknown option must yield exit code 1");

        // Duplicate --receipt option
        int exit4 = VerifierCli.execute("--receipt", "a", "--receipt", "b", "--pubkey", "c");
        assertEquals(1, exit4, "Duplicate option must yield exit code 1");

        // No arguments
        int exit5 = VerifierCli.execute();
        assertEquals(1, exit5, "No arguments must yield exit code 1");
    }

    @Test
    public void testReceiptFileReaderUnit(@TempDir Path tempDir) throws Exception {
        Path smallFile = tempDir.resolve("small.txt");
        Files.writeString(smallFile, "{\"test\": 1}", StandardCharsets.UTF_8);

        byte[] bytes = ReceiptFileReader.readLimited(smallFile, 1024, "test file");
        assertEquals("{\"test\": 1}", new String(bytes, StandardCharsets.UTF_8));

        // Missing file -> VerifierInputException
        assertThrows(VerifierInputException.class, () ->
            ReceiptFileReader.readLimited(tempDir.resolve("missing.txt"), 1024, "missing")
        );

        // Directory -> VerifierInputException
        Path dir = tempDir.resolve("dir");
        Files.createDirectories(dir);
        assertThrows(VerifierInputException.class, () ->
            ReceiptFileReader.readLimited(dir, 1024, "directory")
        );

        // Oversized -> VerifierInputException
        assertThrows(VerifierInputException.class, () ->
            ReceiptFileReader.readLimited(smallFile, 5, "oversized")
        );
    }

    @Test
    public void testReceiptParserUnit() {
        ReceiptParser parser = new ReceiptParser();
        CanonicalJsonSerializer canonicalizer = new Rfc8785Canonicalizer();

        // Not a receipt
        assertThrows(VerifierInputException.class, () ->
            parser.parse("{\"not\": \"a receipt\"}".getBytes(StandardCharsets.UTF_8), canonicalizer)
        );

        // Trailing tokens
        assertThrows(VerifierInputException.class, () ->
            parser.parse("{\"valid\": 1} trailing".getBytes(StandardCharsets.UTF_8), canonicalizer)
        );
    }

    @Test
    public void testPublicKeyReaderUnit() throws Exception {
        Path vectorsBase = findVectorsBase();
        Path validPubKey = vectorsBase.resolve("valid/public.pem");
        byte[] validPemBytes = Files.readAllBytes(validPubKey);

        PublicKey pk = PublicKeyReader.parse(validPemBytes);
        assertNotNull(pk);
        assertEquals("EdDSA", pk.getAlgorithm());

        // Reject raw 32-byte key
        assertThrows(VerifierInputException.class, () ->
            PublicKeyReader.parse(new byte[32])
        );

        // Reject certificate
        assertThrows(VerifierInputException.class, () ->
            PublicKeyReader.parse("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----".getBytes(StandardCharsets.UTF_8))
        );

        // Reject private key
        assertThrows(VerifierInputException.class, () ->
            PublicKeyReader.parse("-----BEGIN PRIVATE KEY-----\nMIIB\n-----END PRIVATE KEY-----".getBytes(StandardCharsets.UTF_8))
        );
    }

    @Test
    public void testRfc8785CanonicalizerUnit() throws Exception {
        Rfc8785Canonicalizer canonicalizer = new Rfc8785Canonicalizer();
        assertEquals("RFC 8785 JCS", canonicalizer.algorithmId());

        byte[] input = "{\"b\": 2, \"a\": 1}".getBytes(StandardCharsets.UTF_8);
        byte[] canonical = canonicalizer.canonicalize(input);
        assertEquals("{\"a\":1,\"b\":2}", new String(canonical, StandardCharsets.UTF_8));
    }

    @Test
    public void testReceiptVerifierRejectsUnsupportedAlgorithm() {
        CanonicalJsonSerializer mockAlg = new CanonicalJsonSerializer() {
            @Override
            public String algorithmId() {
                return "UNSUPPORTED_ALGO";
            }
            @Override
            public byte[] canonicalize(byte[] json) {
                return json;
            }
        };

        assertThrows(IllegalArgumentException.class, () ->
            new ReceiptVerifier(mockAlg)
        );
    }

    private Path findVectorsBase() {
        Path p = Paths.get("src/test/resources/vectors");
        if (Files.exists(p)) return p;
        p = Paths.get("aeib-verifier/src/test/resources/vectors");
        if (Files.exists(p)) return p;
        throw new IllegalStateException("Could not locate vectors directory");
    }
}
