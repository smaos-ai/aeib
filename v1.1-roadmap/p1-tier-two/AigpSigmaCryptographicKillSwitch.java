package ai.sovereign.aeib.v11.p1;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Priority P1 AIGP-SIGMA Cryptographic Kill Switch (Threshold TSS & ANSI 86 State Lockout).
 *
 * <p>Operates under the stated model: Enforces offline, decentralized emergency halting of
 * autonomous agent execution loops across the boundary. Requires k-of-n valid cryptographic
 * witness signatures (Ed25519) over an RFC 8785 canonical statement to trip or reset the boundary.
 *
 * <p>Anti-Replay Invariant: Rejects any HALT or RESET beacon with sequence <= lastSeenSequence.
 * Once tripped, latches to HALT_ACTIVE (ANSI 86 Lockout) dropping all subsequent dispatches fail-closed.
 *
 * <p>Deployment Boundary: A received, sufficiently fresh, quorum-signed HALT command may be verified
 * locally. Delivery, transport availability, and freshness remain deployment contracts.
 */
public final class AigpSigmaCryptographicKillSwitch {

    public record SignedHaltBeacon(
            long sequenceNumber,
            String commandType,            // "HALT" or "RESET"
            String reason,
            String targetScope,            // e.g. "boundary:all", "agent:treasury"
            long timestampEpochMs,
            Map<String, String> witnessSignaturesHex // witnessPrincipalId -> signatureHex
    ) {
        public String toCanonicalStatement() {
            // Deterministic lexicographically sorted RFC 8785 JSON representation
            return "{"
                    + "\"commandType\":\"" + escapeJson(commandType) + "\","
                    + "\"reason\":\"" + escapeJson(reason) + "\","
                    + "\"sequenceNumber\":" + sequenceNumber + ","
                    + "\"targetScope\":\"" + escapeJson(targetScope) + "\","
                    + "\"timestampEpochMs\":" + timestampEpochMs
                    + "}";
        }

        private static String escapeJson(String s) {
            return s.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }

    public record KillSwitchVerdict(
            boolean accepted,
            boolean haltActive,
            long recordedSequenceNumber,
            int validWitnessSignaturesCount,
            String diagnosticMessage
    ) {}

    public static class KillSwitchTrippedException extends IllegalStateException {
        public KillSwitchTrippedException(String message) {
            super(message);
        }
    }

    private final Map<String, PublicKey> witnessPublicKeys;
    private final int thresholdK;
    private final AtomicLong lastSeenSequenceNumber = new AtomicLong(0);
    private final AtomicBoolean haltActive = new AtomicBoolean(false);

    public AigpSigmaCryptographicKillSwitch(
            Map<String, PublicKey> witnessPublicKeys,
            int thresholdK
    ) {
        Objects.requireNonNull(witnessPublicKeys, "witnessPublicKeys must not be null");
        if (witnessPublicKeys.isEmpty()) {
            throw new IllegalArgumentException("witnessPublicKeys must contain at least 1 key");
        }
        if (thresholdK <= 0 || thresholdK > witnessPublicKeys.size()) {
            throw new IllegalArgumentException("thresholdK must satisfy 1 <= k <= " + witnessPublicKeys.size());
        }
        this.witnessPublicKeys = new HashMap<>(witnessPublicKeys);
        this.thresholdK = thresholdK;
    }

    public boolean isHaltActive() {
        return haltActive.get();
    }

    public long getLastSeenSequenceNumber() {
        return lastSeenSequenceNumber.get();
    }

    /**
     * Asserts that the boundary is not currently halted. Fails closed with exception if halted.
     */
    public void assertNotHalted() {
        if (haltActive.get()) {
            throw new KillSwitchTrippedException(
                    "KILL_SWITCH_ACTIVE: Execution boundary is latched in ANSI 86 Lockout state; all dispatches dropped"
            );
        }
    }

    /**
     * Processes candidate signed HALT beacon, evaluates k-of-n Ed25519 signatures,
     * checks monotonic sequence anti-replay, and trips the kill switch.
     */
    public KillSwitchVerdict processHaltBeacon(SignedHaltBeacon beacon) {
        return processBeacon(beacon, "HALT");
    }

    /**
     * Processes candidate signed RESET beacon, evaluates k-of-n Ed25519 signatures,
     * checks monotonic sequence anti-replay, and clears the lockout state.
     */
    public KillSwitchVerdict processResetBeacon(SignedHaltBeacon beacon) {
        return processBeacon(beacon, "RESET");
    }

    private synchronized KillSwitchVerdict processBeacon(SignedHaltBeacon beacon, String expectedCommandType) {
        Objects.requireNonNull(beacon, "beacon must not be null");

        if (!expectedCommandType.equalsIgnoreCase(beacon.commandType())) {
            return new KillSwitchVerdict(
                    false,
                    haltActive.get(),
                    lastSeenSequenceNumber.get(),
                    0,
                    "REJECTED: expected commandType '" + expectedCommandType + "' but observed '" + beacon.commandType() + "'"
            );
        }

        // 1. Anti-Replay Check: Strictly monotonic sequence number
        if (beacon.sequenceNumber() <= lastSeenSequenceNumber.get()) {
            return new KillSwitchVerdict(
                    false,
                    haltActive.get(),
                    lastSeenSequenceNumber.get(),
                    0,
                    "REJECTED_REPLAY: beacon sequence " + beacon.sequenceNumber()
                            + " <= last recorded sequence " + lastSeenSequenceNumber.get()
            );
        }

        // 2. Evaluate k-of-n Ed25519 signatures over canonical RFC 8785 statement
        byte[] canonicalBytes = beacon.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
        int validWitnesses = 0;
        Set<String> verifiedWitnesses = new HashSet<>();

        for (Map.Entry<String, String> entry : beacon.witnessSignaturesHex().entrySet()) {
            String witnessId = entry.getKey();
            String sigHex = entry.getValue();

            PublicKey pubKey = witnessPublicKeys.get(witnessId);
            if (pubKey == null) {
                continue; // Unknown or unauthorized witness
            }

            if (verifiedWitnesses.contains(witnessId)) {
                continue; // Prevent duplicate counting of the same witness
            }

            if (verifyEd25519(pubKey, canonicalBytes, sigHex)) {
                verifiedWitnesses.add(witnessId);
                validWitnesses++;
            }
        }

        if (validWitnesses < thresholdK) {
            return new KillSwitchVerdict(
                    false,
                    haltActive.get(),
                    lastSeenSequenceNumber.get(),
                    validWitnesses,
                    "REJECTED_QUORUM: observed " + validWitnesses + " valid witness signatures; required threshold k=" + thresholdK
            );
        }

        // 3. Quorum verified and sequence is strictly fresh -> Commit state transition
        lastSeenSequenceNumber.set(beacon.sequenceNumber());
        if ("HALT".equalsIgnoreCase(beacon.commandType())) {
            haltActive.set(true);
            return new KillSwitchVerdict(
                    true,
                    true,
                    beacon.sequenceNumber(),
                    validWitnesses,
                    "HALT_ENGAGED: Quorum reached (" + validWitnesses + "/" + thresholdK + "); ANSI 86 Lockout active"
            );
        } else {
            haltActive.set(false);
            return new KillSwitchVerdict(
                    true,
                    false,
                    beacon.sequenceNumber(),
                    validWitnesses,
                    "RESET_ENGAGED: Quorum reached (" + validWitnesses + "/" + thresholdK + "); Lockout cleared"
            );
        }
    }

    private static boolean verifyEd25519(PublicKey publicKey, byte[] data, String signatureHex) {
        try {
            byte[] sigBytes = hexToBytes(signatureHex);
            Signature sig = Signature.getInstance("Ed25519");
            sig.initVerify(publicKey);
            sig.update(data);
            return sig.verify(sigBytes);
        } catch (Exception e) {
            return false;
        }
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
