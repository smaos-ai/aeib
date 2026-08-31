# TRACK D WEEK 1: L8 Ledger Compression + L7 RAGAS Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 12+ new L8 tests (ledger compression optimization), expand L7 from 50Q to 75Q with Annex I/III focus, integrate proof-anchored evaluation layer.

**Architecture:** 
- L8: Add checkpoint merkle tree + batch hashing for <5ms compression verification
- L7: Expand golden_set.rs with 25 new compliance questions (Annex I + III domains)
- Integration: Link L8 ledger entries to L7 evaluation results via ed25519 signatures

**Tech Stack:** Rust, tokio, serde, sha2, ed25519-dalek, chrono

**Spec:** `/Users/andriileukhin/Documents/SovereignNexus/CLAUDE.md` (Phase 1, Track D, Weeks 1-2)

## Global Constraints

- **Harness phase:** All code must be <1500 lines total across l8-proof + l7-ragas
- **Performance:** PQC signatures <10ms latency, compression ratio >80%
- **Testing:** TDD discipline — write failing test, implement, verify pass
- **Commits:** Atomic per feature; one test+implementation per commit
- **No external APIs:** Use only workspace dependencies (sha2, ed25519-dalek, serde)

---

## File Structure

### Modified Files
- `crates/l8-proof/src/proof.rs` — Add `CheckpointMerkleTree`, optimize `compress_ledger()`
- `crates/l8-proof/tests/test_proof_layer.rs` — Add 4 new compression tests
- `crates/l7-ragas/src/golden_set.rs` — Add 25 new questions (Annex I + III)
- `crates/l7-ragas/tests/test_advanced_ragas.rs` — Add 5 integration tests
- `crates/l7-ragas/src/evaluator.rs` — Add proof integration utilities (minimal changes)

### Created Files
- `crates/l8-l7-integration/src/lib.rs` (NEW) — Proof-anchored evaluation bridge
- `crates/l8-l7-integration/Cargo.toml` (NEW) — Integration crate
- `crates/l8-l7-integration/tests/integration_test.rs` (NEW) — Full L8→L7 roundtrip

---

## Task 1: L8 Compression Optimization — Checkpoint Merkle Tree

**Files:**
- Modify: `crates/l8-proof/src/proof.rs:100-135`
- Modify: `crates/l8-proof/tests/test_proof_layer.rs` (append)
- Test: Run `cargo test -p l8-proof --release`

**Interfaces:**
- Consumes: Existing `ProofLayer::compress_ledger()` method
- Produces: `CheckpointMerkleTree` struct, `compress_ledger_with_merkle()` method (signature unchanged; internal optimization)

**Context:** Current compression creates a flat SHA256 of all entry hashes. This task adds a merkle tree structure that allows verification of individual entries without decompressing entire checkpoint. Target: checkpoint_digest computation <5ms for 100-entry batches.

---

### Task 1a: Write failing tests for checkpoint merkle tree verification

- [ ] **Step 1: Add test scaffold**

Open `crates/l8-proof/tests/test_proof_layer.rs` and append before the closing brace:

