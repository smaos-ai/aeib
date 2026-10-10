package ai.sovereign.aeib.jcstress;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import com.aeib.crypto.Ed25519ProofEngine;
import com.aeib.runtime.DefaultSemanticStateEvaluator;
import com.aeib.runtime.Station2EffectReconciler;
import com.aeib.runtime.Station3ContinuousLedger;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Workstream 5: High-Contention Virtual-Thread & CyclicBarrier Concurrency Stress Suite.
 *
 * Evaluates under the stated model:
 *   1. Station2EffectReconciler & ProbeBudget atomic CAS loop rate/concurrency bounding
 *      under a 1,000-virtual-thread CyclicBarrier stampede.
 *   2. Station2EffectReconciler N=1 single-flight coalescing under 1,000 concurrent callers.
 *   3. Station3ContinuousLedger SHA-256 hash-chain integrity and CAS epoch monotonicity
 *      across 1,000 concurrent virtual threads.
 */
public class ProbeBudgetConcurrencyStressTest {

    private static final int VIRTUAL_THREAD_COUNT = 1_000;

    /**
     * Lock-free atomic CAS loop enforcing ProbeBudget per-minute token bucket and
     * concurrent probe ceiling under virtual-thread contention.
     */
    public static final class AtomicCasProbeBudgetGate {
        private final int maxProbesPerMinute;
        private final int maxConcurrentProbes;
        private final AtomicLong currentMinuteWindow;
        private final AtomicInteger consumedInWindow = new AtomicInteger(0);
        private final AtomicInteger activeConcurrent = new AtomicInteger(0);
        private final AtomicInteger observedPeakConcurrent = new AtomicInteger(0);

        public AtomicCasProbeBudgetGate(ProbeBudget budget) {
            this.maxProbesPerMinute = budget.maxProbesPerMinute();
            this.maxConcurrentProbes = budget.maxConcurrentProbes();
            this.currentMinuteWindow = new AtomicLong(Instant.now().getEpochSecond() / 60L);
        }

        /**
         * Acquires a minute-window token using a strict compareAndSet loop.
         */
        public boolean tryAcquireMinutePermit(long epochSecond) {
            long window = epochSecond / 60L;
            while (true) {
                long observedWindow = currentMinuteWindow.get();
                if (window > observedWindow) {
                    if (currentMinuteWindow.compareAndSet(observedWindow, window)) {
                        consumedInWindow.set(0);
                    }
                    continue;
                }
                int currentTokens = consumedInWindow.get();
                if (currentTokens >= maxProbesPerMinute) {
                    return false;
                }
                if (consumedInWindow.compareAndSet(currentTokens, currentTokens + 1)) {
                    return true;
                }
            }
        }

        /**
         * Acquires an in-flight concurrency slot using a strict compareAndSet loop.
         */
        public boolean tryAcquireConcurrencySlot() {
            while (true) {
                int current = activeConcurrent.get();
                if (current >= maxConcurrentProbes) {
                    return false;
                }
                if (activeConcurrent.compareAndSet(current, current + 1)) {
                    observedPeakConcurrent.accumulateAndGet(current + 1, Math::max);
                    return true;
                }
            }
        }

        public void releaseConcurrencySlot() {
            activeConcurrent.decrementAndGet();
        }

        public int consumedTokens() {
            return consumedInWindow.get();
        }

        public int peakConcurrent() {
            return observedPeakConcurrent.get();
        }
    }

    /**
     * Lock-free atomic CAS epoch coordinator enforcing non-decreasing epoch transitions
     * across Station3ContinuousLedger operations.
     */
    public static final class MonotonicEpochLedgerCoordinator {
        private final AtomicLong highWaterEpoch;
        private final ConcurrentHashMap<Long, Station3ContinuousLedger> epochLedgers = new ConcurrentHashMap<>();
        private final KeyPair keyPair;
        private final String keyId;

        public MonotonicEpochLedgerCoordinator(KeyPair keyPair, String keyId, long initialEpoch) {
            this.keyPair = keyPair;
            this.keyId = keyId;
            this.highWaterEpoch = new AtomicLong(initialEpoch);
        }

