package ai.sovereign.aeib.v11.p1;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;

/**
 * Priority P1 SCITT AIR Profile Translator (IETF SCITT COSE_Sign1 Envelopes).
 *
 * <p>Operates under the stated model: Translates AEIB ContinuityReceipt records into IETF SCITT
 * COSE_Sign1 envelopes. Maps AEIB transport classifications directly into SCITT states:
 * <ul>
 *   <li>EFFECT_INDETERMINATE -> pending_confirmation</li>
 *   <li>CONFIRMED -> success</li>
 *   <li>REFUTED -> failed</li>
 *   <li>REJECTED -> policy_rejected</li>
 * </ul>
 *
 * <p>Produces Ed25519-signed Sig_structure representations binding the action payload hash,
 * Merkle anchor root, and protected header parameters without external dependencies.
 *
 * <p>PROTOTYPE PROFILE TRANSLATION: This adapter translates AEIB receipts into COSE_Sign1
 * representations. It does NOT claim formal IETF SCITT conformance or transparency
 * service interoperability until cross-implementation conformance vectors have passed.
 */
public final class ScittAirProfileTranslator {

    public record ScittCoseSign1Envelope(
            String protectedHeaderJcs,
            Map<String, Object> unprotectedHeader,
            String payloadHash,          // "sha256:<64-hex>"
            String scittStatus,          // "pending_confirmation", "success", "failed", etc.
            String signatureHex,
            String merkleAnchorRoot
    ) {}

    private final PrivateKey scittSignerKey;
    private final String keyId;

    public ScittAirProfileTranslator(PrivateKey scittSignerKey, String keyId) {
        this.scittSignerKey = Objects.requireNonNull(scittSignerKey, "scittSignerKey must not be null");
        this.keyId = Objects.requireNonNull(keyId, "keyId must not be null");
    }

    public ScittAirProfileTranslator(PrivateKey scittSignerKey) {
        this(scittSignerKey, "did:aeib:scitt-signer-01");
    }

    /**
     * Translates a receipt statement into an IETF SCITT COSE_Sign1 envelope.
     */
    public ScittCoseSign1Envelope translateReceiptToScittAir(
            String receiptStatementJcs,
            String disposition,
            String merkleRoot
    ) {
        Objects.requireNonNull(receiptStatementJcs, "receiptStatementJcs must not be null");
        Objects.requireNonNull(disposition, "disposition must not be null");
        Objects.requireNonNull(merkleRoot, "merkleRoot must not be null");

        String scittStatus = switch (disposition.toUpperCase(Locale.ROOT)) {
            case "EFFECT_INDETERMINATE", "DISPATCHED_UNCONFIRMED" -> "pending_confirmation";
            case "CONFIRMED" -> "success";
            case "REFUTED" -> "failed";
            case "REJECTED" -> "policy_rejected";
            default -> "pending_confirmation";
        };

        String payloadHash = computeSha256(receiptStatementJcs.getBytes(StandardCharsets.UTF_8));

        // Deterministic lexicographically sorted RFC 8785 JSON representation of protected header
        String protectedHeaderJcs = "{"
                + "\"alg\":\"EdDSA\","
                + "\"crit\":[\"merkle_root\",\"scitt_status\"],"
                + "\"kid\":\"" + escapeJson(keyId) + "\","
                + "\"merkle_root\":\"" + escapeJson(merkleRoot) + "\","
                + "\"profile\":\"ietf-scitt-agent-action-capsule-01\","
                + "\"scitt_status\":\"" + escapeJson(scittStatus) + "\""
                + "}";

        // COSE_Sign1 Sig_structure canonical representation
        String sigStructure = "{"
                + "\"body_protected\":" + protectedHeaderJcs + ","
                + "\"context\":\"Signature1\","
                + "\"external_aad\":\"urn:aeib:merkle:" + escapeJson(merkleRoot) + "\","
                + "\"payload_hash\":\"" + escapeJson(payloadHash) + "\""
                + "}";

        byte[] sigBytes = signEd25519(scittSignerKey, sigStructure.getBytes(StandardCharsets.UTF_8));
        String signatureHex = bytesToHex(sigBytes);

        Map<String, Object> unprotectedHeader = Map.of(
                "timestamp", System.currentTimeMillis()
        );

        return new ScittCoseSign1Envelope(
                protectedHeaderJcs,
                unprotectedHeader,
                payloadHash,
                scittStatus,
                signatureHex,
                merkleRoot
        );
    }

    /**
     * Verifies candidate SCITT COSE_Sign1 envelope using public key.
     */
    public static boolean verifyScittEnvelope(ScittCoseSign1Envelope envelope, PublicKey scittPublicKey) {
        Objects.requireNonNull(envelope, "envelope must not be null");
        Objects.requireNonNull(scittPublicKey, "scittPublicKey must not be null");

        String sigStructure = "{"
                + "\"body_protected\":" + envelope.protectedHeaderJcs() + ","
                + "\"context\":\"Signature1\","
                + "\"external_aad\":\"urn:aeib:merkle:" + escapeJson(envelope.merkleAnchorRoot()) + "\","
                + "\"payload_hash\":\"" + escapeJson(envelope.payloadHash()) + "\""
                + "}";

        byte[] sigBytes = hexToBytes(envelope.signatureHex());
        return verifyEd25519(scittPublicKey, sigStructure.getBytes(StandardCharsets.UTF_8), sigBytes);
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String computeSha256(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(data);
            return "sha256:" + bytesToHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private static byte[] signEd25519(PrivateKey privateKey, byte[] data) {
        try {
            Signature sig = Signature.getInstance("Ed25519");
            sig.initSign(privateKey);
            sig.update(data);
            return sig.sign();
        } catch (Exception e) {
            throw new IllegalStateException("Ed25519 signing failed", e);
        }
    }

    private static boolean verifyEd25519(PublicKey publicKey, byte[] data, byte[] signatureBytes) {
        try {
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(publicKey);
            sig.update(data);
            return sig.verify(signatureBytes);
        } catch (Exception e) {
            return false;
        }
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
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
