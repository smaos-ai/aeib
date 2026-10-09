package com.aeib.verifier;

import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.nio.file.Path;
import java.util.concurrent.Callable;

/**
 * Command-line entry point for the offline AEIB ContinuityReceipt verifier.
 *
 * Exit code contract:
 *   0: Receipt is structurally valid and signature verifies under supplied key.
 *   1: CLI usage / argument syntax error (missing options, unknown flags).
 *   2: Cryptographic or canonicalization rejection (signature, tampering, non-canonical).
 *   3: Input file, format, schema, size, or readability error.
 *   4: Internal verifier failure.
 */
@Command(
    name = "aeib-verifier",
    mixinStandardHelpOptions = true,
    version = "AEIB Verifier 1.0",
    description = "Verifies an AEIB ContinuityReceipt using a caller-supplied public key."
)
public final class VerifierCli implements Callable<Integer> {

    @Option(
        names = {"--receipt"},
        required = true,
        description = "Path to the ContinuityReceipt JSON file."
    )
    private Path receiptPath;

    @Option(
        names = {"--pubkey"},
        required = true,
        description = "Path to the PEM-encoded X.509 SubjectPublicKeyInfo public key."
    )
    private Path publicKeyPath;

    @Override
    public Integer call() {
        try {
            VerifierArguments arguments = new VerifierArguments(receiptPath, publicKeyPath);
            ReceiptVerificationResult result = new ReceiptVerifier().verify(arguments);

            if (result.valid()) {
                System.out.println("VALID: receipt signature and statement verified.");
                return 0;
            }

            System.err.println("INVALID: " + result.failureReason());
            return 2;

        } catch (VerifierInputException e) {
            System.err.println("INPUT_ERROR: " + e.getMessage());
            return 3;

        } catch (Exception e) {
            System.err.println("VERIFIER_ERROR: verification could not complete.");
            return 4;
        }
    }

    /**
     * Executes the CLI command with pinned exception handlers, returning the exit code.
     *
     * @param args Command-line arguments
     * @return Exit code per contract (0, 1, 2, 3, 4)
     */
    public static int execute(String... args) {
        CommandLine cmd = new CommandLine(new VerifierCli());
        cmd.setParameterExceptionHandler((exception, argsList) -> {
            System.err.println("USAGE_ERROR: " + exception.getMessage());
            return 1;
        });
        cmd.setExecutionExceptionHandler((exception, commandLine, parseResult) -> {
            System.err.println("VERIFIER_ERROR: verification could not complete.");
            return 4;
        });
        return cmd.execute(args);
    }

    public static void main(String[] args) {
        int exitCode = execute(args);
        System.exit(exitCode);
    }
}
