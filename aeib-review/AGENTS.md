# AEIB Review Rules

## Claim boundaries
- Do not accept a claim unless a test artifact proves it.
- Distinguish local evidence from target-side evidence.
- Reject any test that hardcodes the outcome it is meant to prove.
- Reject any claim of exactly-once execution across uncooperative targets.
- Reject any Merkle claim unless a real inclusion path and independent verifier exist.

## Station 0
- The expected digest must come from a trusted ManifestPinStore.
- Verify parser limits, duplicate keys, unknown fields, depth, and canonical digest.
- Prove that caller-supplied digests cannot authorize unpinned manifests.

## Station 1
- CAID must be computed from one canonical RFC 8785 envelope.
- Enforce exact policy-epoch matching.
- Prove zero network and filesystem I/O.
- Prove deterministic output across repeated evaluation.

## Station 2
- Enforce all ProbeBudget fields.
- Coalesce concurrent probes by operationId.
- Cancel the underlying probe on timeout.
- Preserve thread interruption.
- Do not treat a non-empty target state as confirmation.
- Test CONFIRMED, REFUTED, CONFLICT, and INDETERMINATE.

## Station 3
- Receipts must be operation-bound.
- Verify signatures over exact signedStatement bytes.
- Do not call a hash-chain tip a Merkle proof.
- Verify independently in a separate process.

## Release rule
- No release claim is allowed without a passing build, test report, artifact digest, and independent reproduction.
