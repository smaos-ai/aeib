# PCT Patent Claims — SovereignNexus (WIPO Format)
**Filing Date:** June 26, 2026  
**Applicant:** Andrii Leukhin  
**Invention Title:** Pre-Execution Governance Architecture for Autonomous Systems  
**Designations:** USA, EU, Japan, China  
**Filing Method:** WIPO PCT Portal (online submission)  

---

## ABSTRACT

A system and method for cryptographically-governed execution of autonomous agents prior to action, comprising a Merkle-DAG ledger that stores immutable decision records, an Ed25519 attestation layer that cryptographically binds decisions to authorized signatories, a swarm consensus validation mechanism that requires N-1 nodes to approve actions before execution permission is granted, and a temporal decay + adversarial sampling framework that scores execution risk in real-time. The system prevents harm through fail-closed gates: if consensus is not achieved, execution is blocked (not escalated). Applications include autonomous defense systems, creator economy settlement proofs, and EU AI Act compliance infrastructure.

---

## INDEPENDENT CLAIMS (4 Core)

### CLAIM 1: Pre-Execution Governance via Merkle-DAG + Cryptographic Attestation

**A method for ensuring cryptographic proof of AI decisions before execution, comprising:**

1. **Merkle-DAG Ledger Construction:**
   - Receive decision intent (agent request containing input state, proposed action, success criteria)
   - Hash decision with SHA-256 and index in append-only ledger
   - Each ledger entry contains: [timestamp, agent_id, decision_hash, parent_hash, metadata]
   - Parent hash creates immutable chain: entry_N links to entry_N-1, preventing tampering
   - Compute Merkle root as cryptographic commitment to all historical decisions

2. **Ed25519 Cryptographic Attestation:**
   - Authorized human signer retrieves decision hash from Merkle-DAG
   - Sign decision hash with Ed25519 private key (fail-closed: signing only happens post-human approval)
   - Signature includes: decision_hash, timestamp, signer_id, nonce (replay protection)
   - Signature is appended to decision record; signature + ledger entry form immutable proof bundle
   - Merkle root is re-computed after signature to bind attestation into ledger chain

3. **Verification & Auditability:**
   - Any third party (auditor, regulator, customer) can verify proof without re-executing computation
   - Verification requires: original decision, Merkle root, Ed25519 signature, public key of signer
   - Verification algorithm: recompute hash, verify signature, check parent chain for tamper
   - If any link is broken, verification fails (detect corruption instantly)
   - Cryptographic proof chain can be published to immutable storage (blockchain, IPFS, append-only ledger)

4. **Pre-Execution Gate:**
   - Before execution, system verifies: Merkle-DAG entry exists AND Ed25519 signature is valid AND signer is authorized
   - If any check fails: execution is **blocked** (fail-closed semantics)
   - If all checks pass: execution is permitted and ledger records proof of execution
   - Post-execution, system stores result hash in ledger; result becomes part of next decision's parent chain

---

### CLAIM 2: Swarm Consensus Validation for N-1 Approval Pre-Execution

**A system for requiring multi-node consensus agreement before autonomous action execution, comprising:**

1. **Distributed Approval Protocol:**
   - Decision enters consensus buffer (not yet approved)
   - Decision is broadcast to swarm of N independent validator nodes
   - Each node evaluates decision against local policy:
     - Is blast radius within safety bounds? (resource limits, financial caps, physical limits)
     - Is decision consistent with system covenant (1%/99% split, no fraud, no drift)?
     - Has node verified cryptographic signature from authorized signer?
   - Node votes: APPROVE (decision passes all checks) or REJECT (any check fails)

2. **N-1 Approval Requirement (Resilience Rule):**
   - N-1 approvals = execution permission granted (allows 1 node failure without blocking)
   - If approvals < N-1: execution is **blocked** (fail-closed)
   - Approval threshold is configurable per deployment (e.g., N=3 nodes → 2 approvals required; N=7 → 6 required)
   - Approvals are timestamped and cryptographically signed by each validator node
   - Approval consensus record is appended to Merkle-DAG ledger (immutable proof of committee agreement)

3. **Asynchronous Consensus with Timeout:**
   - Validators have configurable timeout (e.g., 30 seconds) to submit vote
   - If N-1 approvals achieved before timeout: execution proceeds immediately
   - If timeout expires with <N-1 approvals: decision is **paused** and escalated to human operator
   - Paused decisions remain in ledger as "pending human review" (auditable state)
   - Human can reject paused decision (reverts to start) or force-approve with explicit signature

