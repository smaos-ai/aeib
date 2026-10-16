package ai.sovereign.aeib.core.incident;

import java.util.Map;
import java.util.regex.Pattern;

/**
 * Observed consequence plane in the incident evidence record.
 * Evaluated under the stated model.
 */
public record ObservedConsequence(
    String dispatchIntentDigest,
    Map<String, Object> transportObservation,
    Map<String, Object> targetEvidence,
    Map<String, Object> reconciliationResult,
    String finalDisposition
) {
    private static final Pattern HEX_64 = Pattern.compile("^[0-9a-f]{64}$");

    public ObservedConsequence {
        if (dispatchIntentDigest != null && !HEX_64.matcher(dispatchIntentDigest).matches()) {
            throw new IllegalArgumentException("dispatch_intent_digest must be a 64-character lowercase hex string: " + dispatchIntentDigest);
        }
        if (finalDisposition == null || finalDisposition.isBlank()) {
            throw new IllegalArgumentException("final_disposition cannot be empty");
        }
        transportObservation = transportObservation == null ? null : Map.copyOf(transportObservation);
        targetEvidence = targetEvidence == null ? null : Map.copyOf(targetEvidence);
        reconciliationResult = reconciliationResult == null ? null : Map.copyOf(reconciliationResult);
    }
}
