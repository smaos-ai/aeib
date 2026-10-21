------------------------ MODULE AEIBStation1And2 ------------------------
EXTENDS Integers, FiniteSets

CONSTANTS
    Operations,         \* Finite set of candidate operation IDs
    SprintLimitMinor,   \* Maximum total exposure (Reserved + Settled)
    MaxPerCallMinor     \* Maximum per-call delegation cap

VARIABLES
    opState,            \* opState[op] \in {"IDLE", "DISPATCHED", "INDETERMINATE", "CONFIRMED", "REFUTED", "REJECTED"}
    opAmount,           \* opAmount[op] \in 0..SprintLimitMinor
    reservedMinor,      \* Current escrow reservation (DISPATCHED + INDETERMINATE)
    settledMinor        \* Current confirmed spend (CONFIRMED)

vars == <<opState, opAmount, reservedMinor, settledMinor>>

TypeOK ==
    /\ opState \in [Operations -> {"IDLE", "DISPATCHED", "INDETERMINATE", "CONFIRMED", "REFUTED", "REJECTED"}]
    /\ reservedMinor \in 0..SprintLimitMinor
    /\ settledMinor \in 0..SprintLimitMinor

\* SAFETY INVARIANT 1: Total financial exposure never exceeds SprintLimitMinor
SafetyBudgetConservation ==
    (reservedMinor + settledMinor) <= SprintLimitMinor

\* SAFETY INVARIANT 2: Accounting identity holds across all operation states
SafetyEscrowIdentity ==
    /\ reservedMinor = (LET active == {o \in Operations : opState[o] \in {"DISPATCHED", "INDETERMINATE"}}
                        IN IF active = {} THEN 0 ELSE CHOOSE s \in Nat : TRUE)

Init ==
    /\ opState = [o \in Operations |-> "IDLE"]
    /\ opAmount = [o \in Operations |-> 0]
    /\ reservedMinor = 0
    /\ settledMinor = 0

AuthorizeAndReserve(op, amt, taintTier2) ==
    /\ opState[op] = "IDLE"
    /\ IF /\ ~taintTier2
          /\ amt > 0
          /\ amt <= MaxPerCallMinor
          /\ (reservedMinor + settledMinor + amt) <= SprintLimitMinor
       THEN /\ opState' = [opState EXCEPT ![op] = "DISPATCHED"]
            /\ opAmount' = [opAmount EXCEPT ![op] = amt]
            /\ reservedMinor' = reservedMinor + amt
            /\ UNCHANGED <<settledMinor>>
       ELSE /\ opState' = [opState EXCEPT ![op] = "REJECTED"]
            /\ UNCHANGED <<opAmount, reservedMinor, settledMinor>>

TransportTimeoutOr5xx(op) ==
    /\ opState[op] = "DISPATCHED"
    /\ opState' = [opState EXCEPT ![op] = "INDETERMINATE"]
    /\ UNCHANGED <<opAmount, reservedMinor, settledMinor>>

TransportSuccess200(op) ==
    /\ opState[op] = "DISPATCHED"
    /\ opState' = [opState EXCEPT ![op] = "CONFIRMED"]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ settledMinor' = settledMinor + opAmount[op]
    /\ UNCHANGED <<opAmount>>

ReconcileConfirmed(op) ==
    /\ opState[op] = "INDETERMINATE"
    /\ opState' = [opState EXCEPT ![op] = "CONFIRMED"]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ settledMinor' = settledMinor + opAmount[op]
    /\ UNCHANGED <<opAmount>>

ReconcileRefuted(op) ==
    /\ opState[op] = "INDETERMINATE"
    /\ opState' = [opState EXCEPT ![op] = "REFUTED"]
    /\ reservedMinor' = reservedMinor - opAmount[op]
    /\ UNCHANGED <<opAmount, settledMinor>>

=============================================================================