4. **Byzantine-Tolerant Consensus (Defense Against Malicious Nodes):**
   - If validator node submits contradictory votes (approval then rejection): node is marked as faulty
   - Faulty node is temporarily removed from validator set; alternative validator is recruited
   - Consensus algorithm remains safe as long as <N/3 nodes are faulty (Byzantine Fault Tolerance guarantee)
   - Faulty node accusation is logged with cryptographic proof; enables offline forensics

---

### CLAIM 3: Governance Ledger Architecture (Append-Only, Tamper-Evident, Decision-Rooted)

**A data structure for immutable, decision-rooted governance history, comprising:**

1. **Append-Only Ledger Design:**
   - Entries are indexed chronologically: [Entry 0: genesis] → [Entry 1: parent_hash=genesis] → [Entry 2: parent_hash=Entry1] → ...
   - Entries are never modified or deleted (immutable)
   - Only operation: APPEND (new entry with parent reference)
   - Ledger is stored in distributed, redundant storage (local SQLite + IPFS + blockchain optional)
   - Ledger can be queried by decision_id, timestamp range, or agent_id

2. **Tamper-Evidence Mechanism:**
   - Each entry contains: [timestamp, agent_id, decision_hash, parent_hash, metadata_json, approvals_array, execution_result]
   - Merkle root is computed across all entries
   - Merkle root is published to external witness (blockchain, notary service, government registry) at regular intervals (e.g., every 24 hours)
   - If attacker modifies any historical entry:
     - Entry hash changes
     - Merkle root changes
     - Published witness no longer matches computed root
     - Tampering is **detectable** via public witness verification
   - Tamper evidence creates liability incentive (fraud is provable and expensive to commit)

3. **Decision-Rooted Architecture:**
   - Every entry is rooted in a decision: "Agent requested action X, decision_hash=H, N-1 nodes approved, human signed, execution occurred at T"
   - Ledger answers audit questions:
     - "Who approved action X?" → Query by decision_hash; see approver_ids
     - "When was decision X approved?" → Query by decision_id; see approval_timestamps
     - "Did execution match decision?" → Compare decision_hash to execution_result_hash
     - "Were all decisions made by authorized signers?" → Verify Ed25519 signatures across range
   - Ledger serves as governance proof for regulatory audits (EU AI Act, FDA compliance, enterprise liability)

4. **Cryptographic Completeness Proof:**
   - System computes Merkle root of ledger at specified interval
   - Root is signed by system operator (Ed25519)
   - Root + signature are published to tamper-evident storage (notary, blockchain, regulatory registry)
   - Any external auditor can verify: "All decisions from T0 to T1 were approved and recorded without tampering"
   - Proof is cryptographically complete: no hidden decisions, no retroactive modifications

---

### CLAIM 4: Temporal Decay + Adversarial Sampling for Risk Scoring in Autonomous Execution

**A method for real-time risk assessment of autonomous decisions using temporal dynamics and adversarial testing, comprising:**

1. **Temporal Decay Scoring Model:**
   - Each decision has a risk score (0-100, where 100 = maximum risk)
   - Risk decays over time: risk_score(t) = initial_score × e^(-λt)
   - Decay rate λ is configurable (e.g., λ=0.01 → risk halves every 70 seconds)
   - If decision executes without incident (no errors, no alerts): decay accelerates (λ increases 2x)
   - If decision generates errors or policy violations: decay stops and score increases +20 points
   - Score feeds into next decision's consensus voting: higher risk requires faster unanimous approval (shorter timeout)

2. **Adversarial Sampling Framework:**
   - Execution environment is augmented with adversarial test module
   - Before real execution, system simulates 100 adversarial scenarios:
     - Network failure (loss of 1 validator node)
     - Byzantine attack (1 validator votes maliciously)
     - Resource exhaustion (memory/CPU constraint)
     - State corruption (partial ledger loss)
     - Timing attack (clock skew across nodes)
   - Simulation runs in sandboxed environment (no real side effects)
   - Each adversarial scenario tests: "Does execution remain fail-closed under attack?"
   - If any adversarial scenario causes execution to proceed without N-1 approval: decision is **rejected** automatically

3. **Risk-Aware Consensus Thresholds:**
   - Decisions with score <30: require N-1 approvals + 10-second timeout
   - Decisions with score 30-60: require N-1 approvals + 5-second timeout
   - Decisions with score >60: require unanimous (N/N) approval + 2-second timeout
   - Financial decisions: risk score multiplied by transaction amount (e.g., $100M decision ≥ 1000 risk points automatically escalates to human)
   - Physical actions (robotics, autonomous vehicles): any risk score >50 requires human override approval

