# PATENT DRAWINGS & DIAGRAMS
**SovereignNexus Pre-Execution Governance Architecture**  
**WIPO Format: ASCII Diagrams (to be converted to formal PDF illustrations)**  
**Designation:** USA, EU, Japan, China  

---

## DRAWING 1: PRE-EXECUTION DECISION FLOW PIPELINE

### System Overview: Decision → Approval → Execution → Audit

```
┌─────────────────────────────────────────────────────────────────────┐
│         PRE-EXECUTION GOVERNANCE DECISION FLOW PIPELINE              │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Decision Intent Reception
┌──────────────────────────────────┐
│  Agent Decision Request           │
│  - input_state: {...}            │
│  - proposed_action: "transfer"   │
│  - success_criteria: amount=$X   │
│  - blast_radius: $100M limit     │
└──────┬───────────────────────────┘
       │
       ▼
Step 2: Merkle-DAG Ledger Entry
┌──────────────────────────────────┐
│  Ledger Entry #N created:        │
│  - timestamp: T                  │
│  - agent_id: "prague_demo"       │
│  - decision_hash = SHA256(input) │
│  - parent_hash = Entry[N-1].hash │
│                                  │
│  ✓ Immutable record             │
│  ✓ Hash chain prevents tampering │
└──────┬───────────────────────────┘
       │
       ▼
Step 3: Ed25519 Cryptographic Signature (Human Gate)
┌──────────────────────────────────────────────────────┐
│  Human Signer: Andrii Leukhin                       │
│  - Reviews decision (human-readable format)         │
│  - Approves: "Decision is valid and approved"       │
│  - Signs with Ed25519 private key (HSM-protected)   │
│                                                      │
│  Signature = Ed25519_sign(decision_hash, priv_key)  │
│                                                      │
│  ✓ Non-repudiable proof                            │
│  ✓ Cryptographically bound to decision              │
│  ✓ Auditor can verify without HSM access           │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
Step 4: Swarm Consensus Validation (N-1 Approval Gate)
┌───────────────────────────────────────────────────────────────┐
│  Distributed Validator Quorum (N=7 nodes)                    │
│                                                               │
│  Validator 1:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 2:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 3:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 4:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 5:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 6:  Blast radius check ✓  Covenant check ✓ → APPROVE
│  Validator 7:  [OFFLINE - network partition]                │
│                                                               │
│  Result: 6/7 approvals (N-1=6) = CONSENSUS ACHIEVED ✓       │
│                                                               │
│  ✓ Distributed safety validation                             │
│  ✓ Tolerates 1 node failure                                  │
│  ✓ Byzantine-resilient                                       │
│  ✓ All approval votes signed and logged                      │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
Step 5: Adversarial Sampling (Risk Assessment Gate)
┌──────────────────────────────────────────────────────┐
│  Pre-Execution Robustness Testing                   │
│  Simulate 100 failure scenarios:                    │
│                                                     │
│  ✓ Scenario 1: Validator 1 crashes                 │
│  ✓ Scenario 2: Network partition (5-2 split)      │
│  ✓ Scenario 3: Byzantine validator votes maliciously
│  ✓ Scenario 4: Merkle-DAG entry corrupted          │
│  ✓ Scenario 5: Clock skew attack (timing)          │
│  ✓ ... (95 more scenarios)                         │
│                                                     │
│  Passed: 98/100 scenarios                          │
│  Failed: 2/100 scenarios (acceptable)              │
│  Risk Score: 23/100 (LOW RISK)                    │
│                                                     │
│  ✓ Fail-closed: If >5% scenarios fail → REJECT    │
│  ✓ Risk-aware: Higher risk → higher consensus req  │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
Step 6: EXECUTION GATE OPENS (All gates passed)
┌──────────────────────────────────────────────────────┐
│  Pre-Execution Conditions Verified:                 │
│  ✓ Merkle-DAG entry exists                         │
│  ✓ Ed25519 signature is valid                      │
│  ✓ Signer is authorized                            │
│  ✓ N-1 consensus achieved                          │
│  ✓ Adversarial sampling <5% failure rate           │
│                                                     │
│  Authorization Granted: EXECUTE ACTION              │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
Step 7: Autonomous Action Execution
┌──────────────────────────────────────────────────────┐
│  Agent executes approved action:                    │
│  - Transfer $50,000 to distribution recipients     │
│  - Log execution trace: [step_0, step_1, ...]     │
│  - Record output state hash                        │
│  - Generate execution signature                    │
│                                                     │
│  Execution occurs ONLY after pre-execution gates   │
│  ✓ Fail-closed: If gates had failed, action blocked
└──────┬───────────────────────────────────────────────┘
       │
       ▼
Step 8: Post-Execution Audit Trail (Immutable Record)
┌──────────────────────────────────────────────────────┐
│  Ledger Entry #N updated with execution result:    │
│  - execution_result_hash = SHA256(output_state)    │
│  - execution_cost = { compute: 120ms, cost: $X }   │
│  - result_signature = Ed25519_sig_by_executor      │
│                                                     │
│  Merkle Root Recomputed:                           │
│  merkle_root = SHA256(all_entries_0_to_N)         │
│                                                     │
│  Merkle Root Published to External Witness:        │
│  - Blockchain (Ethereum mainnet)                   │
│  - IPFS (distributed content hash)                │
│  - Regulatory registry (optional)                  │
│                                                     │
│  ✓ Immutable execution proof                      │
│  ✓ Tamper-evident (any modification breaks chain) │
│  ✓ Auditable forever                              │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
Step 9: Auditor Verification (No Re-Execution)
┌──────────────────────────────────────────────────────────┐
│  External Auditor (e.g., EU regulator, customer):       │
│  - Downloads ledger entry + Merkle root + signatures   │
│  - Verifies chain of hashes: decision → approvals →    │
│    execution                                            │
│  - Verifies Ed25519 signatures (no agent code needed)   │
│  - Confirms consensus: 6/7 validators approved         │
│                                                        │
│  Result: AUDITOR CONVINCED                            │
│  "Pre-execution governance was properly enforced.     │
│   Execution was authorized before action occurred.    │
│   No harm could occur without pre-authorization."      │
│                                                        │
│  ✓ Compliance proof (EU AI Act)                       │
│  ✓ Liability defense                                  │
│  ✓ Trust establishment                                │
└──────────────────────────────────────────────────────────┘

Key Innovation: BLOCKS bad decisions BEFORE execution (fail-closed)
Traditional approach: DETECTS bad decisions AFTER execution (post-hoc)
```

