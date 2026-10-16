package com.aeib.runtime;

import java.util.List;
import java.util.Set;

/**
 * Delegation Attenuation & Cascade Revocation Gate (AT39).
 * Enforces monotonic containment: Scope_child ⊆ Scope_parent.
 * Enforces cascade revocation: if any ancestor grant is revoked, all descendants fail closed.
 */
public class DelegationAttenuationCascade {

    public record DelegationNode(
        String nodeId,
        String principalId,
        String grantId,
        Set<String> allowedCapabilities,
        long maxAmountMinorUnits,
        boolean revoked
    ) {}

    public record DelegationVerdict(
        boolean valid,
        String failureCode,
        String failureReason
    ) {}

    public DelegationVerdict verifyChain(List<DelegationNode> chain) {
        if (chain == null || chain.isEmpty()) {
            return new DelegationVerdict(false, "EMPTY_DELEGATION_CHAIN", "Delegation chain cannot be empty");
        }

        // 1. Check cascade revocation down the chain
        for (int i = 0; i < chain.size(); i++) {
            DelegationNode node = chain.get(i);
            if (node.revoked()) {
                return new DelegationVerdict(
                    false,
                    "CASCADE_REVOKED",
                    "Delegation node at hop " + i + " (" + node.principalId() + ") has been revoked"
                );
            }
        }

        // 2. Check monotonic attenuation from parent to child
        for (int i = 0; i < chain.size() - 1; i++) {
            DelegationNode parent = chain.get(i);
            DelegationNode child = chain.get(i + 1);

            // Capabilities attenuation: child capabilities must be a subset of parent
            if (!parent.allowedCapabilities().contains("*")) {
                for (String childCap : child.allowedCapabilities()) {
                    if (!parent.allowedCapabilities().contains(childCap)) {
                        return new DelegationVerdict(
                            false,
                            "SCOPE_INFLATION_DETECTED",
                            "Child node " + child.principalId() + " requested capability " + childCap + 
                            " which exceeds parent " + parent.principalId() + " scope"
                        );
                    }
                }
            }

            // Numeric ceiling attenuation: child cannot exceed parent amount
            if (child.maxAmountMinorUnits() > parent.maxAmountMinorUnits()) {
                return new DelegationVerdict(
                    false,
                    "NUMERIC_CEILING_INFLATION",
                    "Child node " + child.principalId() + " amount limit " + child.maxAmountMinorUnits() + 
                    " exceeds parent limit " + parent.maxAmountMinorUnits()
                );
            }
        }

        return new DelegationVerdict(true, null, "Delegation chain monotonically attenuated and unrevoked");
    }
}