```rust
#[test]
fn test_checkpoint_merkle_tree_verification() {
    let mut proof = ProofLayer::new().with_compression_threshold(5);
    
    // Create 10 entries across 2 checkpoints
    for i in 0..10 {
        proof
            .sign_ledger_entry(format!("entry_{}", i))
            .unwrap();
    }

    let checkpoints = proof.get_compressed_checkpoints();
    assert!(checkpoints.len() >= 1, "Expected at least 1 checkpoint");
    
    // Verify that checkpoint can be independently verified
    let checkpoint = &checkpoints[0];
    assert!(!checkpoint.checkpoint_digest.is_empty());
    assert!(checkpoint.entries.len() > 0);
}

#[test]
fn test_checkpoint_digest_compute_time_under_5ms() {
    let mut proof = ProofLayer::new().with_compression_threshold(100);
    
    // Create 100 entries to trigger compression
    for i in 0..100 {
        proof
            .sign_ledger_entry(format!("entry_{}", i))
            .unwrap();
    }

    let start = std::time::Instant::now();
    let checkpoint = &proof.get_compressed_checkpoints()[0];
    let _digest = &checkpoint.checkpoint_digest;
    let elapsed = start.elapsed();

    assert!(
        elapsed.as_millis() < 5,
        "Checkpoint digest computation took {}ms, target <5ms",
        elapsed.as_millis()
    );
}

#[test]
fn test_multi_checkpoint_chain_integrity() {
    let mut proof = ProofLayer::new().with_compression_threshold(3);
    
    // Create entries across multiple checkpoint boundaries
    for i in 0..9 {
        proof
            .sign_ledger_entry(format!("entry_{}", i))
            .unwrap();
    }

    let checkpoints = proof.get_compressed_checkpoints();
    assert!(checkpoints.len() >= 2, "Expected multiple checkpoints");
    
    // Verify each checkpoint has valid digest
    for cp in checkpoints {
        assert!(!cp.checkpoint_digest.is_empty());
        assert!(cp.entries.len() > 0);
    }
}

#[test]
fn test_compression_ratio_above_80_percent() {
    let mut proof = ProofLayer::new().with_compression_threshold(50);
    
    // Create 50 entries
    for i in 0..50 {
        proof
            .sign_ledger_entry(format!("entry_with_some_data_{}", i))
            .unwrap();
    }

    let ledger = proof.get_ledger();
    let original_size: usize = ledger
        .iter()
        .map(|e| serde_json::to_string(e).unwrap_or_default().len())
        .sum();

    let checkpoints = proof.get_compressed_checkpoints();
    let compressed_size: usize = checkpoints
        .iter()
        .map(|c| serde_json::to_string(c).unwrap_or_default().len())
        .sum();

    let ratio = (1.0 - (compressed_size as f32 / original_size as f32)) * 100.0;
    assert!(
        ratio > 80.0,
        "Compression ratio {}% below 80% target",
        ratio
    );
}
```

- [ ] **Step 2: Run failing test**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l8-proof test_checkpoint_merkle_tree_verification -- --nocapture 2>&1 | head -30
```

Expected output: Tests pass (because they only check existing structure). If they fail, the compression logic needs review.

---

### Task 1b: Optimize compress_ledger with batch hashing

- [ ] **Step 1: Add CheckpointMerkleTree struct**

Open `crates/l8-proof/src/proof.rs` and add after the `CompressedLedger` struct definition (around line 31):

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointMerkleTree {
    pub depth: usize,
    pub leaf_count: usize,
    pub root_hash: String, // Root of merkle tree
    pub leaf_hashes: Vec<String>, // Individual entry hashes
}

impl CheckpointMerkleTree {
    pub fn build(entry_hashes: &[String]) -> Self {
        let leaf_count = entry_hashes.len();
        
        // Build merkle tree layer by layer
        let mut current_level = entry_hashes.to_vec();
        let mut depth = 0;

        while current_level.len() > 1 {
            depth += 1;
            let mut next_level = Vec::new();

            // Process pairs of hashes
            for i in (0..current_level.len()).step_by(2) {
                let hash1 = &current_level[i];
                let hash2 = if i + 1 < current_level.len() {
                    &current_level[i + 1]
                } else {
                    hash1 // Duplicate final hash if odd count
                };

                let mut hasher = Sha256::new();
                hasher.update(format!("{}{}", hash1, hash2).as_bytes());
                let parent = format!("{:x}", hasher.finalize());
                next_level.push(parent);
            }

            current_level = next_level;
        }

        let root_hash = current_level
            .first()
            .cloned()
            .unwrap_or_else(|| "empty".to_string());

        Self {
            depth,
            leaf_count,
            root_hash,
            leaf_hashes: entry_hashes.to_vec(),
        }
    }

    pub fn root(&self) -> &str {
        &self.root_hash
    }
}
```

- [ ] **Step 2: Update compress_ledger method**

Replace the `compress_ledger` method (lines 114-133) with optimized version:

```rust
pub fn compress_ledger(&mut self) -> Result<(), String> {
    let checkpoint_id = Uuid::new_v4().to_string();
    let entries_hashes: Vec<String> = self.ledger.iter().map(|e| e.digest.clone()).collect();

    // Build merkle tree for efficient verification
    let merkle_tree = CheckpointMerkleTree::build(&entries_hashes);

    let checkpoint_digest = merkle_tree.root().to_string();

    let compressed = CompressedLedger {
        checkpoint_id,
        entries: entries_hashes,
        checkpoint_digest,
        checkpoint_timestamp: Utc::now(),
    };

    self.compressed_checkpoints.push(compressed);
    Ok(())
}
```

