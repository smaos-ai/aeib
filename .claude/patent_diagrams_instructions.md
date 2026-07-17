# PATENT DRAWINGS INSTRUCTIONS
## How to Create Figures 1-5

**Tools to use:** PowerPoint, Google Slides, Lucidchart (free), or draw.io  
**Format:** Save as PDF or PNG (600 dpi for USPTO quality)  
**Size:** Each figure should fit on 8.5" x 11" page with 1-inch margins

---

## FIGURE 1: Merkle-DAG Audit Chain Structure

**ASCII Reference:**
```
Node 1 (Genesis)
├─ Index: 1
├─ Decision Data: [AI output A]
├─ Parent Hash: None
├─ Self Hash: SHA256(data_A)
└─ Signature: ED25519(hash_1)
       ↓
       └──────────────────────┐
                              ↓
                    Node 2
                    ├─ Index: 2
                    ├─ Decision Data: [AI output B]
                    ├─ Parent Hash: hash_1 ←──┐
                    ├─ Self Hash: SHA256(hash_1 + data_B)
                    └─ Signature: ED25519(hash_2)
                           ↓
                           └──────────────────────┐
                                                  ↓
                                        Node 3
                                        ├─ Index: 3
                                        ├─ Decision Data: [AI output C]
                                        ├─ Parent Hash: hash_2 ←──┐
                                        ├─ Self Hash: SHA256(hash_2 + data_C)
                                        └─ Signature: ED25519(hash_3)
```

**How to draw:**
1. Draw 3 boxes (Node 1, Node 2, Node 3) vertically stacked
2. Inside each box, write:
   - Index number (1, 2, 3)
   - "Data: [AI decision]"
   - "Parent Hash: [previous hash]" (first node has "None")
   - "Self Hash: SHA256(...)"
   - "Signature: ED25519(...)"
3. Draw arrows from each node's "Self Hash" pointing to next node's "Parent Hash"
4. Add label: "Append-Only Chain: Each node references parent via hash"
5. Add callout box: "Immutability: Changing Node 1 would invalidate Nodes 2 & 3"

---

## FIGURE 2: Pre-Execution Governance Gate Logic

**ASCII Reference:**
```
┌─────────────────────────────────────────────────┐
│ AI Decision Arrives                             │
└────────────────────┬────────────────────────────┘
                     ↓
        ┌────────────────────────┐
        │ Gate 1: Known System?  │
        │ (Is this AI trusted?)  │
        └────────┬───────────────┘
                 │ YES
                 ↓
        ┌────────────────────────┐
        │ Gate 2: Fresh?         │
        │ (Temporal decay check) │
        │ (Not injected 5h ago?) │
        └────────┬───────────────┘
                 │ PASS
                 ↓
        ┌────────────────────────────────────────┐
        │ Gate 3: Merkle Commit                  │
        │ Append to audit chain, generate hash   │
        └────────┬───────────────────────────────┘
                 │ COMMITTED
                 ↓
        ┌─────────────────────────────────────────────┐
        │ Gate 4: N-1 Consensus Validation           │
        │ Send decision to 5 validators               │
        │ Validator 1: ✓ Approve                      │
        │ Validator 2: ✓ Approve                      │
        │ Validator 3: ✗ Reject                       │
        │ Validator 4: ✓ Approve                      │
        │ Validator 5: ✓ Approve                      │
        │ Result: 4/5 APPROVE (4 ≥ N-1=4) ✓ PASS    │
        └────────┬────────────────────────────────────┘
                 │ CONSENSUS ACHIEVED
                 ↓
        ┌────────────────────────┐
        │ Gate 5: Sign Decision  │
        │ ED25519 signature      │
        └────────┬───────────────┘
                 │ SIGNED
                 ↓
        ┌────────────────────────┐
        │ ✓ EXECUTE ACTION       │
        │ (All gates passed)     │
        └────────────────────────┘

Fail-Closed Rule:
If ANY gate fails → REJECT (default DENY)
```

**How to draw:**
1. Draw 5 boxes vertically (Gates 1-5)
2. Each box has decision logic inside
3. Gate 4 shows validator voting details (5 boxes with checkmarks/X)
4. Draw arrows connecting gates
5. Add red box at bottom right: "REJECT" with arrows from failed gates
6. Add green box at bottom left: "✓ EXECUTE" for success path
7. Title: "Pre-Execution Governance: Fail-Closed Enforcement"

---

## FIGURE 3: Swarm Consensus Voting (N-1 Byzantine)

**ASCII Reference:**
```
                    Decision Hash
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                   ↓
   ┌────────────┐                    ┌────────────┐
   │ Validator  │                    │ Validator  │
   │     1      │                    │     5      │
   │ ✓ APPROVE  │                    │ ✓ APPROVE  │
   └────┬───────┘                    └────┬───────┘
        │                                  │
        │    ┌──────────────┐              │
        └───→│  Vote Count  │←─────────────┘
             │              │
             │  4/5 Votes   │
             │  ≥ N-1 (4)?  │
             │    YES ✓     │
             └──────┬───────┘
                    ↓
            ┌──────────────┐
            │  CONSENSUS   │
            │   ACHIEVED   │
            └──────────────┘

N-1 Byzantine Fault Tolerance:
- N validators total: 5
- N-1 requirement: 4 votes minimum
- Security: System safe if ≤1 validator compromised
- Failure: 3 or fewer votes = REJECT decision
```

