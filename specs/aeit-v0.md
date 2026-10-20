# Agent Execution Integrity Telemetry (AEIT) — Specification v0

```text
Status       : Telemetry & Monitoring Specification
Role         : Operational risk monitoring & descriptive execution telemetry
Usage Policy : input_only_not_decision
```

---

## 1. Purpose & Separation of Concerns

Agent Execution Integrity Telemetry (AEIT) defines a standard machine-readable schema for summarizing autonomous agent dispatch telemetry, boundary interventions, and uncertainty resolution.

### Non-Goals & Strict Boundaries
- **Not an Authorization Oracle**: AEIT metrics and indicators **never** make execution or authorization decisions. Authorization is governed strictly by Station 1 policy, exact CAID binding, and halt states.
- **Not an Insurance Underwriting Rating**: AEIT does not output insurance ratings, actuarial prices, or credit scores (e.g., "AAA"). It provides descriptive telemetry intended as input for external operator analysis.

---

## 2. Telemetry Schema & Metric Semantics

```yaml
aeit_v0:
  output: descriptive_metrics_and_indicator
  not_output:
    - insurance approval
    - credit rating
    - authorization decision
    - actuarial price
  metrics:
    - dispatch_count: "Total tool/mutation dispatch requests processed."
    - ambiguous_outcome_count: "Dispatches encountering transport uncertainty (e.g., HTTP 504)."
    - reconciled_count: "Ambiguous outcomes definitively resolved via authoritative probing."
    - unresolved_count: "Ambiguous outcomes currently awaiting reconciliation."
    - policy_violation_count: "Attempts to breach tenant budgets, epochs, or standing."
    - halt_count: "Hard safety halt events triggered."
    - boundary_integrity_events:
        - attenuation_breaches_blocked: "Dynamic escalation attempts stopped at boundary."
        - taint_violations_blocked: "Context taint downgrades blocked."
        - malformed_payloads_blocked: "Invalid schema or wire encoding attempts blocked."

  interpretation_rules:
    ambiguous_outcomes: "Neutral or positive if reconciled; reflects safe latching under network failure."
    unresolved_ambiguity: "Operational risk signal; indicates outstanding transport uncertainty."
    policy_violations: "Security risk signal; indicates adversarial or out-of-bounds agent trajectory."
    halt_events: "Context-dependent signal; reflects active containment of severe invariants."
```

---

## 3. Reference Indicator Formulation

The Execution Integrity Indicator (EII) produces a normalized metric $[0.0, 100.0]$:

$$\text{EII} = \max\left(0.0, \min\left(100.0, 100.0 - 10 \cdot U - 20 \cdot P - 25 \cdot H - \min(15.0, 50 \cdot B / D)\right)\right)$$

Where:
- $U$: Unresolved ambiguous outcomes ($\text{ambiguous} - \text{reconciled}$).
- $P$: Unmitigated policy violations.
- $H$: Hard safety halts.
- $B$: Blocked boundary integrity infractions.
- $D$: Total dispatches.

Properly reconciled outcomes ($U = 0$) do not penalize the indicator, confirming that safe uncertainty handling is evaluated as positive boundary behavior.