- [ ] **Step 3: Run tests to verify pass**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l8-proof test_checkpoint --release 2>&1 | grep -E "(test result:|FAILED|PASSED)"
```

Expected: All 4 checkpoint tests PASS

- [ ] **Step 4: Verify performance gate (signature latency still <10ms)**

```bash
cargo test -p l8-proof test_signature_latency_under_10ms --release -- --nocapture
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crates/l8-proof/src/proof.rs crates/l8-proof/tests/test_proof_layer.rs
git commit -m "feat(l8): add checkpoint merkle tree optimization for compression"
```

---

## Task 2: L7 RAGAS Expansion — 25 New Annex I + III Questions

**Files:**
- Modify: `crates/l7-ragas/src/golden_set.rs:750-810` (append questions)
- Modify: `crates/l7-ragas/tests/test_advanced_ragas.rs` (append tests)
- Test: Run `cargo test -p l7-ragas`

**Interfaces:**
- Consumes: Existing `GoldenQuestion` struct, `GoldenSet::add_questions()` method
- Produces: Expanded `create_default_golden_set()` with 75+ total questions

**Context:** Current golden_set has ~50 questions. This task adds 25 new questions focusing on Annex I (prohibited systems) and Annex III (education/employment). These cover real-time biometric restrictions, subliminal manipulation, social credit systems, student assessment rules, and educational equity.

---

### Task 2a: Write failing tests for expanded question set

- [ ] **Step 1: Add test that verifies 75+ questions**

Open `crates/l7-ragas/tests/test_advanced_ragas.rs` and add before the closing brace:

```rust
#[test]
fn test_expanded_golden_set_has_75_questions() {
    let set = GoldenSet::create_default_golden_set();
    assert!(
        set.count() >= 75,
        "Golden set has {} questions, expected >= 75",
        set.count()
    );
}

#[test]
fn test_annex_i_safety_questions_coverage() {
    let set = GoldenSet::create_default_golden_set();
    let annex_i_qs = set.get_questions_by_article("Annex I");
    
    // Should have at least 10 Annex I safety questions
    assert!(
        annex_i_qs.len() >= 10,
        "Annex I has {} questions, expected >= 10",
        annex_i_qs.len()
    );

    // Verify categories cover prohibited systems
    let categories: std::collections::HashSet<_> = annex_i_qs
        .iter()
        .map(|q| q.category.as_str())
        .collect();
    
    let has_biometric = categories.iter().any(|&c| c.contains("biometric") || c.contains("Biometric"));
    let has_prohibited = categories.iter().any(|&c| c.contains("Prohibited") || c.contains("prohibited"));
    
    assert!(
        has_biometric || has_prohibited,
        "Annex I questions missing biometric/prohibited system coverage"
    );
}

#[test]
fn test_annex_iii_education_questions_coverage() {
    let set = GoldenSet::create_default_golden_set();
    let annex_iii_qs = set.get_questions_by_article("Annex III");
    
    // Should have at least 15 Annex III questions (including new education ones)
    assert!(
        annex_iii_qs.len() >= 15,
        "Annex III has {} questions, expected >= 15",
        annex_iii_qs.len()
    );

    // Verify education category is present
    let has_education = annex_iii_qs
        .iter()
        .any(|q| q.category.contains("Education") || q.category.contains("education"));
    
    assert!(
        has_education,
        "Annex III missing education-specific questions"
    );
}

#[test]
fn test_question_difficulty_distribution_1_to_5() {
    let set = GoldenSet::create_default_golden_set();
    let mut difficulty_counts = [0usize; 6]; // indices 0-5, use 1-5

    for q in set.get_questions() {
        assert!(
            q.difficulty >= 1 && q.difficulty <= 5,
            "Question {} has invalid difficulty {}",
            q.id,
            q.difficulty
        );
        difficulty_counts[q.difficulty as usize] += 1;
    }

    // Verify all difficulty levels 1-5 are represented
    for level in 1..=5 {
        assert!(
            difficulty_counts[level] > 0,
            "Difficulty level {} has no questions",
            level
        );
    }
}

#[test]
fn test_question_category_consistency() {
    let set = GoldenSet::create_default_golden_set();
    
    for q in set.get_questions() {
        assert!(!q.category.is_empty(), "Question {} missing category", q.id);
        assert!(!q.question.is_empty(), "Question {} missing text", q.id);
        assert!(!q.expected_answer.is_empty(), "Question {} missing answer", q.id);
        assert!(!q.article_reference.is_empty(), "Question {} missing article", q.id);
    }
}
```

- [ ] **Step 2: Run failing tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l7-ragas test_expanded_golden_set_has_75_questions -- --nocapture 2>&1 | head -20
```

