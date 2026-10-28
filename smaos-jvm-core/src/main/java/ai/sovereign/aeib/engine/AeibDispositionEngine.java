package ai.sovereign.aeib.engine;

/**
 * Winandy Model Layer 1 Architectural Invariant Engine.
 * 5 Closed Policy Verdicts:
 *   ALLOWED, REDACTED, BLOCKED, QUARANTINED, ROUTED_FOR_HUMAN_APPROVAL
 * 
 * 7 Disposition Mapping Rules:
 *   1. OUTCOME_VERIFIED
 *   2. NOT_FOUND_AFTER_GRACE
 *   3. PROBE_PENDING
 *   4. RECONCILIATION_CONFLICT
 *   5. POLICY_REFUSED
 *   6. DISPATCHED_UNCONFIRMED
 *   7. PROBE_TIMEOUT_UNKNOWN
 */
public class AeibDispositionEngine {
    public enum PolicyVerdict {
        ALLOWED, REDACTED, BLOCKED, QUARANTINED, ROUTED_FOR_HUMAN_APPROVAL
    }

    public enum Disposition {
        OUTCOME_VERIFIED,
        NOT_FOUND_AFTER_GRACE,
        PROBE_PENDING,
        RECONCILIATION_CONFLICT,
        POLICY_REFUSED,
        DISPATCHED_UNCONFIRMED,
        PROBE_TIMEOUT_UNKNOWN
    }

    public static Disposition evaluate(int wireStatus, boolean probeFound, boolean isCommitted, boolean hasConflict) {
        if (hasConflict) {
            return Disposition.RECONCILIATION_CONFLICT;
        }
        if (wireStatus == 403) {
            return Disposition.POLICY_REFUSED;
        }
        if (wireStatus == 200 && isCommitted) {
            return Disposition.OUTCOME_VERIFIED;
        }
        if (wireStatus == 504 || wireStatus == 0) {
            if (probeFound && isCommitted) {
                return Disposition.OUTCOME_VERIFIED;
            } else if (probeFound && !isCommitted) {
                return Disposition.DISPATCHED_UNCONFIRMED;
            } else {
                return Disposition.NOT_FOUND_AFTER_GRACE;
            }
        }
        return Disposition.PROBE_TIMEOUT_UNKNOWN;
    }
}
