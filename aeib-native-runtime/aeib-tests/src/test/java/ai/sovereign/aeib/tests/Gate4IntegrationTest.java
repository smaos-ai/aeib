package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import com.aeib.runtime.Station2EffectReconciler;
import com.aeib.runtime.DefaultSemanticStateEvaluator;
import com.aeib.runtime.Station3ContinuousLedger;
import com.aeib.crypto.Ed25519ProofEngine;
import com.aeib.verifier.*;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Map;
import java.util.LinkedHashMap;

/**
 * Gate 4 Integration Test: Unsimulated physical socket wire fault, out-of-band effect reconciliation,
 * continuous ledger recording, and offline standalone verification.
 */
public class Gate4IntegrationTest {

    private ServerSocket rawFaultTargetServer;
    private ServerSocket statusServer;
    private int faultTargetPort;
    private int statusTargetPort;
    private Thread targetThread;
    private Thread statusThread;
    
    private final AtomicInteger targetMutationCount = new AtomicInteger();
    private final AtomicInteger statusProbeCount = new AtomicInteger();

    public enum DispatchOutcome {
        COMPLETED,
        INDETERMINATE
    }

    /**
     * Dispatcher instrumenting real mutation dispatch attempts.
     */
    public static final class InstrumentedMutationDispatcher {
        private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();

        private final AtomicInteger dispatchAttempts = new AtomicInteger();

        public DispatchOutcome dispatch(HttpRequest request) {
            dispatchAttempts.incrementAndGet();
            try {
                client.send(request, HttpResponse.BodyHandlers.discarding());
                return DispatchOutcome.COMPLETED;
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return DispatchOutcome.INDETERMINATE;
            } catch (IOException fault) {
                // Physical wire severed, reset, or timeout
                return DispatchOutcome.INDETERMINATE;
            }
        }

        public int dispatchAttempts() {
            return dispatchAttempts.get();
        }
    }

    /**
     * Reads HTTP headers up to the "\r\n\r\n" terminator, bounded to 16KB to prevent runaway loops.
     */
    private static String readHttpHeaders(InputStream in) throws IOException {
        StringBuilder request = new StringBuilder();
        byte[] buffer = new byte[1024];
        int maxHeaderBytes = 16384;
        int totalRead = 0;

        while (!request.toString().contains("\r\n\r\n")) {
            int n = in.read(buffer);
            if (n == -1) {
                break;
            }
            totalRead += n;
            if (totalRead > maxHeaderBytes) {
                throw new IOException("HTTP header section exceeds 16KB limit");
            }
            request.append(new String(buffer, 0, n, StandardCharsets.US_ASCII));
        }

        return request.toString();
    }

    private final AtomicInteger wireCloseEvents = new AtomicInteger();
    private volatile byte[] recordedTargetPayload = new byte[0];

    private void handleFaultRequest(Socket client) {
        try {
            client.setSoTimeout(2000);
            InputStream in = client.getInputStream();
            ByteArrayOutputStream rawBuf = new ByteArrayOutputStream();
            byte[] buffer = new byte[1024];
            int headerEndIdx = -1;
            while (headerEndIdx == -1) {
                int n = in.read(buffer);
                if (n == -1) break;
                rawBuf.write(buffer, 0, n);
                if (rawBuf.size() > 16384) {
                    throw new IOException("HTTP header section exceeds 16KB limit");
                }
                String current = rawBuf.toString(StandardCharsets.US_ASCII);
                headerEndIdx = current.indexOf("\r\n\r\n");
            }
            String rawStr = rawBuf.toString(StandardCharsets.US_ASCII);
            if (rawStr.contains("POST") && headerEndIdx != -1) {
                int contentLength = 0;
                for (String line : rawStr.substring(0, headerEndIdx).split("\r\n")) {
                    if (line.toLowerCase(java.util.Locale.ROOT).startsWith("content-length:")) {
                        contentLength = Integer.parseInt(line.substring(15).trim());
                    }
                }
                byte[] allRead = rawBuf.toByteArray();
                int bodyStart = headerEndIdx + 4;
                ByteArrayOutputStream bodyBuf = new ByteArrayOutputStream();
                if (allRead.length > bodyStart) {
                    bodyBuf.write(allRead, bodyStart, allRead.length - bodyStart);
                }
                while (bodyBuf.size() < contentLength) {
                    int n = in.read(buffer, 0, Math.min(buffer.length, contentLength - bodyBuf.size()));
                    if (n == -1) break;
                    bodyBuf.write(buffer, 0, n);
                }
                recordedTargetPayload = bodyBuf.toByteArray();
                targetMutationCount.incrementAndGet();
                // Sever the transport abruptly (TCP RST / FIN without HTTP response)
                client.setSoLinger(true, 0);
                client.close();
            }
        } catch (IOException e) {
            wireCloseEvents.incrementAndGet();
        }
    }