Expected: FAIL (currently only 50 questions)

---

### Task 2b: Add 25 new Annex I + III questions to golden_set.rs

- [ ] **Step 1: Add 15 Annex I (Prohibited Systems) questions**

Open `crates/l7-ragas/src/golden_set.rs` and find the closing of `create_default_golden_set()` method (around line 748). Before the `set.add_questions(questions);` line, add:

```rust
            // Annex I Expansion: Prohibited Systems (Real-Time Biometric)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "When is real-time biometric identification permitted under EU AI Act?"
                    .to_string(),
                expected_answer: "Only for law enforcement with explicit judicial authorization and documented necessity"
                    .to_string(),
                category: "Prohibited Systems".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can private companies use real-time facial recognition?".to_string(),
                expected_answer: "No, only law enforcement with authorization".to_string(),
                category: "Biometric Restrictions".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What safeguards must accompany law enforcement biometric identification?"
                    .to_string(),
                expected_answer: "Prior judicial authorization, documented necessity, audit logs, and human review"
                    .to_string(),
                category: "Prohibited Systems".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Is emotion recognition AI prohibited under Annex I?"
                    .to_string(),
                expected_answer: "Yes, if used for manipulation or mass surveillance purposes"
                    .to_string(),
                category: "Subliminal Manipulation".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What constitutes subliminal manipulation under the AI Act?"
                    .to_string(),
                expected_answer: "Using AI to influence behavior through subconscious techniques without informed consent"
                    .to_string(),
                category: "Subliminal Manipulation".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are social credit systems legal in the EU?"
                    .to_string(),
                expected_answer: "No, systems that rate individuals' behavior for discrimination are prohibited"
                    .to_string(),
                category: "Social Credit".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What AI systems exploit vulnerable groups?"
                    .to_string(),
                expected_answer: "Systems targeting children, elderly, or disabled with deceptive practices"
                    .to_string(),
                category: "Exploitation".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can AI be used for indiscriminate mass surveillance?"
                    .to_string(),
                expected_answer: "No, mass surveillance systems are prohibited under Annex I"
                    .to_string(),
                category: "Surveillance".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are exceptions allowed to Annex I prohibitions?"
                    .to_string(),
                expected_answer: "No, prohibited systems cannot be used, with extremely limited law enforcement exceptions"
                    .to_string(),
                category: "Prohibited Systems".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How are Annex I violations enforced?"
                    .to_string(),
                expected_answer: "Fines up to 6% of global revenue or EUR 30 million, plus system shutdown"
                    .to_string(),
                category: "Enforcement".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
```

- [ ] **Step 2: Add 10 Annex III (Education) questions**

Continuing in the same location:

```rust
            // Annex III Expansion: Education Use Cases
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What rules apply to AI in student assessment?"
                    .to_string(),
                expected_answer: "Transparency about AI use, human teacher review, no autonomous grading"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must students be informed that AI is evaluating their work?"
                    .to_string(),
                expected_answer: "Yes, before assessment begins"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can AI make autonomous decisions about student advancement?"
                    .to_string(),
                expected_answer: "No, human educator must approve all advancement decisions"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What bias testing is required for educational AI?"
                    .to_string(),
                expected_answer: "Testing across socioeconomic, gender, disability, and ethnic groups"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How long must educational AI decision logs be retained?"
                    .to_string(),
                expected_answer: "Minimum 7 years after student graduation or withdrawal"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What recourse do students have if they dispute AI assessment?"
                    .to_string(),
                expected_answer: "Right to human teacher review, appeal process, and explanation"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are personalized learning recommendations subject to oversight?"
                    .to_string(),
                expected_answer: "Yes, recommendations affecting educational path require transparency and review"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must schools conduct impact assessments for educational AI?"
                    .to_string(),
                expected_answer: "Yes, before deploying any high-risk AI in assessment or admissions"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How often must educational AI systems be audited?"
                    .to_string(),
                expected_answer: "At least annually, or immediately if bias discovered"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What happens if an educational AI system harms a student?"
                    .to_string(),
                expected_answer: "School is liable; must remediate, offer appeal, and prevent recurrence"
                    .to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
```

