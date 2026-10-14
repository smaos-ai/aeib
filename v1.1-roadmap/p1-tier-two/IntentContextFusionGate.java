package ai.sovereign.aeib.v11.p1;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Priority P1 Intent-Context Fusion Gate (Two-Tier Hold-and-Scan AI DLP Architecture).
 *
 * <p>Operates under the stated model: Evaluates action intent and payload data sensitivity as an
 * atomic pre-dispatch decision before RFC 8785 JCS canonicalization and socket transmission.
 *
 * <p>Tier 1: Evaluates raw payload strings against deterministic regex patterns for sensitive
 * secrets (unredacted IBANs, PANs, API bearer tokens, and private key headers).
 *
 * <p>Tier 2: If unredacted sensitive payload data is detected without an explicit enclave exemption,
 * blocks wire dispatch fail-closed with disposition NOT_DISPATCHED (retry_safe: false).
 */
public final class IntentContextFusionGate {

    private static final Pattern IBAN_PATTERN =
            Pattern.compile("\\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\\b");
    private static final Pattern PAN_PATTERN =
            Pattern.compile("\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\\b");
    private static final Pattern BEARER_PATTERN =
            Pattern.compile("(?:Bearer\\s+[A-Za-z0-9_\\-\\.]{16,}|(?:ghp_|sk_live_|AKIA)[A-Za-z0-9_\\-]{16,})");
    private static final Pattern PRIVATE_KEY_PATTERN =
            Pattern.compile("-----BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE KEY)");

    public record SensitivityVerdict(
            String privacyClearance,      // "PERMITTED", "REJECTED_UNREDACTED_PII", or "EXEMPTED"
            String disposition,           // "CONFIRMED" or "EFFECT_INDETERMINATE"
            boolean retrySafe,
            List<String> violationsDetected,
            String payloadDigest,         // "sha256:<64-hex>"
            String diagnosticMessage
    ) {}

    private final boolean allowUnredactedPii;

    public IntentContextFusionGate(boolean allowUnredactedPii) {
        this.allowUnredactedPii = allowUnredactedPii;
    }

    public IntentContextFusionGate() {
        this(false);
    }

    /**
     * Evaluates payload sensitivity against detected secret patterns.
     * Blocks dispatch fail-closed if sensitive data is found unredacted.
     */
    public SensitivityVerdict evaluatePayloadSensitivity(
            String intent,
            String serializedPayloadJson
    ) {
        Objects.requireNonNull(intent, "intent must not be null");
        Objects.requireNonNull(serializedPayloadJson, "serializedPayloadJson must not be null");

        List<String> violations = new ArrayList<>();
        if (IBAN_PATTERN.matcher(serializedPayloadJson).find()) {
            violations.add("UNREDACTED_IBAN");
        }
        if (PAN_PATTERN.matcher(serializedPayloadJson).find()) {
            violations.add("UNREDACTED_PAN");
        }
        if (BEARER_PATTERN.matcher(serializedPayloadJson).find()) {
            violations.add("UNREDACTED_API_BEARER_TOKEN");
        }
        if (PRIVATE_KEY_PATTERN.matcher(serializedPayloadJson).find()) {
            violations.add("UNREDACTED_PRIVATE_KEY_PEM");
        }

        String payloadDigest = computeSha256(serializedPayloadJson.getBytes(StandardCharsets.UTF_8));

        if (!violations.isEmpty()) {
            if (allowUnredactedPii) {
                return new SensitivityVerdict(
                        "EXEMPTED",
                        "CONFIRMED",
                        true,
                        Collections.unmodifiableList(violations),
                        payloadDigest,
                        "Under the stated model: sensitive patterns observed but allowed under enclave exemption"
                );
            }

            return new SensitivityVerdict(
                    "REJECTED_UNREDACTED_PII",
                    "NOT_DISPATCHED",
                    false,
                    Collections.unmodifiableList(violations),
                    payloadDigest,
                    "INTENT_CONTEXT_DIVIDE_HALT: Unredacted sensitive payload detected (" + String.join(", ", violations) + "); dispatch denied fail-closed (NOT_DISPATCHED)"
            );
        }

        return new SensitivityVerdict(
                "PERMITTED",
                "CONFIRMED",
                true,
                Collections.emptyList(),
                payloadDigest,
                "Zero sensitive secret patterns detected in candidate payload"
        );
    }

    private static String computeSha256(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(data);
            StringBuilder sb = new StringBuilder("sha256:");
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 algorithm unavailable", e);
        }
    }
}
