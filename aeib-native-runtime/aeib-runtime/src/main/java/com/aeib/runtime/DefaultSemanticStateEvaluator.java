package com.aeib.runtime;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.SemanticStateEvaluator;
import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.EffectDisposition;
import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.SemanticState;

import java.util.Arrays;
import java.security.MessageDigest;

/**
 * Concrete implementation of SemanticStateEvaluator for AEIB v1.0.
 * Performs strict byte-for-byte or cryptographic hash comparison between the 
 * intended JCS payload and the observed Target SemanticState.
 */
public class DefaultSemanticStateEvaluator implements SemanticStateEvaluator {

    @Override
    public EffectDisposition evaluate(byte[] intendedJcsPayload, SemanticState observedState) {
        if (observedState == null || observedState.targetStatusString() == null) {
            return EffectDisposition.INDETERMINATE; // Ambiguous or unreachable
        }

        String status = observedState.targetStatusString().toUpperCase();

        switch (status) {
            case "PENDING":
            case "PROCESSING":
            case "UNKNOWN":
                // Target acknowledges the key but hasn't finalized a state.
                return EffectDisposition.INDETERMINATE;
                
            case "FAILED":
            case "REJECTED":
            case "NOT_FOUND":
                // Target authoritatively reports the operation failed or does not exist.
                return EffectDisposition.REFUTED;
                
            case "SUCCESS":
            case "COMPLETED":
                // Target reports success. We MUST verify the payload to prevent blind confirmation.
                if (observedState.rawTargetPayload() == null) {
                    return EffectDisposition.CONFLICT; // Claimed success but provided no evidence
                }
                
                // Strict Cryptographic or Byte-for-Byte comparison
                if (Arrays.equals(intendedJcsPayload, observedState.rawTargetPayload())) {
                    return EffectDisposition.CONFIRMED;
                } else {
                    // The target has a finalized state for this idempotency key, but it 
                    // DOES NOT match the intended payload. This is a severe Conflict.
                    return EffectDisposition.CONFLICT;
                }
                
            default:
                // Any unrecognized status string is inherently indeterminate.
                return EffectDisposition.INDETERMINATE;
        }
    }
}