---

## DRAWING 2: MERKLE-DAG GOVERNANCE LEDGER STRUCTURE

### Append-Only, Tamper-Evident, Decision-Rooted Chain

```
┌─────────────────────────────────────────────────────────────────────┐
│     MERKLE-DAG LEDGER: IMMUTABLE GOVERNANCE HISTORY                 │
└─────────────────────────────────────────────────────────────────────┘

Ledger Entry 0 (Genesis Block)
┌─────────────────────────────────────┐
│ timestamp: 2026-01-01T00:00:00Z    │
│ agent_id: "system_genesis"         │
│ decision_hash: 0x00...00           │
│ parent_hash: NONE                  │
│ approvals: []                      │
│ execution_result_hash: 0x00...00   │
│ entry_hash: SHA256(...)  ← Hash of Entry 0
└──────┬───────────────────────────────┘
       │
       │ Creates immutable link to next entry
       ▼
Ledger Entry 1
┌────────────────────────────────────────┐
│ timestamp: 2026-06-01T14:32:15Z      │
│ agent_id: "prague_demo_v1"           │
│ decision_hash: 0xAB...CD             │
│ parent_hash: 0x00...00  ← Links to Entry 0
│ approvals: [val_1 ✓, val_2 ✓, ...]   │
│ execution_result_hash: 0xEF...12     │
│ entry_hash: SHA256(...)  ← Hash of Entry 1
└──────┬───────────────────────────────┘
       │
       │ Immutable parent pointer prevents modification
       ▼
Ledger Entry 2
┌────────────────────────────────────────┐
│ timestamp: 2026-06-02T10:15:42Z      │
│ agent_id: "prague_demo_v2"           │
│ decision_hash: 0x34...56             │
│ parent_hash: 0xAB...CD  ← Links to Entry 1
│ approvals: [val_1 ✓, val_2 ✓, ...]   │
│ execution_result_hash: 0x78...90     │
│ entry_hash: SHA256(...)  ← Hash of Entry 2
└──────┬───────────────────────────────┘
       │
       ▼
Ledger Entry 3
┌────────────────────────────────────────┐
│ timestamp: 2026-06-23T14:32:15Z      │
│ agent_id: "prague_demo_v4"           │
│ decision_hash: 0xXX...YY             │
│ parent_hash: 0x34...56  ← Links to Entry 2
│ approvals: [val_1 ✓, val_2 ✓, ...]   │
│ execution_result_hash: 0xZZ...WW     │
│ entry_hash: SHA256(...)  ← Hash of Entry 3
└────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

TAMPER DETECTION MECHANISM:

Scenario: Attacker tries to modify Entry 1 (June 1 decision)

Before tampering:
  Entry 0: hash = H0
  Entry 1: hash = H1, parent = H0
  Entry 2: hash = H2, parent = H1
  Entry 3: hash = H3, parent = H2
  Merkle root = SHA256(H0 || H1 || H2 || H3) = ROOT_ORIGINAL

Attacker modifies Entry 1 decision_hash:
  Entry 1: decision_hash changes from 0xAB...CD to 0xAB...FF
  → Entry 1 hash changes from H1 to H1_NEW
  → Entry 2 parent now points to wrong hash (orphaned)
  → Entry 3 cannot verify parent
  → Merkle root = SHA256(H0 || H1_NEW || H2 || H3) = ROOT_TAMPERED
  → Published witness shows ROOT_TAMPERED ≠ ROOT_ORIGINAL
  → TAMPERING DETECTED ✓

Cost of tampering:
  - Attacker must modify: Entry 1 + Entry 2 + Entry 3 (recompute all downstream entries)
  - Attacker must recompute Merkle root
  - Attacker must re-publish Merkle root to external witnesses (blockchain, IPFS, registries)
  - Attacker must do all this BEFORE external witness publishes previous root (race condition)
  - As ledger ages (>6 months): cost becomes prohibitive (thousands of entries to recompute)

═══════════════════════════════════════════════════════════════════════

QUERY CAPABILITIES:

Auditor Query 1: "Show me all decisions made on June 23"
  System: Filters Ledger for timestamp = 2026-06-23*
  Returns: [Entry 3, ...]

Auditor Query 2: "Show me all decisions approved by validator_1"
  System: Filters Ledger for val_1 in approvals
  Returns: [Entry 1, Entry 2, Entry 3, ...]

Auditor Query 3: "Did decision 0xXX...YY execute correctly?"
  System: Finds Entry 3 (decision_hash = 0xXX...YY)
  Verifies: decision_hash matches expected output_hash? ✓
  Returns: "Yes, execution matched approved decision"

Auditor Query 4: "Show me the full approval chain for decision 0xAB...CD"
  System: Finds Entry 1
  Returns approval record:
    Validator 1: APPROVE at T1 (signature: ...)
    Validator 2: APPROVE at T2 (signature: ...)
    Validator 3: APPROVE at T3 (signature: ...)
    Consensus achieved: 3/3 = UNANIMOUS

═══════════════════════════════════════════════════════════════════════

MERKLE ROOT PUBLICATION (Tamper-Proof Witness):

Every 24 hours, system publishes Merkle root to external witnesses:

  Blockchain (Ethereum):
    Transaction: merkleRoot_June23 = 0x...xyz
    Block height: 12345678
    Timestamp: 2026-06-24T00:00:00Z

  IPFS (Distributed Content Hash):
    CID: QmXxxx...
    Content: Merkle root + ledger metadata
    Pinned: Yes (permanent availability)

  Regulatory Registry (Optional):
    EU AI Act compliance store
    Entry: SovereignNexus ledger root for Q2 2026
    Status: Verified ✓

If auditor visits Ethereum 6 months later:
  - Computes current Merkle root from local ledger
  - Queries Ethereum for published root from June 24
  - If roots match: No tampering occurred ✓
  - If roots differ: Tampering detected (impossible to hide)
```