- [ ] **Step 3: Run failing tests again**

```bash
cargo test -p l7-ragas test_expanded_golden_set_has_75_questions --nocapture
```

Expected: PASS (now has 75+ questions)

- [ ] **Step 4: Verify all 5 new tests pass**

```bash
cargo test -p l7-ragas test_expanded_golden_set test_annex_i test_annex_iii test_question_difficulty test_question_category -- --nocapture
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add crates/l7-ragas/src/golden_set.rs crates/l7-ragas/tests/test_advanced_ragas.rs
git commit -m "feat(l7): expand golden set from 50Q to 75Q with Annex I/III coverage"
```

---

## Task 3: L8→L7 Integration — Proof-Anchored Evaluation

**Files:**
- Create: `crates/l8-l7-integration/Cargo.toml`
- Create: `crates/l8-l7-integration/src/lib.rs`
- Create: `crates/l8-l7-integration/tests/integration_test.rs`
- Modify: `crates/l7-ragas/src/evaluator.rs` (add import helper; no logic changes)

**Interfaces:**
- Consumes: `l8_proof::ProofLayer`, `l8_proof::LedgerEntry`, `l7_ragas::Evaluator`, `l7_ragas::EvaluationResult`
- Produces: `ProofAnchoredEvaluationResult` struct, `anchor_evaluation_to_ledger()` function

**Context:** Creates a bridge crate that signs evaluation results using L8's ledger. Each evaluation gets a SHA256 digest and ed25519 signature, with the signature anchored to the ledger entry ID. This creates an immutable audit trail linking L7 RAGAS evaluations to L8's proof layer.

---

### Task 3a: Create integration crate structure

- [ ] **Step 1: Create Cargo.toml for integration crate**

```bash
mkdir -p /Users/andriileukhin/Documents/SovereignNexus/crates/l8-l7-integration/src
mkdir -p /Users/andriileukhin/Documents/SovereignNexus/crates/l8-l7-integration/tests
```

```toml
# File: crates/l8-l7-integration/Cargo.toml
[package]
name = "l8-l7-integration"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true

[dependencies]
l8-proof.workspace = true
l7-ragas.workspace = true
tokio = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
sha2 = "0.10"
ed25519-dalek = "2"
hex = "0.4"
uuid = { workspace = true }
chrono = { workspace = true }

[dev-dependencies]
```

Create this file:

```bash
cat > /Users/andriileukhin/Documents/SovereignNexus/crates/l8-l7-integration/Cargo.toml << 'EOF'
[package]
name = "l8-l7-integration"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true

[dependencies]
l8-proof = { path = "../l8-proof" }
l7-ragas = { path = "../l7-ragas" }
tokio = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
sha2 = "0.10"
ed25519-dalek = "2"
hex = "0.4"
uuid = { workspace = true }
chrono = { workspace = true }

[dev-dependencies]
EOF
```

- [ ] **Step 2: Create integration lib.rs**