4. **Convergence Proof via Adversarial Sampling:**
   - System maintains historical adversarial test results
   - If decision D passes 95% of adversarial scenarios: mark as "low-risk convergent"
   - If decision D fails <5% of adversarial scenarios: keep score at 30-40 (acceptable)
   - If decision D fails >10% of adversarial scenarios: mark as "high-risk unstable" and reject entire decision class
   - Convergence proof is cryptographically signed and stored in governance ledger
   - Enables auditors to verify: "System underwent rigorous adversarial testing before deployment"

---

## DEPENDENT CLAIMS (3 Variations for Defense)

### CLAIM 5: Pre-Execution Validation in Air-Gapped Networks

**The method of Claim 1-4, wherein the swarm consensus validation operates in air-gapped networks without internet connectivity, comprising:**

1. **Local Validator Quorum:**
   - All N validator nodes run locally on same physical network segment (no internet required)
   - Validators are co-located in secure enclosure (faraday cage, isolated datacenter, aircraft)
   - Consensus communication uses local-only transport (point-to-point fiber, mesh radio, air-gap protocol)
   - Merkle-DAG ledger is stored on local distributed storage (SQLite cluster, RAID array)

2. **Offline-First Decision Making:**
   - Decision intent is entered into local buffer
   - Validators evaluate and vote using pre-cached policy (no internet lookups)
   - Approval consensus happens entirely offline (no external API calls)
   - Decision is executed based on N-1 offline approval
   - Ledger is updated locally; sync to external storage happens only after network reconnection

3. **Asymmetric Ledger Sync Protocol:**
   - When network reconnects: local ledger is synced to external witness (blockchain, cloud notary)
   - Sync is one-directional: external witness receives ledger entries, checks Merkle root consistency
   - If local and external ledgers diverge: external ledger is treated as authoritative (prevents offline tampering)
   - Offline execution remains valid (cryptographic signatures prove it happened); external sync provides tampering proof

4. **Military / Aerospace Applications:**
   - Claimed use case: autonomous drone swarm in jamming environment (no satellite comms)
   - Claimed use case: submarine AI system (no external connectivity for months)
   - Claimed use case: nuclear power plant emergency shutdown (fail-closed safety critical)
   - All use cases require provable offline consensus; Claim 5 covers this specifically

---

### CLAIM 6: N-1 Consensus Attestation for Failure Resilience

**The method of Claim 2-4, wherein N-1 approval ensures that loss of any single validator node does not block execution, comprising:**

1. **Fault Tolerance Guarantee:**
   - N = total validator nodes in quorum
   - Approval threshold = N-1 (requires all but one)
   - If any one node fails (network partition, crash, Byzantine vote), N-1 >= approval count
   - Execution proceeds without delay (no waiting for failed node)
   - Failed node is marked offline; temporary replacement validator is recruited from backup pool