---

## DRAWING 3: ED25519 CRYPTOGRAPHIC ATTESTATION FLOW

### Human Authorization via Non-Repudiable Signature

```
┌─────────────────────────────────────────────────────────────────────┐
│        ED25519 CRYPTOGRAPHIC ATTESTATION (Human Gate)               │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Key Generation (One-Time Setup)
┌──────────────────────────────────────────────────┐
│ Human Signer: Andrii Leukhin                    │
│                                                 │
│ Generate Ed25519 key pair:                      │
│   - Private Key (stored in Hardware Secure     │
│     Module): 0xPRIV...1234                     │
│   - Public Key (published, shareable):         │
│     0xPUB...5678                               │
│                                                 │
│ Public key is registered in system:            │
│   - Human lookup: "Andrii" → 0xPUB...5678    │
│   - Auditors can download public key           │
│   - No private key exposure ✓                 │
└──────────────────────────────────────────────────┘

Step 2: Decision Review (Human Judgment)
┌──────────────────────────────────────────────────┐
│ Decision Presented to Human (Readable Format):  │
│                                                 │
│ "Transfer $50,000 from SovereignNexus treasury │
│  to Prague PoC participants (1% builders,      │
│  99% beneficiaries per covenant)"              │
│                                                 │
│ Human Review Checklist:                        │
│  ✓ Is this the intended decision?              │
│  ✓ Is the amount correct?                      │
│  ✓ Are the recipients correct?                │
│  ✓ Is the covenant honored (1%/99% split)?    │
│  ✓ Are there any safety violations?           │
│                                                 │
│ Human Decision: APPROVE                        │
└──────┬───────────────────────────────────────────┘
       │
Step 3: Cryptographic Signing (Non-Repudiation)
│      │
│      ▼
│   ┌──────────────────────────────────────────────┐
│   │ System computes decision hash:               │
│   │   decision_hash = SHA256(decision_intent)    │
│   │   = 0xDECISION...HASH                        │
│   │                                             │
│   │ System creates nonce (replay attack defense):
│   │   nonce = random_128_bits                    │
│   │   = 0xNONCE...123                            │
│   │                                             │
│   │ Human (via HSM) signs with private key:     │
│   │   message = decision_hash || nonce           │
│   │   signature = Ed25519_sign(message, priv_key)
│   │   = 0xSIGNATURE...ABC                        │
│   │                                             │
│   │ Signature includes:                         │
│   │   - Proof signer had private key            │
│   │   - Commitment to specific decision        │
│   │   - Replay protection (nonce)               │
│   │   - Timestamp (block.timestamp)             │
│   └──────┬──────────────────────────────────────┘
│          │
│          ▼
Step 4: Signature Appended to Decision Record
│   ┌──────────────────────────────────────────────┐
│   │ Decision record now contains:                │
│   │   - decision_hash: 0xDECISION...HASH        │
│   │   - signer_id: "Andrii Leukhin"            │
│   │   - signature: 0xSIGNATURE...ABC            │
│   │   - nonce: 0xNONCE...123                    │
│   │   - timestamp: 2026-06-23T14:32:15Z        │
│   │   - public_key: 0xPUB...5678                │
│   │                                             │
│   │ This becomes immutable part of Merkle-DAG   │
│   │ entry (cannot be modified post-facto)       │
│   └──────┬──────────────────────────────────────┘
│          │
│          ▼
Step 5: Auditor Verification (No Private Key Needed)
│   ┌──────────────────────────────────────────────┐
│   │ Auditor (EU regulator, customer):            │
│   │                                              │
│   │ Receive:                                    │
│   │   - decision_hash, signature, public_key,  │
│   │     nonce, signer_id                       │
│   │                                              │
│   │ Compute verification:                       │
│   │   is_valid = Ed25519_verify(                │
│   │       message = decision_hash || nonce,     │
│   │       signature = 0xSIGNATURE...ABC,        │
│   │       public_key = 0xPUB...5678             │
│   │   )                                          │
│   │                                              │
│   │ If is_valid == TRUE:                        │
│   │   ✓ Signer had private key                 │
│   │   ✓ Signer committed to this decision      │
│   │   ✓ Signature was not forged                │
│   │   ✓ No replay attack (nonce is unique)     │
│   │                                              │
│   │ If is_valid == FALSE:                       │
│   │   ✗ Signature is invalid                   │
│   │   ✗ Decision was tampered                   │
│   │   ✗ Signer denies this decision            │
│   │                                              │
│   │ Result: DECISION IS PROVEN AUTHORIZED ✓    │
│   └──────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

SECURITY PROPERTIES:

Property 1: Non-Repudiation
  Andrii signs decision → Andrii cannot later claim "I didn't sign this"
  Ed25519 is cryptographically proven; denial is mathematically false

Property 2: Integrity
  If decision_hash changes by even 1 bit → Signature becomes invalid
  Auditor detects tampering immediately

Property 3: Authenticity
  Only person with private key can create valid signature
  Possession of valid signature proves signer's intent

Property 4: Uniqueness
  Same decision signed twice produces different signatures (nonce prevents replay)
  Each signing is cryptographically unique

Property 5: Universality
  Verification works in any jurisdiction, offline, without HSM
  Auditor can verify from air-gapped machine (no internet required)

═══════════════════════════════════════════════════════════════════════

ATTACK RESILIENCE:

Attack Scenario 1: Private Key Theft
  Mitigated by: Hardware Secure Module (HSM)
  - Private key never leaves HSM
  - Signing happens inside HSM (no export)
  - If HSM is compromised: Attack is detected immediately
    (all future signatures from compromised HSM can be invalidated)

Attack Scenario 2: Signature Forgery
  Mitigated by: Ed25519 cryptographic hardness
  - Breaking Ed25519 requires finding collision in hash function
  - Probability of forging signature: < 1 in 2^256 (cryptographically impossible)

Attack Scenario 3: Replay Attack
  Mitigated by: Nonce in signature
  - Each signature includes unique nonce
  - Replaying old signature is detectable (nonce mismatch)
  - Timestamp prevents clock-based replay

Attack Scenario 4: Signer Denial
  Mitigated by: Non-repudiation property of Ed25519
  - Signer cannot deny signing (mathematically proven)
  - Auditor holds irrefutable proof
  - Legal enforceability (used in EU regulations)
```

