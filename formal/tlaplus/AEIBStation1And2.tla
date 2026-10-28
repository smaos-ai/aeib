------------------------ MODULE AEIBStation1And2 ------------------------
\* Station 1 (budget authorisation + escrow) and Station 2 (EO1 settle-before-retry with
\* read-back reconciliation). Protocol modelled: A5 = effect-key CAID + read-back reconciler +
\* attempt fencing (FencingEnabled = TRUE). With FencingEnabled = FALSE the module is A4,
\* which trusts a NOT_APPLIED read-back; the Python checker finds a 7-step duplicate-effect
\* counterexample for A4 once late commits (LIMBO timeout_late) are possible.
\*
\* Status: checked with TLC (tla2tools.jar v1.8.0, SHA-256 pinned in scripts/fetch_tla2tools.sh),
\* run by scripts/run_tlc_formal_gate.sh against the two configs in this directory:
\*   AEIBStation1And2_A5.cfg (FencingEnabled = TRUE): no error, 34047 distinct states, depth 21;
\*   AEIBStation1And2_A4.cfg (FencingEnabled = FALSE): SafetyNoDuplicateEffect is violated, with the
\*   same 7-action trace the Python checker reports.
\* The same actions are also explored by src/eo1_protocol_model_checker.py (stdlib BFS); the two
\* checkers agree on the A5 state count. Bounds: Operations = {"op1", "op2"}, MaxPerCallMinor = 2,
\* SprintLimitMinor = 3, MaxAttempts = 2. Results hold for the stated model and bounds only.
\*
\* Late commits ARE modelled (Transport(op, "timeout_late") + LateCommit). Not modelled: lying
\* read-backs or fences, transport redelivery.
EXTENDS Integers, FiniteSets

CONSTANTS
    Operations,         \* Finite set of candidate operation IDs
    SprintLimitMinor,   \* Maximum total exposure (Reserved + Settled)
    MaxPerCallMinor,    \* Maximum per-call delegation cap
    FencingEnabled      \* TRUE = A5 (target fence before re-dispatch), FALSE = A4 (trusts NOT_APPLIED)

\* Derived bounds (definitions).
Amounts == 1..MaxPerCallMinor
MaxAttempts == 2
WireFaults == {"200", "timeout_pre", "timeout_post", "http500_post", "timeout_late"}
ApplyingFaults == {"200", "timeout_post", "http500_post"}

VARIABLES
    opState,            \* opState[op] \in {"IDLE", "DISPATCHED", "INDETERMINATE", "CONFIRMED", "REFUTED", "REJECTED"}
    opAmount,           \* opAmount[op] \in 0..SprintLimitMinor
    reservedMinor,      \* Current escrow reservation (DISPATCHED + INDETERMINATE)
    settledMinor,       \* Current confirmed spend (CONFIRMED)
    targetEffects,      \* Effects applied at the target for op's logical effect key
    latchState,         \* "NONE" | "LATCHED" | "RELEASED"
    readbackResult,     \* "NONE" | "APPLIED" | "NOT_APPLIED" | "UNKNOWN" (UNKNOWN = read-back timeout, F7)
    readbackEffects,    \* ghost: targetEffects observed when the read-back answered
    releaseEvidence,    \* ghost: "NONE" | "APPLIED" | "NOT_APPLIED" | "UNKNOWN" | "NO_READBACK"
    attempts,           \* dispatch attempts so far
    regenerated,        \* a regenerated retry (changed memo / UUID) was issued
    inflight,           \* attempt number of a write still in flight at the target (0 = none)
    fenceBelow          \* target refuses in-flight writes whose attempt < fenceBelow

vars == <<opState, opAmount, reservedMinor, settledMinor, targetEffects, latchState,
          readbackResult, readbackEffects, releaseEvidence, attempts, regenerated, inflight, fenceBelow>>

TypeOK ==
    /\ opState \in [Operations -> {"IDLE", "DISPATCHED", "INDETERMINATE", "CONFIRMED", "REFUTED", "REJECTED"}]
    /\ opAmount \in [Operations -> 0..SprintLimitMinor]
    /\ reservedMinor \in 0..SprintLimitMinor
    /\ settledMinor \in 0..SprintLimitMinor
    /\ targetEffects \in [Operations -> Nat]
    /\ latchState \in [Operations -> {"NONE", "LATCHED", "RELEASED"}]
    /\ readbackResult \in [Operations -> {"NONE", "APPLIED", "NOT_APPLIED", "UNKNOWN"}]
    /\ readbackEffects \in [Operations -> Nat]
    /\ releaseEvidence \in [Operations -> {"NONE", "APPLIED", "NOT_APPLIED", "UNKNOWN", "NO_READBACK"}]
    /\ attempts \in [Operations -> 0..MaxAttempts]
    /\ regenerated \in [Operations -> BOOLEAN]
    /\ inflight \in [Operations -> 0..MaxAttempts]
    /\ fenceBelow \in [Operations -> 0..(MaxAttempts + 1)]