    private void handleStatusRequest(Socket client) {
        try {
            client.setSoTimeout(2000);
            InputStream in = client.getInputStream();
            String headers = readHttpHeaders(in);

            if (headers.contains("GET")) {
                statusProbeCount.incrementAndGet();

                OutputStream out = client.getOutputStream();
                int mutations = targetMutationCount.get();
                String statusStr = mutations > 0 ? "COMMITTED" : "NOT_FOUND";
                String payloadB64 = mutations > 0 ? Base64.getEncoder().encodeToString(recordedTargetPayload) : "";
                String body = "{\"status\":\"" + statusStr + "\", \"mutations\":" + mutations + ", \"payloadBase64\":\"" + payloadB64 + "\"}";
                String response = "HTTP/1.1 200 OK\r\n" +
                                  "Content-Length: " + body.length() + "\r\n" +
                                  "Content-Type: application/json\r\n\r\n" + body;
                out.write(response.getBytes(StandardCharsets.UTF_8));
                out.flush();
                client.close();
            }
        } catch (IOException e) {
            wireCloseEvents.incrementAndGet();
        }
    }

    @BeforeEach
    public void startRealHttpTargets() throws Exception {
        targetMutationCount.set(0);
        statusProbeCount.set(0);
        recordedTargetPayload = new byte[0];

        rawFaultTargetServer = new ServerSocket(0);
        faultTargetPort = rawFaultTargetServer.getLocalPort();
        
        statusServer = new ServerSocket(0);
        statusTargetPort = statusServer.getLocalPort();
        
        targetThread = new Thread(() -> {
            while (!rawFaultTargetServer.isClosed()) {
                try {
                    Socket client = rawFaultTargetServer.accept();
                    handleFaultRequest(client);
                } catch (IOException e) {
                    if (rawFaultTargetServer.isClosed()) {
                        return;
                    }
                }
            }
        });
        targetThread.start();
        
        statusThread = new Thread(() -> {
            while (!statusServer.isClosed()) {
                try {
                    Socket client = statusServer.accept();
                    handleStatusRequest(client);
                } catch (IOException e) {
                    if (statusServer.isClosed()) {
                        return;
                    }
                }
            }
        });
        statusThread.start();
    }

    @AfterEach
    public void stopRealHttpTargets() throws Exception {
        if (rawFaultTargetServer != null && !rawFaultTargetServer.isClosed()) {
            rawFaultTargetServer.close();
        }
        if (statusServer != null && !statusServer.isClosed()) {
            statusServer.close();
        }
        if (targetThread != null) {
            targetThread.interrupt();
            targetThread.join(1000);
        }
        if (statusThread != null) {
            statusThread.interrupt();
            statusThread.join(1000);
        }
    }

