package com.aeib.runtime;

import ai.sovereign.aeib.core.FOUR_STATION_INTERFACES.*;
import com.aeib.crypto.Ed25519ProofEngine;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.security.MessageDigest;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

public class Station1DispatchInterlock implements DispatchInterlock {
    
    private final long currentEpoch;
    private static final ObjectMapper MAPPER = new ObjectMapper();
    
    public Station1DispatchInterlock(long currentEpoch) {
        this.currentEpoch = currentEpoch;
    }

    @Override
    public InterlockDecision evaluate(CandidateAction action, SecurityContext ctx) {
        if (action == null || ctx == null) {
            return new InterlockDecision(
                DispatchDisposition.REJECTED,
                null,
                this.currentEpoch,
                "Null CandidateAction or SecurityContext rejected fail-closed"
            );
        }
        if (action.capabilityIdentifier() == null || action.capabilityIdentifier().isBlank()
                || action.noun() == null || action.noun().isBlank()
                || action.verb() == null || action.verb().isBlank()
                || action.manifestDigest() == null || action.manifestDigest().isBlank()) {
            return new InterlockDecision(
                DispatchDisposition.REJECTED,
                null,
                this.currentEpoch,
                "Missing capabilityIdentifier, noun, verb, or manifestDigest"
            );
        }
        // Strict epoch equality enforcement (prevent drift)
        if (action.proposedEpoch() != this.currentEpoch) {
            return new InterlockDecision(
                DispatchDisposition.REJECTED,
                null,
                this.currentEpoch,
                "Epoch mismatch: proposed=" + action.proposedEpoch() + ", current=" + this.currentEpoch
            );
        }
        // Verify declared grant standing if grants are populated
        if (ctx.grants() != null && ctx.grants().length > 0) {
            boolean granted = false;
            for (String g : ctx.grants()) {
                if (action.capabilityIdentifier().equals(g) || "*".equals(g)) {
                    granted = true;
                    break;
                }
            }
            if (!granted) {
                return new InterlockDecision(
                    DispatchDisposition.REJECTED,
                    null,
                    this.currentEpoch,
                    "Capability not in SecurityContext grants: " + action.capabilityIdentifier()
                );
            }
        }

        // Compute CAID via strict RFC 8785 JCS Envelope over explicit fields
        String caidEnvelope = buildCaidEnvelope(action);
        byte[] canonBytes = Ed25519ProofEngine.canonicalize(caidEnvelope);
        
        String caidDigest;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashBytes = digest.digest(canonBytes);
            caidDigest = Base64.getEncoder().encodeToString(hashBytes);
        } catch (Exception e) {
            throw new RuntimeException("SHA-256 not available", e);
        }

        return new InterlockDecision(
            DispatchDisposition.AUTHORIZED,
            caidDigest,
            this.currentEpoch,
            "Authorized by Interlock"
        );
    }
    
    private String buildCaidEnvelope(CandidateAction action) {
        try {
            String payloadBase64 = action.jcsPayload() != null ? Base64.getEncoder().encodeToString(action.jcsPayload()) : "";
            
            // Use Jackson to safely serialize map and prevent JSON injection attacks
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("capabilityIdentifier", action.capabilityIdentifier());
            envelope.put("manifestDigest", action.manifestDigest());
            envelope.put("noun", action.noun());
            envelope.put("payload", payloadBase64);
            envelope.put("policyEpoch", action.proposedEpoch());
            envelope.put("verb", action.verb());
            
            return MAPPER.writeValueAsString(envelope);
        } catch (Exception e) {
            throw new RuntimeException("Failed to construct CAID envelope securely", e);
        }
    }
}