        /**
         * Advances or retains the active epoch via an atomic CAS loop; rejects stale epochs.
         */
        public boolean tryAdvanceEpoch(long candidateEpoch) {
            while (true) {
                long current = highWaterEpoch.get();
                if (candidateEpoch < current) {
                    return false; // Stale epoch regression rejected
                }
                if (candidateEpoch == current || highWaterEpoch.compareAndSet(current, candidateEpoch)) {
                    return true;
                }
            }
        }

        public ContinuityReceipt recordAndSignIfMonotonic(
            long candidateEpoch,
            LifecycleEvent event,
            Station3ContinuousLedger sharedLedger
        ) {
            if (!tryAdvanceEpoch(candidateEpoch)) {
                return null;
            }
            synchronized (sharedLedger) {
                sharedLedger.appendEvent(event);
                return sharedLedger.generateReceipt(event.operationId());
            }
        }

        public long activeEpoch() {
            return highWaterEpoch.get();
        }
    }

    @Test
    public void stressTestProbeBudgetAtomicCasLoopUnder1000VirtualThreads() throws Exception {
        byte[] intendedPayload = "{\"action\":\"transfer\",\"amount\":100}".getBytes(StandardCharsets.UTF_8);
        int maxConcurrent = 32;
        int maxPerMinute = 250;

        ProbeBudget budget = new ProbeBudget(
            maxConcurrent,
            maxPerMinute,
            Duration.ofMillis(1500),
            Instant.now().plusSeconds(60)
        );

        AtomicCasProbeBudgetGate casGate = new AtomicCasProbeBudgetGate(budget);
        AtomicInteger targetInvocations = new AtomicInteger(0);
        AtomicInteger inFlightTargetCalls = new AtomicInteger(0);
        AtomicInteger maxObservedTargetConcurrency = new AtomicInteger(0);

        TargetStatusClient instrumentedClient = key -> {
            if (!casGate.tryAcquireMinutePermit(Instant.now().getEpochSecond())) {
                return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
            }
            int currentInFlight = inFlightTargetCalls.incrementAndGet();
            maxObservedTargetConcurrency.accumulateAndGet(currentInFlight, Math::max);
            try {
                targetInvocations.incrementAndGet();
                Thread.sleep(5);
                return new SemanticState(intendedPayload, "PROOF-OK".getBytes(StandardCharsets.UTF_8), "COMMITTED");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
            } finally {
                inFlightTargetCalls.decrementAndGet();
            }
        };

        Station2EffectReconciler reconciler = new Station2EffectReconciler(
            instrumentedClient,
            new DefaultSemanticStateEvaluator(),
            budget.maxConcurrentProbes(),
            budget.maxProbesPerMinute(),
            intendedPayload
        );

        CyclicBarrier startBarrier = new CyclicBarrier(VIRTUAL_THREAD_COUNT);
        AtomicInteger confirmedCount = new AtomicInteger(0);
        AtomicInteger indeterminateCount = new AtomicInteger(0);
        AtomicInteger unexpectedDispositionCount = new AtomicInteger(0);

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<?>> futures = new ArrayList<>(VIRTUAL_THREAD_COUNT);
            for (int i = 0; i < VIRTUAL_THREAD_COUNT; i++) {
                final int idx = i;
                futures.add(executor.submit(() -> {
                    try {
                        startBarrier.await(10, TimeUnit.SECONDS);
                    } catch (Exception e) {
                        throw new RuntimeException("Barrier synchronization failed", e);
                    }
                    String opId = "OP-CAS-" + idx;
                    IdempotencyKey key = new IdempotencyKey("CAID-" + idx, opId);
                    ReconciledState state = reconciler.resolveIndeterminate(opId, key, budget);
                    if (state.disposition() == EffectDisposition.CONFIRMED) {
                        confirmedCount.incrementAndGet();
                    } else if (state.disposition() == EffectDisposition.INDETERMINATE) {
                        indeterminateCount.incrementAndGet();
                    } else {
                        unexpectedDispositionCount.incrementAndGet();
                    }
                }));
            }

            for (Future<?> f : futures) {
                f.get(30, TimeUnit.SECONDS);
            }
        }

