package com.aeib.runtime;

import java.util.Objects;

/**
 * Station 1 Five-Term Conjunctive Admissibility Gate.
 * Evaluates the formal predicate:
 * AuthorizationAdmissibility = GrantValid ∧ PolicyEpochFresh ∧ SourceEpochFresh ∧ ControlHealthy ∧ RiskProfileWithinGrantLimits
 *
 * Fails closed if any term is false, identifying the exact failing conjunct.
 */
public class Station1FiveTermAdmissibilityGate {

    public record CandidateActionRecord(
        String actionId,
        String capabilityIdentifier,
        long policyEpoch,
        long sourceEpoch,
        long notionalAmountMinorUnits,
        String caid
    ) {}

    public record GrantRecord(
        String grantId,
        String capabilityIdentifier,
        long maxNotionalAmountMinorUnits,
        boolean expired
    ) {}

    public record AdmissibilityVerdict(
        boolean admissible,
        String failingTerm,
        String details
    ) {}

    public AdmissibilityVerdict evaluate(
        CandidateActionRecord action,
        GrantRecord grant,
        long activePolicyEpoch,
        long activeSourceEpoch,
        boolean controlHealthy
    ) {
        if (action == null) {
            return new AdmissibilityVerdict(false, "ACTION_NULL", "CandidateActionRecord cannot be null");
        }

        // Term 1: GrantValid
        if (grant == null) {
            return new AdmissibilityVerdict(false, "GRANT_INVALID", "No valid grant provided for action");
        }
        if (grant.expired()) {
            return new AdmissibilityVerdict(false, "GRANT_EXPIRED", "Grant " + grant.grantId() + " is expired");
        }
        if (!Objects.equals(grant.capabilityIdentifier(), action.capabilityIdentifier()) && !"*".equals(grant.capabilityIdentifier())) {
            return new AdmissibilityVerdict(false, "GRANT_SCOPE_MISMATCH", 
                "Grant scope " + grant.capabilityIdentifier() + " does not cover action capability " + action.capabilityIdentifier());
        }

        // Term 2: PolicyEpochFresh
        if (action.policyEpoch() != activePolicyEpoch) {
            return new AdmissibilityVerdict(false, "POLICY_EPOCH_STALE",
                "Action policy epoch " + action.policyEpoch() + " does not match active epoch " + activePolicyEpoch);
        }

        // Term 3: SourceEpochFresh
        if (action.sourceEpoch() != activeSourceEpoch) {
            return new AdmissibilityVerdict(false, "SOURCE_EPOCH_STALE",
                "Action source epoch " + action.sourceEpoch() + " does not match active epoch " + activeSourceEpoch);
        }

        // Term 4: ControlHealthy
        if (!controlHealthy) {
            return new AdmissibilityVerdict(false, "CONTROL_UNHEALTHY",
                "Execution boundary control plane reported unhealthy or suspended telemetry status");
        }

        // Term 5: RiskProfileWithinGrantLimits
        if (action.notionalAmountMinorUnits() > grant.maxNotionalAmountMinorUnits()) {
            return new AdmissibilityVerdict(false, "RISK_LIMIT_EXCEEDED",
                "Notional amount " + action.notionalAmountMinorUnits() + " exceeds grant ceiling " + grant.maxNotionalAmountMinorUnits());
        }

        return new AdmissibilityVerdict(true, null, "All 5 admissibility terms satisfied under active epochs");
    }
}
