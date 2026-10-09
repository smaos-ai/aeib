package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import com.aeib.runtime.Station2EffectReconciler;
import com.aeib.runtime.DefaultSemanticStateEvaluator;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.time.Instant;
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class Station2ConcurrencyTest {

    @Test
    public void testSingleFlightCoalescingAndTimeoutCancellation() throws Exception {
        byte[] payload = "{\"test\":1}".getBytes();
        SemanticStateEvaluator evaluator = new DefaultSemanticStateEvaluator();
        AtomicInteger networkCallCount = new AtomicInteger(0);
        
        // Mock a slow network target
        TargetStatusClient slowClient = key -> {
            networkCallCount.incrementAndGet();
            try {
                // Sleep longer than the probe timeout to force cancellation
                Thread.sleep(5000); 
            } catch (InterruptedException e) {
                // Thread interrupted by future.cancel(true)
                Thread.currentThread().interrupt();
                throw new RuntimeException("Interrupted by Reconciler", e);
            }
            return new SemanticState(payload, null, "SUCCESS");
        };

        // Budget: Max 10 concurrent, 100 per minute, 500ms timeout
        ProbeBudget budget = new ProbeBudget(
            10, 
            100, 
            Duration.ofMillis(500), 
            Instant.now().plusSeconds(60)
        );
        
        Station2EffectReconciler reconciler = new Station2EffectReconciler(
            slowClient, evaluator, budget.maxConcurrentProbes(), budget.maxProbesPerMinute(), payload
        );

        IdempotencyKey key = new IdempotencyKey("caid-123", "op-1");
        
        // Fire 100 concurrent virtual threads requesting reconciliation for the same operationId
        ExecutorService attackers = Executors.newVirtualThreadPerTaskExecutor();
        CountDownLatch latch = new CountDownLatch(100);
        ConcurrentLinkedQueue<ReconciledState> results = new ConcurrentLinkedQueue<>();
        
        for (int i = 0; i < 100; i++) {
            attackers.submit(() -> {
                results.add(reconciler.resolveIndeterminate("op-1", key, budget));
                latch.countDown();
            });
        }
        
        latch.await(2, TimeUnit.SECONDS);

        // 1. Single-Flight Coalescing: The network client should have only been invoked exactly ONCE
        assertEquals(1, networkCallCount.get(), "N=1 Coalescing failed: Target hit multiple times");
        
        // 2. Timeout & Cancellation: All 100 callers should gracefully receive INDETERMINATE after 500ms
        assertEquals(100, results.size());
        for (ReconciledState state : results) {
            assertEquals(EffectDisposition.INDETERMINATE, state.disposition(), "Slow probe did not timeout to INDETERMINATE");
        }
    }
}
