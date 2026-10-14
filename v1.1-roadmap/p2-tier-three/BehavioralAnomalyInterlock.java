package ai.sovereign.aeib.v11.p2;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Priority P2 Behavioral Anomaly Interlock (Velocity Spike & Machine-Speed Loop Breaker).
 *
 * <p>Operates under the stated model: Monitors call frequencies and sliding-window event rates per
 * agent principal. When an automated machine-speed loop or burst frequency spike is detected, the
 * runtime immediately holds the dispatch pre-dispatch with disposition NOT_DISPATCHED (retry_safe: false).
 *
 * <p>Prevents cascading mutations and automated retry storms across the governed boundary.
 */
public final class BehavioralAnomalyInterlock {

    public record AnomalyVerdict(
            boolean permitted,
            String disposition,           // "CONFIRMED" or "NOT_DISPATCHED"
            boolean retrySafe,
            int rateObserved,
            int maxAllowedRate,
            String diagnosticMessage
    ) {}

    public static class BehavioralAnomalyException extends IllegalStateException {
        public BehavioralAnomalyException(String message) {
            super(message);
        }
    }

    private final int maxRatePerWindow;
    private final long windowSeconds;
    private final ConcurrentHashMap<String, Deque<Long>> principalTimestamps = new ConcurrentHashMap<>();

    public BehavioralAnomalyInterlock(int maxRatePerWindow, long windowSeconds) {
        if (maxRatePerWindow <= 0) {
            throw new IllegalArgumentException("maxRatePerWindow must be > 0");
        }
        if (windowSeconds <= 0) {
            throw new IllegalArgumentException("windowSeconds must be > 0");
        }
        this.maxRatePerWindow = maxRatePerWindow;
        this.windowSeconds = windowSeconds;
    }

    /**
     * Records candidate invocation timestamp and evaluates sliding-window velocity.
     * Latches to EFFECT_INDETERMINATE (retry_safe: false) if velocity threshold is breached.
     */
    public AnomalyVerdict recordAndAssertVelocity(String principalId, long currentTimestampSeconds) {
        Objects.requireNonNull(principalId, "principalId must not be null");

        Deque<Long> timestamps = principalTimestamps.computeIfAbsent(principalId, k -> new ArrayDeque<>());
        synchronized (timestamps) {
            long windowStart = currentTimestampSeconds - windowSeconds;

            // Purge expired timestamps outside current sliding window
            while (!timestamps.isEmpty() && timestamps.peekFirst() <= windowStart) {
                timestamps.pollFirst();
            }

            int currentRate = timestamps.size() + 1;
            if (currentRate > maxRatePerWindow) {
                return new AnomalyVerdict(
                        false,
                        "NOT_DISPATCHED",
                        false,
                        currentRate,
                        maxRatePerWindow,
                        "BEHAVIORAL_ANOMALY_SPIKE: principal '" + principalId + "' exceeded rate ceiling ("
                                + currentRate + "/" + maxRatePerWindow + " req/" + windowSeconds + "s); dispatch held (NOT_DISPATCHED)"
                );
            }

            timestamps.addLast(currentTimestampSeconds);
            return new AnomalyVerdict(
                    true,
                    "CONFIRMED",
                    true,
                    currentRate,
                    maxRatePerWindow,
                    "Velocity within configured bounds (" + currentRate + "/" + maxRatePerWindow + ")"
            );
        }
    }
}