\* Fold sum of opAmount over a finite set of operations (replaces the earlier vacuous
\* CHOOSE over Nat, which named one arbitrary fixed natural number instead of the sum).
RECURSIVE SumAmounts(_)
SumAmounts(S) == IF S = {} THEN 0
                 ELSE LET x == CHOOSE v \in S : TRUE IN opAmount[x] + SumAmounts(S \ {x})

\* SAFETY INVARIANT 1: Total financial exposure never exceeds SprintLimitMinor
SafetyBudgetConservation ==
    (reservedMinor + settledMinor) <= SprintLimitMinor

\* SAFETY INVARIANT 2: Exact accounting identity for reserved and settled amounts
SafetyEscrowIdentity ==
    /\ reservedMinor = SumAmounts({o \in Operations : opState[o] \in {"DISPATCHED", "INDETERMINATE"}})
    /\ settledMinor = SumAmounts({o \in Operations : opState[o] = "CONFIRMED"})

\* SAFETY INVARIANT 3: At most one effect per logical effect key
SafetyNoDuplicateEffect ==
    \A op \in Operations : targetEffects[op] <= 1

\* SAFETY INVARIANT 4: a latch is released only on an explicit read-back answer, and an
\* operation becomes REFUTED (re-dispatchable) only when read-back observed NOT_APPLIED.
SafetyNeverReleaseLatchWithoutReadback ==
    \A op \in Operations :
        /\ releaseEvidence[op] \in {"NONE", "APPLIED", "NOT_APPLIED"}
        /\ opState[op] = "REFUTED" => releaseEvidence[op] = "NOT_APPLIED"

\* SAFETY INVARIANT 5: a read-back timeout (UNKNOWN) keeps the operation latched in
\* INDETERMINATE and no new attempt adds an effect afterwards (readbackEffects counts the
\* effects committed plus a write still in flight when the read-back timed out).
SafetyF7StaysIndeterminate ==
    \A op \in Operations :
        readbackResult[op] = "UNKNOWN" =>
            /\ opState[op] = "INDETERMINATE"
            /\ latchState[op] = "LATCHED"
            /\ targetEffects[op] <= readbackEffects[op]

Init ==
    /\ opState = [o \in Operations |-> "IDLE"]
    /\ opAmount = [o \in Operations |-> 0]
    /\ reservedMinor = 0
    /\ settledMinor = 0
    /\ targetEffects = [o \in Operations |-> 0]
    /\ latchState = [o \in Operations |-> "NONE"]
    /\ readbackResult = [o \in Operations |-> "NONE"]
    /\ readbackEffects = [o \in Operations |-> 0]
    /\ releaseEvidence = [o \in Operations |-> "NONE"]
    /\ attempts = [o \in Operations |-> 0]
    /\ regenerated = [o \in Operations |-> FALSE]
    /\ inflight = [o \in Operations |-> 0]
    /\ fenceBelow = [o \in Operations |-> 0]

\* Per-op variables touched by no action below unless listed (keeps UNCHANGED lists short).
Rest == <<inflight, fenceBelow>>

AuthorizeAndReserve(op, amt, taintTier2) ==
    /\ opState[op] = "IDLE"
    /\ IF /\ ~taintTier2
          /\ amt > 0
          /\ amt <= MaxPerCallMinor
          /\ (reservedMinor + settledMinor + amt) <= SprintLimitMinor
       THEN /\ opState' = [opState EXCEPT ![op] = "DISPATCHED"]
            /\ opAmount' = [opAmount EXCEPT ![op] = amt]
            /\ attempts' = [attempts EXCEPT ![op] = 1]
            /\ reservedMinor' = reservedMinor + amt
            /\ UNCHANGED <<settledMinor, targetEffects, latchState, readbackResult,
                           readbackEffects, releaseEvidence, regenerated>>
       ELSE /\ opState' = [opState EXCEPT ![op] = "REJECTED"]
            /\ UNCHANGED <<opAmount, reservedMinor, settledMinor, targetEffects, latchState,
                           readbackResult, readbackEffects, releaseEvidence, attempts, regenerated>>
    /\ UNCHANGED Rest

