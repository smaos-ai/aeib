package ai.sovereign.aeib.v11.p2;

import java.math.BigInteger;
import java.security.PublicKey;
import java.util.*;

/**
 * Priority P2 W3C DID Agent Identity Resolver (did:key Ed25519).
 *
 * <p>Operates under the stated model: Deterministically converts and resolves Ed25519 agent public
 * keys to W3C Decentralized Identifiers under the {@code did:key} method with multicodec header
 * {@code 0xed01} and base58-btc encoding (prefixed with 'z').
 *
 * <p>Enables zero-egress, decentralized identity verification for agentic participants.
 */
public final class W3cDidKeyResolver {

    private static final byte[] ED25519_MULTICODEC_PREFIX = new byte[]{(byte) 0xed, (byte) 0x01};
    private static final String BASE58_ALPHABET =
            "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

    public static String pubkeyToDidKey(PublicKey publicKey) {
        Objects.requireNonNull(publicKey, "publicKey must not be null");

        byte[] encoded = publicKey.getEncoded();
        // Standard SubjectPublicKeyInfo for Ed25519 has 12 bytes header followed by 32 raw key bytes
        byte[] rawKey;
        if (encoded.length == 32) {
            rawKey = encoded;
        } else if (encoded.length > 32) {
            rawKey = Arrays.copyOfRange(encoded, encoded.length - 32, encoded.length);
        } else {
            throw new IllegalArgumentException("Invalid Ed25519 public key byte length: " + encoded.length);
        }

        byte[] prefixed = new byte[ED25519_MULTICODEC_PREFIX.length + rawKey.length];
        System.arraycopy(ED25519_MULTICODEC_PREFIX, 0, prefixed, 0, ED25519_MULTICODEC_PREFIX.length);
        System.arraycopy(rawKey, 0, prefixed, ED25519_MULTICODEC_PREFIX.length, rawKey.length);

        return "did:key:z" + base58Encode(prefixed);
    }

    public static Map<String, Object> resolveDidDocument(String did) {
        Objects.requireNonNull(did, "did must not be null");
        if (!did.startsWith("did:key:z")) {
            throw new IllegalArgumentException("DID_RESOLVER_ERROR: unsupported DID format '" + did + "'; expected 'did:key:z...'");
        }

        String didSuffix = did.substring(did.lastIndexOf(':') + 1);
        String keyId = did + "#" + didSuffix;

        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("@context", List.of(
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/suites/ed25519-2020/v1"
        ));
        doc.put("id", did);
        doc.put("authentication", List.of(keyId));

        Map<String, Object> vm = new LinkedHashMap<>();
        vm.put("id", keyId);
        vm.put("type", "Ed25519VerificationKey2020");
        vm.put("controller", did);
        vm.put("publicKeyMultibase", didSuffix);

        doc.put("verificationMethod", List.of(vm));
        return Collections.unmodifiableMap(doc);
    }

    private static String base58Encode(byte[] input) {
        if (input.length == 0) {
            return "";
        }
        BigInteger bi = new BigInteger(1, input);
        BigInteger radix = BigInteger.valueOf(58);
        StringBuilder sb = new StringBuilder();

        while (bi.compareTo(BigInteger.ZERO) > 0) {
            BigInteger[] divmod = bi.divideAndRemainder(radix);
            sb.append(BASE58_ALPHABET.charAt(divmod[1].intValue()));
            bi = divmod[0];
        }

        for (byte b : input) {
            if (b == 0) {
                sb.append(BASE58_ALPHABET.charAt(0));
            } else {
                break;
            }
        }

        return sb.reverse().toString();
    }
}
