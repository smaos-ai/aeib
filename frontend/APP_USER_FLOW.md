# SMAOS Dashboard — User Flow Guide

## Complete Journey (15-30 minutes)

---

## 1️⃣ LANDING PAGE (30 sec)

**What you see:**
- Big blue hero text: "Deploy AI. Stay Compliant. Ship on Time."
- 4 person cards (personas with pain points)
- 6 problem cards
- 6 solution cards
- 6 outcome metrics

**What you do:**
- Click blue button: **"▶ Enter Interactive Demo"**

**Result:** → Proceeds to ONBOARDING

---

## 2️⃣ ONBOARDING MODAL (5-7 min)

**What you see:**
- 7-screen interactive tutorial
- Each screen explains one phase of the journey

**Screen 1: Welcome**
- Introduction to SMAOS
- Click: "Next"

**Screen 2: PRE-FLIGHT Phase**
- Learn about the learning/prep phase
- What you'll do: review architecture & compliance

**Screen 3: LAUNCH Phase**
- Learn about initialization
- What happens: systems boot up, countdown timer

**Screen 4: FLYING Phase**
- Learn about live monitoring
- What you see: real-time graphs, DAG flow, terminal logs

**Screen 5: ARRIVAL Phase**
- Learn about completion & proof
- What you get: audit trail, signatures

**Screen 6: Pro Tips**
- Best practices for using the system

**Screen 7: Ready to Go!**
- Click: **"🚀 Let's Go!"**

**Result:** → Proceeds to PRE-FLIGHT PHASE

---

## 3️⃣ PRE-FLIGHT PHASE 🔵 (5 min)

**What you see:**
- 4 blue cards with information

### Card 1: Architecture Guide
- Diagram showing: User → Intent → Agent → Policy → Gate → Ledger → DB
- Explains each component
- Button: **"🚀 READY FOR LAUNCH?"**

### Card 2: Regulatory Dashboard
- Compliance timeline
- Regulatory requirements
- Status indicators

### Card 3: Evidence Completeness
- Checklist of what's been verified
- Progress bars

### Card 4: Button Reference
- Guide explaining all buttons in the system

**What you do:**
- Read the information
- Click: **"🚀 READY FOR LAUNCH?"**

**Result:**
- Phase changes to LAUNCH
- Countdown starts: T-5, T-4, T-3...
- System initialization begins

---

## 4️⃣ LAUNCH PHASE 🟡 (30-60 sec)

**What you see:**

### Top: Big Countdown Timer
- T-5, T-4, T-3, T-2, T-1, T-0 (BLASTOFF!)
- Orange text showing seconds remaining

### Left Card: SYSTEM STATUS
- 6 systems initializing in sequence:
  1. ✓ Policy Engine initialized
  2. ✓ Knowledge Base connected
  3. ✓ Permit Gates configured
  4. ✓ MCP Servers registered
  5. ✓ Infrastructure online
  6. ✓ Proof Ledger anchored

- Progress bars fill as each completes

### Right Card: INITIALIZATION LOG
- Real-time log entries appear
- Timestamps for each event
- Color-coded: green=success, gray=info

### Bottom: Progress Percentage
- 0% → 100% READY FOR LIFTOFF

**What you do:**
- Watch the countdown
- Watch logs appear in real-time
- Wait for auto-transition

**Auto-transition timing:**
- At 100% progress: "🚀 All systems nominal. Launching..."
- After 2 seconds: AUTO-ADVANCES to FLYING phase

---

## 5️⃣ FLYING PHASE ✈️ (10-15 min) ⭐ **MAIN INTERACTION**

**What you see:**

### Top Controls (2 buttons)
1. **"🕸️ Show Entity Graph"** — Toggle to see data relationships
2. **"⚠️ Simulate Veto Gate"** — Trigger a human approval scenario

### Section 1: Agent Execution Flow (DAG)

**Timeline showing 5 steps:**
1. 📥 **User Intent** → Agent receives task (✓ Complete)
2. 🔍 **Policy Check** → Verify EU AI Act (→ Processing)
3. ⚠️ **Veto Gate** → Human review (○ Waiting)
4. ✅ **Approve** → Authorization signed (○ Waiting)
5. 🔒 **Ledger Sign** → Ed25519 recorded (○ Waiting)

**Animation:**
- Each step glows and pulses as it becomes active
- Cycles through automatically every 5 seconds
- Shows current step description below

### Section 2: Entity Relationship Graph (if you click "Show Entity Graph")

**Visual network showing:**
- 8 nodes: User, Intent, Agent, Policy, Gate, Ledger, DB, PII
- Color-coded relationships
- Hover over nodes to highlight connections
- Shows "blast radius" — who can access what

### Section 3: System Status
- Green indicators showing system health
- CPU, RAM, Disk usage
- Real-time metrics

### Section 4: Live Metrics
- Token speed: tok/s (animated)
- Pool status: 2/5 ready
- Network status: AIRGAP VERIFIED
- Policy status: A+ grade

### Section 5: Terminal Stream (HQTUI)
- Live scrolling terminal logs
- Color-coded messages:
  - 🟢 Green = Success
  - 🔵 Blue = Info
  - 🟡 Orange = Warning
  - 🔴 Red = Error
- Timestamps on each entry
- Auto-scrolls to latest log

### Section 6: System Flows
- Visual diagram of data flow
- Shows how components interact

### Section 7: Transaction Simulator
- Simulate running a transaction
- See what policies are checked
- Watch logs in real-time

---

