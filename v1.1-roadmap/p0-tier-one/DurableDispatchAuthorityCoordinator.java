package ai.sovereign.aeib.v11.p0;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Priority P0 Tier 1 Core Delivery: Durable Dispatch Intent & Persistent Ticket Coordinator.
 *
 * <p>Operates under the stated model: Eliminates in-memory-only ticket assumptions.
 * Enforces the crash-safe, restart-safe Tier 1 execution contract:
 * <ol>
 *   <li>Pre-dispatch validation: authority signature, target identity, policy epoch, manifest, CAID.</li>
 *   <li>Durable DISPATCH_INTENT journal write with fsync acknowledgement.</li>
 *   <li>Persistent, restart-safe single-use ticket consumption.</li>
 *   <li>Governed execution through target dispatch hook.</li>
 *   <li>Deterministic outcome classification: latching transport ambiguity to EFFECT_INDETERMINATE.</li>
 *   <li>Bounded operation-specific reconciliation (ProbeBudget: 1).</li>
 *   <li>Persist resolution to durable journal with fsync.</li>
 *   <li>Emit RFC 8785 canonical Ed25519 ContinuityReceipt.</li>
 * </ol>
 */
public final class DurableDispatchAuthorityCoordinator {

    public record GovernedDispatchReceipt(
            String operationId,
            String decisionId,
            String disposition,           // "CONFIRMED", "REFUSED", "EFFECT_INDETERMINATE"
            boolean retrySafe,
            String actionCaid,
            long policyEpoch,
            String targetIdentity,
            long timestampEpochMs,
            String receiptSignatureHex
    ) {}

    public static final class PersistentTicketStore {
        private final Path storagePath;
        private final Set<String> consumedDecisions = ConcurrentHashMap.newKeySet();

        public PersistentTicketStore(Path storagePath) throws IOException {
            this.storagePath = Objects.requireNonNull(storagePath, "storagePath must not be null");
            loadFromDisk();
        }

        private synchronized void loadFromDisk() throws IOException {
            if (Files.exists(storagePath)) {
                List<String> lines = Files.readAllLines(storagePath, StandardCharsets.UTF_8);
                for (String line : lines) {
                    line = line.trim();
                    if (!line.isEmpty() && line.startsWith("CONSUMED:")) {
                        consumedDecisions.add(line.substring("CONSUMED:".length()));
                    }
                }
            }
        }

        public boolean isConsumed(String decisionId) {
            return consumedDecisions.contains(decisionId);
        }

        public synchronized boolean consumeAuthority(String decisionId, long timestampEpochMs) throws IOException {
            if (consumedDecisions.contains(decisionId)) {
                return false;
            }

            if (storagePath.getParent() != null) {
                Files.createDirectories(storagePath.getParent());
            }

            // Write with fsync durability acknowledgement
            try (FileOutputStream fos = new FileOutputStream(storagePath.toFile(), true);
                 OutputStreamWriter writer = new OutputStreamWriter(fos, StandardCharsets.UTF_8)) {
                writer.write("CONSUMED:" + decisionId + ":" + timestampEpochMs + "\n");
                writer.flush();
                fos.getFD().sync();
            }

            consumedDecisions.add(decisionId);
            return true;
        }
    }

    public static final class DurableIntentJournal {
        private final Path journalPath;

        public DurableIntentJournal(Path journalPath) {
            this.journalPath = Objects.requireNonNull(journalPath, "journalPath must not be null");
        }

        public synchronized void persistIntent(String operationId, String decisionId, String actionCaid, String targetIdentity, long timestampEpochMs) throws IOException {
            if (journalPath.getParent() != null) {
                Files.createDirectories(journalPath.getParent());
            }
            try (FileOutputStream fos = new FileOutputStream(journalPath.toFile(), true);
                 OutputStreamWriter writer = new OutputStreamWriter(fos, StandardCharsets.UTF_8)) {
                writer.write("INTENT:" + operationId + ":" + decisionId + ":" + actionCaid + ":" + targetIdentity + ":" + timestampEpochMs + "\n");
                writer.flush();
                fos.getFD().sync();
            }
        }

        public synchronized void markDispatchStarted(String operationId, long timestampEpochMs) throws IOException {
            try (FileOutputStream fos = new FileOutputStream(journalPath.toFile(), true);
                 OutputStreamWriter writer = new OutputStreamWriter(fos, StandardCharsets.UTF_8)) {
                writer.write("DISPATCH_STARTED:" + operationId + ":" + timestampEpochMs + "\n");
                writer.flush();
                fos.getFD().sync();
            }
        }

