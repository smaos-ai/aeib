package ai.sovereign.aeib.core;

import java.time.Instant;
import java.time.Duration;
import java.util.Optional;

public interface FOUR_STATION_INTERFACES {
    
    public record CandidateAction(
        String capabilityIdentifier,
        long proposedEpoch,
        String noun,
        String verb,
        byte[] jcsPayload,
        String manifestDigest
    ) {}
    
    public enum DispatchDisposition {
        AUTHORIZED, REJECTED, SUSPENDED
    }
    
    public record InterlockDecision(
        DispatchDisposition disposition,
        String caid,
        long activeEpoch,
        String explanation
    ) {}
    
    public interface DispatchInterlock {
        InterlockDecision evaluate(CandidateAction action, SecurityContext ctx);
    }
    
    public record SecurityContext(String identity, String[] grants) {}
    
    public record IdempotencyKey(String caid, String operationId) {}
    
    public record ProbeBudget(
        int maxConcurrentProbes,
        int maxProbesPerMinute,
        Duration probeTimeout,
        Instant reconciliationDeadline
    ) {}
    
    public enum EffectDisposition {
        CONFIRMED, REFUTED, CONFLICT, INDETERMINATE
    }
    
    public record SemanticState(
        byte[] rawTargetPayload,
        byte[] authoritativeProof,
        String targetStatusString
    ) {}
    
    public record ReconciledState(
        EffectDisposition disposition,
        byte[] authoritativeProof,
        Instant reconciledAt
    ) {}
    
    public interface TargetStatusClient {
        SemanticState querySemanticState(IdempotencyKey key);
    }
    
    public interface SemanticStateEvaluator {
        EffectDisposition evaluate(byte[] intendedJcsPayload, SemanticState observedState);
    }
    
    public interface EffectReconciler {
        ReconciledState resolveIndeterminate(String operationId, IdempotencyKey key, ProbeBudget budget);
    }
    
    public enum EventPhase {
        PROPOSED, DISPATCHED, INDETERMINATE, RECONCILED, FINALIZED
    }
    
    public record LifecycleEvent(
        String operationId,
        EventPhase phase,
        byte[] eventDataHash,
        Instant timestamp
    ) {}
    
    public record ScittReceipt(byte[] coseSign1, byte[] inclusionProof) {}

    public record HybridSignature(
        byte[] ed25519Signature,
        byte[] mlDsa65Signature, // null in v1.0
        String keyId,
        long keyEpoch
    ) {}
    
    public record ContinuityReceipt(
        String operationId,
        long epoch,
        byte[] chainTip,
        String signatureAlgorithm,
        String hashAlgorithm,
        HybridSignature signature,
        byte[] signedStatement,
        Optional<ScittReceipt> scittReceipt
    ) {}
    
    public interface ContinuousLedger {
        void appendEvent(LifecycleEvent event);
        ContinuityReceipt generateReceipt(String operationId);
    }
}
