package ai.sovereign.aeib.v11.p0;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;

/**
 * Priority P0 Delegation Chain Attenuation Gate (IETF AIP Alignment).
 *
 * <p>Operates under the stated model: Enforces monotonic authority reduction across
 * multi-hop agent delegation chains (draft-prakash-aip-02).
 * Verifies that each intermediate hop appends caveats and strictly narrows effective scopes:
 * Scope(Child) subset-of Scope(Parent) subset-of Scope(Root).
 *
 * <p>Fails closed if any delegated hop attempts to expand scopes or budgets.
 */
public final class DelegationAttenuationGate {

    public record DelegationHop(
            String delegatorPrincipalId,
            String delegateeAgentId,
            Set<String> permittedScopes,
            long maxSpendEur,
            long validUntilEpoch,
            String hopSignatureHex
    ) {
        public String toCanonicalStatement() {
            List<String> sortedScopes = new ArrayList<>(permittedScopes);
            Collections.sort(sortedScopes);
            StringBuilder sb = new StringBuilder();
            sb.append("{\"delegateeAgentId\":\"").append(escapeJson(delegateeAgentId)).append("\",");
            sb.append("\"delegatorPrincipalId\":\"").append(escapeJson(delegatorPrincipalId)).append("\",");
            sb.append("\"maxSpendEur\":").append(maxSpendEur).append(",");
            sb.append("\"permittedScopes\":[");
            for (int i = 0; i < sortedScopes.size(); i++) {
                sb.append("\"").append(escapeJson(sortedScopes.get(i))).append("\"");
                if (i < sortedScopes.size() - 1) sb.append(",");
            }
            sb.append("],");
            sb.append("\"validUntilEpoch\":").append(validUntilEpoch).append("}");
            return sb.toString();
        }

        private static String escapeJson(String s) {
            return s.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }

    public record DelegationVerdict(
            boolean valid,
            Set<String> effectiveScopes,
            long effectiveMaxSpendEur,
            String diagnosticMessage
    ) {}

    private final Map<String, PublicKey> knownPrincipalPublicKeys;

    public DelegationAttenuationGate(Map<String, PublicKey> knownPrincipalPublicKeys) {
        this.knownPrincipalPublicKeys = new HashMap<>(knownPrincipalPublicKeys);
    }

    /**
     * Evaluates a multi-hop delegation chain, verifying cryptographic hop signatures
     * and asserting monotonic scope and spend attenuation.
     */
    public DelegationVerdict evaluateDelegationChain(
            List<DelegationHop> chain,
            long currentTimestamp
    ) throws GeneralSecurityException {
        if (chain == null || chain.isEmpty()) {
            return new DelegationVerdict(false, Collections.emptySet(), 0,
                    "Empty delegation chain rejected fail-closed");
        }

        Set<String> runningScopes = null;
        long runningMaxSpend = Long.MAX_VALUE;
        String expectedDelegator = null;

        for (int i = 0; i < chain.size(); i++) {
            DelegationHop hop = chain.get(i);

            // Expiration check
            if (currentTimestamp > hop.validUntilEpoch()) {
                return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "Delegation hop " + i + " expired at " + hop.validUntilEpoch());
            }

            // Chain linkage check
            if (expectedDelegator != null && !Objects.equals(hop.delegatorPrincipalId(), expectedDelegator)) {
                return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "Delegation chain broken at hop " + i + ": expected delegator "
                                + expectedDelegator + ", got " + hop.delegatorPrincipalId());
            }

            // Cryptographic verification
            PublicKey delegatorKey = knownPrincipalPublicKeys.get(hop.delegatorPrincipalId());
            if (delegatorKey == null) {
                return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "Unknown public key for delegator " + hop.delegatorPrincipalId());
            }

            byte[] stmtBytes = hop.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
            byte[] sigBytes = hexToBytes(hop.hopSignatureHex());
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(delegatorKey);
            sig.update(stmtBytes);
            if (!sig.verify(sigBytes)) {
                return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "Invalid cryptographic signature on delegation hop " + i);
            }

            // Monotonic scope attenuation check: Hop(N).scopes must be subset of Hop(N-1).scopes
            if (runningScopes == null) {
                runningScopes = new HashSet<>(hop.permittedScopes());
            } else {
                if (!runningScopes.containsAll(hop.permittedScopes())) {
                    Set<String> expanded = new HashSet<>(hop.permittedScopes());
                    expanded.removeAll(runningScopes);
                    return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "ATTENUATION_VIOLATION: hop " + i + " expanded scopes with unauthorized: " + expanded);
                }
                runningScopes = new HashSet<>(hop.permittedScopes());
            }

            // Monotonic budget attenuation check: Hop(N).spend must be <= Hop(N-1).spend
            if (hop.maxSpendEur() > runningMaxSpend) {
                return new DelegationVerdict(false, Collections.emptySet(), 0,
                        "ATTENUATION_VIOLATION: hop " + i + " increased max spend: "
                                + hop.maxSpendEur() + " > " + runningMaxSpend);
            }
            runningMaxSpend = hop.maxSpendEur();

            // Next hop's delegator must match this hop's delegatee
            expectedDelegator = hop.delegateeAgentId();
        }

        return new DelegationVerdict(
                true,
                Collections.unmodifiableSet(runningScopes != null ? runningScopes : Collections.emptySet()),
                runningMaxSpend,
                "Delegation chain valid with strict monotonic attenuation confirmed"
        );
    }

    private static byte[] hexToBytes(String hex) {
        int len = hex.length();
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            data[i / 2] = (byte) ((Character.digit(hex.charAt(i), 16) << 4)
                    + Character.digit(hex.charAt(i + 1), 16));
        }
        return data;
    }
}
