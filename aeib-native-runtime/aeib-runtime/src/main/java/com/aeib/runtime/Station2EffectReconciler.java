package com.aeib.runtime;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import java.time.Instant;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class Station2EffectReconciler implements EffectReconciler {

    private final TargetStatusClient statusClient;
    private final SemanticStateEvaluator stateEvaluator;
    private final ConcurrentHashMap<String, Future<ReconciledState>> activeProbes = new ConcurrentHashMap<>();
    
    // Concurrency Limit
    private final Semaphore maxConcurrentSemaphore;
    
    // Rate Limiting (Token Bucket approximation for v1.0)
    private final int maxProbesPerMinute;
    private final AtomicInteger minuteTokenBucket = new AtomicInteger(0);
    private volatile long currentMinuteWindow = Instant.now().getEpochSecond() / 60;
    
    private final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();
    private final byte[] intendedJcsPayload; // Captured at construction or passed in

    public Station2EffectReconciler(TargetStatusClient statusClient, SemanticStateEvaluator stateEvaluator, int maxConcurrentProbes, int maxProbesPerMinute, byte[] intendedJcsPayload) {
        this.statusClient = statusClient;
        this.stateEvaluator = stateEvaluator;
        this.maxConcurrentSemaphore = new Semaphore(maxConcurrentProbes);
        this.maxProbesPerMinute = maxProbesPerMinute;
        this.intendedJcsPayload = intendedJcsPayload;
    }

    private synchronized boolean tryAcquireRateLimit() {
        long nowMinute = Instant.now().getEpochSecond() / 60;
        if (nowMinute > currentMinuteWindow) {
            currentMinuteWindow = nowMinute;
            minuteTokenBucket.set(0);
        }
        if (minuteTokenBucket.incrementAndGet() > maxProbesPerMinute) {
            minuteTokenBucket.decrementAndGet();
            return false; // Rate limit exceeded
        }
        return true;
    }

    @Override
    public ReconciledState resolveIndeterminate(String operationId, IdempotencyKey key, ProbeBudget budget) {
        // Enforce reconciliation deadline *before* dispatch
        if (Instant.now().isAfter(budget.reconciliationDeadline())) {
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
        }
        
        Future<ReconciledState> probeFuture = activeProbes.computeIfAbsent(operationId, opId -> 
            virtualThreadExecutor.submit(() -> executeReconciliationProbe(key, budget))
        );

        try {
            long deadlineRemainingMillis = Math.max(1L, budget.reconciliationDeadline().toEpochMilli() - Instant.now().toEpochMilli());
            long waitMillis = Math.min(budget.probeTimeout().toMillis(), deadlineRemainingMillis);
            return probeFuture.get(waitMillis, TimeUnit.MILLISECONDS);
        } catch (TimeoutException | CancellationException e) {
            probeFuture.cancel(true); 
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
        } catch (ExecutionException e) {
            if (e.getCause() instanceof InterruptedException) {
                return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
            }
            probeFuture.cancel(true);
            return new ReconciledState(EffectDisposition.CONFLICT, null, Instant.now());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            probeFuture.cancel(true);
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
        } catch (Exception e) {
            probeFuture.cancel(true);
            return new ReconciledState(EffectDisposition.CONFLICT, null, Instant.now());
        } finally {
            activeProbes.remove(operationId, probeFuture);
        }
    }

    private ReconciledState executeReconciliationProbe(IdempotencyKey key, ProbeBudget budget) {
        if (!tryAcquireRateLimit()) {
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now()); // Throttled
        }
        
        try {
            if (!maxConcurrentSemaphore.tryAcquire(budget.probeTimeout().toMillis(), TimeUnit.MILLISECONDS)) {
                return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
            }
            try {
                SemanticState targetState = statusClient.querySemanticState(key);
                EffectDisposition disposition = stateEvaluator.evaluate(intendedJcsPayload, targetState);
                return new ReconciledState(disposition, targetState.authoritativeProof(), Instant.now());
            } finally {
                maxConcurrentSemaphore.release();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
        } catch (Exception e) {
            return new ReconciledState(EffectDisposition.INDETERMINATE, null, Instant.now());
        }
    }
}
