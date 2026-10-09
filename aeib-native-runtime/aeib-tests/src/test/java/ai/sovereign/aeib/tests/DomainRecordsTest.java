package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

public class DomainRecordsTest {

    @Test
    public void testManifestVerdict() {
        ManifestVerdict verdict = new ManifestVerdict(
            ManifestDisposition.PINNED,
            "sha256-dummy-digest",
            Instant.now(),
            null
        );
        assertEquals(ManifestDisposition.PINNED, verdict.disposition());
        assertEquals("sha256-dummy-digest", verdict.manifestDigest());
    }

    @Test
    public void testCandidateAction() {
        byte[] payload = "{\"key\":\"value\"}".getBytes();
        CandidateAction action = new CandidateAction(
            "op-123",
            "Payment",
            "execute",
            payload,
            1710000000L,
            "manifest-hash",
            "cap-456"
        );
        assertEquals("op-123", action.operationId());
        assertEquals("Payment", action.noun());
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
        assertNotNull(decision.rejectionReason());
    }

    @Test
    public void testProbeBudget() {
        ProbeBudget budget = new ProbeBudget(
            5,
            100,
            Duration.ofSeconds(2),
            Duration.ofMinutes(5)
        );
        assertEquals(5, budget.maxConcurrentProbes());
        assertEquals(Duration.ofSeconds(2), budget.probeTimeout());
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
            sig,
            new byte[]{4, 5, 6},
            Optional.empty()
        );
        assertEquals("op-123", receipt.operationId());
        assertTrue(receipt.scittReceipt().isEmpty());
    }
}
