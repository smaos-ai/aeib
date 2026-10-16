package ai.sovereign.aeib.core.incident;

import java.util.regex.Pattern;

/**
 * Execution authority plane in the incident evidence record.
 * Evaluated under the stated model.
 */
public record ExecutionAuthority(
    String governingAuthorityId,
    AuthorityRevocationState authorityRevocationState,
    long policyEpoch,
    String delegationChainDigest,
    BoundaryVerdict boundaryVerdict,
    String rejectionCode
) {
    private static final Pattern HEX_64 = Pattern.compile("^[0-9a-f]{64}$");

    public ExecutionAuthority {
        if (authorityRevocationState == null) {
            throw new IllegalArgumentException("authority_revocation_state is required");
        }
        if (boundaryVerdict == null) {
            throw new IllegalArgumentException("boundary_verdict is required");
        }
        if (policyEpoch < 0) {
            throw new IllegalArgumentException("policy_epoch must be non-negative: " + policyEpoch);
        }
        if (delegationChainDigest != null && !HEX_64.matcher(delegationChainDigest).matches()) {
            throw new IllegalArgumentException("delegation_chain_digest must be a 64-character lowercase hex string: " + delegationChainDigest);
        }
    }
}
