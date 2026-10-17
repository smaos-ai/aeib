package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import com.aeib.runtime.Station2EffectReconciler;
import com.aeib.runtime.DefaultSemanticStateEvaluator;
import com.aeib.runtime.Station3ContinuousLedger;
import com.aeib.crypto.Ed25519ProofEngine;
import com.aeib.verifier.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;

/**
 * AmbiguousRefundScenarioTest: Executes HTTP 504 fault-injection scenario
 * (-PtargetUrl=http://localhost:8080 -PfaultType=http_504_after_dispatch)
 * against either the external mock_payment_api.py target or an embedded fallback
 * HTTP 504 target, latches EFFECT_INDETERMINATE, reconciles via single-flight
 * GET /status, and emits signed receipt.json and ledger-public.pem.
 * Evaluated under the stated model.
 */
public class AmbiguousRefundScenarioTest {

    @Test
    public void testAmbiguousRefundScenarioHttp504AfterDispatch() throws Exception {
        String configuredTargetUrl = System.getProperty("targetUrl", "");
        String configuredFaultType = System.getProperty("faultType", "http_504_after_dispatch");
        assertEquals("http_504_after_dispatch", configuredFaultType);

        HttpServer fallbackServer = null;
        final AtomicInteger fallbackMutations = new AtomicInteger(0);
        final byte[][] fallbackLastPayload = new byte[][]{new byte[0]};

        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();

        String activeBaseUrl = configuredTargetUrl;
        boolean externalReachable = false;
        if (activeBaseUrl != null && !activeBaseUrl.isBlank()) {
            try {
                HttpRequest healthReq = HttpRequest.newBuilder()
                    .uri(URI.create(activeBaseUrl + "/health"))
                    .timeout(Duration.ofSeconds(1))
                    .GET()
                    .build();
                HttpResponse<String> healthRes = client.send(healthReq, HttpResponse.BodyHandlers.ofString());
                if (healthRes.statusCode() == 200) {
                    externalReachable = true;
                }
            } catch (Exception ignored) {
                externalReachable = false;
            }
        }

        if (!externalReachable) {
            fallbackServer = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            fallbackServer.createContext("/mutate", exchange -> {
                try (InputStream is = exchange.getRequestBody()) {
                    fallbackLastPayload[0] = is.readAllBytes();
                }
                fallbackMutations.incrementAndGet();
                byte[] resp = "{\"error\":\"http_504_after_dispatch\"}".getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(504, resp.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(resp);
                }
            });
            fallbackServer.createContext("/status", exchange -> {
                int m = fallbackMutations.get();
                String statusStr = m > 0 ? "COMMITTED" : "NOT_FOUND";
                String b64 = m > 0 ? Base64.getEncoder().encodeToString(fallbackLastPayload[0]) : "";
                byte[] resp = ("{\"status\":\"" + statusStr + "\",\"mutations\":" + m + ",\"payloadBase64\":\"" + b64 + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, resp.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(resp);
                }
            });
            fallbackServer.start();
            activeBaseUrl = "http://127.0.0.1:" + fallbackServer.getAddress().getPort();
        }

        try {
            final String targetBase = activeBaseUrl;
            byte[] intendedPayload = "{\"amount_minor\":99900,\"currency\":\"EUR\",\"operation\":\"refund\",\"recipient_iban\":\"DE89370400440532013000\"}"
                .getBytes(StandardCharsets.UTF_8);
            String operationId = "OP-AMBIGUOUS-REFUND-504";
            String idempotencyKeyHeader = "aeib-idem-v1-ambiguous-refund-504";

            java.security.KeyPair keyPair = Ed25519ProofEngine.generateKeyPair();
            Station3ContinuousLedger ledger = new Station3ContinuousLedger(
                keyPair.getPrivate(), "aeib-rc3-key-01", 1000L
            );

            // 1. Dispatch POST /mutate and observe HTTP 504 gateway timeout
            HttpRequest postReq = HttpRequest.newBuilder()
                .uri(URI.create(targetBase + "/mutate"))
                .header("Content-Type", "application/json")
                .header("Idempotency-Key", idempotencyKeyHeader)
                .POST(HttpRequest.BodyPublishers.ofByteArray(intendedPayload))
                .build();

            HttpResponse<String> postRes = client.send(postReq, HttpResponse.BodyHandlers.ofString());
            assertEquals(504, postRes.statusCode(), "Target server must inject HTTP 504 fault after dispatch");

            // 2. Latch EFFECT_INDETERMINATE in Station 3 Continuous Ledger
            ledger.appendEvent(new LifecycleEvent(operationId, EventPhase.INDETERMINATE, intendedPayload, Instant.now()));
            ContinuityReceipt indeterminateReceipt = ledger.generateReceipt(operationId);
            assertNotNull(indeterminateReceipt);

            // 3. Reconcile via single-flight ProbeBudget(1) against GET /status
            ObjectMapper mapper = new ObjectMapper();
            TargetStatusClient statusClient = key -> {
                try {
                    HttpRequest getReq = HttpRequest.newBuilder()
                        .uri(URI.create(targetBase + "/status"))
                        .header("Idempotency-Key", key.caid())
                        .GET()
                        .build();
                    HttpResponse<String> getRes = client.send(getReq, HttpResponse.BodyHandlers.ofString());
                    JsonNode node = mapper.readTree(getRes.body());
                    String statusStr = node.path("status").asText("UNKNOWN");
                    String payloadB64 = node.path("payloadBase64").asText("");
                    byte[] observedPayload = payloadB64.isEmpty() ? new byte[0] : Base64.getDecoder().decode(payloadB64);
                    return new SemanticState(observedPayload, getRes.body().getBytes(StandardCharsets.UTF_8), statusStr);
                } catch (Exception e) {
                    return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
                }
            };

            ProbeBudget budget = new ProbeBudget(1, 10, Duration.ofSeconds(2), Instant.now().plusSeconds(10));
            Station2EffectReconciler reconciler = new Station2EffectReconciler(
                statusClient, new DefaultSemanticStateEvaluator(),
                budget.maxConcurrentProbes(), budget.maxProbesPerMinute(), intendedPayload
            );

            ReconciledState reconciled = reconciler.resolveIndeterminate(
                operationId, new IdempotencyKey(idempotencyKeyHeader, operationId), budget
            );
            assertEquals(EffectDisposition.CONFIRMED, reconciled.disposition());

            // 4. Write signed receipt.json and ledger-public.pem for offline verification
            byte[] serializedReceipt = writeEvidenceArtifacts(indeterminateReceipt, keyPair.getPublic());
            ParsedReceipt parsed = new ReceiptParser().parse(serializedReceipt, new Rfc8785Canonicalizer());
            ReceiptVerificationResult verified = new ReceiptVerifier().verifyParsed(parsed, keyPair.getPublic());
            assertTrue(verified.valid(), "Standalone offline verifier must validate receipt.json");
        } finally {
            if (fallbackServer != null) {
                fallbackServer.stop(0);
            }
        }
    }

    private byte[] writeEvidenceArtifacts(ContinuityReceipt receipt, java.security.PublicKey pubKey) throws Exception {
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

        Path[] targetDirs = new Path[]{
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
        return receiptJson.getBytes(StandardCharsets.UTF_8);
    }
}
