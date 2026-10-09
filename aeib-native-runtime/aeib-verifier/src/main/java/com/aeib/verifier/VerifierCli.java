package com.aeib.verifier;

import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Standalone offline verifier CLI for AEIB Continuance Receipts.
 * 
 * Exit code contract:
 *  0: Verification succeeded under supplied public key.
 *  1: Malformed receipt / invalid JSON / trailing tokens / missing required fields / invalid CLI arguments.
 *  2: Verification failed: signature mismatch / statement tampering / field binding mismatch / non-canonical statement.
 *  3: Internal system error / unhandled exception.
 *  4: File I/O violation (oversized input >50MB or non-regular file).
 */
public class VerifierCli {

    public static void main(String[] args) {
        if (args.length == 0) {
            printUsageAndExit();
        }

        try {
            Path receiptPath = null;
            Path pubKeyPath = null;

            for (int i = 0; i < args.length; i++) {
                if ("--receipt".equals(args[i]) && i + 1 < args.length) {
                    receiptPath = Paths.get(args[++i]);
                } else if ("--pubkey".equals(args[i]) && i + 1 < args.length) {
                    pubKeyPath = Paths.get(args[++i]);
                }
            }

            if (receiptPath != null && pubKeyPath != null) {
                int exitCode = verify(receiptPath, pubKeyPath);
                System.exit(exitCode);
                return;
            }

            if (args.length >= 3) {
                int exitCode = verifyPositional(Paths.get(args[0]), args[1], args[2]);
                System.exit(exitCode);
                return;
            }

            printUsageAndExit();

        } catch (Exception e) {
            System.err.println("ERROR: Verification aborted due to exception: " + e.getMessage());
            System.exit(3);
        }
    }

    /**
     * Verifies receipt file against public key file.
     *
     * @param receiptPath Path to receipt JSON
     * @param pubKeyPath Path to public key PEM
     * @return Exit code (0=VALID, 1=MALFORMED, 2=VERIFICATION_FAILED, 3=INTERNAL_ERROR, 4=IO_VIOLATION)
     */
    public static int verify(Path receiptPath, Path pubKeyPath) {
        try {
            ReceiptVerifier.VerificationResult result = ReceiptVerifier.verify(receiptPath, pubKeyPath);
            if (result.outcome() == ReceiptVerifier.VerificationOutcome.VALID) {
                System.out.println("VALID: " + result.detail());
            } else if (result.outcome() == ReceiptVerifier.VerificationOutcome.VERIFICATION_FAILED) {
                System.err.println("INVALID: " + result.detail());
            } else {
                System.err.println("ERROR: " + result.detail());
            }
            return result.exitCode();
        } catch (Exception e) {
            System.err.println("ERROR: Verification exception: " + e.getMessage());
            return 3;
        }
    }

    /**
     * Verifies positional arguments: payload file, base64 signature, base64 public key.
     *
     * @param payloadPath Path to payload file
     * @param sigB64 Base64 encoded Ed25519 signature
     * @param pubKeyB64 Base64 encoded Ed25519 public key
     * @return Exit code (0=VALID, 1=MALFORMED, 2=VERIFICATION_FAILED, 3=INTERNAL_ERROR, 4=IO_VIOLATION)
     */
    public static int verifyPositional(Path payloadPath, String sigB64, String pubKeyB64) {
        try {
            ReceiptVerifier.VerificationResult result = ReceiptVerifier.verifyPositional(payloadPath, sigB64, pubKeyB64);
            if (result.outcome() == ReceiptVerifier.VerificationOutcome.VALID) {
                System.out.println("VALID: " + result.detail());
            } else if (result.outcome() == ReceiptVerifier.VerificationOutcome.VERIFICATION_FAILED) {
                System.err.println("INVALID: " + result.detail());
            } else {
                System.err.println("ERROR: " + result.detail());
            }
            return result.exitCode();
        } catch (Exception e) {
            System.err.println("ERROR: Positional verification error: " + e.getMessage());
            return 3;
        }
    }

    private static void printUsageAndExit() {
        System.err.println("Usage:");
        System.err.println("  aeib-verifier --receipt <receipt.json> --pubkey <public_key.pem>");
        System.err.println("  aeib-verifier <payload_file> <signature_base64> <public_key_base64>");
        System.exit(1);
    }
}
