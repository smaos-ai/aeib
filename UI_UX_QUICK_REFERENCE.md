# SMAOS Dashboard UI/UX Quick Reference
## Actionable Implementation Checklist

**Status:** Ready for Phase 1 Frontend Dev  
**Target:** 4-phase journey visualization for harness v1.0  
**Owner:** Frontend Team  

---

## EXECUTIVE SUMMARY

```
SMAOS UI = 4 phases + 8 layers + immutable proof trail

PRE-FLIGHT   →   LAUNCH   →   FLYING   →   BLACK BOX
(Setup)          (Ignition)    (Monitor)     (Archive)
5-30 min         10-60 sec     Hours         Ongoing
```

---

## PHASE 1: PRE-FLIGHT (Setup) — WEEK 1

### What to Show
- [ ] Checklist (✓/○/✗ states)
- [ ] System requirements table
- [ ] Configuration wizard (step counter)
- [ ] Prerequisites verifier
- [ ] Learning sidebar (documentation links)
- [ ] "Ready for launch?" button (initially disabled)

### Colors & Style
- **Primary:** Blueprint blue (#2C3E50)
- **Accent:** Light gray backgrounds
- **Font:** Monospace for values, sans-serif for labels
- **Aesthetic:** Technical, engineering-like, professional

### Key Component
```html
<ProgressBar>
  [✓ Policy] [✓ Database] [○ Config] [✗ Team]
  3 of 4 complete (75%)
</ProgressBar>
```

### SMAOS L1-L3 Mapping
```
PRE-FLIGHT shows:
├─ L1: "Policy rules loaded: 47 active rules"
├─ L2: "Knowledge base ready: 2500 vectors indexed"
└─ L3: "Permit gates configured: 6 gates armed"
```

### User Flow
1. User lands on dashboard
2. Sees checklist with incomplete items
3. Completes each section (database, API keys, etc.)
4. "Ready?" button becomes enabled
5. User clicks → Transition to LAUNCH phase

---

## PHASE 2: LAUNCH (Ignition) — WEEK 2

### What to Show
- [ ] Countdown timer (T-5... T-4... T-3...)
- [ ] Health check progress bars (one per subsystem)
- [ ] Ignition animation (rising visual energy)
- [ ] Status message ("Initializing...")
- [ ] "Begin flight" button (disabled until checks pass)
- [ ] Abort button (secondary)

### Colors & Style
- **Primary:** Energy orange (#FF6B35), electric blue (#004E89)
- **Background:** Dark (#1a1f2e to #16213e)
- **Animation:** Pulse, countdown blink, progress fill
- **Font:** Large countdown (120px+), bold, monospace

### Key Component
```html
<CountdownTimer>
  <Value>00:05</Value>
  <HealthCheck name="Policy Engine" progress={100} />
  <HealthCheck name="Knowledge Base" progress={75} />
  <HealthCheck name="Permit Gates" progress={100} />
</CountdownTimer>
```

### SMAOS L1-L8 Mapping
```
LAUNCH shows 6 health checks:
├─ L1: "Policy engine initialized"
├─ L2: "Loading vectors (2500/3400)... 73%"
├─ L3: "Arming permit gates..."
├─ L4: "Orchestration loading..."
├─ L5: "MCP servers connecting (3/6)..."
├─ L6: "Infrastructure ready"
├─ L8: "Proof ledger initializing..."
└─ L7: "RAGAS baseline loading..."
```

### Transition Rule
When all checks reach 100% → Show "Systems nominal" popup → Enable "Begin flight"

---

## PHASE 3: FLYING (Monitor) — WEEK 3

### What to Show
- [ ] Metrics grid (8 cards: requests, latency, accuracy, throughput, CPU, memory, fuel, duration)
- [ ] Status indicators (● green/yellow/red dots)
- [ ] Live event log (scrollable, latest on top)
- [ ] Real-time line charts (optional but recommended)
- [ ] Pause/Land buttons
- [ ] Current timestamp (always visible)

### Colors & Style
- **Primary:** Live green (#2ECC71), alert orange (#F39C12), error red (#E74C3C)
- **Background:** Dark (#0f0f0f)
- **Theme:** Mission control (Datadog/New Relic style)
- **Font:** Monospace throughout (metrics, logs, timestamps)

### Key Component
```html
<MetricsGrid>
  <MetricCard label="Requests" value={42} unit="/min" />
  <MetricCard label="Latency" value={87} unit="ms" status="good" />
  <MetricCard label="Accuracy" value={99.2} unit="%" bar={true} />
  <MetricCard label="Throughput" value={1200} unit="msg/s" />
  <MetricCard label="CPU" value={45} unit="%" bar={true} />
  <MetricCard label="Memory" value={62} unit="%" bar={true} />
  <MetricCard label="Fuel" value={234} unit="min" warning={true} />
  <MetricCard label="Duration" value="2h 14m" unit="elapsed" />
</MetricsGrid>

<EventLog>
  14:35:22 [INFO] Policy: 42 requests processed
  14:35:18 [INFO] Knowledge: 87ms latency
  14:35:10 [WARN] Memory: 62% threshold
</EventLog>
```

### SMAOS L1-L8 Mapping
```
FLYING shows live metrics per layer:
├─ L1: Policy requests/min + chart
├─ L2: Knowledge latency (ms) + accuracy
├─ L3: Permit decisions (approved/denied)
├─ L4: Orchestration status (pilots running)
├─ L5: MCP throughput (msg/s) + connections
├─ L6: CPU/memory gauges + alerts
├─ L7: RAGAS accuracy (%) + golden set progress
├─ L8: Event count (increments per action)
```

### User Interactions
- Hover metrics → Show 24hr history
- Click event log entry → Expand detail
- Click "Pause" → Freeze metrics, show pause UI
- Click "Land" → Transition to BLACK BOX

---

## PHASE 4: BLACK BOX (Archive) — WEEK 4

### What to Show
- [ ] Immutable ledger table (# | Timestamp | Action | Actor | Signature)
- [ ] Expandable signature details (ED25519, public key, verification)
- [ ] Search/filter UI (date range, action type, actor)
- [ ] Export buttons (JSON, CSV, signed PDF)
- [ ] Proof artifacts section (chain of custody, tamper detection)
- [ ] Entry count (1251 entries, 100% signed)

### Colors & Style
- **Primary:** Dark charcoal (#1C1C1C), mono white (#E8E8E8)
- **Accent:** Green for verified (#27AE60)
- **Background:** Near-black (#0A0A0A)
- **Font:** Monospace for everything (hashes, signatures, timestamps)

### Key Component
```html
<LedgerTable>
  <Row>
    <Col>#</Col>
    <Col timestamp>2026-09-01 14:23:15</Col>
    <Col action="LAUNCH" />
    <Col actor>user@company</Col>
    <Col signature>sig_abc123...</Col>
    <Expand>
      <FullSignature>3c4a5b6c7d8e...</FullSignature>
      <PublicKey>ed25519_pub_key_...</PublicKey>
      <Verified>✓ Valid (PQC-resistant)</Verified>
    </Expand>
  </Row>
</LedgerTable>

<Artifacts>
  Chain of Custody: ✓ Verified
  Tamper Detection: ✓ No tampering
  Signatures: 1251/1251 (100%)
  Last Verification: 2026-09-01 14:35Z
</Artifacts>
```

### SMAOS L1-L8 Mapping
```
BLACK BOX shows ALL actions:
├─ L1: POLICY_EVAL, POLICY_CHANGE
├─ L2: QUERY, INDEXING, LATENCY_ALERT
├─ L3: PERMIT_GRANT, PERMIT_DENY, OVERRIDE
├─ L4: PILOT_START, PILOT_COMPLETE
├─ L5: MCP_MESSAGE_SENT, MCP_MESSAGE_RECV
├─ L6: RESOURCE_ALERT, SCALING_EVENT
├─ L7: RAGAS_EVAL, ACCURACY_CHANGE
└─ L8: PROOF_SIGNED, CHAIN_LINK, EXPORT

Every entry: timestamp (UTC) + actor + signature (ED25519)
All immutable after 12 confirmations
```

### User Interactions
- Type in search → Filter ledger (regex or simple match)
- Click filter button → Show only POLICY/CONFIG/ACTION/ALERT
- Click row → Expand full signature details
- Click "Verify All" → Run cryptographic verification
- Click "Export" → Download signed JSON (entire ledger)

---

## PHASE PROGRESS COMPONENT (ALL PHASES)

**Always visible at top:**

```html
<PhaseProgress>
  <Step status="complete" phase="PRE-FLIGHT" />
  <Connector status="complete" />
  <Step status="active" phase="LAUNCH" />
  <Connector status="pending" />
  <Step status="pending" phase="FLYING" />
  <Connector status="pending" />
  <Step status="recording" phase="BLACK BOX" />
</PhaseProgress>

Status states:
- complete: ✓ green, pulsed
- active: ⚡ orange, pulsing
- pending: ○ gray
- recording: ⚫ red, pulsing
```

**CSS Pattern:**
```css
.phase-step.active .phase-dot {
  background: #ff6b35;
  animation: pulse-orange 2s infinite;
}

.phase-step.recording .phase-dot {
  background: #e74c3c;
  animation: pulse-red 1s infinite;
}
```

---

## STATE MANAGEMENT ARCHITECTURE

```
React Context Tree:

AppContext
├─ currentPhase: 'PRE_FLIGHT' | 'LAUNCH' | 'FLYING' | 'BLACK_BOX'
├─ launchCountdown: number (seconds remaining)
├─ healthChecks: { [layer: string]: { status, progress, message } }
├─ liveMetrics: { [metric: string]: number | string }
├─ eventLog: Event[]
├─ ledger: LedgerEntry[] (immutable, append-only)
└─ uiState: { alertsVisible, sidebarOpen, selectedLogEntry }

Transitions:
PRE_FLIGHT → (user clicks "Ready") → LAUNCH
LAUNCH → (all checks 100%) → FLYING
FLYING → (user clicks "Land") → BLACK_BOX
BLACK_BOX → (user clicks "Reset") → PRE_FLIGHT (new session)
```

---

## DATA FLOW (8 Layers → UI)

```
L1 (Policy):         {requests: 42, policy_id: 'p47'} → Metrics card
L2 (Knowledge):      {latency_ms: 87, accuracy: 99.2} → Metrics card
L3 (Permit):         {approved: 41, denied: 6} → Event + Metrics
L4 (Orchestration):  {pilots_active: 3, state: 'running'} → Metrics
L5 (Communication):  {messages: 1200, throughput: 1.2K} → Metrics + Event
L6 (Infrastructure): {cpu: 45, memory: 62, alert: 'high_mem'} → Metrics + Alert
L7 (RAGAS):          {accuracy: 92%, questions_eval: 45/50} → Metrics
L8 (Proof):          {event: {timestamp, action, signature}} → Ledger row

ALL → Event log (append-only stream)
ALL → BLACK BOX ledger (immutable, signed, timestamped)
```

---

## ALERT SYSTEM

```
Colors (consistent across all phases):

GREEN (#27AE60):  ✓ Nominal / Success / Complete
YELLOW (#F39C12): ⚠ Warning (high memory, slow latency, pending)
RED (#E74C3C):    ✗ Critical (service down, failed check, deny action)
BLUE (#3498DB):   ℹ Info (deployment event, config change)
GRAY (#404040):   ⊘ Offline / Paused / Disabled

Placement:
PRE-FLIGHT: Checklist item borders
LAUNCH: Health check bars
FLYING: Status indicator dots, event log [level]
BLACK BOX: Border on ledger rows (if alert event)
```

---

## KEYBOARD NAVIGATION

```
Tab:        Focus next field
Shift+Tab:  Focus previous field
Enter:      Confirm action (Ready, Begin, Land)
Escape:     Close modal, cancel action
Ctrl+F:     Focus search box (BLACK BOX phase)
Ctrl+L:     Clear event log (FLYING phase)
Ctrl+E:     Export data (BLACK BOX phase)
```

---

## RESPONSIVE DESIGN

```
Desktop (1200px+):
├─ 4-column metric grid
├─ Full ledger table (all columns visible)
└─ Sidebar always visible

Tablet (768px-1199px):
├─ 2-column metric grid
├─ Ledger table scrollable horizontally
└─ Sidebar toggle (hamburger menu)

Mobile (< 768px):
├─ 1-column metric grid
├─ Ledger table stacked (single column, expandable rows)
└─ Sidebar off-canvas
```

---

## ANIMATION TIMINGS

```
Countdown blink:    1s (on/off toggle)
Pulse orange:       2s (scale 0 to 8px shadow)
Pulse red:          1s (fast for critical)
Progress bar fill:  0.5s (smooth linear)
Phase transition:   0.3s (fade in/out)
Metric value update: 0.2s (number animate if possible)
Ledger row hover:   0.2s (background change)
```

---

## ACCESSIBILITY CHECKLIST

- [ ] All colors have sufficient contrast (WCAG AA minimum)
- [ ] Icons have text labels or aria-labels
- [ ] Form inputs have associated labels
- [ ] Keyboard navigation works (no mouse-only interactions)
- [ ] Screen reader tested (VoiceOver, NVDA)
- [ ] Focus indicator visible (outline or border)
- [ ] Timestamps in UTC (no timezone ambiguity)
- [ ] Signature data copyable (click to select, Ctrl+C)

---

## QUICK START (24-48 hours)

**Day 1 (8 hours):**
1. [ ] Create phase progress component (5 hours)
2. [ ] Create metric card component (2 hours)
3. [ ] Stub out 4 page layouts (1 hour)

**Day 2 (8 hours):**
1. [ ] Wire pre-flight checklist (3 hours)
2. [ ] Wire launch countdown + health checks (3 hours)
3. [ ] Wire phase transitions in React Router (2 hours)

**Day 3+ (Implementation of individual phases in parallel):**
- Team A: FLYING dashboard + event log
- Team B: BLACK BOX ledger + search
- Team C: Styling + dark theme toggle
- Team D: Integration tests + accessibility audit

---

## DELIVERABLES (Per Phase)

| Phase | Components | Tests | Accessibility | Est. Time |
|-------|-----------|-------|---|---|
| PRE-FLIGHT | Checklist, Config, Progress | Unit+E2E | WCAG AA | 1 week |
| LAUNCH | Countdown, Health bars, Button | Unit+E2E | WCAG AA | 1 week |
| FLYING | Dashboard, Metrics, Log, Controls | Unit+E2E | WCAG AA | 2 weeks |
| BLACK BOX | Ledger, Search, Export, Proof | Unit+E2E | WCAG AA | 2 weeks |
| **Total** | **12 components** | **24+ tests** | **Audit** | **6 weeks** |

---

## FILE STRUCTURE (Recommended)

```
frontend/src/
├─ components/
│  ├─ Phase/
│  │  ├─ PhaseProgress.tsx
│  │  ├─ PreFlight.tsx
│  │  ├─ Launch.tsx
│  │  ├─ Flying.tsx
│  │  └─ BlackBox.tsx
│  ├─ Cards/
│  │  ├─ MetricCard.tsx
│  │  ├─ StatusCard.tsx
│  │  └─ HealthCheckBar.tsx
│  └─ Layout/
│     ├─ DashboardHeader.tsx
│     ├─ Sidebar.tsx
│     └─ MainContent.tsx
├─ hooks/
│  ├─ usePhase.ts
│  ├─ useLiveMetrics.ts
│  └─ useLedger.ts
├─ types/
│  ├─ phase.ts
│  ├─ metrics.ts
│  └─ ledger.ts
├─ styles/
│  ├─ phase-progress.css
│  ├─ metrics-dashboard.css
│  ├─ ledger-table.css
│  └─ dark-theme.css
└─ pages/
   └─ Dashboard.tsx
```

---

## TESTING STRATEGY

```
Unit Tests:
├─ Component rendering (phase progress, metrics cards)
├─ State transitions (phase changes)
├─ Event log filtering
└─ Ledger sorting/search

E2E Tests:
├─ Full user flow (PRE-FLIGHT → LAUNCH → FLYING → BLACK BOX)
├─ Phase transitions
├─ Data persistence (ledger immutability)
└─ Export functionality

Accessibility Tests:
├─ WCAG AA compliance (color contrast, keyboard nav)
├─ Screen reader testing (NVDA, JAWS)
└─ Focus management

Performance Tests:
├─ Dashboard load time (< 2s)
├─ Live metrics update (real-time, < 100ms latency)
└─ Ledger table render (1000+ rows in < 1s)
```

---

## SUCCESS CRITERIA

- ✅ All 4 phases implemented and tested
- ✅ Phase transitions smooth and logical
- ✅ WCAG AA accessibility compliance
- ✅ Live metrics update in real-time (< 100ms)
- ✅ Ledger immutability enforced (append-only, signed)
- ✅ Performance: Full dashboard loads < 2 seconds
- ✅ Responsive design works on mobile/tablet/desktop
- ✅ Keyboard navigation fully functional

---

## REFERENCES

- Full spec: `/UI_UX_JOURNEY_PATTERNS.md`
- SMAOS Phase 1: `/PHASE1_STATUS.md`
- Hotel pilot: Reference L1→L8 flow in running system
- Examples: Slack (onboarding), Figma (dashboard), DataDog (monitoring)

---

**Owner:** Frontend Lead  
**Deadline:** May 31, 2027 (Phase 1)  
**Priority:** Blockers for KARP submission Sep 16-22  
