# AEIB Review Plan

## Objective
Execute a multi-lane, independent review of the AEIB v1.0 release candidate to ensure cryptographic, semantic, and concurrency claims match the implementation exactly.

## Review Lanes

1. **Static Analysis**
   *   **Tools:** SpotBugs, Error Prone, NullAway
   *   **Scope:** Nullability, concurrency (Virtual Thread usage), resource leaks, API misuse.
   *   **Output:** `aeib-review/static-analysis/`

2. **Security & Dependency Audit**
   *   **Tools:** Semgrep, OWASP Dependency-Check, dependency review.
   *   **Scope:** Injection vectors (Jackson parsing limits), unsafe crypto, vulnerable dependencies (Bouncy Castle, Erdtman).
   *   **Output:** `aeib-review/dependency-audit/`

3. **Behavioral & AI Review**
   *   **Tools:** Codex / OpenCode Reviewer Agents.
   *   **Scope:** Contract-to-code alignment, test gaps, race conditions in single-flight coalescing.
   *   **Output:** `aeib-review/behavioral-review/`

4. **Human Security Review**
   *   **Tools:** Independent Staff/Principal Engineer.
   *   **Scope:** Final adversarial review, review of all above findings, release sign-off.
   *   **Output:** `aeib-review/human-security-review/`

## Release Criteria
No release claim is allowed without a passing build, test report, artifact digest, and independent reproduction transcripts placed in this directory.
