package ai.sovereign.aeib.core.incident;

/**
 * Boundary verdicts for incident disclosure.
 * Evaluated under the stated model.
 */
public enum BoundaryVerdict {
    ALLOWED,
    DENIED,
    HELD,
    ESCALATED,
    NOT_EVALUATED,
    EFFECT_INDETERMINATE;

    public static BoundaryVerdict fromString(String val) {
        if (val == null) {
            throw new IllegalArgumentException("boundary_verdict cannot be null");
        }
        try {
            return BoundaryVerdict.valueOf(val.trim());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid boundary_verdict enum value: '" + val + "'", e);
        }
    }
}