        public synchronized void persistResolution(String operationId, String disposition, boolean retrySafe, long timestampEpochMs) throws IOException {
            try (FileOutputStream fos = new FileOutputStream(journalPath.toFile(), true);
                 OutputStreamWriter writer = new OutputStreamWriter(fos, StandardCharsets.UTF_8)) {
                writer.write("RESOLVED:" + operationId + ":" + disposition + ":" + retrySafe + ":" + timestampEpochMs + "\n");
                writer.flush();
                fos.getFD().sync();
            }
        }

        public synchronized String scanRecoveryState(String operationId) throws IOException {
            if (!Files.exists(journalPath)) {
                return "NOT_RECORDED";
            }
            List<String> lines = Files.readAllLines(journalPath, StandardCharsets.UTF_8);
            boolean hasIntent = false;
            boolean hasStarted = false;
            boolean hasResolved = false;

            for (String line : lines) {
                if (line.contains(":" + operationId + ":")) {
                    if (line.startsWith("INTENT:")) hasIntent = true;
                    if (line.startsWith("DISPATCH_STARTED:")) hasStarted = true;
                    if (line.startsWith("RESOLVED:")) hasResolved = true;
                }
            }

            if (hasResolved) return "RESOLVED";
            if (hasStarted) return "REQUIRES_RECONCILIATION";
            if (hasIntent) return "ABORTED_PRE_DISPATCH";
            return "UNKNOWN";
        }
    }

    @FunctionalInterface
    public interface WireDispatcher {
        Map<String, Object> dispatch(String candidatePayload) throws Exception;
    }

    @FunctionalInterface
    public interface ProbeReconciler {
        String reconcile(String operationId, String actionCaid);
    }

    private final PublicKey authorityPublicKey;
    private final PrivateKey ledgerSigningKey;
    private final PersistentTicketStore ticketStore;
    private final DurableIntentJournal journal;
    private final long activePolicyEpoch;
    private final String pinnedManifestDigest;
    private final ProbeReconciler probeReconciler;

    public DurableDispatchAuthorityCoordinator(
            PublicKey authorityPublicKey,
            PrivateKey ledgerSigningKey,
            PersistentTicketStore ticketStore,
            DurableIntentJournal journal,
            long activePolicyEpoch,
            String pinnedManifestDigest,
            ProbeReconciler probeReconciler
    ) {
        this.authorityPublicKey = Objects.requireNonNull(authorityPublicKey, "authorityPublicKey must not be null");
        this.ledgerSigningKey = Objects.requireNonNull(ledgerSigningKey, "ledgerSigningKey must not be null");
        this.ticketStore = Objects.requireNonNull(ticketStore, "ticketStore must not be null");
        this.journal = Objects.requireNonNull(journal, "journal must not be null");
        this.activePolicyEpoch = activePolicyEpoch;
        this.pinnedManifestDigest = Objects.requireNonNull(pinnedManifestDigest, "pinnedManifestDigest must not be null");
        this.probeReconciler = probeReconciler;
    }