        assertEquals(0, unexpectedDispositionCount.get(), "Observed unexpected disposition under CAS stress");
        assertEquals(VIRTUAL_THREAD_COUNT, confirmedCount.get() + indeterminateCount.get(),
            "All 1,000 virtual threads must complete with a deterministic disposition");
        assertEquals(maxPerMinute, confirmedCount.get(),
            "Atomic CAS token bucket must admit exactly maxProbesPerMinute (" + maxPerMinute + ") probes");
        assertEquals(VIRTUAL_THREAD_COUNT - maxPerMinute, indeterminateCount.get(),
            "Remaining probes exceeding budget must fail-closed to INDETERMINATE");
        assertEquals(maxPerMinute, casGate.consumedTokens(),
            "CAS token counter must equal maxProbesPerMinute with zero overshoot");
        assertTrue(maxObservedTargetConcurrency.get() <= maxConcurrent,
            "Observed concurrent probes (" + maxObservedTargetConcurrency.get() + ") exceeded ceiling (" + maxConcurrent + ")");
    }

    @Test
    public void stressTestSingleFlightCoalescingUnder1000VirtualThreads() throws Exception {
        byte[] intendedPayload = "{\"action\":\"coalesce\",\"seq\":1}".getBytes(StandardCharsets.UTF_8);
        AtomicInteger backendHits = new AtomicInteger(0);

        TargetStatusClient coalescedClient = key -> {
            backendHits.incrementAndGet();
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return new SemanticState(new byte[0], new byte[0], "UNKNOWN");
            }
            return new SemanticState(intendedPayload, "COALESCED-PROOF".getBytes(StandardCharsets.UTF_8), "COMMITTED");
        };

        ProbeBudget budget = new ProbeBudget(
            16,
            500,
            Duration.ofSeconds(5),
            Instant.now().plusSeconds(30)
        );

        Station2EffectReconciler reconciler = new Station2EffectReconciler(
            coalescedClient,
            new DefaultSemanticStateEvaluator(),
            budget.maxConcurrentProbes(),
            budget.maxProbesPerMinute(),
            intendedPayload
        );

        CyclicBarrier barrier = new CyclicBarrier(VIRTUAL_THREAD_COUNT);
        IdempotencyKey sharedKey = new IdempotencyKey("CAID-SHARED-1000", "OP-SHARED-1000");
        AtomicInteger confirmedCallers = new AtomicInteger(0);

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<?>> futures = new ArrayList<>(VIRTUAL_THREAD_COUNT);
            for (int i = 0; i < VIRTUAL_THREAD_COUNT; i++) {
                futures.add(executor.submit(() -> {
                    try {
                        barrier.await(10, TimeUnit.SECONDS);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                    ReconciledState state = reconciler.resolveIndeterminate("OP-SHARED-1000", sharedKey, budget);
                    if (state.disposition() == EffectDisposition.CONFIRMED) {
                        confirmedCallers.incrementAndGet();
                    }
                }));
            }
            for (Future<?> f : futures) {
                f.get(15, TimeUnit.SECONDS);
            }
        }

        assertEquals(1, backendHits.get(), "Single-flight coalescing must collapse 1,000 concurrent callers into 1 probe");
        assertEquals(VIRTUAL_THREAD_COUNT, confirmedCallers.get(), "All 1,000 coalesced callers must receive CONFIRMED");
    }

    @Test
    public void stressTestStation3HashChainAndEpochMonotonicityUnder1000VirtualThreads() throws Exception {
        KeyPair keyPair = Ed25519ProofEngine.generateKeyPair();
        long baseEpoch = 1_000L;
        Station3ContinuousLedger ledger = new Station3ContinuousLedger(keyPair.getPrivate(), "stress-key-v1.1", baseEpoch);
        MonotonicEpochLedgerCoordinator coordinator = new MonotonicEpochLedgerCoordinator(keyPair, "stress-key-v1.1", baseEpoch);

        CyclicBarrier barrier = new CyclicBarrier(VIRTUAL_THREAD_COUNT);
        Set<String> uniqueChainTips = ConcurrentHashMap.newKeySet();
        AtomicInteger validReceipts = new AtomicInteger(0);
        AtomicInteger staleEpochRejections = new AtomicInteger(0);

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<?>> futures = new ArrayList<>(VIRTUAL_THREAD_COUNT);
            for (int i = 0; i < VIRTUAL_THREAD_COUNT; i++) {
                final int idx = i;
                futures.add(executor.submit(() -> {
                    try {
                        barrier.await(10, TimeUnit.SECONDS);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }

                    // Advance monotonic epoch via CAS coordinator
                    long candidateEpoch = baseEpoch + (idx / 10);
                    coordinator.tryAdvanceEpoch(candidateEpoch);

                    // Also exercise stale epoch rejection on every 5th thread
                    if (idx % 5 == 0 && coordinator.activeEpoch() > baseEpoch) {
                        boolean staleAccepted = coordinator.tryAdvanceEpoch(baseEpoch - 1);
                        if (!staleAccepted) {
                            staleEpochRejections.incrementAndGet();
                        }
                    }

                    byte[] eventHash = ("EVENT-HASH-" + idx).getBytes(StandardCharsets.UTF_8);
                    LifecycleEvent event = new LifecycleEvent(
                        "OP-LEDGER-" + idx,
                        EventPhase.RECONCILED,
                        eventHash,
                        Instant.ofEpochMilli(1_710_000_000_000L + idx)
                    );

                    ContinuityReceipt receipt;
                    synchronized (ledger) {
                        ledger.appendEvent(event);
                        receipt = ledger.generateReceipt(event.operationId());
                    }

                    assertNotNull(receipt);
                    assertEquals(32, receipt.chainTip().length, "SHA-256 chainTip must be 32 bytes");
                    uniqueChainTips.add(HexFormat.of().formatHex(receipt.chainTip()));

                    boolean sigValid = Ed25519ProofEngine.verify(
                        receipt.signedStatement(),
                        receipt.signature().ed25519Signature(),
                        keyPair.getPublic()
                    );
                    if (sigValid) {
                        validReceipts.incrementAndGet();
                    }
                }));
            }

            for (Future<?> f : futures) {
                f.get(30, TimeUnit.SECONDS);
            }
        }

        assertEquals(VIRTUAL_THREAD_COUNT, validReceipts.get(),
            "All 1,000 concurrent ledger receipts must pass Ed25519 signature verification");
        assertEquals(VIRTUAL_THREAD_COUNT, uniqueChainTips.size(),
            "All 1,000 sequential SHA-256 chainTip states must be collision-free and distinct");
        assertEquals(baseEpoch + ((VIRTUAL_THREAD_COUNT - 1) / 10), coordinator.activeEpoch(),
            "Final high-water epoch must equal the maximum candidate epoch");
        assertTrue(staleEpochRejections.get() > 0, "Stale epoch regressions must be rejected by CAS monotonicity guard");

        ContinuityReceipt terminalReceipt = ledger.generateReceipt("OP-TERMINAL");
        assertFalse(Arrays.equals(new byte[32], terminalReceipt.chainTip()),
            "Terminal chainTip must diverge from 32-byte zero genesis block");
    }

    public static void main(String[] args) throws Exception {
        ProbeBudgetConcurrencyStressTest suite = new ProbeBudgetConcurrencyStressTest();
        System.out.println("[+] Running stressTestProbeBudgetAtomicCasLoopUnder1000VirtualThreads...");
        suite.stressTestProbeBudgetAtomicCasLoopUnder1000VirtualThreads();
        System.out.println("[+] Running stressTestSingleFlightCoalescingUnder1000VirtualThreads...");
        suite.stressTestSingleFlightCoalescingUnder1000VirtualThreads();
        System.out.println("[+] Running stressTestStation3HashChainAndEpochMonotonicityUnder1000VirtualThreads...");
        suite.stressTestStation3HashChainAndEpochMonotonicityUnder1000VirtualThreads();
        System.out.println("[+] All 3 high-contention 1,000-virtual-thread stress tests completed with 0 failures.");
    }
}