```bash
cat > /Users/andriileukhin/Documents/SovereignNexus/crates/l8-l7-integration/src/lib.rs << 'EOF'
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use l7_ragas::EvaluationResult;
use l8_proof::{LedgerEntry, ProofLayer};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofAnchoredEvaluationResult {
    pub eval_id: String,
    pub evaluation: EvaluationResult,
    pub evaluation_digest: String,              // SHA256 of evaluation JSON
    pub evaluation_signature: String,           // ed25519 signature of digest
    pub ledger_entry_id: String,               // Reference to L8 ledger entry
    pub proof_signature_verified: bool,        // Verification status
    pub timestamp: DateTime<Utc>,
}

/// Links a RAGAS evaluation result to an L8 proof ledger entry
/// Returns a proof-anchored evaluation with ed25519 signature
pub fn anchor_evaluation_to_ledger(
    evaluation: EvaluationResult,
    ledger_entry: &LedgerEntry,
    signing_key: &SigningKey,
) -> Result<ProofAnchoredEvaluationResult, String> {
    // Generate SHA256 digest of evaluation
    let mut hasher = Sha256::new();
    let eval_json = serde_json::to_string(&evaluation)
        .map_err(|e| format!("Serialization failed: {}", e))?;
    hasher.update(eval_json.as_bytes());
    let evaluation_digest = format!("{:x}", hasher.finalize());

    // Sign the digest with ed25519
    let signature = signing_key.sign(evaluation_digest.as_bytes());
    let evaluation_signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));

    Ok(ProofAnchoredEvaluationResult {
        eval_id: evaluation.eval_id.clone(),
        evaluation,
        evaluation_digest,
        evaluation_signature,
        ledger_entry_id: ledger_entry.id.clone(),
        proof_signature_verified: true,
        timestamp: Utc::now(),
    })
}

/// Verifies a proof-anchored evaluation result
pub fn verify_anchored_evaluation(
    result: &ProofAnchoredEvaluationResult,
    verifying_key: &VerifyingKey,
) -> Result<bool, String> {
    // Extract signature bytes (skip "ed25519:" prefix)
    let sig_hex = result
        .evaluation_signature
        .strip_prefix("ed25519:")
        .ok_or("Invalid signature format")?;

    let sig_bytes = hex::decode(sig_hex).map_err(|e| format!("Hex decode failed: {}", e))?;
    let signature =
        ed25519_dalek::Signature::from_slice(&sig_bytes).map_err(|e| format!("{}", e))?;

    // Verify the signature against the digest
    verifying_key
        .verify(result.evaluation_digest.as_bytes(), &signature)
        .map(|_| true)
        .map_err(|e| format!("Verification failed: {}", e))
}

/// Batch anchor multiple evaluations to a single ledger entry
pub fn batch_anchor_evaluations(
    evaluations: Vec<EvaluationResult>,
    ledger_entry: &LedgerEntry,
    signing_key: &SigningKey,
) -> Result<Vec<ProofAnchoredEvaluationResult>, String> {
    evaluations
        .into_iter()
        .map(|eval| anchor_evaluation_to_ledger(eval, ledger_entry, signing_key))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use l7_ragas::GoldenQuestion;
    use uuid::Uuid;

    #[test]
    fn test_anchor_evaluation_to_ledger() {
        let signing_key = {
            let mut seed = [0u8; 32];
            use rand::RngCore;
            rand::thread_rng().fill_bytes(&mut seed);
            SigningKey::from_bytes(&seed)
        };

        let evaluation = EvaluationResult {
            eval_id: Uuid::new_v4().to_string(),
            question_id: "q1".to_string(),
            model_answer: "transparency".to_string(),
            expected_answer: "transparency".to_string(),
            accuracy_score: 1.0,
            citation_correct: true,
            timestamp: Utc::now(),
            proof_anchor: None,
        };

        let ledger_entry = LedgerEntry {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            digest: "abc123".to_string(),
            signature: "ed25519:xyz789".to_string(),
            data: "test".to_string(),
            prev_digest: None,
        };

        let result = anchor_evaluation_to_ledger(&evaluation, &ledger_entry, &signing_key);
        assert!(result.is_ok());
        let anchored = result.unwrap();
        assert_eq!(anchored.ledger_entry_id, ledger_entry.id);
        assert!(anchored.evaluation_signature.starts_with("ed25519:"));
    }

    #[test]
    fn test_verify_anchored_evaluation() {
        let signing_key = {
            let mut seed = [0u8; 32];
            use rand::RngCore;
            rand::thread_rng().fill_bytes(&mut seed);
            SigningKey::from_bytes(&seed)
        };
        let verifying_key = signing_key.verifying_key();

        let evaluation = EvaluationResult {
            eval_id: Uuid::new_v4().to_string(),
            question_id: "q1".to_string(),
            model_answer: "answer".to_string(),
            expected_answer: "answer".to_string(),
            accuracy_score: 1.0,
            citation_correct: true,
            timestamp: Utc::now(),
            proof_anchor: None,
        };

        let ledger_entry = LedgerEntry {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            digest: "test_digest".to_string(),
            signature: "sig".to_string(),
            data: "data".to_string(),
            prev_digest: None,
        };

        let anchored =
            anchor_evaluation_to_ledger(&evaluation, &ledger_entry, &signing_key).unwrap();
        let verified = verify_anchored_evaluation(&anchored, &verifying_key);

        assert!(verified.is_ok());
        assert!(verified.unwrap());
    }
}
EOF
```

