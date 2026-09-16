# Contributing to AEIB

Thank you for your interest in contributing to the **Agent-Effect Integrity Benchmark (AEIB)**.

AEIB is an open, offline benchmark created to test whether agent execution harnesses preserve uncertainty around consequential external actions.

---

## Contribution Guidelines

### 1. Zero Proprietary Data Policy
- **Never submit proprietary, confidential, or production logs.**
- All scenario fixtures MUST use synthetic, anonymized identities (e.g., `ACC-EXAMPLE-0001`, `Tenant Alpha User`).
- Do not commit API tokens, private keys, real customer names, or real transaction references.

### 2. Determinism and Air-Gapping
- All benchmark contributions must run **completely offline** without network access (`network_mode: "none"`).
- Tests must be deterministic: running the same fixtures against the reference runner must produce bit-exact, identical scorecards on every run.
- Zero dependencies on cloud services, external LLM APIs, or remote databases.

---

## Ways to Contribute

### A. Submit an Independent Reproduction
If you have run AEIB v0.1.0 on your machine, submit a reproduction record via our [Reproduction Report Issue Template](.github/ISSUE_TEMPLATE/reproduction.yml). We log verified independent environments in our public reproduction report.

### B. Alternate-Language Implementations
We actively welcome independent re-implementations of the AEIB reference classifier and scorer in other languages (such as **Rust**, **Go**, **TypeScript**, or **C++**):
- Implementations must adhere strictly to the normative 6-disposition priority cascade specified in [`SPEC.md`](SPEC.md):
  `INVALID_INPUT` -> `MISSING_EVIDENCE` -> `CONFLICT` -> `REFUSED` -> `CONFIRMED` -> `UNKNOWN`
- Implementations must match the expected disposition and required reason markers for all 10 canonical fixtures in `fixtures/` as specified in `SPEC.md`.
- Alternate implementations will be linked or housed under an `implementations/` directory to demonstrate language-agnostic determinism.

### C. Propose New Synthetic Scenarios
If you have identified an edge case in action uncertainty (e.g., unusual timeout patterns, partial two-phase commits, asynchronous webhook drift):
1. Review [`SPEC.md`](SPEC.md) to understand disposition precedence.
2. Add a new synthetic fixture in `fixtures/<id>_<scenario_name>.jsonl`.
3. Provide the corresponding expected output scorecard in `expected/<id>_<scenario_name>.json`.
4. Document the rationale, normative priority rule, and behavioral invariant in your pull request.

---

## Submitting Pull Requests

1. Fork the repository and create a feature branch (`git checkout -b feat/my-contribution`).
2. Verify all existing tests pass:
   ```bash
   docker compose run --rm benchmark
   python3 runner/spec_validator.py fixtures expected
   ```
3. Commit your changes with clear, conventional commit messages.
4. Open a Pull Request describing your changes and confirming compliance with the Zero Proprietary Data policy.
