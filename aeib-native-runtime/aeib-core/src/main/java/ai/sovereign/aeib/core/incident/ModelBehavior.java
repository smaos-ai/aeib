package ai.sovereign.aeib.core.incident;

import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Model behavior plane in the incident evidence record.
 * Evaluated under the stated model.
 */
public record ModelBehavior(
    String proposalDigest,
    String modelOrAgentVersion,
    String inputContextDigest,
    List<Map<String, Object>> untrustedContentReferences
) {
    private static final Pattern HEX_64 = Pattern.compile("^[0-9a-f]{64}$");

    public ModelBehavior {
        if (proposalDigest == null || !HEX_64.matcher(proposalDigest).matches()) {
            throw new IllegalArgumentException("proposal_digest must be a 64-character lowercase hex string: " + proposalDigest);
        }
        if (modelOrAgentVersion == null || modelOrAgentVersion.isBlank()) {
            throw new IllegalArgumentException("model_or_agent_version cannot be empty");
        }
        if (inputContextDigest != null && !HEX_64.matcher(inputContextDigest).matches()) {
            throw new IllegalArgumentException("input_context_digest must be a 64-character lowercase hex string: " + inputContextDigest);
        }
        untrustedContentReferences = untrustedContentReferences == null ? List.of() : List.copyOf(untrustedContentReferences);
    }
}