**How to draw:**
1. Draw 5 circles representing validators (arranged in a circle)
2. Label each: "Validator 1", "Validator 2", etc.
3. Show voting results next to each (✓ APPROVE or ✗ REJECT)
4. Draw arrows from each validator to a central "Vote Count" box
5. In central box, show: "4/5 votes" and "N-1 = 4, PASS ✓"
6. Add callout: "If 3 or fewer approve: Decision REJECTED"

---

## FIGURE 4: Temporal Decay Risk Scoring

**ASCII Reference:**
```
Confidence Score vs. Age

100% ┌─────────────────────────────────────
     │  Fresh Decision
     │  (Just committed to chain)
     │
 75% │         ╲
     │          ╲
 50% │           ╲  ← Half-life line (1 hour)
     │            ╲
 25% │             ╲___
     │                 ╲___
 10% ├─────────────────────╲─────  REJECT THRESHOLD
  0% │                      ╲___________
     └──────────────────────────────────── Time
       0h   1h   2h   3h   4h   5h   6h

Example: Decision age = 5 hours
- Confidence = exp(-5 hours / 1 hour) ≈ 0.007 (< 10%)
- Action: REJECT (too old, likely adversarial injection)

Decision age = 30 minutes
- Confidence = exp(-0.5) ≈ 0.61 (> 10%)
- Action: ACCEPT (fresh enough)
```

**How to draw:**
1. Draw X-axis labeled "Time (hours)" from 0 to 6
2. Draw Y-axis labeled "Confidence (%)" from 0 to 100%
3. Plot exponential decay curve: steeply downward, flattens out
4. Draw horizontal line at 10% labeled "REJECT THRESHOLD"
5. Mark area above line "ACCEPT ZONE" (green)
6. Mark area below line "REJECT ZONE" (red)
7. Add annotation: "Half-life = 1 hour"
8. Add example point: "5h old = 0.7% (REJECT)"

---

## FIGURE 5: End-to-End System Architecture

**ASCII Reference:**
```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────┘

INPUT LAYER:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ AI Model 1   │  │ AI Model 2   │  │ AI Model N   │
│ (Decision A) │  │ (Decision B) │  │ (Decision C) │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ↓
        ┌─────────────────────────────────┐
        │   GOVERNANCE GATE VALIDATION    │
        │ ├─ Known AI System Check        │
        │ ├─ Temporal Decay Check         │
        │ └─ Replay Attack Detection      │
        └──────────────┬──────────────────┘
                       ↓
        ┌──────────────────────────────────┐
        │  MERKLE-DAG AUDIT CHAIN          │
        │  ├─ Append Decision              │
        │  ├─ Compute Parent Hash          │
        │  ├─ Compute Self Hash            │
        │  └─ Store Immutably              │
        └──────────────┬───────────────────┘
                       ↓
        ┌──────────────────────────────────┐
        │  SWARM CONSENSUS VALIDATION      │
        │  ├─ Validator 1: ✓ Approve       │
        │  ├─ Validator 2: ✓ Approve       │
        │  ├─ Validator 3: ✗ Reject        │
        │  ├─ Validator 4: ✓ Approve       │
        │  ├─ Validator 5: ✓ Approve       │
        │  └─ Result: 4/5 PASS (N-1=4)     │
        └──────────────┬───────────────────┘
                       ↓
        ┌──────────────────────────────────┐
        │    CRYPTOGRAPHIC ATTESTATION     │
        │    ├─ Sign with ED25519          │
        │    ├─ Generate Signature         │
        │    └─ Attach to Decision Record  │
        └──────────────┬───────────────────┘
                       ↓
OUTPUT LAYER:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Action A     │  │ Action B     │  │ Action C     │
│ Executed ✓   │  │ Executed ✓   │  │ Executed ✓   │
│ + Proof      │  │ + Proof      │  │ + Proof      │
└──────────────┘  └──────────────┘  └──────────────┘

With Merkle Proof + Ed25519 Signature + Validator Audit Trail
```

**How to draw:**
1. Draw 3 input boxes at top (AI Model 1, 2, N)
2. Draw arrows converging to central "Governance Gate" box
3. Below that, stack boxes vertically: Gate → Merkle-DAG → Validators → Signature
4. Each box shows key internal steps
5. Arrows point downward through each stage
6. At bottom, show 3 output boxes (Actions A, B, C with ✓ checkmarks)
7. Title: "Pre-Execution Governance: Complete Pipeline"

---

## QUICK CREATE GUIDE (PowerPoint)

**Using Microsoft PowerPoint:**
1. Open PowerPoint → New Blank Presentation
2. For each figure:
   - Insert → Shapes → Rectangle (for boxes)
   - Insert → Shapes → Line/Arrow (for connections)
   - Insert → Text Box (for labels)
   - Right-click → Format Shape → Colors (green for PASS, red for FAIL)
3. Export as PDF:
   - File → Export As → PDF
   - Save as: `Figure_1.pdf`, `Figure_2.pdf`, etc.

**Minimum viable:**
- PowerPoint quality is acceptable for USPTO filing
- Hand-drawn + scanned is also acceptable (must be legible)
- Professional graphics not required, but clarity is essential

---

## FILE NAMING FOR USPTO

Save figures as:
- `Figure_1_Merkle_DAG.pdf`
- `Figure_2_Governance_Gate.pdf`
- `Figure_3_Swarm_Consensus.pdf`
- `Figure_4_Temporal_Decay.pdf`
- `Figure_5_System_Architecture.pdf`

All files must be:
- Black & white (or color, both acceptable)
- 600 dpi minimum resolution
- PDF or TIFF format (not JPEG for USPTO submission)
