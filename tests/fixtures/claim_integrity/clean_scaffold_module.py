"""Structural scaffold for a Lean 4 / TPM attestation adapter.

This module does not invoke `lake build` or tpm2 tooling; verification results
here are simulated placeholders and must not be reported as observed outcomes.
"""


def describe_pipeline():
    return ["export theorem", "run lean kernel (not wired)", "verify tpm quote (not wired)"]