    @Test
    public void testRealNetworkFaultAndReconciliation() throws Exception {
        java.security.KeyPair keyPair = Ed25519ProofEngine.generateKeyPair();
        Station3ContinuousLedger ledger = new Station3ContinuousLedger(keyPair.getPrivate(), "test-key-gate4", 1000L);
        byte[] intendedPayload = "{\"test\":1}".getBytes(StandardCharsets.UTF_8);
        ObjectMapper jsonMapper = new ObjectMapper();

        TargetStatusClient realStatusClient = key -> {
            try {
                HttpClient httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
                HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + statusTargetPort + "/status"))
                    .header("Idempotency-Key", key.caid())
                    .GET()
                    .build();
                HttpResponse<String> res = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
                com.fasterxml.jackson.databind.JsonNode node = jsonMapper.readTree(res.body());
                String statusStr = node.path("status").asText("UNKNOWN");
                String payloadB64 = node.path("payloadBase64").asText("");
                byte[] observedPayload = payloadB64.isEmpty() ? new byte[0] : Base64.getDecoder().decode(payloadB64);
                return new SemanticState(observedPayload, res.body().getBytes(StandardCharsets.UTF_8), statusStr);
            } catch (Exception e) {
                return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
            }
        };

        ProbeBudget budget = new ProbeBudget(1, 10, Duration.ofSeconds(2), Instant.now().plusSeconds(10));
        Station2EffectReconciler reconciler = new Station2EffectReconciler(
            realStatusClient, new DefaultSemanticStateEvaluator(),
            budget.maxConcurrentProbes(), budget.maxProbesPerMinute(), intendedPayload
        );

        // ----------------------------------------------------------------------------------
        // Phase 0: Negative Check — Before any mutation, status server reports 0 mutations (NOT_FOUND -> REFUTED)
        // ----------------------------------------------------------------------------------
        IdempotencyKey preDispatchKey = new IdempotencyKey("CAID-PRE-000", "OP-GATE4-PRE");
        ReconciledState preResult = reconciler.resolveIndeterminate("OP-GATE4-PRE", preDispatchKey, budget);
        assertEquals(EffectDisposition.REFUTED, preResult.disposition(), "Zero recorded target mutations must yield REFUTED");
        statusProbeCount.set(0);

        InstrumentedMutationDispatcher dispatcher = new InstrumentedMutationDispatcher();
        
        // ----------------------------------------------------------------------------------
        // Phase 1: Direct Mutation Dispatch with Unsimulated Wire Disconnect (HTTP 504 / RST)
        // ----------------------------------------------------------------------------------
        HttpRequest postReq = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:" + faultTargetPort + "/mutate"))
            .header("Idempotency-Key", "CAID-REAL-001")
            .POST(HttpRequest.BodyPublishers.ofByteArray(intendedPayload))
            .build();
            
        DispatchOutcome dispatchOutcome = dispatcher.dispatch(postReq);
        assertEquals(DispatchOutcome.INDETERMINATE, dispatchOutcome, "Wire disconnect must yield INDETERMINATE");
        assertEquals(1, dispatcher.dispatchAttempts(), "Dispatcher must attempt dispatch exactly ONCE");
        assertEquals(1, targetMutationCount.get(), "Target must record exactly ONE mutation");
        assertArrayEquals(intendedPayload, recordedTargetPayload, "Target socket must receive exact intended payload bytes");

        // Record initial INDETERMINATE event in ledger
        ledger.appendEvent(new LifecycleEvent("OP-GATE4-REAL", EventPhase.INDETERMINATE, intendedPayload, Instant.now()));
        ContinuityReceipt indeterminateReceipt = ledger.generateReceipt("OP-GATE4-REAL");
        assertNotNull(indeterminateReceipt);

        // ----------------------------------------------------------------------------------
        // Phase 2: Station 2 Out-of-Band Effect Reconciliation (Observed vs Intended Payload)
        // ----------------------------------------------------------------------------------
        IdempotencyKey idKey = new IdempotencyKey("CAID-REAL-001", "OP-GATE4-REAL");
        ReconciledState result = reconciler.resolveIndeterminate("OP-GATE4-REAL", idKey, budget);
        
        assertEquals(1, statusProbeCount.get(), "Reconciler must probe status exactly ONCE");
        assertEquals(EffectDisposition.CONFIRMED, result.disposition(), "Evaluator must output CONFIRMED when target payload matches");

        // Negative Check — Tampered target payload must yield CONFLICT
        recordedTargetPayload = "{\"test\":999}".getBytes(StandardCharsets.UTF_8);
        ReconciledState conflictResult = reconciler.resolveIndeterminate("OP-GATE4-CONFLICT", new IdempotencyKey("CAID-CONFLICT", "OP-GATE4-CONFLICT"), budget);
        assertEquals(EffectDisposition.CONFLICT, conflictResult.disposition(), "Mismatched target payload must yield CONFLICT");
        recordedTargetPayload = intendedPayload;

        // ----------------------------------------------------------------------------------
        // Phase 3: Station 3 Continuous Ledger Resolution Receipt Generation (Action 25)
        // ----------------------------------------------------------------------------------
        ledger.appendEvent(new LifecycleEvent("OP-GATE4-REAL", EventPhase.RECONCILED, result.authoritativeProof(), Instant.now()));
        ContinuityReceipt receipt = ledger.generateReceipt("OP-GATE4-REAL");
        
        assertNotNull(receipt, "Receipt must be generated");
        assertEquals("OP-GATE4-REAL", receipt.operationId(), "Receipt operationId must match");
        assertFalse(java.util.Arrays.equals(indeterminateReceipt.chainTip(), receipt.chainTip()), "Resolution receipt must advance chainTip from INDETERMINATE receipt");

        // ----------------------------------------------------------------------------------
        // Phase 4: Standalone Offline Receipt Verification
        // ----------------------------------------------------------------------------------
        byte[] serializedReceiptJson = writeArtifactsForVerification(receipt, keyPair.getPublic());
        
        ParsedReceipt parsedReceipt = new ReceiptParser().parse(serializedReceiptJson, new Rfc8785Canonicalizer());
        ReceiptVerificationResult verifierResult = new ReceiptVerifier().verifyParsed(parsedReceipt, keyPair.getPublic());
        assertTrue(verifierResult.valid(), "Standalone verifier must accept receipt under valid public key");
        assertNull(verifierResult.failureReason(), "Failure reason must be null for valid receipt");
    }

    private byte[] writeArtifactsForVerification(ContinuityReceipt receipt, java.security.PublicKey pubKey) {
        try {
            ObjectMapper mapper = new ObjectMapper();
            Map<String, Object> receiptMap = new LinkedHashMap<>();
            receiptMap.put("operationId", receipt.operationId());
            receiptMap.put("epoch", receipt.epoch());
            receiptMap.put("chainTip", Base64.getEncoder().encodeToString(receipt.chainTip()));
            receiptMap.put("signatureAlgorithm", receipt.signatureAlgorithm());
            receiptMap.put("hashAlgorithm", receipt.hashAlgorithm());
            
            Map<String, Object> sigMap = new LinkedHashMap<>();
            sigMap.put("ed25519Signature", Base64.getEncoder().encodeToString(receipt.signature().ed25519Signature()));
            sigMap.put("keyId", receipt.signature().keyId());
            sigMap.put("keyEpoch", receipt.signature().keyEpoch());
            receiptMap.put("signature", sigMap);
            
            receiptMap.put("signedStatement", Base64.getEncoder().encodeToString(receipt.signedStatement()));

            String receiptJson = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(receiptMap);
            byte[] receiptJsonBytes = receiptJson.getBytes(StandardCharsets.UTF_8);

            String pem = "-----BEGIN PUBLIC KEY-----\n" +
                Base64.getMimeEncoder(64, new byte[]{'\n'}).encodeToString(pubKey.getEncoded()) +
                "\n-----END PUBLIC KEY-----\n";

            Path[] targetDirs = new Path[] {
                Paths.get("build/test-results"),
                Paths.get("../build/test-results"),
                Paths.get("aeib-native-runtime/build/test-results")
            };

            for (Path dir : targetDirs) {
                try {
                    Files.createDirectories(dir);
                    Files.writeString(dir.resolve("receipt.json"), receiptJson, StandardCharsets.UTF_8);
                    Files.writeString(dir.resolve("ledger-public.pem"), pem, StandardCharsets.UTF_8);
                } catch (Exception ignored) {
                }
            }

            return receiptJsonBytes;
        } catch (Exception e) {
            System.err.println("Notice: Could not write verification artifacts to disk: " + e.getMessage());
            return new byte[0];
        }
    }
}
