package ai.sovereign.aeib.core.incident;

/**
 * Authority revocation states for incident disclosure.
 * Evaluated under the stated model.
 */
public enum AuthorityRevocationState {
    VALID,
    EXPIRED,
    REVOKED,
    SUPERSEDED,
    UNKNOWN;

    public static AuthorityRevocationState fromString(String val) {
        if (val == null) {
            throw new IllegalArgumentException("authority_revocation_state cannot be null");
        }
        try {
            return AuthorityRevocationState.valueOf(val.trim());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid authority_revocation_state enum value: '" + val + "'", e);
        }
    }
}