\* Wire outcome of a dispatched attempt: 200 confirms; timeout_pre applies nothing;
\* timeout_post / http500_post apply the effect but lose the acknowledgement; timeout_late
\* leaves the write in flight at the target (it may still commit later: LateCommit).
Transport(op, fault) ==
    /\ opState[op] = "DISPATCHED"
    /\ targetEffects' = [targetEffects EXCEPT ![op] = IF fault \in ApplyingFaults THEN @ + 1 ELSE @]
    /\ IF fault = "200"
       THEN /\ opState' = [opState EXCEPT ![op] = "CONFIRMED"]
            /\ reservedMinor' = reservedMinor - opAmount[op]
            /\ settledMinor' = settledMinor + opAmount[op]
            /\ UNCHANGED latchState
       ELSE /\ opState' = [opState EXCEPT ![op] = "INDETERMINATE"]
            /\ latchState' = [latchState EXCEPT ![op] = "LATCHED"]
            /\ UNCHANGED <<reservedMinor, settledMinor>>
    /\ inflight' = [inflight EXCEPT ![op] = IF fault = "timeout_late" THEN attempts[op] ELSE @]
    /\ UNCHANGED <<opAmount, readbackResult, readbackEffects, releaseEvidence, attempts, regenerated, fenceBelow>>

\* Backward-compatible names for the earlier transport actions.
TransportTimeoutOr5xx(op) == \E f \in WireFaults \ {"200"} : Transport(op, f)
TransportSuccess200(op) == Transport(op, "200")

\* An in-flight write commits late unless the target has fenced its attempt.
LateCommit(op) ==
    /\ inflight[op] > 0
    /\ inflight[op] >= fenceBelow[op]
    /\ targetEffects' = [targetEffects EXCEPT ![op] = @ + 1]
    /\ inflight' = [inflight EXCEPT ![op] = 0]
    /\ UNCHANGED <<opState, opAmount, reservedMinor, settledMinor, latchState, readbackResult,
                   readbackEffects, releaseEvidence, attempts, regenerated, fenceBelow>>

\* An in-flight write ends without effect (expired, or refused by the fence).
InflightEnds(op) ==
    /\ inflight[op] > 0
    /\ inflight' = [inflight EXCEPT ![op] = 0]
    /\ UNCHANGED <<opState, opAmount, reservedMinor, settledMinor, targetEffects, latchState,
                   readbackResult, readbackEffects, releaseEvidence, attempts, regenerated, fenceBelow>>

\* Truthful read-back of committed effects; a write still in flight reads as absent.
\* UNKNOWN models a read-back timeout and is sticky.
Readback(op, r) ==
    /\ opState[op] = "INDETERMINATE"
    /\ latchState[op] = "LATCHED"
    /\ readbackResult[op] = "NONE"
    /\ r \in (IF targetEffects[op] >= 1 THEN {"APPLIED", "UNKNOWN"} ELSE {"NOT_APPLIED", "UNKNOWN"})
    /\ readbackResult' = [readbackResult EXCEPT ![op] = r]
    /\ readbackEffects' = [readbackEffects EXCEPT ![op] = targetEffects[op] + (IF inflight[op] > 0 THEN 1 ELSE 0)]
    /\ UNCHANGED <<opState, opAmount, reservedMinor, settledMinor, targetEffects, latchState,
                   releaseEvidence, attempts, regenerated>>
    /\ UNCHANGED Rest

ReconcileConfirmed(op) ==
    /\ opState[op] = "INDETERMINATE"
    /\ readbackResult[op] = "APPLIED"
    /\ opState' = [opState EXCEPT ![op] = "CONFIRMED"]
    /\ latchState' = [latchState EXCEPT ![op] = "RELEASED"]
    /\ releaseEvidence' = [releaseEvidence EXCEPT ![op] = "APPLIED"]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ settledMinor' = settledMinor + opAmount[op]
    /\ UNCHANGED <<opAmount, targetEffects, readbackResult, readbackEffects, attempts, regenerated>>
    /\ UNCHANGED Rest

\* A4 only (FencingEnabled = FALSE): trusts NOT_APPLIED. Unsafe under late commits.
ReconcileRefuted(op) ==
    /\ ~FencingEnabled
    /\ opState[op] = "INDETERMINATE"
    /\ readbackResult[op] = "NOT_APPLIED"
    /\ opState' = [opState EXCEPT ![op] = "REFUTED"]
    /\ latchState' = [latchState EXCEPT ![op] = "RELEASED"]
    /\ releaseEvidence' = [releaseEvidence EXCEPT ![op] = "NOT_APPLIED"]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ UNCHANGED <<opAmount, settledMinor, targetEffects, readbackResult, readbackEffects,
                   attempts, regenerated>>
    /\ UNCHANGED Rest

