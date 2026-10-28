# Claim-integrity gate fixtures

Files prefixed `bad_` intentionally contain claim-integrity violations and MUST be
flagged by `compliance/claim_integrity_gate.py`. Files prefixed `clean_` MUST NOT
be flagged. This directory is excluded from `--all` and `--staged` scans; the
fixtures are only parsed (never executed) by `tests/test_claim_integrity_gate.py`.
