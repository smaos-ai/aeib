package com.aeib.runtime;

import com.aeib.crypto.Ed25519ProofEngine;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.security.PublicKey;
import java.util.Base64;
import java.util.Objects;

/**
 * Level 3 Target-Attested Reconciliation Engine (REC-01 to REC-05).
 * Enforces contracts/refund_status_v1.schema.json under strict Ed25519 verification.
 */
public class TargetEvidenceReconciler {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public enum ReconciliationDisposition {
        RESOLVED_CONFIRMED,
        RESOLVED_REFUTED,
        EFFECT_INDETERMINATE
    }

    public record ReconciliationOutcome(
        ReconciliationDisposition disposition,
        String targetStatus,
        boolean signatureVerified,
        String failureReason
    ) {}

    public ReconciliationOutcome reconcile(
        String rawTargetJson,
        String expectedOperationId,
        String expectedCaid,
        long expectedAmountMinorUnits,
        String expectedCurrency,
        String expectedRecipient,
        PublicKey pinnedTargetPublicKey
    ) {
        if (rawTargetJson == null || rawTargetJson.isBlank()) {
            return new ReconciliationOutcome(
                ReconciliationDisposition.EFFECT_INDETERMINATE,
                "EMPTY_RESPONSE",
                false,
                "Target evidence payload was empty"
            );
        }

        try {
            JsonNode root = MAPPER.readTree(rawTargetJson);

            // 1. Contract version check
            String version = root.path("contract_version").asText();
            if (!"1.0.0".equals(version)) {
                return new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    "INVALID_CONTRACT",
                    false,
                    "Unsupported contract version: " + version
                );
            }

            // 2. Operation ID and Idempotency Key matching
            String opId = root.path("operation_id").asText();
            String idemKey = root.path("idempotency_key").asText();
            if (!Objects.equals(opId, expectedOperationId) || !Objects.equals(idemKey, expectedCaid)) {
                return new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    "ID_MISMATCH",
                    false,
                    "Operation ID or idempotency key mismatch with pre-dispatch intent"
                );
            }

            // 3. Unredacted parameter parity check
            JsonNode parity = root.path("parameter_parity");
            long amt = parity.path("amount_minor_units").asLong();
            String curr = parity.path("currency").asText();
            String recipient = parity.path("recipient_binding").asText();

            if (amt != expectedAmountMinorUnits || !Objects.equals(curr, expectedCurrency) || !Objects.equals(recipient, expectedRecipient)) {
                return new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    "PARAMETER_PARITY_FAILED",
                    false,
                    "Target parameters diverged from pre-dispatch CAID"
                );
            }

            // 4. Ed25519 signature verification over canonical payload
            String sigB64 = root.path("signature_b64").asText();
            if (sigB64 == null || sigB64.isBlank() || pinnedTargetPublicKey == null) {
                return new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    "UNAUTHENTICATED",
                    false,
                    "Missing signature or pinned public key"
                );
            }

            // Extract unsigned payload (remove digest and signature_b64)
            ObjectNode unsignedCopy = ((ObjectNode) root).deepCopy();
            unsignedCopy.remove("digest");
            unsignedCopy.remove("signature_b64");

            byte[] canonicalBytes = Ed25519ProofEngine.canonicalize(unsignedCopy.toString());
            byte[] signatureBytes = Base64.getDecoder().decode(sigB64);

            boolean sigValid = Ed25519ProofEngine.verify(canonicalBytes, signatureBytes, pinnedTargetPublicKey);
            if (!sigValid) {
                return new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    "SIGNATURE_INVALID",
                    false,
                    "Receiver Ed25519 signature verification failed"
                );
            }

            // 5. Authoritative target status mapping
            String targetStatus = root.path("target_status").asText();
            return switch (targetStatus) {
                case "SETTLED" -> new ReconciliationOutcome(
                    ReconciliationDisposition.RESOLVED_CONFIRMED,
                    targetStatus,
                    true,
                    "Target confirmed settlement under authenticated contract"
                );
                case "REVERSED", "REJECTED" -> new ReconciliationOutcome(
                    ReconciliationDisposition.RESOLVED_REFUTED,
                    targetStatus,
                    true,
                    "Target refuted mutation under authenticated contract"
                );
                default -> new ReconciliationOutcome(
                    ReconciliationDisposition.EFFECT_INDETERMINATE,
                    targetStatus,
                    true,
                    "Target reported non-final state: " + targetStatus + "; preserving uncertainty"
                );
            };

        } catch (Exception e) {
            return new ReconciliationOutcome(
                ReconciliationDisposition.EFFECT_INDETERMINATE,
                "PARSING_ERROR",
                false,
                "Exception evaluating target evidence: " + e.getMessage()
            );
        }
    }
}
