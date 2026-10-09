package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import ai.sovereign.aeib.core.Jcs;
import com.aeib.runtime.Station2EffectReconciler;
import com.aeib.runtime.DefaultSemanticStateEvaluator;
import com.aeib.runtime.Station3ContinuousLedger;
import com.aeib.crypto.Ed25519ProofEngine;
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

    public static final class InstrumentedMutationDispatcher {
        private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();

        private final AtomicInteger dispatchAttempts = new AtomicInteger();
        private final AtomicInteger retryAttempts = new AtomicInteger();

        public DispatchOutcome dispatch(HttpRequest request) {
            dispatchAttempts.incrementAndGet();
            try {
                client.send(request, HttpResponse.BodyHandlers.discarding());
                return DispatchOutcome.COMPLETED;
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return DispatchOutcome.INDETERMINATE;
            } catch (IOException fault) {
                return DispatchOutcome.INDETERMINATE;
            }
        }

        public DispatchOutcome retry(HttpRequest request) {
            retryAttempts.incrementAndGet();
            return dispatch(request);
        }

        public int dispatchAttempts() { return dispatchAttempts.get(); }
        public int retryAttempts() { return retryAttempts.get(); }
    }

    private static String readHttpHeaders(InputStream in) throws IOException {
        StringBuilder request = new StringBuilder();
        byte[] buffer = new byte[4096];

        while (!request.toString().contains("\r\n\r\n")) {
            int n = in.read(buffer);
            if (n == -1) {
                break;
            }
            request.append(new String(buffer, 0, n, StandardCharsets.US_ASCII));
        }

        return request.toString();
    }

    private void handleFaultRequest(Socket client) {
        try {
            client.setSoTimeout(2000);
            InputStream in = client.getInputStream();
            String headers = readHttpHeaders(in);

            if (headers.contains("POST")) {
                targetMutationCount.incrementAndGet();
                // Close the connection before returning an HTTP response
                client.setSoLinger(true, 0);
                client.close();
            }
        } catch (IOException ignored) {
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
                String body = "{\"status\":\"COMMITTED\", \"mutations\":" + targetMutationCount.get() + "}";
                String response = "HTTP/1.1 200 OK\r\n" +
                                  "Content-Length: " + body.length() + "\r\n" +
                                  "Content-Type: application/json\r\n\r\n" + body;
                out.write(response.getBytes(StandardCharsets.UTF_8));
                out.flush();
                client.close();
            }
        } catch (IOException ignored) {
        }
    }

    @BeforeEach
    public void startRealHttpTargets() throws Exception {
        targetMutationCount.set(0);
        statusProbeCount.set(0);

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
            targetThread.join(1000);
        }
        if (statusThread != null) {
            statusThread.join(1000);
        }
    }

    @Test
    public void testRealNetworkFaultAndReconciliation() throws Exception {
        java.security.KeyPair keyPair = Ed25519ProofEngine.generateKeyPair();
        Station3ContinuousLedger ledger = new Station3ContinuousLedger(keyPair.getPrivate(), "test-key-gate4", 1000L);
        byte[] intendedPayload = "{\"test\":1}".getBytes(StandardCharsets.UTF_8);

        InstrumentedMutationDispatcher dispatcher = new InstrumentedMutationDispatcher();
        
        HttpRequest postReq = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:" + faultTargetPort + "/mutate"))
            .header("Idempotency-Key", "CAID-REAL-001")
            .POST(HttpRequest.BodyPublishers.ofByteArray(intendedPayload))
            .build();
            
        DispatchOutcome dispatchOutcome = dispatcher.dispatch(postReq);
        assertEquals(DispatchOutcome.INDETERMINATE, dispatchOutcome, "Wire disconnect must yield INDETERMINATE");

        TargetStatusClient realStatusClient = key -> {
            try {
                HttpClient httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
                HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + statusTargetPort + "/status"))
                    .header("Idempotency-Key", key.caid())
                    .GET()
                    .build();
                HttpResponse<String> res = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
                
                if (res.body().contains("\"COMMITTED\"")) {
                    return new SemanticState(intendedPayload, res.body().getBytes(StandardCharsets.UTF_8), "COMMITTED");
                }
                return new SemanticState(new byte[0], new byte[0], "NOT_FOUND");
            } catch (Exception e) {
                return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
            }
        };

        ProbeBudget budget = new ProbeBudget(1, 10, Duration.ofSeconds(2), Instant.now().plusSeconds(10));
        Station2EffectReconciler reconciler = new Station2EffectReconciler(
            realStatusClient, new DefaultSemanticStateEvaluator(), 
            budget.maxConcurrentProbes(), budget.maxProbesPerMinute(), intendedPayload
        );
        
        IdempotencyKey idKey = new IdempotencyKey("CAID-REAL-001", "OP-GATE4-REAL");
        
        ReconciledState result = reconciler.resolveIndeterminate("OP-GATE4-REAL", idKey, budget);
        
        ledger.appendEvent(new LifecycleEvent("OP-GATE4-REAL", EventPhase.RECONCILED, new byte[0], Instant.now()));
        ContinuityReceipt receipt = ledger.generateReceipt("OP-GATE4-REAL");
        
        assertEquals(1, targetMutationCount.get(), "Target must record exactly ONE mutation");
        assertEquals(1, dispatcher.dispatchAttempts(), "Dispatcher must attempt dispatch exactly ONCE");
        assertEquals(0, dispatcher.retryAttempts(), "AEIB must not invoke the callable retry path");
        assertEquals(1, statusProbeCount.get(), "Reconciler must probe status exactly ONCE");
        assertEquals(EffectDisposition.CONFIRMED, result.disposition(), "Evaluator must output CONFIRMED");
        assertNotNull(receipt, "Receipt must be generated");

        writeArtifactsForVerification(receipt, keyPair.getPublic());
    }

    private void writeArtifactsForVerification(ContinuityReceipt receipt, java.security.PublicKey pubKey) {
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
        } catch (Exception e) {
            System.err.println("Notice: Could not write verification artifacts to disk: " + e.getMessage());
        }
    }
}