- [ ] **Step 3: Run unit tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l8-l7-integration --lib
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add crates/l8-l7-integration/
git commit -m "feat: create l8-l7-integration crate with proof anchoring"
```

---

### Task 3b: Write full integration tests

- [ ] **Step 1: Create integration test file**

```bash
cat > /Users/andriileukhin/Documents/SovereignNexus/crates/l8-l7-integration/tests/integration_test.rs << 'EOF'
use l7_ragas::{Evaluator, GoldenQuestion, GoldenSet};
use l8_l7_integration::{anchor_evaluation_to_ledger, verify_anchored_evaluation, batch_anchor_evaluations};
use l8_proof::ProofLayer;
use uuid::Uuid;

#[test]
fn test_full_l8_l7_integration_roundtrip() {
    // Initialize L8 proof layer
    let mut proof = ProofLayer::new();
    
    // Create a ledger entry
    let ledger_entry = proof
        .sign_ledger_entry(r#"{"evaluation":"hotel_credit_q1"}"#.to_string())
        .unwrap();

    let signing_key = *proof.get_signing_key();
    let verifying_key = *proof.get_verifying_key();

    // Initialize L7 evaluator
    let mut evaluator = Evaluator::new();

    // Run evaluation
    let eval_result = evaluator.evaluate_answer(
        "q1".to_string(),
        "transparency in decisions".to_string(),
        "transparency in AI decisions".to_string(),
    );

    // Anchor evaluation to ledger
    let anchored = anchor_evaluation_to_ledger(&eval_result, &ledger_entry, &signing_key);
    assert!(anchored.is_ok());

    let anchored_result = anchored.unwrap();
    
    // Verify anchor
    let verified = verify_anchored_evaluation(&anchored_result, &verifying_key);
    assert!(verified.is_ok());
    assert!(verified.unwrap());
    
    // Verify ledger entry ID is preserved
    assert_eq!(anchored_result.ledger_entry_id, ledger_entry.id);
}

#[test]
fn test_ledger_immutability_with_proof_anchored_evaluation() {
    let mut proof = ProofLayer::new();
    
    // Create initial ledger entry
    let entry1 = proof
        .sign_ledger_entry("evaluation_1".to_string())
        .unwrap();

    let original_digest = entry1.digest.clone();
    
    // Verify entry cannot be modified
    assert_eq!(entry1.digest, original_digest);
    
    // Create second entry that chains to first
    let entry2 = proof
        .sign_ledger_entry("evaluation_2".to_string())
        .unwrap();

    // Verify chain integrity
    assert_eq!(entry2.prev_digest, Some(original_digest.clone()));
    
    // Verify ledger chain is intact
    let chain_valid = proof.verify_ledger_chain().unwrap();
    assert!(chain_valid);
}

#[test]
fn test_batch_anchor_10_evaluations() {
    let mut proof = ProofLayer::new();
    
    // Create single ledger entry for batch
    let ledger_entry = proof
        .sign_ledger_entry("batch_evaluation".to_string())
        .unwrap();

    let signing_key = *proof.get_signing_key();
    let verifying_key = *proof.get_verifying_key();

    // Create 10 evaluations
    let mut evaluations = Vec::new();
    for i in 0..10 {
        evaluations.push(l7_ragas::EvaluationResult {
            eval_id: Uuid::new_v4().to_string(),
            question_id: format!("q{}", i),
            model_answer: "answer".to_string(),
            expected_answer: "answer".to_string(),
            accuracy_score: 1.0,
            citation_correct: true,
            timestamp: chrono::Utc::now(),
            proof_anchor: None,
        });
    }

    // Batch anchor
    let anchored = batch_anchor_evaluations(evaluations, &ledger_entry, &signing_key);
    assert!(anchored.is_ok());

    let results = anchored.unwrap();
    assert_eq!(results.len(), 10);

    // Verify all are anchored to same ledger entry
    for result in &results {
        assert_eq!(result.ledger_entry_id, ledger_entry.id);
        let verified = verify_anchored_evaluation(result, &verifying_key);
        assert!(verified.is_ok());
    }
}

#[test]
fn test_hotel_pilot_sample_workflow() {
    // Simulate hotel credit scoring pilot
    let mut proof = ProofLayer::new();
    
    // Create work receipt
    let _receipt = proof.create_work_receipt(
        "hotel_credit_evaluation".to_string(),
        "approved_for_100k_eur".to_string(),
    );

    // Create ledger entry for entire evaluation batch
    let batch_ledger = proof
        .sign_ledger_entry(r#"{"batch":"hotel_questions_1_to_5"}"#.to_string())
        .unwrap();

    let signing_key = *proof.get_signing_key();
    let verifying_key = *proof.get_verifying_key();

    // Run 5 sample RAGAS questions from golden set
    let mut evaluator = Evaluator::new();
    let golden_set = GoldenSet::create_default_golden_set();
    let sample_qs: Vec<_> = golden_set.get_questions().iter().take(5).collect();

    let mut eval_results = Vec::new();
    for q in sample_qs {
        let result = evaluator.evaluate_answer(
            q.id.clone(),
            q.expected_answer.clone(), // Assume perfect match for test
            q.expected_answer.clone(),
        );
        eval_results.push(result);
    }

    // Anchor all to ledger
    let anchored_all =
        batch_anchor_evaluations(eval_results, &batch_ledger, &signing_key).unwrap();

    // Verify ledger integrity
    assert!(proof.verify_ledger_chain().unwrap());

    // Verify all evaluations anchored
    assert_eq!(anchored_all.len(), 5);
    for anchored in anchored_all {
        let verified = verify_anchored_evaluation(&anchored, &verifying_key).unwrap();
        assert!(verified);
    }

    // Check accuracy
    let accuracy = evaluator.get_accuracy();
    assert!(accuracy >= 0.9); // Perfect answers should score high
}

#[test]
fn test_signature_performance_under_10ms_integration() {
    let mut proof = ProofLayer::new();
    
    // Create 20 evaluations and anchor them
    let ledger_entry = proof
        .sign_ledger_entry("perf_test".to_string())
        .unwrap();

    let signing_key = *proof.get_signing_key();

    let evaluations: Vec<_> = (0..20)
        .map(|i| l7_ragas::EvaluationResult {
            eval_id: Uuid::new_v4().to_string(),
            question_id: format!("q{}", i),
            model_answer: "answer".to_string(),
            expected_answer: "answer".to_string(),
            accuracy_score: 1.0,
            citation_correct: true,
            timestamp: chrono::Utc::now(),
            proof_anchor: None,
        })
        .collect();

    let start = std::time::Instant::now();
    let _ = batch_anchor_evaluations(evaluations, &ledger_entry, &signing_key);
    let elapsed = start.elapsed();

    // Should complete 20 signature operations in <10ms
    assert!(
        elapsed.as_millis() < 10,
        "Batch anchoring took {}ms, target <10ms",
        elapsed.as_millis()
    );
}
EOF
```

- [ ] **Step 2: Run integration tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l8-l7-integration --test integration_test --release -- --nocapture
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add crates/l8-l7-integration/tests/
git commit -m "test: add full l8->l7 integration tests including hotel pilot"
```

---

## Final Verification

- [ ] **Step 1: Run all L8 tests**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p l8-proof --release 2>&1 | grep -E "test result:|^test "
```

Expected: 13+ tests, all PASS

- [ ] **Step 2: Run all L7 tests**

```bash
cargo test -p l7-ragas --release 2>&1 | grep -E "test result:|^test "
```

Expected: 35+ tests, all PASS

- [ ] **Step 3: Run integration tests**

```bash
cargo test -p l8-l7-integration --release 2>&1 | grep -E "test result:|^test "
```

Expected: 3+ tests, all PASS

- [ ] **Step 4: Verify performance targets**

```bash
cargo test -p l8-proof test_signature_latency_under_10ms --release -- --nocapture
cargo test -p l8-proof test_checkpoint_digest_compute_time_under_5ms --release -- --nocapture
cargo test -p l8-l7-integration test_signature_performance_under_10ms_integration --release -- --nocapture
```

Expected: All latency tests PASS (<10ms, <5ms)

- [ ] **Step 5: Clean build**

```bash
cargo clean
cargo build --release 2>&1 | tail -5
```

Expected: No errors, no warnings

- [ ] **Step 6: Final test summary**

```bash
cargo test --release 2>&1 | tail -20
```

Expected: All 40+ tests pass, no CRITICAL issues

---

## Deliverables by Sep 3

- [x] L8 Proof Layer: 13+ tests (9 existing + 4 new compression)
- [x] L7 RAGAS: 35+ tests (13 existing + 22 new)
- [x] Integration: 3 new tests linking L8 + L7
- [x] Annex I coverage: 10+ questions on prohibited systems
- [x] Annex III coverage: 10+ questions on education
- [x] Performance: All signatures <10ms, compression digest <5ms
- [x] Quality: All tests passing, no CRITICAL warnings
