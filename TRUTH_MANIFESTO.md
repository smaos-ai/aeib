# TRUTH MANIFESTO

This project is a daily practice. The code exists to make that practice visible.

## Five rules

1. **Evidence over confidence.** Fluent text, a confident model, a title or a majority are not evidence. A claim counts as verified only when a check anyone can re-run passes on the current tree.
2. **Separate what we know from what we assume.** Every material claim is labelled with one of: verified, refuted, assumed, hypothesis, unknown, or disputed. Each claim states what would prove it wrong.
3. **Small pieces.** Build and check one small piece at a time. A big plan hides its mistakes; a small piece shows them.
4. **Nobody is above the check.** This applies to the AI, the vendor, the author, and this document. If a check fails, the claim is refuted, whoever made it.
5. **Humans own irreversible consequences.** The tooling can say "no known blocker". It never says "approved". A named human accepts any remaining risk.

Arithmetic (2 + 2 = 4) is certain inside its formal system. Claims about the world and about software are not certain in that way. For those we have checks, and the checks can be wrong too, so they get reviewed like code.

## The daily loop

```
1. Ground    what can be re-checked right now?        python3 tools/where_we_stand.py
2. Slice     what is the one small piece for today?
3. Falsify   what result would prove it wrong?        write that as a test first
4. Seal      add the claim + its check to the ledger  docs/truth/ledger.json
```

## How "verified" is decided

`src/truth_compass.py` re-runs each claim's check against the current git tree. Statuses are never typed in by hand:

- `FILE_SHA256`: the file is re-hashed.
- `PYTEST`: the named tests are run out-of-process. Exit 0 means verified; exit 1 means refuted (the falsifier fired); anything else means unknown.

A claim with no check can only be assumed, hypothesis, unknown or disputed. If the ledger tries to declare "verified" without a check, it is rejected.

The report is bound to the tree state it was computed on. If the code changes, the old report is stale.

## What this is not

- **Not proof that a statement is true in the world.** A passing test shows the test passed; a weak test makes a weak claim.
- **Not new.** It follows assurance cases (claims, evidence, defeaters) and reproducible-artifact practice, applied as a daily habit to an AI-assisted repo.
- **Not an approval system.** It is a decision aid.
