package ai.sovereign.aeib.engine;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.nio.charset.StandardCharsets;

/**
 * JCS CAID Derivation:
 * CAID = H(Noun_EntityID || Verb_Action || JCS(Payload))
 */
public final class CaidDerivation {
    private CaidDerivation() {}

    public static String deriveCaid(String nounEntityId, String verbAction, String canonicalJsonPayload) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            String preimage = nounEntityId + "::" + verbAction + "::" + canonicalJsonPayload;
            byte[] hash = digest.digest(preimage.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) {
                String h = Integer.toHexString(0xff & b);
                if (h.length() == 1) hex.append('0');
                hex.append(h);
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
