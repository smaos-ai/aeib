package ai.sovereign.aeib.v11.p0;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Priority P0 Decision-to-Dispatch Authority Ticket Gate (TOCTOU Defense).
 *
 * <p>Operates under the stated model: Eliminates the window of vulnerability between policy
 * evaluation and wire socket dispatch. Enforces single-use ticket burn, policy and manifest
 * epoch matching, target identity match, Ed25519 signature verification, and exact RFC 8785
 * JCS Content-Addressed Action Identifier (CAID) wire payload binding.
 *
 * <p>Fails closed: Authorization: DENY -> Execution: NOT_DISPATCHED on any parameter mismatch.
 */
public final class DecisionToDispatchAuthorityGate {

    public record DispatchAuthorizationTicket(
            String decisionId,
            String operationId,
            String principalId,
            String targetIdentity,
            String actionDigest,       // "sha256:<64-hex>"
            long policyEpoch,
            String manifestDigest,     // "sha256:<64-hex>"
            long expiresAt,
            boolean singleUse,
            String signatureHex
    ) {
        public String toCanonicalStatement() {
            // Deterministic lexicographically sorted RFC 8785 UTF-16 code unit JSON representation
            return "{"
                    + "\"actionDigest\":\"" + escapeJson(actionDigest) + "\","
                    + "\"decisionId\":\"" + escapeJson(decisionId) + "\","
                    + "\"expiresAt\":" + expiresAt + ","
                    + "\"manifestDigest\":\"" + escapeJson(manifestDigest) + "\","
                    + "\"operationId\":\"" + escapeJson(operationId) + "\","
                    + "\"policyEpoch\":" + policyEpoch + ","
                    + "\"principalId\":\"" + escapeJson(principalId) + "\","
                    + "\"singleUse\":" + singleUse + ","
                    + "\"targetIdentity\":\"" + escapeJson(targetIdentity) + "\""
                    + "}";
        }

        private static String escapeJson(String s) {
            return s.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }

    public record AuthorityGateVerdict(
            String authorization,       // "ALLOW" or "DENY"
            String execution,           // "DISPATCH_AUTHORIZED" or "NOT_DISPATCHED"
            String decisionId,
            String operationId,
            boolean singleUseBurned,
            String diagnosticMessage
    ) {}

    private final PublicKey authorityPublicKey;
    private final Set<String> burnedDecisions = ConcurrentHashMap.newKeySet();

    public DecisionToDispatchAuthorityGate(PublicKey authorityPublicKey) {
        this.authorityPublicKey = Objects.requireNonNull(authorityPublicKey, "authorityPublicKey must not be null");
    }

    /**
     * Evaluates candidate ticket against wire payload bytes, target identity, and active epoch.
     * Burns ticket on single use. Fails closed fail-safe on any mismatch.
     */
    public AuthorityGateVerdict evaluateAndBurnTicket(
            DispatchAuthorizationTicket ticket,
            byte[] wirePayloadCanonicalBytes,
            String targetUrl,
            String activeManifestDigest,
            long activePolicyEpoch,
            long currentTimestamp
    ) throws GeneralSecurityException {
        if (ticket == null) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", "UNKNOWN", "UNKNOWN", false,
                    "Null DispatchAuthorizationTicket rejected fail-closed");
        }

        // 1. Single-use replay check
        if (ticket.singleUse() && burnedDecisions.contains(ticket.decisionId())) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Ticket decision '" + ticket.decisionId() + "' already burned (replay detected)");
        }

        // 2. Expiration check
        if (currentTimestamp > ticket.expiresAt()) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Ticket expired at " + ticket.expiresAt() + " (current=" + currentTimestamp + ")");
        }

        // 3. Policy and Manifest epoch checks
        if (ticket.policyEpoch() != activePolicyEpoch) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Policy epoch mismatch: ticket=" + ticket.policyEpoch() + ", active=" + activePolicyEpoch);
        }
        if (!Objects.equals(ticket.manifestDigest(), activeManifestDigest)) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Manifest digest mismatch: ticket=" + ticket.manifestDigest() + ", active=" + activeManifestDigest);
        }

        // 4. Target Identity match
        if (!Objects.equals(ticket.targetIdentity(), targetUrl)) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Target identity mutation: ticket=" + ticket.targetIdentity() + ", requested=" + targetUrl);
        }

        // 5. Cryptographic signature check
        byte[] stmtBytes = ticket.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
        byte[] sigBytes = hexToBytes(ticket.signatureHex());
        Signature sig = Signature.getInstance("Ed25519");
        sig.initVerify(authorityPublicKey);
        sig.update(stmtBytes);
        if (!sig.verify(sigBytes)) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "Cryptographic Ed25519 signature verification failed");
        }

        // 6. TOCTOU Action Digest check over wire payload bytes
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] computedHash = md.digest(wirePayloadCanonicalBytes);
        String computedDigest = "sha256:" + bytesToHex(computedHash);
        if (!Objects.equals(ticket.actionDigest(), computedDigest)) {
            return new AuthorityGateVerdict("DENY", "NOT_DISPATCHED", ticket.decisionId(), ticket.operationId(), false,
                    "TOCTOU payload mutation: ticket=" + ticket.actionDigest() + ", wire=" + computedDigest);
        }

        // Burn ticket upon successful evaluation
        if (ticket.singleUse()) {
            burnedDecisions.add(ticket.decisionId());
        }

        return new AuthorityGateVerdict(
                "ALLOW",
                "DISPATCH_AUTHORIZED",
                ticket.decisionId(),
                ticket.operationId(),
                ticket.singleUse(),
                "Standing confirmed and ticket burned successfully"
        );
    }

    public static DispatchAuthorizationTicket mintTicket(
            PrivateKey authorityPrivateKey,
            String decisionId,
            String operationId,
            String principalId,
            String targetIdentity,
            byte[] actionPayloadCanonicalBytes,
            String manifestDigest,
            long policyEpoch,
            long expiresAt,
            boolean singleUse
    ) throws GeneralSecurityException {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        String actionDigest = "sha256:" + bytesToHex(md.digest(actionPayloadCanonicalBytes));

        DispatchAuthorizationTicket draft = new DispatchAuthorizationTicket(
                decisionId,
                operationId,
                principalId,
                targetIdentity,
                actionDigest,
                policyEpoch,
                manifestDigest,
                expiresAt,
                singleUse,
                ""
        );

        byte[] stmtBytes = draft.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
        Signature sig = Signature.getInstance("Ed25519");
        sig.initSign(authorityPrivateKey);
        sig.update(stmtBytes);
        String sigHex = bytesToHex(sig.sign());

        return new DispatchAuthorizationTicket(
                decisionId,
                operationId,
                principalId,
                targetIdentity,
                actionDigest,
                policyEpoch,
                manifestDigest,
                expiresAt,
                singleUse,
                sigHex
        );
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
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
