# Reproducing AEIB v0.4.0 Review Candidate Verification

## 🏛️ Epistemic Status & Handover Boundary

```text
AEIB v0.4.0 is a review candidate and reproducibility package.

The implementation and test results are reported as passing by the producing environment.
Independent reproduction, target-side effect confirmation, real TinyFish validation,
kernel-level egress validation, and regulatory conformity assessment remain pending.

The package proves controlled gateway behavior under declared synthetic scenarios.
It does not prove universal exactly-once execution, absence of remote duplicate effects,
complete prompt-injection prevention, or regulatory compliance.
```

---

## 🎯 Positioning & Architectural Scope

AEIB is not a complete agent-security platform. (Enterprise identity, governed authorization, and prompt defense are addressed by platforms such as Microsoft Foundry / Entra and Google Model Armor / Agent Gateway).

**AEIB is positioned strictly as:**
> **A vendor-neutral effect-integrity and reconciliation layer that plugs into existing identity, gateway, security, and incident-management systems.**

Its distinct testable state machine output is:
```text
remote action dispatched
→ response ambiguous
→ outcome remains unknown
→ retry authority removed
→ target-side reconciliation required
→ release remains separate
```

---

## 🚀 Exact Verification Sequence

To independently reproduce the reported verification results on your host terminal, execute:

```bash
# 1. Capture environment commit and archive digest
git rev-parse HEAD
shasum -a 256 aeib-v0.4.0-review-candidate.tar.gz || sha256sum aeib-v0.4.0-review-candidate.tar.gz

# 2. Inspect runtime versions
python3 --version
pytest --version

# 3. Verify grounded claims without bypasses
python3 scripts/ci_claims_verifier.py

# 4. Enforce AST mock purity across codebase
python3 scripts/ast_purity_scanner.py

# 5. Run core protection, falsifiability, MCP gate, and BBS+ matrix
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_mcp_acceptance_criteria.py \
       tests/test_bbs_plus_redactable.py -v

# 6. Verify signed CRVP attestation and local codebase SHA-256 digest
python3 verifier/verify_attestation.py

echo "rc=$?"
```

---

## 🔒 14 Mandatory Negative (Release-Blocking) Falsifiability Cases

The clean-room harness evaluates these 14 negative cases to confirm the engine fails closed:

1. **Mutated `effect_id`**: Altering the effect identifier causes receipt verification failure.
2. **Mutated CAID**: Tampering with the Canonical Action Identifier triggers `ERR_MERKLE_PROOF_MISMATCH`.
3. **Tenant / Principal Mismatch**: Re-submitting under an altered tenant or principal fails authorization bounds.
4. **Policy Epoch Drift**: Actions evaluated against a stale or drifted policy epoch halt execution.
5. **Schema Default Modification**: Mutating an MCP tool parameter default raises `MCP_SCHEMA_MUTATION_REJECTED`.
6. **Referenced Evidence Deletion**: Omitting or removing evidence leaves disposition in `MISSING_EVIDENCE`.
7. **Speculative `retry_safe: true`**: Tampering `retry_safe` to true without probe proof fails receipt verification.
8. **Cross-Tenant Receipt Reuse**: A valid receipt presented under an unmapped tenant is rejected.
9. **Receipt Replay**: Resubmitting a previously committed receipt fails unique idempotency check.
10. **Missing Release Authorization**: Dispatches lacking explicit multi-party quorum remain blocked.
11. **Corrupted Ledger State**: Ledger deserialization or SQLite integrity failure fails closed.
12. **Restart During Ambiguity**: Process restart following an ambiguous wire drop preserves `retry_safe: false`.
13. **Probe Disagreement**: Mismatched probe evidence yields `RECONCILIATION_CONFLICT`, not confirmation.
14. **Unapproved Signing Key / Algorithm**: Signatures from untracked profiles or algorithms are rejected fail-closed.
