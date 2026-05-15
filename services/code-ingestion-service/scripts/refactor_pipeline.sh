#!/bin/bash
set -e

echo "🚀 Starting Sequential Agent Pipeline: ArxivIngestionService Refactor"

# Ensure clean state directory for handoffs
mkdir -p .claude/state
> .claude/state/synthesis.md

# ---------------------------------------------------------
# STEP 1: THE ARCHITECT
# ---------------------------------------------------------
echo "🧠 [1/4] Spawning Architect Agent..."
claude -p "You are the Architect. Read the .claude/skills/java-architecture/reference.md file to understand our Spring Boot standards.
Task: Refactor ArxivIngestionService.java. When Atom feed parsing fails, it must throw a structured IllegalArgumentException (which maps to our HTTP 400 GlobalExceptionHandler) instead of a generic RuntimeException.
Constraint: Do NOT update downstream callers. Focus purely on the service contract. Apply the edits to the file."

# Capture state for the next agents
git diff > .claude/state/architect.diff
git add .
git commit -m "architect: update ArxivIngestionService exception contract"
echo "✅ Architect complete. Diff saved."

# ---------------------------------------------------------
# STEP 2: THE TEST-WRITER
# ---------------------------------------------------------
echo "🧪 [2/4] Spawning Test-Writer Agent..."
claude -p "You are the Test-Writer. Review the architectural changes in .claude/state/architect.diff.
Task: Update or create unit tests for ArxivIngestionService to assert that the new IllegalArgumentException is thrown correctly on malformed XML or missing fields.
Constraint: Strictly follow the 'Prove-It' TDD pattern. Run 'mvn test' to verify your tests fail or pass appropriately. Apply the edits."

git diff > .claude/state/test_writer.diff
git add .
git commit -m "test: implement tests for new ArxivIngestionService contract"
echo "✅ Test-Writer complete."

# ---------------------------------------------------------
# STEP 3: THE IMPLEMENTER
# ---------------------------------------------------------
echo "🛠️ [3/4] Spawning Implementer Agent..."
claude -p "You are the Implementer. Review the API changes in .claude/state/architect.diff.
Task: Find all downstream callers of ArxivIngestionService (specifically IngestionController and IngestionScheduler). Update them to handle the new IllegalArgumentException gracefully, ensuring the REST endpoints map it to the correct JSON error schema. Apply the edits."

git diff > .claude/state/implementer.diff
git add .
git commit -m "feat: update downstream callers for ArxivIngestionService"
echo "✅ Implementer complete."

# ---------------------------------------------------------
# STEP 4: THE VALIDATOR
# ---------------------------------------------------------
echo "🛡️ [4/4] Spawning Validator Agent..."
claude -p "You are the Validator. Your job is adversarial review.
Task:
1. Run 'mvn clean test'.
2. Review the recent git history and diffs in .claude/state/.
3. Check the changes against .claude/skills/java-architecture/reference.md.
4. If there are test failures or architecture violations, fix them immediately.
5. If everything is green, generate a final Markdown summary of the blast radius and changes, and save it to .claude/state/synthesis.md."

echo "✅ Validation complete."
echo "🎉 Pipeline finished successfully. Read .claude/state/synthesis.md for the final report."
