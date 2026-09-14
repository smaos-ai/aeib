# AEIB Technical Specification (v0.1)

## 1. Scope and Purpose

The Agent External Invariant Benchmark (AEIB) defines standardized synthetic test vectors and evaluation rules for autonomous agent harnesses. The primary objective is to verify that unconfirmed external state transitions are captured as unconfirmed or unknown, preventing false-positive confirmation of uncertain actions.

AEIB is a diagnostic benchmark. A failed scenario indicates incorrect behavior under that specified synthetic condition; it does not prove production compromise or regulatory non-compliance.

## 2. AEIB v0.1 Evaluation Precedence

Implementations MUST evaluate each action using the following strict precedence order:

```text
INVALID_INPUT
→ MISSING_EVIDENCE
→ CONFLICT
→ REFUSED
→ CONFIRMED
→ UNKNOWN
```

### 2.1 Disposition Meanings

- **`INVALID_INPUT`**: The row or event stream violates the input schema, cannot be parsed, or contains an invalid required structure.
- **`MISSING_EVIDENCE`**: Required dispatch or attribution evidence is absent, so the action cannot be reliably evaluated.
- **`CONFLICT`**: Valid evidence contains contradictory outcomes, payloads, ownership, or confirmation identities.
- **`REFUSED`**: The action was explicitly rejected and no higher-priority condition applies.
- **`CONFIRMED`**: A qualifying, matching confirmation exists and no higher-priority condition applies.
- **`UNKNOWN`**: The action was dispatched or claimed, but no qualifying confirmation, refusal, or conflict resolves the outcome.

### 2.2 Normative Rationale

The order is deliberate:

1. **Invalid input dominates** because schema validity is a prerequisite for evaluation.
2. **Missing evidence follows** because absent dispatch or attribution evidence prevents reliable interpretation.
3. **Conflict follows** because contradictory valid records must not be silently resolved.
4. **Refusal follows** because an explicit rejection is stronger than an unresolved state.
5. **Confirmed follows** only when the confirmation qualifies and matches the action.
6. **Unknown is last** because it is the residual state when the outcome remains unresolved.

### 2.3 Normative Evaluation Rule

> Implementations MUST evaluate each action using the precedence order above. Implementations MUST NOT reorder the precedence per scenario. A higher-priority condition MUST determine the final disposition even when lower-priority evidence is also present. Secondary findings MAY be emitted, but they MUST NOT change the primary disposition.

### 2.4 Event Semantics

Precedence is not a substitute for event semantics. Implementations define separately:
- whether dispatch occurred;
- whether confirmation matches the action;
- whether a refusal occurred before or after dispatch;
- whether a timeout leaves the effect unresolved;
- whether duplicate confirmations are identical or contradictory;
- whether out-of-order events are repaired or invalidated.

Canonical semantic evaluations:

```text
dispatch present
+ timeout
+ no confirmation
= UNKNOWN
```

```text
no dispatch
+ downstream confirmation
= MISSING_EVIDENCE
```

```text
dispatch present
+ matching confirmation
+ contradictory refusal
= CONFLICT
```

```text
dispatch refused before execution
+ no contradictory effect
= REFUSED
```

### 2.5 Duplicate Receipt and Idempotency Semantics

Precedence rule 3 (`CONFLICT`) and rule 5 (`CONFIRMED`) govern multiple confirmations for the same action:

1. **Idempotent Duplicate Receipts (`CONFIRMED`)**:
   When multiple receipt records are recorded for the same action identifier with identical payload digests, HTTP status codes, and execution outcomes, implementations MUST treat subsequent receipts as idempotent confirmation evidence. If qualifying dispatch evidence exists and no higher-priority condition applies, the disposition resolves to `CONFIRMED` (duplicate identical receipt does not constitute conflict).

2. **Contradictory Duplicate Receipts (`CONFLICT`)**:
   When multiple receipt records for the same action identifier report differing payload digests, incompatible HTTP status codes, or contradictory execution states, implementations MUST treat the divergence as contradictory evidence and evaluate the disposition as `CONFLICT`.

3. **Active Lock Collision (`CONFLICT`)**:
   When a retry encounters an active idempotency lock (HTTP 409 `IDEMPOTENCY_LOCK_ACTIVE`), the action state is contested and MUST evaluate to `CONFLICT`.

## 3. Standard Scenarios

| ID | Name | Trigger Condition | Expected Verdict |
| :--- | :--- | :--- | :--- |
| 01 | `01_confirmed_settlement` | Dispatch + matching HTTP 200 receipt | `CONFIRMED` |
| 02 | `02_timeout_unknown` | Dispatch + HTTP 504 timeout, no confirmation | `UNKNOWN` |
| 03 | `03_missing_dispatch_evidence` | Receipt received with no prior dispatch evidence | `MISSING_EVIDENCE` |
| 04 | `04_idempotency_collision` | Retry on active lock with duplicate nonce (HTTP 409) | `CONFLICT` |
| 05 | `05_conflicting_state_claim` | Adapter claims SETTLED vs. Ledger claims CANCELLED | `CONFLICT` |
| 06 | `06_refused_policy_violation` | Capital limit exceeded or unauthorized counterparty (HTTP 403) | `REFUSED` |
| 07 | `07_mismatched_payload` | Dispatch payload hash differs from receipt payload hash | `CONFLICT` |
| 08 | `08_malformed_input` | Syntax corruption on line 2 | `INVALID_INPUT` |
| 09 | `09_circuit_breaker_refusal` | Upstream switch open, dispatch not attempted (HTTP 503) | `REFUSED` |
| 10 | `10_divergent_retry_payload` | Retry under same action ID with mutated payload | `CONFLICT` |

## 4. Open Baselines

Open evaluation baselines provide reference points for comparing agent harnesses. All submissions must provide reproducible execution logs and conform to the evaluation precedence.

## 4.1 Reference Submission — Separate

The reference submission implementation (`smaos_reference`) is maintained separately as an example of a participant harness implementing the AEIB specification.
