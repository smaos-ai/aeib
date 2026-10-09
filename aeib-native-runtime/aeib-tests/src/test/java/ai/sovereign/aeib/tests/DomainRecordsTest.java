package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

public class DomainRecordsTest {

    @Test
    public void testSecurityContextAndIdempotencyKey() {
        SecurityContext ctx = new SecurityContext("user-1", new String[]{"grant-a"});
        assertEquals("user-1", ctx.identity());
        assertArrayEquals(new String[]{"grant-a"}, ctx.grants());

        IdempotencyKey key = new IdempotencyKey("caid-123", "op-456");
        assertEquals("caid-123", key.caid());
        assertEquals("op-456", key.operationId());
    }

    @Test
    public void testCandidateAction() {
        byte[] payload = "{\"key\":\"value\"}".getBytes();
        CandidateAction action = new CandidateAction(
            "cap-456",
            1710000000L,
            "Payment",
            "execute",
            payload,
            "manifest-hash"
        );
        assertEquals("cap-456", action.capabilityIdentifier());
        assertEquals(1710000000L, action.proposedEpoch());
        assertEquals("Payment", action.noun());
        assertEquals("execute", action.verb());
        assertArrayEquals(payload, action.jcsPayload());
        assertEquals("manifest-hash", action.manifestDigest());
    }

    @Test
    public void testInterlockDecision() {
        InterlockDecision decision = new InterlockDecision(
            DispatchDisposition.REJECTED,
            "caid-hash",
            1710000000L,
            "Policy epoch expired"
        );
        assertEquals(DispatchDisposition.REJECTED, decision.disposition());
        assertEquals("caid-hash", decision.caid());
        assertEquals(1710000000L, decision.activeEpoch());
        assertEquals("Policy epoch expired", decision.explanation());
    }

    @Test
    public void testProbeBudget() {
        Instant deadline = Instant.now().plus(Duration.ofMinutes(5));
        ProbeBudget budget = new ProbeBudget(
            5,
            100,
            Duration.ofSeconds(2),
            deadline
        );
        assertEquals(5, budget.maxConcurrentProbes());
        assertEquals(100, budget.maxProbesPerMinute());
        assertEquals(Duration.ofSeconds(2), budget.probeTimeout());
        assertEquals(deadline, budget.reconciliationDeadline());
    }

    @Test
    public void testContinuityReceipt() {
        HybridSignature sig = new HybridSignature(
            new byte[]{1, 2, 3},
            null,
            "key-1",
            1L
        );
        ContinuityReceipt receipt = new ContinuityReceipt(
            "op-123",
            500L,
            new byte[]{4, 5, 6},
            "Ed25519",
            "SHA-256",
            sig,
            new byte[]{7, 8, 9},
            Optional.empty()
        );
        assertEquals("op-123", receipt.operationId());
        assertEquals(500L, receipt.epoch());
        assertArrayEquals(new byte[]{4, 5, 6}, receipt.chainTip());
        assertEquals("Ed25519", receipt.signatureAlgorithm());
        assertEquals("SHA-256", receipt.hashAlgorithm());
        assertEquals(sig, receipt.signature());
        assertArrayEquals(new byte[]{7, 8, 9}, receipt.signedStatement());
        assertTrue(receipt.scittReceipt().isEmpty());
    }

    @Test
    public void testSemanticAndReconciledState() {
        byte[] raw = new byte[]{1};
        byte[] proof = new byte[]{2};
        SemanticState state = new SemanticState(raw, proof, "COMMITTED");
        assertArrayEquals(raw, state.rawTargetPayload());
        assertArrayEquals(proof, state.authoritativeProof());
        assertEquals("COMMITTED", state.targetStatusString());

        Instant now = Instant.now();
        ReconciledState reconciled = new ReconciledState(EffectDisposition.CONFIRMED, proof, now);
        assertEquals(EffectDisposition.CONFIRMED, reconciled.disposition());
        assertArrayEquals(proof, reconciled.authoritativeProof());
        assertEquals(now, reconciled.reconciledAt());
    }

    @Test
    public void testLifecycleEventAndScittReceipt() {
        Instant now = Instant.now();
        LifecycleEvent event = new LifecycleEvent("op-1", EventPhase.DISPATCHED, new byte[]{9}, now);
        assertEquals("op-1", event.operationId());
        assertEquals(EventPhase.DISPATCHED, event.phase());
        assertArrayEquals(new byte[]{9}, event.eventDataHash());
        assertEquals(now, event.timestamp());

        ScittReceipt scitt = new ScittReceipt(new byte[]{10}, new byte[]{11});
        assertArrayEquals(new byte[]{10}, scitt.coseSign1());
        assertArrayEquals(new byte[]{11}, scitt.inclusionProof());
    }
}
