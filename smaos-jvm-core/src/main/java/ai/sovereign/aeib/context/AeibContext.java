package ai.sovereign.aeib.context;

/**
 * Immutable Context record for multi-agent stack propagation per JEP 506.
 */
public record AeibContext(
    String tenantId,
    String principalDid,
    String caid,
    String purposeMarking,
    String contractVersion
) {
    public static AeibContext of(String tenantId, String principalDid, String caid) {
        return new AeibContext(tenantId, principalDid, caid, "GENERAL_PROCESSING", "0.2.5");
    }
}