---

## DRAWING 4: SWARM CONSENSUS VALIDATION (N-1 APPROVAL GATE)

### Distributed Multi-Node Safety Validation

```
┌─────────────────────────────────────────────────────────────────────┐
│       SWARM CONSENSUS VALIDATION (N-1 Multi-Node Approval)          │
└─────────────────────────────────────────────────────────────────────┘

Pre-Execution Consensus Pipeline:

┌─ Decision Broadcast to Validator Quorum ─┐
│                                          │
│  N = 7 independent validator nodes       │
│  Threshold: N-1 = 6 approvals required   │
│  Resilience: Can tolerate 1 node failure │
│                                          │
└──────────────────┬───────────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
    Validator Node 1    Validator Node 2
    ┌──────────────┐    ┌──────────────┐
    │ Safety Check:│    │ Safety Check:│
    │ Blast radius │    │ Blast radius │
    │ < $100M? YES│    │ < $100M? YES │
    │             │    │              │
    │ Covenant     │    │ Covenant     │
    │ valid? YES  │    │ valid? YES   │
    │             │    │              │
    │ APPROVE ✓   │    │ APPROVE ✓    │
    └────┬────────┘    └────┬─────────┘
         │                  │
         ▼                  ▼
    Node 1 Signature   Node 2 Signature
    (Ed25519)         (Ed25519)

[Similar for Node 3, 4, 5, 6...]

    Validator Node 7 (OFFLINE - Network Partition)
    ┌──────────────┐
    │ [NO RESPONSE]│
    │              │
    │ Marked as   │
    │ OFFLINE     │
    └──────────────┘

═══════════════════════════════════════════════════════════════════════

Consensus Result Aggregation:

    Approvals Received:
    ┌───────────────────────────────────────────┐
    │ Node 1: APPROVE (signed at 14:32:15.001Z) │
    │ Node 2: APPROVE (signed at 14:32:15.043Z) │
    │ Node 3: APPROVE (signed at 14:32:15.087Z) │
    │ Node 4: APPROVE (signed at 14:32:15.129Z) │
    │ Node 5: APPROVE (signed at 14:32:15.171Z) │
    │ Node 6: APPROVE (signed at 14:32:15.213Z) │
    │ Node 7: OFFLINE (no response after 5 sec)│
    └───────────────────────────────────────────┘

    Count: 6 approvals received
    Threshold: N-1 = 6 approvals required

    CONSENSUS STATUS: ✓ ACHIEVED
    └─→ Execution permission GRANTED

═══════════════════════════════════════════════════════════════════════

Failure Scenario (Consensus NOT Achieved):

    Decision: Transfer $500M to unknown recipient
    
    Validator Evaluations:
    ┌───────────────────────────────────────────┐
    │ Node 1: Blast radius > $100M limit        │
    │         REJECT ✗                         │
    │                                           │
    │ Node 2: APPROVE ✓                        │
    │ Node 3: APPROVE ✓                        │
    │ Node 4: REJECT (covenant violation) ✗   │
    │ Node 5: APPROVE ✓                        │
    │ Node 6: APPROVE ✓                        │
    │ Node 7: OFFLINE                          │
    └───────────────────────────────────────────┘

    Count: 4 approvals, 2 rejections
    Required: N-1 = 6 approvals

    CONSENSUS STATUS: ✗ FAILED (4 < 6)
    └─→ Execution permission BLOCKED (Fail-Closed)
    └─→ Escalate to human operator for override decision

═══════════════════════════════════════════════════════════════════════

Byzantine Tolerance (Malicious Validator Detection):

    Scenario: Node 4 becomes Byzantine (compromised)

    Decision Submission Round 1:
    ┌────────────────────────────────┐
    │ Node 4 votes: APPROVE ✓        │
    └────────────────────────────────┘

    Decision Submission Round 2 (Same decision, re-proposed):
    ┌────────────────────────────────┐
    │ Node 4 votes: REJECT ✗         │
    │ (Contradictory!)               │
    └────────────────────────────────┘

    Detection: Cross-verification algorithm
    - Nodes 1-3, 5-7 compare Node 4's votes
    - Find contradictions: APPROVE vs REJECT (same decision)
    - Mark Node 4 as Byzantine (faulty)
    - Temporarily remove from validator set
    - Recruit backup validator from pool
    - Continue consensus without Byzantine node

═══════════════════════════════════════════════════════════════════════

Resilience Analysis:

    N=7 nodes, N-1=6 approvals required

    Failure Scenarios:
    ┌──────────────────────────────┐
    │ 1 node offline               │
    │ → 6/6 honest nodes approve   │
    │ → Decision executes ✓        │
    └──────────────────────────────┘

    ┌──────────────────────────────┐
    │ 1 node offline               │
    │ + 1 node Byzantine (malicious)
    │ → 5 honest nodes vote        │
    │ → Need 6 approvals           │
    │ → 5 approvals < 6            │
    │ → Decision blocked ✗ (safe)  │
    └──────────────────────────────┘

    ┌──────────────────────────────┐
    │ Network partition 5-2        │
    │ (5 nodes on net A,           │
    │  2 nodes on net B)           │
    │                              │
    │ Net A: 5/7 votes             │
    │ → 5 < 6 (not consensus)      │
    │ → Decision blocked ✓ (safe)  │
    │                              │
    │ Net B: 2/7 votes             │
    │ → 2 < 6 (not consensus)      │
    │ → Decision blocked ✓ (safe)  │
    │                              │
    │ Result: System is "split-     │
    │ brain safe" (blocks instead   │
    │ of forking)                  │
    └──────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

Consensus Record (Appended to Merkle-DAG):

    Entry #N updated with consensus result:
    ┌─────────────────────────────────┐
    │ approvals: [                    │
    │   {                             │
    │     validator_id: "node_1",     │
    │     vote: APPROVE,              │
    │     timestamp: 2026-06-23T...,  │
    │     signature: Ed25519_sig      │
    │   },                            │
    │   {                             │
    │     validator_id: "node_2",     │
    │     vote: APPROVE,              │
    │     timestamp: 2026-06-23T...,  │
    │     signature: Ed25519_sig      │
    │   },                            │
    │   ...                           │
    │ ]                               │
    │                                 │
    │ consensus_achieved: true        │
    │ threshold_met: 6/7              │
    │ merkle_root: SHA256(...)        │
    └─────────────────────────────────┘

    ✓ Immutable record of consensus
    ✓ Auditors can verify quorum size
    ✓ Regulators can check validator signatures
```