2. **Asymmetric Failure Handling:**
   - Validator node failure modes:
     - Network partition (can't communicate): node is counted as offline after timeout
     - Crash (disappears): node is marked faulty; replacement starts consensus from current state
     - Byzantine vote (contradictory): node is caught via cross-verification; marked faulty and excluded
   - For each failure type: N-1 approval quorum guarantees decision can proceed
   - No decision is ever blocked because one node is down (fail-closed semantics preserved)

3. **Majority Proof for Regulatory Audit:**
   - Approval record includes: [decision_id, [approver_ids...], [timestamps...], [signatures...]]
   - For N=7, N-1=6 approvals means: at least 86% of quorum approved (supermajority)
   - Supermajority proof is stored in ledger and can be verified by regulators
   - Enables compliance narrative: "Decision was approved by supermajority and cannot be blocked by single node failure"

4. **Cascading Failure Detection:**
   - System monitors approval latency for each validator (e.g., response time = 100ms ± 50ms)
   - If validator response time spikes to >500ms: mark as faulty candidate
   - If validator consistently votes contradict other validators: mark as Byzantine
   - Faulty validators are escalated to human operator; ledger records reason for removal
   - Ensures N-1 quorum remains honest (not just N-1 in count, but N-1 of honest validators)

---

### CLAIM 7: Cryptographic Proof of Execution Path Without Re-Computation

**The method of Claim 1-4, wherein execution results are verified without re-running the autonomous agent, comprising:**

1. **Execution Proof Chain:**
   - Agent execution produces: [input_state, decision_hash, execution_trace, output_state, execution_cost]
   - Execution trace records all deterministic steps: [step_0_hash, step_1_hash, ..., step_N_hash]
   - Output state is hashed and stored as execution_result_hash
   - Execution proof = [decision_hash + execution_trace + execution_result_hash + Ed25519_signature_by_executor]

2. **Verification Without Re-Execution:**
   - Auditor receives execution proof (no access to original agent code)
   - Auditor downloads from ledger: decision_hash, Merkle root, N-1 approvals, execution_proof
   - Auditor verifies chain of hashes:
     - step_0_hash matches decision_hash ✓
     - step_1_hash is cryptographic commitment to step_0 + deterministic computation ✓
     - step_N_hash commits to execution_result_hash ✓
     - Executor's Ed25519 signature validates ✓
   - If all hashes validate: auditor can prove execution happened without re-running agent
   - Computation cost ≈ O(N) hash verifications (N = number of execution steps)

3. **Deterministic Computation Binding:**
   - Agent code is compiled with deterministic randomness:
     - Random seed = hash(input_state + decision_hash + timestamp_rounded_to_1_second)
     - Output of deterministic agent is always same given same input
     - Execution trace is therefore reproducible by auditor
   - For non-deterministic agents (e.g., LLMs with temperature>0):
     - System records each LLM output token + its logit score
     - Auditor can verify logit scores match LLM model output (without calling LLM)
     - Enables proof without re-querying cloud API

4. **Failure Proof & Audit Trail:**
   - If execution_result_hash doesn't match claimed output: execution proof is invalid
   - Ledger records: [execution_proof_id, verification_result, discrepancy_hash, auditor_id, timestamp]
   - Discrepancy triggers investigation: either executor lied or agent non-determinism occurred
   - Cryptographic proof enables blame assignment: "Executor signature is valid, so agent non-determinism must have occurred"

---

## PRIOR ART DIFFERENTIATION

| Prior Art | Reference | Our Differentiation |
|-----------|-----------|-------------------|
| **Merkle Trees for Storage** | US9705730B1 | We use Merkle-DAG specifically for decision provenance + governance, not general storage. Parent-hashing creates immutable causality chain (novel). |
| **Digital Signatures (RSA/ECDSA)** | US4309569A | We combine Ed25519 signing with pre-execution gates. Prior art is static signing; we add real-time consensus validation (N-1 approval) and fail-closed semantics. |
| **Blockchain Consensus (PoW/PoS)** | Bitcoin, Ethereum | Blockchain validates transactions post-hoc (settled on ledger). We validate decisions pre-execution (before action). Different problem space. |
| **OneTrust Post-Hoc Monitoring** | OneTrust platform | Post-hoc monitoring detects harm after it occurs. We prevent harm pre-execution via fail-closed gates. Complementary, not overlapping. |
| **LangGraph DAG Execution** | LangChain 1.2 | LangGraph records execution as ungoverned DAG. We govern execution with cryptographic signatures + consensus before action is permitted. |
| **Byzantine Fault Tolerance (PBFT)** | Castro & Liskov 1999 | PBFT requires 3f+1 nodes for consensus (f=faulty). We require N-1 (simpler threshold). PBFT is designed for untrusted networks; we assume some validators are trusted (simpler protocol, faster consensus). |

---

## CLAIMS STRUCTURE SUMMARY

**Core Invention (Claim 1):**
- Merkle-DAG ledger + Ed25519 signatures + pre-execution gate = cryptographic proof of decision before action

**Enhancement (Claim 2):**
- Adds N-1 consensus validation = distributed approval required before execution

**Infrastructure (Claim 3):**
- Governance ledger architecture = append-only, tamper-evident, decision-rooted storage

**Defense (Claim 4):**
- Temporal decay + adversarial sampling = real-time risk scoring to strengthen consensus decisions

**Dependent Claims (5-7):**
- Fallback positions if core claims are challenged
- Claim 5: Air-gapped networks (military application)
- Claim 6: Failure resilience (redundancy argument)
- Claim 7: Proof without re-computation (efficiency argument)

---

## WIPO FORMAT COMPLIANCE

- **Title:** Pre-Execution Governance Architecture for Autonomous Systems (concise, descriptor)
- **Abstract:** Single paragraph, technical language, <150 words ✓
- **Claims:** Numbered 1-7, independent first (1-4), dependent after (5-7) ✓
- **Language:** English (WIPO working language) ✓
- **Format:** Markdown (will be converted to .txt for WIPO portal) ✓
- **Designation:** USA, EU, Japan, China (all four markets covered) ✓

---

## NEXT STEPS FOR FILING

1. Convert to plain text format (.txt) for WIPO portal (remove markdown formatting)
2. Combine with technical_disclosure.md (6-page specification)
3. Combine with drawings.md (ASCII diagrams → formal PDF illustrations)
4. Prepare pct_filing_checklist.md (step-by-step WIPO instructions)
5. File on WIPO PCT portal June 26, 2026
6. Receive filing receipt with priority date lock (global 30-month window)