    public GovernedDispatchReceipt executeGovernedAction(
            DecisionToDispatchAuthorityGate.DispatchAuthorizationTicket ticket,
            byte[] candidatePayloadBytes,
            String targetIdentity,
            long currentTimestampEpochMs,
            WireDispatcher wireDispatcher
    ) throws Exception {
        Objects.requireNonNull(ticket, "ticket must not be null");

        // 1. Validate authority, target, epoch, manifest, and action digest (CAID)
        String computedCaid = computeSha256(candidatePayloadBytes);
        if (!ticket.actionDigest().equals(computedCaid)) {
            throw new SecurityException("ACTION_DIGEST_MISMATCH: ticket " + ticket.actionDigest() + " != computed " + computedCaid);
        }
        if (!ticket.targetIdentity().equals(targetIdentity)) {
            throw new SecurityException("TARGET_MISMATCH: ticket " + ticket.targetIdentity() + " != actual " + targetIdentity);
        }
        if (ticket.policyEpoch() != activePolicyEpoch) {
            throw new SecurityException("POLICY_EPOCH_STALE: ticket epoch " + ticket.policyEpoch() + " != active " + activePolicyEpoch);
        }
        if (!ticket.manifestDigest().equals(pinnedManifestDigest)) {
            throw new SecurityException("MANIFEST_DRIFT: ticket manifest " + ticket.manifestDigest() + " != active " + pinnedManifestDigest);
        }
        if (ticket.expiresAt() < currentTimestampEpochMs) {
            throw new SecurityException("TICKET_EXPIRED: ticket expired at " + ticket.expiresAt());
        }

        // Verify Ed25519 signature
        byte[] stmtBytes = ticket.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
        if (!verifyEd25519(authorityPublicKey, stmtBytes, ticket.signatureHex())) {
            throw new SecurityException("AUTHORITY_SIGNATURE_INVALID: ticket signature rejected");
        }

        if (ticketStore.isConsumed(ticket.decisionId())) {
            throw new SecurityException("AUTHORITY_ALREADY_CONSUMED: decisionId " + ticket.decisionId() + " already consumed");
        }

        // 2. Persist DISPATCH_INTENT with fsync durability acknowledgement
        journal.persistIntent(ticket.operationId(), ticket.decisionId(), computedCaid, targetIdentity, currentTimestampEpochMs);

        // 3. Atomically consume single-use authority
        if (!ticketStore.consumeAuthority(ticket.decisionId(), currentTimestampEpochMs)) {
            throw new SecurityException("CONCURRENT_CONSUMPTION_ABORT: decisionId " + ticket.decisionId() + " consumed concurrently");
        }

        // 4. Mark dispatch started and execute via wire dispatcher
        journal.markDispatchStarted(ticket.operationId(), currentTimestampEpochMs);

        Map<String, Object> outcome;
        try {
            outcome = wireDispatcher.dispatch(new String(candidatePayloadBytes, StandardCharsets.UTF_8));
        } catch (Exception e) {
            outcome = Map.of("http_status", 504, "transport_ambiguity", true, "error", e.getMessage());
        }

        // 5. Classify outcome
        int httpStatus = (int) outcome.getOrDefault("http_status", 500);
        boolean transportAmbiguity = (boolean) outcome.getOrDefault("transport_ambiguity", false) || httpStatus == 504;

        String finalDisposition;
        boolean retrySafe;

        if (!transportAmbiguity && httpStatus == 200) {
            finalDisposition = "CONFIRMED";
            retrySafe = true;
        } else if (!transportAmbiguity && (httpStatus >= 400 && httpStatus < 500)) {
            finalDisposition = "REFUSED";
            retrySafe = false;
        } else {
            finalDisposition = "EFFECT_INDETERMINATE";
            retrySafe = false;

            // 6. Bounded operation-specific reconciliation probe
            if (probeReconciler != null) {
                String reconciled = probeReconciler.reconcile(ticket.operationId(), computedCaid);
                if ("CONFIRMED".equalsIgnoreCase(reconciled)) {
                    finalDisposition = "CONFIRMED";
                    retrySafe = true;
                } else if ("NOT_FOUND".equalsIgnoreCase(reconciled) || "ROLLED_BACK".equalsIgnoreCase(reconciled)) {
                    finalDisposition = "REFUTED";
                    retrySafe = false;
                }
            }
        }

        // 7. Persist resolution to durable journal
        journal.persistResolution(ticket.operationId(), finalDisposition, retrySafe, currentTimestampEpochMs);

        // 8. Emit RFC 8785 signed ContinuityReceipt
        String receiptStmt = "{"
                + "\"actionDigest\":\"" + escapeJson(computedCaid) + "\","
                + "\"decisionId\":\"" + escapeJson(ticket.decisionId()) + "\","
                + "\"disposition\":\"" + escapeJson(finalDisposition) + "\","
                + "\"operationId\":\"" + escapeJson(ticket.operationId()) + "\","
                + "\"policyEpoch\":" + activePolicyEpoch + ","
                + "\"retrySafe\":" + retrySafe + ","
                + "\"targetIdentity\":\"" + escapeJson(targetIdentity) + "\","
                + "\"timestamp\":" + currentTimestampEpochMs
                + "}";

        byte[] receiptSig = signEd25519(ledgerSigningKey, receiptStmt.getBytes(StandardCharsets.UTF_8));
        String sigHex = bytesToHex(receiptSig);

        return new GovernedDispatchReceipt(
                ticket.operationId(),
                ticket.decisionId(),
                finalDisposition,
                retrySafe,
                computedCaid,
                activePolicyEpoch,
                targetIdentity,
                currentTimestampEpochMs,
                sigHex
        );
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String computeSha256(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            return "sha256:" + bytesToHex(md.digest(data));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private static byte[] signEd25519(PrivateKey key, byte[] data) {
        try {
            Signature sig = Signature.getInstance("Ed25519");
            sig.initSign(key);
            sig.update(data);
            return sig.sign();
        } catch (Exception e) {
            throw new IllegalStateException("Ed25519 signing failed", e);
        }
    }

    private static boolean verifyEd25519(PublicKey key, byte[] data, String sigHex) {
        try {
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(key);
            sig.update(data);
            return sig.verify(hexToBytes(sigHex));
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
