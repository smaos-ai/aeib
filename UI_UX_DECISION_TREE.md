# SMAOS Dashboard UI/UX Decision Tree
## Visual Reference for Design & Development Decisions

**Updated:** Sep 1, 2026  
**Purpose:** Quick lookup for UI/UX pattern selection and component choice  
**Audience:** Designers, frontend engineers, product managers  

---

## DECISION TREE: "What should I show right now?"

```
START: User lands on dashboard
│
├─ Is system already configured?
│  ├─ NO → Show PRE-FLIGHT phase
│  │       ├─ Show: Checklist, config panels, learning sidebar
│  │       ├─ Hide: Metrics, monitoring, archive
│  │       └─ Action: "Ready for launch?" button
│  │
│  └─ YES → Is system currently running?
│     ├─ NO, but ready → Show LAUNCH phase
│     │                  ├─ Show: Countdown, health checks, ignition animation
│     │                  ├─ Hide: Metrics, monitoring, archive
│     │                  └─ Action: "Begin flight" button
│     │
│     └─ YES → Show FLYING phase
│        ├─ Show: Live metrics, event log, control buttons
│        ├─ Hide: Config, checklist, learning
│        ├─ Action: "Pause" / "Land" buttons
│        │
│        └─ User clicks "Land" → Show BLACK BOX phase
│           ├─ Show: Immutable ledger, signatures, export
│           ├─ Hide: Real-time metrics (data frozen)
│           └─ Action: "Export" / "Verify" buttons
```

---

## PHASE SELECTION MATRIX

### Quick Lookup Table