## 6️⃣ VETO GATE SCENARIO (if you click "⚠️ Simulate Veto Gate")

**What you see:**
- Full-screen modal overlay
- **⚠️ HUMAN VETO GATE** header
- Dark semi-transparent background

**Modal shows:**
```
TOOL: database.query_pii_table
LEGAL REASON: EU AI Act Article 14 — PII Access Gate
ACTION: User requested access to customer data
DECISION REQUIRED: Approve or Block?

✅ AUTHORIZE & SIGN (blue button)
❌ BLOCK THIS ACTION (red button)
```

**What you do:**
- Click **"✅ AUTHORIZE & SIGN"** to approve
  - Ed25519 signature generated
  - Ledger entry recorded
  - Modal closes
  - Flow continues
  
- OR click **"❌ BLOCK THIS ACTION"** to reject
  - Action denied
  - Reason: "Human veto"
  - Ledger entry recorded
  - Modal closes

**Result:**
- Either way, the action is logged and signed
- Terminal shows the decision
- System continues monitoring

---

## 7️⃣ LANDING / ARRIVAL PHASE ✈️ (2-5 min)

**How to get here:**
- Click **"🛬 LAND / SHUTDOWN"** button in FLYING phase

**What you see:**

### Airport Arrival Board Style
```
FLIGHT #847 — ARRIVAL BOARD

Destination:    EU AI Act Compliance ✓
Departure:      Sep 1, 2026 — 12:00:00
Arrival:        Sep 1, 2026 — 12:45:22
Duration:       45 min 22 sec
Status:         ✅ ARRIVED SAFELY
```

### Flight Data Recorder (Black Box)
- 8 entries logged during the flight:
  1. [12:00:00] Policy Engine initialized
  2. [12:15:22] Agent.plan executed
  3. [12:20:44] Gate.allow approved by human
  4. [12:35:11] Sign.receipt recorded
  5. ... (more entries)
  6. [12:45:22] ARRIVAL — All actions logged

### Ledger Proof Section
- Shows Ed25519 signature
- Copy button for proof ID
- Example: `ed25519:abc123def456...`

### Action Buttons
1. **"📥 Download Boarding Pass"** → Save audit trail as PDF/JSON
2. **"🔄 New Flight"** → Reset and start over (return to PRE-FLIGHT)

---

## 🎯 COMPLETE FLOW SUMMARY

```
┌─────────────────┐
│  Landing Page   │  ← You are here first
│  (learn & enter)│
└────────┬────────┘
         │ Click: "Enter Demo"
         ▼
┌─────────────────┐
│  Onboarding     │  ← Learn the 5 phases
│  (7 screens)    │
└────────┬────────┘
         │ Click: "Let's Go"
         ▼
┌─────────────────┐
│  PRE-FLIGHT 🔵  │  ← Read & understand
│  (Architecture) │
└────────┬────────┘
         │ Click: "Ready for Launch"
         ▼
┌─────────────────┐
│  LAUNCH 🟡      │  ← Auto 30-60 sec
│  (Countdown)    │
└────────┬────────┘
         │ Auto-transition
         ▼
┌─────────────────┐
│  FLYING ✈️      │  ← Main experience
│  (Monitoring)   │     10-15 min
└────────┬────────┘
         │ Click: "Land"
         ▼
┌─────────────────┐
│  ARRIVAL ✈️     │  ← View results
│  (Proof)        │
└────────┬────────┘
         │ Click: "New Flight"
         │ (Loop back to PRE-FLIGHT)
         │
         └─────────────────────────────────┐
                                           ▼
                                    (Back to PRE-FLIGHT)
```

---

## 💡 KEY INTERACTION POINTS

### Buttons That Change Phase
- **"🚀 READY FOR LAUNCH?"** — PRE-FLIGHT → LAUNCH
- **"🛬 LAND / SHUTDOWN"** — FLYING → ARRIVAL
- **"🔄 New Flight"** — ARRIVAL → PRE-FLIGHT
- **"Back to Pre-Flight"** — FLYING → PRE-FLIGHT

### Buttons That Toggle Views
- **"🕸️ Show/Hide Entity Graph"** — Shows/hides relationship network
- **"⚠️ Simulate Veto Gate"** — Opens approval modal

### Navigation (Left Sidebar)
- Click section names to jump to that part of FLYING phase
- Options: Status, Ports, Metrics, Terminal, Flows, Simulator, DAG, Ledger

### Real-Time Updates
- Terminal Stream: logs appear every 500ms
- Metrics: update every 1 second
- DAG: cycles through steps every 5 seconds
- All animate smoothly

---

## 🎓 WHAT YOU LEARN

**Landing Page:** Why you need this (problems + solutions)

**Onboarding:** How the 5 phases work (theory)

**PRE-FLIGHT:** What the system is (architecture + compliance)

**LAUNCH:** How fast it initializes (30-60 sec demo)

**FLYING:** Live monitoring in action (real-time logs, graphs, decisions)

**ARRIVAL:** Proof of what happened (audit trail + signatures)

---

## ✅ YOU SUCCESSFULLY COMPLETED:

1. ✓ Saw the system architecture
2. ✓ Watched initialization countdown
3. ✓ Monitored live execution flow
4. ✓ Reviewed system health & metrics
5. ✓ Made a human approval decision (veto gate)
6. ✓ Got a cryptographically signed audit trail
7. ✓ Understood the complete compliance flow

**Time spent:** 15-30 minutes  
**Knowledge gained:** Full understanding of SMAOS governance model
