# Contributing to OCR Audit Engine

We welcome contributions from security engineers, compliance auditors, and AI safety researchers.

## How to Contribute

1. Fork the repository and create a feature branch (`feat/your-feature`).
2. Implement your changes adhering to PEP 8 standards and type annotations.
3. Ensure all unit and integration tests pass:
   ```bash
   pytest src/tests/
   ```
4. Verify that deterministic line grounding remains at 0.00% drift.
5. Open a pull request with clear description and benchmark results.

## Code Standards
- Zero dependencies outside Python standard library + `cryptography`.
- 100% offline capability (no unsolicited network requests).
- Bit-exact reproducibility across Mac, Linux, and Windows.