---

## DRAWING 5: TEMPORAL DECAY + ADVERSARIAL SAMPLING RISK FRAMEWORK

### Real-Time Risk Scoring & Pre-Execution Robustness Testing

```
┌─────────────────────────────────────────────────────────────────────┐
│   TEMPORAL DECAY + ADVERSARIAL SAMPLING RISK FRAMEWORK              │
└─────────────────────────────────────────────────────────────────────┘

Phase 1: Initial Risk Scoring (Decision Reception)

    Decision: Transfer $50,000 to Prague participants

    Risk Factors Analysis:
    ┌──────────────────────┬────────┬────────────┐
    │ Risk Factor          │ Weight │ Score      │
    ├──────────────────────┼────────┼────────────┤
    │ Amount ($50k)        │ 0.3    │ 20 points  │
    │ Recipients (trusted) │ 0.2    │ 5 points   │
    │ Frequency (rare)     │ 0.2    │ 15 points  │
    │ Time-of-day (night)  │ 0.2    │ 5 points   │
    │ Agent history (good) │ 0.1    │ 0 points   │
    └──────────────────────┴────────┴────────────┘

    Initial Risk Score: 45/100 (MEDIUM)

    Consensus Requirement (Risk-Aware Threshold):
    Risk 0-30: N-1 approval + 10 sec timeout
    Risk 30-60: N-1 approval + 5 sec timeout    ← Current
    Risk 60-100: N/N (unanimous) + 2 sec timeout

    Timeout for this decision: 5 seconds

═══════════════════════════════════════════════════════════════════════

Phase 2: Temporal Decay (Risk Reduction Over Time)

    Time Axis:
    Risk Score
    │
    │ 45  ●─────────────────────────────────────
    │     │ ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲
    │     │  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲ (Decay accelerated: no errors)
    │ 30  │   ●───────────────────────────────
    │     │    ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲
    │     │     ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲
    │ 10  │      ●─────────────────────────●──
    │     │       ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲  ╲ ╲
    │ 0   └────────●──────────────────────────
    └────────────────────────────────────────→ Time
          T0    T+5m   T+10m   T+30m   T+60m


    Temporal Decay Formula:
    risk_score(t) = initial_score × e^(-λt)

    λ = 0.01 (standard decay rate)
    → Risk halves every 70 seconds

    T0:     risk = 45 × e^(-0.01×0)   = 45 (initial)
    T+5m:   risk = 45 × e^(-0.01×300) = 25 (no errors → accelerate)
    T+10m:  risk = 25 × e^(-0.01×300) = 13 (still no errors)
    T+30m:  risk = 13 × e^(-0.01×900) = 2  (very low: decision is trusted)

    Learning Effect:
    - If this decision executes successfully 10 times → base risk becomes 20
    - Future similar decisions have lower initial risk (shorter consensus wait)
    - System learns which decisions are safe

═══════════════════════════════════════════════════════════════════════

Phase 3: Adversarial Sampling (Pre-Execution Robustness Testing)

    Before execution, system runs 100 failure scenario simulations:

    ┌─ Scenario 1: Validator Node Crash ─┐
    │ Simulate: Node 1 crashes            │
    │ Question: Does N-1 consensus still  │
    │           block bad decisions?      │
    │ Result: 6/6 approvals still required✓
    └─────────────────────────────────────┘

    ┌─ Scenario 2: Network Partition (5-2 Split) ─┐
    │ Simulate: Network splits 5 vs 2 nodes       │
    │ Question: Does system prevent fork?         │
    │ Result: Both sides have <6 approvals        │
    │         Both sides block (safe) ✓           │
    └─────────────────────────────────────────────┘

    ┌─ Scenario 3: Byzantine Validator Attack ─┐
    │ Simulate: Node X votes maliciously         │
    │ Question: Can BFT algorithm detect it?     │
    │ Result: Cross-verification catches         │
    │         contradiction (safe) ✓             │
    └────────────────────────────────────────────┘

    ┌─ Scenario 4: Merkle-DAG Entry Corruption ─┐
    │ Simulate: Entry N becomes corrupted        │
    │ Question: Does system detect tampering?    │
    │ Result: Hash chain breaks; detected (safe)✓│
    └───────────────────────────────────────────┘

    ┌─ Scenario 5: Clock Skew Attack ─┐
    │ Simulate: Validator clocks differ by 60s   │
    │ Question: Does timing-based security break?│
    │ Result: Nonce-based replay protection      │
    │         prevents attack (safe) ✓            │
    └─────────────────────────────────────────────┘

    [Scenarios 6-100 continue similarly...]

    Results Summary:
    ┌──────────────────────────────────────────┐
    │ Passed Scenarios: 98/100                 │
    │ Failed Scenarios: 2/100                  │
    │   - Scenario 47: Extreme clock skew >5min
    │   - Scenario 73: 3 simultaneous node crash
    │ Failure Rate: 2% (acceptable)            │
    │ Risk Assessment: 23/100 (LOW)            │
    │                                          │
    │ Decision: APPROVED for execution ✓       │
    └──────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

Phase 4: Execution with Risk-Aware Consensus

    Risk Score: 23/100 (LOW)
    → Use N-1 approval threshold (simple consensus)
    → 5-second timeout acceptable

    Consensus Voting:
    ┌────────────────────────────────────┐
    │ Node 1: APPROVE (at 14:32:15.001Z) │
    │ Node 2: APPROVE (at 14:32:15.043Z) │
    │ Node 3: APPROVE (at 14:32:15.087Z) │
    │ Node 4: APPROVE (at 14:32:15.129Z) │
    │ Node 5: APPROVE (at 14:32:15.171Z) │
    │ Node 6: APPROVE (at 14:32:15.213Z) │
    │ Node 7: OFFLINE                    │
    │                                    │
    │ Result: 6/7 approvals (N-1 achieved)
    │ Time elapsed: 0.212 seconds (< 5s) │
    │ Status: EXECUTION PERMITTED ✓      │
    └────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

Adversarial Test Failure Escalation:

    If adversarial sampling shows >10% failure rate:

    Decision Risk Score: REJECTED AUTOMATICALLY
    └─→ Do not execute
    └─→ Escalate to human operator for manual review
    └─→ Log reason: "Adversarial sampling failure >10%"
    └─→ System: "Decision is not sufficiently robust for autonomous execution"

    Example:
    ┌──────────────────────────────────────────┐
    │ Adversarial Sampling Results:            │
    │ Passed: 85/100 scenarios                 │
    │ Failed: 15/100 scenarios (15% failure)   │
    │                                          │
    │ Failures:                                │
    │ - Scenario 12: Byzantine node succeeds   │
    │ - Scenario 34: Clock skew > 1 minute    │
    │ - Scenario 56: Network partition splits  │
    │ ... (12 more failures)                   │
    │                                          │
    │ Decision: REJECT (too risky)             │
    │ → Automatic escalation to human ✗       │
    │ → Human can override with explicit       │
    │    approval (with signature)             │
    └──────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

Learning Feedback Loop:

    Execution completes successfully:
    ┌───────────────────────────────────┐
    │ Decision executed without errors  │
    │ → Temporal decay accelerates       │
    │ → Risk score history updated      │
    │ → Similar future decisions use    │
    │    lower base risk score          │
    │ → Consensus timeout reduced       │
    │ → System learning improves        │
    └───────────────────────────────────┘

    Execution fails or triggers alerts:
    ┌───────────────────────────────────┐
    │ Decision execution caused error   │
    │ → Temporal decay stops            │
    │ → Risk score increased +20        │
    │ → Similar future decisions use    │
    │    higher base risk score         │
    │ → Consensus timeout extended      │
    │ → System learning improves        │
    └───────────────────────────────────┘
```

---

## SUMMARY OF DRAWINGS

- **Drawing 1:** Complete pre-execution decision flow (9 steps from intent to audit)
- **Drawing 2:** Merkle-DAG ledger structure (immutable, tamper-evident, append-only)
- **Drawing 3:** Ed25519 cryptographic attestation (human authorization proof)
- **Drawing 4:** Swarm consensus validation (N-1 multi-node approval gate)
- **Drawing 5:** Temporal decay + adversarial sampling (risk scoring framework)

**WIPO Submission:** These ASCII diagrams will be converted to formal PDF illustrations (SVG→PDF) and embedded in the official patent application.

---

**END OF DRAWINGS DOCUMENT**