\* A5: atomic target-side check-and-fence of every attempt <= attempts[op]. If the effect is
\* already present the fence reports it and the op settles CONFIRMED; otherwise REFUTED.
\* A fence that is unsupported or times out enables no action: the op stays INDETERMINATE.
FenceAndRefute(op) ==
    /\ FencingEnabled
    /\ opState[op] = "INDETERMINATE"
    /\ readbackResult[op] = "NOT_APPLIED"
    /\ targetEffects[op] = 0
    /\ opState' = [opState EXCEPT ![op] = "REFUTED"]
    /\ latchState' = [latchState EXCEPT ![op] = "RELEASED"]
    /\ releaseEvidence' = [releaseEvidence EXCEPT ![op] = "NOT_APPLIED"]
    /\ fenceBelow' = [fenceBelow EXCEPT ![op] = attempts[op] + 1]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ UNCHANGED <<opAmount, settledMinor, targetEffects, readbackResult, readbackEffects,
                   attempts, regenerated, inflight>>

FenceObservesApplied(op) ==
    /\ FencingEnabled
    /\ opState[op] = "INDETERMINATE"
    /\ readbackResult[op] = "NOT_APPLIED"
    /\ targetEffects[op] >= 1
    /\ opState' = [opState EXCEPT ![op] = "CONFIRMED"]
    /\ latchState' = [latchState EXCEPT ![op] = "RELEASED"]
    /\ releaseEvidence' = [releaseEvidence EXCEPT ![op] = "APPLIED"]
    /\ fenceBelow' = [fenceBelow EXCEPT ![op] = attempts[op] + 1]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ settledMinor' = settledMinor + opAmount[op]
    /\ UNCHANGED <<opAmount, targetEffects, readbackResult, readbackEffects, attempts, regenerated, inflight>>

\* Exactly one fresh attempt after a NOT_APPLIED settlement, re-reserving the amount.
Redispatch(op) ==
    /\ opState[op] = "REFUTED"
    /\ attempts[op] < MaxAttempts
    /\ (reservedMinor + settledMinor + opAmount[op]) <= SprintLimitMinor
    /\ opState' = [opState EXCEPT ![op] = "DISPATCHED"]
    /\ attempts' = [attempts EXCEPT ![op] = @ + 1]
    /\ latchState' = [latchState EXCEPT ![op] = "NONE"]
    /\ readbackResult' = [readbackResult EXCEPT ![op] = "NONE"]
    /\ readbackEffects' = [readbackEffects EXCEPT ![op] = 0]
    /\ reservedMinor' = reservedMinor + opAmount[op]
    /\ UNCHANGED <<opAmount, settledMinor, targetEffects, releaseEvidence, regenerated>>
    /\ UNCHANGED Rest

\* Regenerated retry with changed incidental fields. With an effect-key CAID it maps onto the
\* same latched / committed record and is refused (no effect).
RegeneratedRetry(op) ==
    /\ opState[op] \in {"CONFIRMED", "INDETERMINATE"}
    /\ ~regenerated[op]
    /\ regenerated' = [regenerated EXCEPT ![op] = TRUE]
    /\ UNCHANGED <<opState, opAmount, reservedMinor, settledMinor, targetEffects, latchState,
                   readbackResult, readbackEffects, releaseEvidence, attempts>>
    /\ UNCHANGED Rest

Next ==
    \E op \in Operations :
        \/ \E amt \in Amounts, t \in BOOLEAN : AuthorizeAndReserve(op, amt, t)
        \/ \E f \in WireFaults : Transport(op, f)
        \/ LateCommit(op)
        \/ InflightEnds(op)
        \/ \E r \in {"APPLIED", "NOT_APPLIED", "UNKNOWN"} : Readback(op, r)
        \/ ReconcileConfirmed(op)
        \/ ReconcileRefuted(op)
        \/ FenceAndRefute(op)
        \/ FenceObservesApplied(op)
        \/ Redispatch(op)
        \/ RegeneratedRetry(op)

Spec == Init /\ [][Next]_vars

THEOREM Spec => [](TypeOK /\ SafetyBudgetConservation /\ SafetyEscrowIdentity /\ SafetyNoDuplicateEffect
                   /\ SafetyNeverReleaseLatchWithoutReadback /\ SafetyF7StaysIndeterminate)

=============================================================================
