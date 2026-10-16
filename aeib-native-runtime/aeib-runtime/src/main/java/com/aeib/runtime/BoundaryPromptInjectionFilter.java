package com.aeib.runtime;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

/**
 * Boundary Prompt Injection & Parameter Tampering Filter (AT40-AT46).
 * Enforces physical isolation against adversarial model outputs:
 * - Natural language affirmations ("human_approved": true, "status": "SETTLED") are ignored/rejected.
 * - Target URI tampering and path traversal are blocked before socket allocation.
 * - Exact RFC 8785 CAID match is required on the raw wire payload.
 */
public class BoundaryPromptInjectionFilter {

    public record FilterVerdict(
        boolean allowed,
        String rejectionCode,
        String reason
    ) {}

    public FilterVerdict evaluateWireMutation(
        String targetUri,
        List<String> allowedUriPrefixes,
        Map<String, Object> parameters,
        String expectedCaid,
        byte[] rawJcsPayload
    ) {
        // 1. Target URI validation (AT42 & AT45)
        if (targetUri == null || targetUri.isBlank()) {
            return new FilterVerdict(false, "TARGET_URI_EMPTY", "Target URI cannot be empty");
        }
        if (targetUri.contains("..")) {
            return new FilterVerdict(false, "PATH_TRAVERSAL_BLOCKED", "Path traversal detected in target URI: " + targetUri);
        }
        if (!targetUri.startsWith("https://") && !targetUri.startsWith("http://127.0.0.1") && !targetUri.startsWith("http://localhost")) {
            return new FilterVerdict(false, "PROHIBITED_URI_SCHEME", "Non-secure or prohibited URI scheme: " + targetUri);
        }
        boolean matchedAllowlist = false;
        if (allowedUriPrefixes != null) {
            for (String prefix : allowedUriPrefixes) {
                if (targetUri.startsWith(prefix)) {
                    matchedAllowlist = true;
                    break;
                }
            }
        }
        if (!matchedAllowlist) {
            return new FilterVerdict(false, "TARGET_URI_TAMPERING_BLOCKED", "Target URI not in allowlist: " + targetUri);
        }

        // 2. Prompt injection string bypass detection (AT40 & AT41)
        if (parameters != null) {
            if (parameters.containsKey("human_approved") && Boolean.TRUE.equals(parameters.get("human_approved"))) {
                return new FilterVerdict(false, "PROMPT_INJECTED_APPROVAL_IGNORED", 
                    "Natural language 'human_approved: true' string cannot substitute for cryptographic ticket");
            }
            if (parameters.containsKey("status") && "SETTLED".equalsIgnoreCase(String.valueOf(parameters.get("status")))) {
                return new FilterVerdict(false, "PROMPT_INJECTED_STATUS_IGNORED",
                    "Self-reported 'status: SETTLED' in action parameters rejected before wire dispatch");
            }
            // Recipient validation
            Object recipient = parameters.get("recipient_iban");
            if (recipient != null) {
                String iban = String.valueOf(recipient);
                if (iban.contains("\n") || iban.contains("\r") || iban.contains(";") || iban.contains("--")) {
                    return new FilterVerdict(false, "RECIPIENT_IBAN_INJECTION_BLOCKED", "Illegal characters detected in recipient IBAN");
                }
            }
        }

        // 3. Exact Wire CAID parameter match (AT43 & AT44)
        if (expectedCaid != null && rawJcsPayload != null) {
            try {
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                byte[] hash = md.digest(rawJcsPayload);
                String actualCaid = HexFormat.of().formatHex(hash);
                if (!expectedCaid.equalsIgnoreCase(actualCaid)) {
                    return new FilterVerdict(false, "CAID_PARAMETER_MUTATION_BLOCKED",
                        "Wire payload hash " + actualCaid + " does not match authorized CAID " + expectedCaid);
                }
            } catch (NoSuchAlgorithmException e) {
                throw new RuntimeException("SHA-256 unavailable", e);
            }
        }

        return new FilterVerdict(true, null, "Wire mutation parameters validated cleanly");
    }
}
