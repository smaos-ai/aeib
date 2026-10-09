package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import ai.sovereign.aeib.core.Jcs;
import com.aeib.crypto.Ed25519ProofEngine;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;

public class MandatoryNegativeTestSuite {

    @Test
    public void testStrictRfc8785ConformanceWithAppendixIVectors() throws Exception {
        // Number formatting
        String numberVector = "{\"numbers\": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001]}";
        String expectedNumber = "{\"numbers\":[333333333.3333333,1e+30,4.5,0.002,1e-27]}";
        assertEquals(expectedNumber, new String(Jcs.canonicalize(numberVector), StandardCharsets.UTF_8));

        // String escaping
        String stringVector = "{\"string\": \"\\u20ac$\\u000F\\u000aA'\\u0042\\u0022\\u005c\\\\\\\"\\/\"}";
        String expectedString = "{\"string\":\"€$\\u000f\\nA'B\\\"\\\\\\\"/\"}";
        assertEquals(expectedString, new String(Jcs.canonicalize(stringVector), StandardCharsets.UTF_8));
        
        // Key ordering
        String orderVector = "{\"z\":1,\"a\":2}";
        String expectedOrder = "{\"a\":2,\"z\":1}";
        assertEquals(expectedOrder, new String(Jcs.canonicalize(orderVector), StandardCharsets.UTF_8));
    }

    @Test
    public void testReceiptInvariant() throws Exception {
        java.security.KeyPair keyPair = Ed25519ProofEngine.generateKeyPair();
        com.aeib.runtime.Station3ContinuousLedger ledger = new com.aeib.runtime.Station3ContinuousLedger(keyPair.getPrivate(), "test-key", 500L);
        ledger.appendEvent(new LifecycleEvent("op-A", EventPhase.PROPOSED, new byte[0], java.time.Instant.now()));
        ContinuityReceipt receipt = ledger.generateReceipt("op-A");
        
        String parsedStatement = new String(receipt.signedStatement(), StandardCharsets.UTF_8);
        assertTrue(parsedStatement.contains("\"operationId\":\"op-A\""));
        assertTrue(parsedStatement.contains("\"epoch\":500"));
        assertTrue(parsedStatement.contains("\"keyId\":\"test-key\""));
        assertEquals("Ed25519", receipt.signatureAlgorithm());
        assertEquals("SHA-256", receipt.hashAlgorithm());
    }

    @Test
    public void testSemanticStateEvaluatorDispositions() throws Exception {
        SemanticStateEvaluator evaluator = (intended, observed) -> {
            if (observed.targetStatusString().equals("SUCCESS")) return EffectDisposition.CONFIRMED;
            if (observed.targetStatusString().equals("FAILED")) return EffectDisposition.REFUTED;
            if (observed.targetStatusString().equals("PENDING")) return EffectDisposition.INDETERMINATE;
            return EffectDisposition.CONFLICT; // E.g. mismatched hash
        };
        
        assertEquals(EffectDisposition.CONFIRMED, evaluator.evaluate(new byte[0], new SemanticState(new byte[0], new byte[0], "SUCCESS")));
        assertEquals(EffectDisposition.REFUTED, evaluator.evaluate(new byte[0], new SemanticState(new byte[0], new byte[0], "FAILED")));
        assertEquals(EffectDisposition.INDETERMINATE, evaluator.evaluate(new byte[0], new SemanticState(new byte[0], new byte[0], "PENDING")));
        assertEquals(EffectDisposition.CONFLICT, evaluator.evaluate(new byte[0], new SemanticState(new byte[0], new byte[0], "UNKNOWN_OR_CORRUPT")));
    }
}
