package ai.sovereign.aeib.core.incident;

import java.util.regex.Pattern;

/**
 * Shared Incident Evidence Record for AEIB.
 * Standardizes incident evidence disclosure across DORA, EU AI Act, and MITRE evaluations.
 * Evaluated under the stated model.
 */
public record IncidentEvidenceRecord(
    String schemaVersion,
    String incidentId,
    String exportedAt,
    String reproducibilityManifestSha256,
    ModelBehavior modelBehavior,
    ExecutionAuthority executionAuthority,
    ObservedConsequence observedConsequence,
    String disclaimer
) {
    public static final String MANDATORY_DISCLAIMER =
        "AEIB exports structured incident evidence. The customer’s authorized incident-management and legal functions determine classification, causation, reportability, and any regulatory submission.";

    public static final String CURRENT_SCHEMA_VERSION = "1.1.0-incident-evidence";

    private static final Pattern HEX_64 = Pattern.compile("^[0-9a-f]{64}$");

    public IncidentEvidenceRecord {
        if (schemaVersion == null || !schemaVersion.equals(CURRENT_SCHEMA_VERSION)) {
            throw new IllegalArgumentException("Invalid schema_version: " + schemaVersion);
        }
        if (incidentId == null || incidentId.isBlank()) {
            throw new IllegalArgumentException("incident_id cannot be empty");
        }
        if (exportedAt == null || exportedAt.isBlank()) {
            throw new IllegalArgumentException("exported_at cannot be empty");
        }
        if (reproducibilityManifestSha256 != null && !HEX_64.matcher(reproducibilityManifestSha256).matches()) {
            throw new IllegalArgumentException("reproducibility_manifest_sha256 must be a 64-character lowercase hex string: " + reproducibilityManifestSha256);
        }
        if (modelBehavior == null) {
            throw new IllegalArgumentException("Missing or invalid evidence plane: model_behavior");
        }
        if (executionAuthority == null) {
            throw new IllegalArgumentException("Missing or invalid evidence plane: execution_authority");
        }
        if (observedConsequence == null) {
            throw new IllegalArgumentException("Missing or invalid evidence plane: observed_consequence");
        }
        if (!MANDATORY_DISCLAIMER.equals(disclaimer)) {
            throw new IllegalArgumentException("Disclaimer modified or missing mandatory legal framing statement");
        }
    }
}