| **Criterion** | **PRE-FLIGHT** | **LAUNCH** | **FLYING** | **BLACK BOX** |
|---|---|---|---|---|
| **User Goal** | Verify readiness | Execute startup | Monitor operations | Review audit trail |
| **Duration** | 5-30 min | 10-60 sec | Minutes to hours | Ongoing (background) |
| **Primary Color** | Blue (#2C3E50) | Orange (#FF6B35) | Green (#2ECC71) | Gray (#1C1C1C) |
| **Theme** | Blueprint/technical | Ignition/energy | Mission control | Blockchain explorer |
| **Interactivity** | High (configure) | Medium (watch) | High (monitor/control) | Medium (search/verify) |
| **Data Flow** | Static (config) | Dynamic (initialization) | Real-time (streaming) | Immutable (append-only) |
| **Animation** | Minimal | Heavy (countdown) | Continuous (pulsing) | None (static ledger) |
| **Data Visibility** | ~50 items | ~6 items | ~20 items | 1000+ items |

---

## COMPONENT DECISION TREE

### "Which component should I use?"

```
Need to show progress/completion?
├─ Quick status (✓/○/✗) → ChecklistItem
├─ Linear progress (0-100%) → ProgressBar
├─ Circular progress (pie) → CircularProgress
├─ Multi-step checklist → ChecklistGroup
└─ Phase progression → PhaseProgress (top of page)

Need to display a metric value?
├─ Single number + unit → MetricCard
├─ Multiple related values → MetricsGrid (4+ cards)
├─ Range/threshold comparison → GaugeCard (dial-style)
├─ Historical trend → TrendCard (with sparkline)
└─ Real-time indicator → StatusBadge (with dot)

Need to show system status?
├─ One system → StatusIndicator (● dot)
├─ Multiple systems → StatusGrid (matrix of dots)
├─ Health check with progress → HealthCheckBar
├─ All systems at once → DashboardOverview
└─ Subsystem details → ExpandableCard

Need to show events/timeline?
├─ Recent entries (5-10) → EventLog (scrollable)
├─ All entries with search → LedgerTable (immutable)
├─ Timeline visualization → VerticalTimeline
├─ Actions only → ActionLog
└─ Errors only → AlertLog

Need to show controls?
├─ Single action → Button
├─ Multiple actions (2-3) → ButtonGroup
├─ System control (pause/play) → ControlPanel
├─ Export/advanced → DropdownMenu
└─ Settings → SettingsPanel
```

---

## COLOR DECISION MATRIX

### Choosing colors for different elements

| **Element** | **PRE-FLIGHT** | **LAUNCH** | **FLYING** | **BLACK BOX** |
|---|---|---|---|---|
| **Background** | White (#FFF) | Dark (#1a1f2e) | Very dark (#0f0f0f) | Nearly black (#0a0a0a) |
| **Primary accent** | Blue (#2C3E50) | Orange (#FF6B35) | Green (#2ECC71) | Gray (#595959) |
| **Secondary accent** | Light gray (#ECF0F1) | Blue (#004E89) | Yellow (#F39C12) | Green (#27AE60) |
| **Success indicator** | Green (#27AE60) | Green (#27AE60) | Green (#2ECC71) | Green (#27AE60) |
| **Warning indicator** | Yellow (#F39C12) | Yellow (#F39C12) | Yellow (#F39C12) | Yellow (#F39C12) |
| **Error indicator** | Red (#E74C3C) | Red (#E74C3C) | Red (#E74C3C) | Red (#E74C3C) |
| **Text primary** | Dark gray (#2C3E50) | Light gray (#ECF0F1) | Light gray (#ECF0F1) | Light gray (#E8E8E8) |
| **Text secondary** | Medium gray (#7F8C8D) | Medium gray (#95A5A6) | Medium gray (#95A5A6) | Dark gray (#888) |
| **Border** | Light gray (#E0E0E0) | Dark gray (#404040) | Dark gray (#333) | Dark gray (#333) |
| **Chart gradient** | Blue→Teal | Orange→Yellow | Green→Cyan | Gray→Green |

**Contrast Check:**
- Text on background: Minimum WCAG AA (4.5:1 for small text)
- PRE-FLIGHT white: Dark gray text ✓
- LAUNCH dark: Light gray text ✓
- FLYING dark: Light gray text ✓
- BLACK BOX dark: Light gray text ✓

---

## LAYOUT DECISION TREE

### Page Layout Patterns

```
PRE-FLIGHT Layout:
┌─────────────────────────────────────────────┐
│ Phase Progress (top)                        │
├─────────────────────────────────────────────┤
│ Main: Checklist (center)  │ Sidebar: Docs   │
│                           │                 │
│ ✓ Policy rules            │ ← "Learn more"  │
│ ✓ Database configured     │   links to docs │
│ ○ API keys (pending)      │                 │
│ ✗ Team added (failed)     │                 │
│                           │                 │
│ [Action: "Ready for ..."] │                 │
├─────────────────────────────────────────────┤
│ Footer: Status, Help                        │
└─────────────────────────────────────────────┘

LAUNCH Layout:
┌─────────────────────────────────────────────┐
│ Phase Progress (top)                        │
├─────────────────────────────────────────────┤
│                                             │
│  Countdown: 00:05                          │
│                                             │
│  Policy Engine:    [████████] 100%         │
│  Knowledge Base:   [██████░░] 75%          │
│  Permit Gates:     [████████] 100%         │
│  MCP Servers:      [████░░░░] 50%          │
│  Infrastructure:   [░░░░░░░░] 0%           │
│  Proof Ledger:     [░░░░░░░░] 0%           │
│                                             │
│ Status: "Initializing systems..."          │
│                                             │
│ [Begin Flight]  [Abort Launch]              │
├─────────────────────────────────────────────┤
│ Footer: Est. time, help                     │
└─────────────────────────────────────────────┘

FLYING Layout:
┌─────────────────────────────────────────────┐
│ Phase Progress (top)    | Status badge: ● OK│
├─────────────────────────────────────────────┤
│ Metrics Grid (8 cards):                     │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│ │Req  │ │Lat  │ │Acc  │ │Tput │           │
│ │42/m │ │87ms │ │99.2%│ │1.2K │           │
│ └─────┘ └─────┘ └─────┘ └─────┘           │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│ │CPU  │ │Mem  │ │Fuel │ │Time │           │
│ │45%  │ │62%  │ │234m │ │2h14 │           │
│ └─────┘ └─────┘ └─────┘ └─────┘           │
│                                             │
│ System Status: ● ● ● ● ● ○ (all green)    │
│                                             │
│ Event Log (scrollable):                     │
│ 14:35:22 [INFO] Policy: 42 requests        │
│ 14:35:18 [INFO] Knowledge: 87ms latency    │
│ 14:35:10 [WARN] Memory: 62% threshold      │
│                                             │
│ [Pause Flight]  [Land System]               │
├─────────────────────────────────────────────┤
│ Footer: Real-time, last update              │
└─────────────────────────────────────────────┘

BLACK BOX Layout:
┌─────────────────────────────────────────────┐
│ Phase Progress (top, frozen state)          │
├─────────────────────────────────────────────┤
│ Search: [________________]  [Filters ↓]     │
│                                             │
│ Ledger Table:                               │
│ # | Timestamp | Action | Actor | Signature │
│ ──┼───────────┼────────┼───────┼───────────│
│ 1247 | 14:23:15 | LAUNCH | user | sig_...│
│ 1248 | 14:23:22 | CONFIG | admin | sig_..│
│ 1249 | 14:24:01 | PERMIT | sys | sig_...│
│ (expandable rows for full signature)        │
│                                             │
│ Proof Artifacts:                            │
│ ✓ Chain of custody  | Signatures: 1251     │
│ ✓ No tampering      | Verified: 100%       │
│                                             │
│ [Verify All]  [Export JSON]  [PDF Download]│
├─────────────────────────────────────────────┤
│ Footer: Immutable ledger, signed            │
└─────────────────────────────────────────────┘
```

---

## ANIMATION DECISION TREE

### When to use which animation

```
Task: Indicate "waiting for input"
├─ NOT critical → Pulse (subtle, 2-3 sec)
├─ Medium critical → Blink (1 sec on/off)
└─ Urgent → Fast pulse (0.5 sec)

Task: Show progress (0% → 100%)
├─ Quick (< 1 sec) → Ease-out (instant-like)
├─ Medium (1-5 sec) → Linear (steady progress)
└─ Slow (> 5 sec) → Ease-in-out (natural feel)

Task: Indicate "currently changing"
├─ Number updating → Fade+slide (0.2s)
├─ Status changing → Color transition (0.3s)
└─ Phase changing → Slide+fade (0.5s)

Task: Show "something happened"
├─ Minor event → No animation (just log it)
├─ Important event → Flash (1s color change)
└─ Critical event → Bounce (attention-grabbing)

Task: Indicate "this is clickable"
├─ Button on hover → Lighten (0.1s)
├─ Expandable row → Slide down (0.3s)
└─ Modal → Fade in (0.2s)
```

---

## REAL-TIME METRIC UPDATE STRATEGY

### How to refresh metrics in FLYING phase

```
Metric Value Update Options:
├─ Animated number (count-up/down)
│  └─ Duration: 0.2-0.5 sec
│  └─ Easing: ease-out
│  └─ Use for: Any metric that changes frequently
│
├─ Fade transition (value swaps)
│  └─ Duration: 0.15 sec
│  └─ Use for: Status text, severity labels
│
├─ Color pulse (highlight change)
│  └─ Duration: 0.3 sec
│  └─ Use for: Thresholds crossed (yellow/red)
│
└─ Chart animation (append new point)
   └─ Duration: 0.5 sec (add new point, remove old)
   └─ Use for: Time-series charts
```

**Update Frequency:**
- Metrics: Every 1-2 seconds (real-time but not overwhelming)
- Charts: New data point every 5-10 seconds (smoother trend)
- Event log: Every event logged (instant, no batching)
- Status indicators: Every 0.5-1 second (catch latency changes)

---

## ACCESSIBILITY DECISION MATRIX

### Choices for different accessibility scenarios

| **Scenario** | **What to do** | **Example** |
|---|---|---|
| **Color-only info** | Add text label or icon | Status "Green" = "● Green - All systems nominal" |
| **Hidden text** | Use aria-label on icon | `<span aria-label="Critical alert">●</span>` |
| **Expandable row** | Add visible expand button | `[→]` or `[+]` button before each row |
| **Keyboard nav** | Tab order (1→2→3...) | Checklist → Ready button → Next phase |
| **Focus indicator** | Visible outline (not subtle) | `outline: 2px solid #FF6B35` |
| **Timestamp timezone** | Always UTC, explicitly marked | "2026-09-01 14:23:15 UTC" |
| **Signature verification** | Make it copyable/selectable | Wrap in `<code>` with select all |
| **Alert without sound** | Visual + text notification | Toast message + banner + log entry |
| **Mobile-specific** | Touch targets ≥ 48px tall | Button: 48x48px minimum |

---

## SMAOS LAYER → UI ELEMENT MAPPING

### Quick reference for which layer data goes where

```
Layer 1 (Policy Routing):
├─ UI Element: Metric card "Policy Requests: 42/min"
├─ Chart: Line graph over 24 hours
├─ Event: "POLICY_EVAL: Rule 42 matched"
├─ Alert: If request rate exceeds threshold
└─ Ledger: POLICY_EVAL + signature + timestamp

Layer 2 (Knowledge Base):
├─ UI Element: Metric card "Knowledge Latency: 87ms"
├─ Chart: Histogram of latency buckets
├─ Event: "QUERY: 2500 vectors searched"
├─ Alert: If latency > 100ms (yellow) or > 200ms (red)
└─ Ledger: QUERY + actor + timestamp + signature

Layer 3 (Permit Gates):
├─ UI Element: Metric card "Permit Decisions: 41 approved, 6 denied"
├─ Chart: Stacked bar (approved/denied over time)
├─ Event: "PERMIT_GRANT or PERMIT_DENY"
├─ Alert: If deny rate spikes (suspicious)
└─ Ledger: PERMIT_GRANT/DENY + signature

Layer 4 (Orchestration):
├─ UI Element: Metric "Pilots Active: 3 running"
├─ Event: "PILOT_START: Hotel scorer initialized"
├─ Alert: If pilot crashes or stalls
└─ Ledger: PILOT_START + PILOT_COMPLETE + signature

Layer 5 (Communication):
├─ UI Element: Metric "MCP Throughput: 1.2K msg/s"
├─ Chart: Real-time throughput graph
├─ Event: "MCP_MESSAGE_SENT: To hotel scorer"
├─ Alert: If latency > 200ms
└─ Ledger: MCP_MESSAGE_SENT/RECV + signature

Layer 6 (Infrastructure):
├─ UI Element: Metrics "CPU: 45%, Memory: 62%"
├─ Charts: Resource usage gauges
├─ Event: "RESOURCE_ALERT: Memory 62% (approaching limit)"
├─ Alert: If CPU > 80% or Memory > 85%
└─ Ledger: RESOURCE_ALERT + signature

Layer 7 (RAGAS):
├─ UI Element: Metric "RAGAS Accuracy: 92%"
├─ Chart: Accuracy trend over evaluation runs
├─ Event: "RAGAS_EVAL: 50 questions, 46 correct"
├─ Alert: If accuracy < 87% (target)
└─ Ledger: RAGAS_EVAL + accuracy + signature

Layer 8 (Proof):
├─ UI Element: Counter "Events Logged: 1251"
├─ Ledger: EVERY event from L1-L7
├─ Chart: Event count over time
├─ No alerts (archival only)
└─ Signature: ED25519 on every entry, PQC-resistant
```

---

## TESTING DECISION MATRIX

### Which test to write for each component

| **Component** | **Unit Test** | **E2E Test** | **Visual Test** | **A11y Test** |
|---|---|---|---|---|
| **Phase Progress** | Render states | All transitions | Phase indicator colors | Focus order, ARIA labels |
| **Metric Card** | Format value | Receive live data | Value positioning | Color contrast, alt text |
| **Event Log** | Filter events | Auto-scroll, update | Log entry styling | Timestamp clarity |
| **Ledger Table** | Sort/search | Expand signature | Monospace fonts | Keyboard nav to rows |
| **Status Indicator** | Color logic | On-screen visual | Dot size/color | Label + aria-label |
| **Countdown Timer** | Tick update | Complete flow | Large numbers | Timer announces completion |
| **Health Check Bar** | Progress calc | Update animation | Bar colors | Progress % announced |

---

## COMMON PITFALLS & SOLUTIONS

| **Pitfall** | **What happens** | **How to avoid** |
|---|---|---|
| **Too much real-time animation** | Overwhelming, hard to read | Batch updates every 1-2 sec, not continuous |
| **Metrics on wrong color background** | Contrast fails accessibility | Use contrast checker (WebAIM) |
| **No phase transition feedback** | Users confused, disoriented | Show progress bar, countdown, status message |
| **Signature data not selectable** | Can't copy-paste for verification | Wrap in `<code>` with 100% select enabled |
| **Timezone assumptions** | Audit trail confusing across regions | Always show UTC, explicitly label it |
| **No keyboard shortcut for search** | Slow ledger lookup | Support Ctrl+F (browser default) |
| **Ledger rows not expandable** | Full signature hidden, hard to verify | Add [→] button for expand/collapse |
| **Status dots only (no text)** | Color-blind users can't see state | Always add text label: "● Green - All OK" |
| **Countdown timer too fast** | Looks broken or unrealistic | Use 1-sec ticks, not milliseconds |
| **Event log timestamp ambiguous** | Is it local time or UTC? | Always explicit: "14:23:15 UTC" |

---

## NEXT STEPS CHECKLIST

- [ ] Pick a phase to start with (suggest: PRE-FLIGHT)
- [ ] Choose your component library or build from scratch
- [ ] Set up color tokens (match palette above)
- [ ] Create component library with 12+ components
- [ ] Wire state management (phase, metrics, ledger)
- [ ] Implement phase transitions
- [ ] Add real data from L1-L8 harness
- [ ] Test accessibility (WCAG AA)
- [ ] Test real-time metric updates (latency < 100ms)
- [ ] User test with non-technical users
- [ ] Final polish & performance optimization

---

**Status:** Ready for implementation  
**Last updated:** Sep 1, 2026  
**Questions?** See full spec in `/UI_UX_JOURNEY_PATTERNS.md`  
