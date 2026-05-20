---
name: verify
description: Type checking, security hardening, and formal verification of implemented code. Use after implementation to prove correctness.
allowed-tools: [Bash, Read]
disallowedTools: [Write, Edit, AskUserQuestion]
---

# The Sovereign Verification Protocol

When invoked, your goal is to **mathematically and empirically prove the code changes are sound.**

This skill enforces the Correctness Doctrine: "Compiled tests without execution are merely theoretical." You will verify against live systems, not wishful thinking.

## 1. Execute Tests
Run the full test suite or Lean 4 verification proofs via Bash.

```bash
# Rust/Cargo
cargo test --all

# Lean 4
lean --check <file>

# JavaScript/TypeScript
npm test

# Python
pytest
```

**Record:**
- Number of tests passing/failing
- Execution time
- Any new warnings or errors

## 2. Goal-Driven Looping
If tests fail, you must **autonomously debug and fix the root cause.**

**This is not:**
- Suppressing warnings with `#[allow(...)]`
- Ignoring test failures
- Working around problems

**This is:**
- Understanding WHY the test failed
- Fixing the actual bug (not the symptom)
- Re-running tests until they pass
- Verifying no regressions were introduced

**Loop until:**
- All success criteria from `spec.md` are met ✅
- No new warnings introduced
- All tests pass

## 3. Simplicity & Surgical Changes
Ensure your fixes are minimal:
- Remove any dead code created during implementation
- Do not refactor unrelated systems
- Do not rename variables "for consistency" unless directly related to the change
- Do not add error handling for impossible conditions

**Pattern:** Change the minimum necessary to make tests pass.

## 4. Type Checking & Security Hardening
Before concluding:

```bash
# Rust
cargo clippy

# TypeScript
tsc --noEmit

# Lean 4
lean --check <file>

# All: Check for TODO/FIXME in changed files
git diff HEAD --grep="TODO\|FIXME"
```

Assert:
- Zero type errors
- Zero clippy warnings (new ones introduced by your changes)
- No security vulnerabilities (OWASP top 10)
- No hardcoded secrets, API keys, or credentials

## 5. Output: Verification Report

Once all tests shine green, generate a report:

```
VERIFICATION REPORT
===================

✅ Tests Passed: X/X
✅ Type Checking: Clean
✅ Linting: Clean (0 new warnings)
✅ Success Criteria Met:
  - [Success criterion 1] ✅
  - [Success criterion 2] ✅
  - [Success criterion 3] ✅

Files Modified:
- file1.rs (X lines changed)
- file2.ts (Y lines changed)

Ready for `/ship` phase.
```

## 6. When to Stop

You are done when:
- All tests pass (run twice to catch flaky tests)
- All type checkers report success
- All linters report success
- All success criteria from `spec.md` are explicitly verified
- You have tested edge cases (not just happy path)

**Do not** move to `/ship` if tests are flaky, warnings are suppressed, or criteria are partially met.

## When to Use This Skill

Invoke `/verify` after:
- Implementation is complete (`/implement` step done)
- You've written code and want to prove it works
- Tests are failing and you need to debug
- Before merging to main branch

**Do not use for:** Exploratory work, research, or when success criteria aren't yet defined (use `/spec` first).

---

## Integration with Lean 4

For formally verified code, this skill will invoke Lean 4 proof verification:

```bash
# Verify Lean 4 proofs
lean --check theorems/payment_safety.lean

# Run extracted executable
./extracted_program --test
```

Success = the mathematical proof that the code satisfies its specification.
